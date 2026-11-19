#!/usr/bin/env python3
# coding=utf-8
"""元素封装：属性式元素访问 + 动作日志 + allure 步骤。

写法：
    class LoginPageEle(BasePage):
        \"\"\"登录页面\"\"\"

        account = element("[name='username']", "账号输入框")
        password = element("[name='password']", "密码输入框", sensitive=True)

用例直接调元素动作，日志和 allure 步骤自动记录：
    page.login_page.account.fill("admin")    # [登录页面] 账号输入框(account) 输入 "admin"
    page.login_page.password.fill("123456")  # [登录页面] 密码输入框(password) 输入 ***
    page.login_page.login_btn.click()        # [登录页面] 登录按钮(login_btn) 点击

设计要点：
- 描述符走标准 MRO 协议，子类继承后 __get__ 照常触发，多继承导出不受影响
- locator 延迟到动作执行时才创建，switch_to_latest_tab 改了 page 后仍然定位正确
- 动作白名单内的 28 个方法记日志；未列出的方法由 __getattr__ 直通原生 Locator
- 链式定位（first/last/nth/filter/get_by_*/locator 等）返回包装后的 Element，日志能力不丢
- 原生 Locator 用 .native 取（.locator 保留 Playwright 原义：子元素定位）
"""
from typing import TYPE_CHECKING, Any, cast, overload

import allure

from just_go._internal.logger import logger

__all__ = [
    "Element",
    "AsyncElement",
    "FrameElement",
    "AsyncFrameElement",
    "element",
    "async_element",
]

# 类型检查期让 Element 以原生 Locator 为基类：Locator 的 70+ 个成员（inner_text /
# count / get_attribute / is_visible ...）由此天然进入 IDE 补全与类型检查，签名和
# 返回类型都是 Playwright 的原文，不用手抄一份会随版本漂移的声明。
# 运行时不继承（保持 object）：Element 只是在 __getattr__ 里转发，真正的定位对象
# 由 .native 提供；继承真类反而会触发 Locator.__init__ 一类的问题。
if TYPE_CHECKING:  # pragma: no cover
    from playwright.async_api import FrameLocator as _AsyncFrameLocatorBase
    from playwright.async_api import Locator as _AsyncLocatorBase
    from playwright.sync_api import FrameLocator as _SyncFrameLocatorBase
    from playwright.sync_api import Locator as _SyncLocatorBase
else:
    _SyncLocatorBase = _AsyncLocatorBase = object
    _SyncFrameLocatorBase = _AsyncFrameLocatorBase = object

# 单个值在日志里的最大长度，避免大字典/长文本把日志刷屏
_MAX_VALUE_LEN = 60

# 动作方法：方法名 -> (日志文案, 是否带值参数)
_ACTION_LABELS = {
    # 点击
    "click": ("点击", False),
    "dblclick": ("双击", False),
    "tap": ("轻触", False),
    # 输入
    "fill": ("输入", True),
    "clear": ("清空", False),
    "type": ("输入", True),
    "press": ("按键", True),
    "press_sequentially": ("逐字输入", True),
    "select_text": ("选择文本", False),
    # 勾选
    "check": ("勾选", False),
    "uncheck": ("取消勾选", False),
    "set_checked": ("设置勾选状态", True),
    # 选择
    "select_option": ("选择选项", True),
    # 悬停 / 焦点
    "hover": ("悬停", False),
    "focus": ("聚焦", False),
    "blur": ("失焦", False),
    # 文件 / 拖拽
    "set_input_files": ("上传文件", True),
    "drop": ("放下", False),
    "drag_to": ("拖拽到", False),
    # 滚动 / 等待
    "scroll_into_view_if_needed": ("滚动进视口", False),
    "wait_for": ("等待", False),
    # 事件 / 脚本
    "dispatch_event": ("触发事件", True),
    "evaluate": ("执行脚本", True),
    "evaluate_all": ("执行脚本", True),
    "evaluate_handle": ("执行脚本", True),
    # 截图 / 高亮
    "screenshot": ("截图", False),
    "highlight": ("高亮", False),
    "hide_highlight": ("取消高亮", False),
}

# 链式定位：调用后返回新的 Locator，需要继续包装
# 注意 visible 是属性不是方法（见 Element.visible），不在这里
_CHILD_METHODS = (
    "filter",
    "nth",
    "locator",
    "get_by_alt_text",
    "get_by_label",
    "get_by_placeholder",
    "get_by_role",
    "get_by_test_id",
    "get_by_text",
    "get_by_title",
    "normalize",
    "describe",
    "and_",
    "or_",
    "within",
)

# FrameLocator 的子定位：locator / get_by_* 返回 Locator，要包装成 Element
_FRAME_LOCATOR_METHODS = (
    "locator",
    "get_by_alt_text",
    "get_by_label",
    "get_by_placeholder",
    "get_by_role",
    "get_by_test_id",
    "get_by_text",
    "get_by_title",
)

# FrameLocator 上面这些方法返回的还是 FrameLocator（嵌套 iframe），继续包成 FrameElement
_FRAME_FRAME_METHODS = (
    "nth",
    "frame_locator",
)

# 异步 Locator 上这些链式方法本身是协程，AsyncElement 版本必须 await 后再包装。
# describe / visible / content_frame 不是协程，filter / nth / locator / get_by_* 也不是。
_ASYNC_AWAIT_CHILD = ("normalize",)

# 名字命中这些词的元素，值在日志里自动脱敏
_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "pwd",
    "token",
    "secret",
    "captcha",
    "密码",
    "口令",
    "验证码",
)


def _page_name(owner):
    """页面名：取所属类 docstring 首行，没有就用类名"""
    cls = type(owner)
    doc = (cls.__doc__ or "").strip()
    return doc.splitlines()[0].strip() if doc else cls.__name__


def _frame_action_hint(name, desc):
    """iframe 上调用了 FrameLocator 没有的成员时的报错文案

    Playwright 的 FrameLocator 只有子定位能力，没有 click / inner_text / visible 这些。
    原样转发会报 "FrameLocator object has no attribute 'click'"，容易被误读成
    「Playwright 版本不支持」，这里直接说清该怎么写。
    文案不区分属性/方法（click 与 visible 都走这里），统一说「没有这个成员」。
    """
    return (
        f"iframe「{desc}」没有 {name}：FrameLocator 只能继续定位子元素。\n"
        f"  正确写法：frame.locator(\"选择器\").{name}  或  "
        f"frame.get_by_role(\"...\").{name}"
    )


def _unwrap_args(args, kwargs):
    """把 Element / AsyncElement 参数还原成原生 Locator（drag_to / filter / drop 等要用）

    AsyncElement 也必须一起还原：异步元素互传（a.drag_to(b)、a.filter(has=b)）时，
    旧实现只认 Element，会把 AsyncElement 原样交给 Playwright 报类型错误。
    """
    types = (Element, AsyncElement)
    new_args = tuple(a.native if isinstance(a, types) else a for a in args)
    new_kwargs = {
        k: (v.native if isinstance(v, types) else v) for k, v in kwargs.items()
    }
    return new_args, new_kwargs


def _basename(value):
    """取文件名：Windows 与 POSIX 路径都按最后一个分隔符切。

    不能用 os.path.basename —— POSIX 上它不把反斜杠当分隔符，
    Windows 盘符路径（D:\\data\\logo.png）会整串留在日志里。
    """
    return str(value).replace("\\", "/").rsplit("/", 1)[-1]


#: 只有“看起来像文件路径”的值才截成文件名：带盘符（D:\...）、以分隔符开头
#: （/tmp/x、\\server\x）、或最后一段带常见文件扩展名。
#: 否则 fill("2026/11/13") 会被记成 "13"、evaluate("a/b") 只剩 "b"，
#: 日志与实际传入值不符，排查时会被误导。
_PATH_SUFFIXES = (
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg",
    ".txt", ".csv", ".json", ".xml", ".xls", ".xlsx",
    ".pdf", ".doc", ".docx", ".zip", ".mp4", ".webm",
)


def _looks_like_path(value: str) -> bool:
    """判断字符串是否文件路径（决定日志里是否只保留文件名）"""
    if not value or ("\\" not in value and "/" not in value):
        return False
    drive = len(value) >= 2 and value[1] == ":"      # D:\data\logo.png
    rooted = value[0] in ("/", "\\")                 # /tmp/x、\\share\x
    tail = value.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return drive or rooted or tail.endswith(_PATH_SUFFIXES)


def _fmt_raw(raw):
    """值格式化：文件路径只留文件名，超长截断"""
    if isinstance(raw, (Element, AsyncElement)):
        return repr(raw)
    if isinstance(raw, (list, tuple)):
        items = [
            _basename(x) if isinstance(x, str) and _looks_like_path(x) else str(x)
            for x in raw
        ]
        text = "[" + ", ".join(items) + "]"
    elif isinstance(raw, str) and _looks_like_path(raw):
        # 文件路径只显示文件名，避免日志里泄露目录结构
        text = _basename(raw)
    else:
        text = str(raw)
    if len(text) > _MAX_VALUE_LEN:
        text = text[: _MAX_VALUE_LEN - 3] + "..."
    return text if text.startswith("[") else f'"{text}"'


class Element(_SyncLocatorBase):
    """同步元素包装：动作记日志 + allure 步骤，其余方法直通原生 Locator。

    - 原生 Locator 用 .native 取，可直接传给 playwright 的 expect()
    - 传给框架的 assert_xxx(locator, ...) 时可以直接传 Element
    """

    def __init__(
        self,
        owner,
        selector=None,
        desc=None,
        attr=None,
        sensitive=None,
        locator=None,
    ):
        self._owner = owner
        self._selector = selector
        self._desc = desc or attr or selector or ""
        self._attr = attr
        self._sensitive = sensitive
        self._raw_locator = locator

    # ------------------------------------------------------------------
    # 定位
    # ------------------------------------------------------------------
    @property
    def native(self):
        """原生 Locator（给 expect() 或需要原始对象的场景）"""
        if self._raw_locator is not None:
            return self._raw_locator
        return self._owner.page.locator(self._selector)

    @property
    def selector(self):
        """元素定位表达式"""
        return self._selector

    @property
    def desc(self):
        """元素描述"""
        return self._desc

    @property
    def _is_sensitive(self):
        """是否脱敏：显式标 sensitive 或名字命中敏感词"""
        if self._sensitive:
            return True
        key = f"{self._attr or ''}{self._desc or ''}".lower()
        return any(k in key for k in _SENSITIVE_KEYS)

    def _derive(self, locator):
        """基于新 Locator 派生 Element，保持包装和日志能力"""
        return Element(
            self._owner,
            selector=self._selector,
            desc=self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            locator=locator,
        )

    def __repr__(self):
        return f"<Element {self._desc}({self._selector or 'derived'})>"

    # ------------------------------------------------------------------
    # 日志
    # ------------------------------------------------------------------
    def _detail(self, label, args, kwargs, has_value):
        if not has_value:
            return label
        raw = args[0] if args else next(iter(kwargs.values()), None)
        if raw is None:
            return label
        text = "***" if self._is_sensitive else _fmt_raw(raw)
        return f"{label} {text}"

    def _run(self, name, label, has_value, args, kwargs):
        args, kwargs = _unwrap_args(args, kwargs)
        detail = self._detail(label, args, kwargs, has_value)
        logger.info(f"[{_page_name(self._owner)}] {self._desc} {detail}")
        with allure.step(f"{self._desc} {detail}"):
            method = getattr(self.native, name, None)
            if method is None:
                raise AttributeError(f"当前 Playwright 版本不支持 Locator.{name}()")
            return method(*args, **kwargs)

    # ------------------------------------------------------------------
    # 链式定位
    # ------------------------------------------------------------------
    @property
    def first(self):
        """匹配结果中的第一个"""
        return self._derive(self.native.first)

    @property
    def last(self):
        """匹配结果中的最后一个"""
        return self._derive(self.native.last)

    @property
    def visible(self) -> "Element":  # pyright: ignore[reportIncompatibleMethodOverride]
        """只要可见的那些（原生 Locator.visible 是属性，不是方法）

        区别于 is_visible()：那个返回布尔，这个继续返回元素，可接着点击。
        """
        return self._derive(self.native.visible)

    @property
    def content_frame(self) -> "FrameElement":  # pyright: ignore[reportIncompatibleMethodOverride]
        """iframe 元素的文档内容（原生返回 FrameLocator，这里包成 FrameElement）"""
        return FrameElement(
            self._owner,
            selector=self._selector,
            desc=self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            frame=self.native.content_frame,
        )

    @property
    def all(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        """匹配结果的全部元素（list[Element]）"""
        return [self.nth(i) for i in range(self.native.count())]

    def frame_locator(self, selector: str) -> "FrameElement":  # type: ignore[override]  # pyright: ignore[reportIncompatibleMethodOverride]
        """进入子 iframe，返回 FrameElement（原生返回 FrameLocator）

        iframe 上不能用 Locator.click 那套动作，只保留 locator / get_by_* 这类子定位，
        返回的仍是包装对象，日志与 allure 步骤不丢。
        """
        return FrameElement(
            self._owner,
            selector=self._selector,
            desc=self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            frame=self.native.frame_locator(selector),
        )

    def __getattr__(self, name):
        """白名单外的成员直通原生 Locator"""
        if name.startswith("_"):
            raise AttributeError(name)
        # 用 object.__getattribute__ 直取 native：常规的 self.native 在 native 求值
        # 失败（如 owner 没有 page）时会抛 AttributeError，从而再次触发 __getattr__，
        # 把真实错误吞成 RecursionError
        native = object.__getattribute__(self, "native")
        return getattr(native, name)

    if TYPE_CHECKING:  # pragma: no cover
        # 动作方法（click / fill / ...）的签名直接来自原生 Locator 基类，不必再声明。
        # 下面这些链式方法体由文件末尾的 setattr 按 _CHILD_METHODS 注入，运行时类体里
        # 并不存在；声明它们是为了把返回类型收窄成 Element（基类声明返回 Locator）。
        # 形参用 *args/**kwargs 是为了不跟基类签名逐一较劲：参数校验交给 Playwright。
        # 新增白名单条目时同步补一行，否则补全会缺。
        def filter(self, *args: Any, **kwargs: Any) -> "Element": ...
        def nth(self, *args: Any, **kwargs: Any) -> "Element": ...
        def locator(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_alt_text(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_label(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_placeholder(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_role(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_test_id(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_text(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_title(self, *args: Any, **kwargs: Any) -> "Element": ...
        def normalize(self, *args: Any, **kwargs: Any) -> "Element": ...
        def describe(self, *args: Any, **kwargs: Any) -> "Element": ...
        # frame_locator / visible / content_frame 有真实方法体（返回包装类型），
        # 不在这里重复声明：同名声明会被当成条件定义，要求签名完全一致
        def and_(self, *args: Any, **kwargs: Any) -> "Element": ...
        def or_(self, *args: Any, **kwargs: Any) -> "Element": ...
        def within(self, *args: Any, **kwargs: Any) -> "Element": ...


def _make_action(name, label, has_value):
    def action(self, *args, **kwargs):
        return self._run(name, label, has_value, args, kwargs)

    action.__name__ = name
    action.__qualname__ = f"Element.{name}"
    action.__doc__ = f"{label}元素（自动记日志）"
    return action


def _make_child(name):
    def child(self, *args, **kwargs):
        args, kwargs = _unwrap_args(args, kwargs)
        method = getattr(self.native, name, None)
        if method is None:
            raise AttributeError(f"当前 Playwright 版本不支持 Locator.{name}()")
        return self._derive(method(*args, **kwargs))

    child.__name__ = name
    child.__qualname__ = f"Element.{name}"
    child.__doc__ = "链式定位，返回包装后的 Element"
    return child


class AsyncElement(_AsyncLocatorBase):
    """异步元素包装：动作方法需 await，日志与 allure 步骤行为同 Element。"""

    def __init__(
        self,
        owner,
        selector=None,
        desc=None,
        attr=None,
        sensitive=None,
        locator=None,
    ):
        self._owner = owner
        self._selector = selector
        self._desc = desc or attr or selector or ""
        self._attr = attr
        self._sensitive = sensitive
        self._raw_locator = locator

    @property
    def native(self):
        """原生 AsyncLocator"""
        if self._raw_locator is not None:
            return self._raw_locator
        return self._owner.page.locator(self._selector)

    @property
    def selector(self):
        """元素定位表达式"""
        return self._selector

    @property
    def desc(self):
        """元素描述"""
        return self._desc

    @property
    def _is_sensitive(self):
        """是否脱敏：显式标 sensitive 或名字命中敏感词"""
        if self._sensitive:
            return True
        key = f"{self._attr or ''}{self._desc or ''}".lower()
        return any(k in key for k in _SENSITIVE_KEYS)

    def _derive(self, locator):
        """基于新 Locator 派生 AsyncElement"""
        return AsyncElement(
            self._owner,
            selector=self._selector,
            desc=self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            locator=locator,
        )

    def __repr__(self):
        return f"<AsyncElement {self._desc}({self._selector or 'derived'})>"

    def _detail(self, label, args, kwargs, has_value):
        if not has_value:
            return label
        raw = args[0] if args else next(iter(kwargs.values()), None)
        if raw is None:
            return label
        text = "***" if self._is_sensitive else _fmt_raw(raw)
        return f"{label} {text}"

    async def _run(self, name, label, has_value, args, kwargs):
        args, kwargs = _unwrap_args(args, kwargs)
        detail = self._detail(label, args, kwargs, has_value)
        logger.info(f"[{_page_name(self._owner)}] {self._desc} {detail}")
        # allure_commons 的 StepContext 只实现了同步上下文协议（__enter__/__exit__），
        # 写 `async with` 会直接 TypeError：所有异步元素动作都跑不起来。
        # 同步 with 里 await 是合法的，步骤的进入/退出时机与异步版本等价。
        with allure.step(f"{self._desc} {detail}"):
            method = getattr(self.native, name, None)
            if method is None:
                raise AttributeError(f"当前 Playwright 版本不支持 Locator.{name}()")
            return await method(*args, **kwargs)

    @property
    def first(self):
        """匹配结果中的第一个"""
        return self._derive(self.native.first)

    @property
    def last(self):
        """匹配结果中的最后一个"""
        return self._derive(self.native.last)

    @property
    def visible(self) -> "AsyncElement":  # pyright: ignore[reportIncompatibleMethodOverride]
        """只要可见的那些（原生 Locator.visible 是属性，不是方法）

        区别于 is_visible()：那个要 await 且返回布尔，这个继续返回元素，可接着点击。
        """
        return self._derive(self.native.visible)

    @property
    def content_frame(self) -> "AsyncFrameElement":  # pyright: ignore[reportIncompatibleMethodOverride]
        """iframe 元素的文档内容（原生返回 FrameLocator，这里包成 AsyncFrameElement）"""
        return AsyncFrameElement(
            self._owner,
            selector=self._selector,
            desc=self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            frame=self.native.content_frame,
        )

    async def all(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        """匹配结果的全部元素（list[AsyncElement]），需 await

        与同步 Element.all 对齐：旧实现 AsyncElement 缺这个方法，
        异步用例只能自己 await native.count() 后循环 nth。
        """
        count = await self.native.count()
        return [self.nth(i) for i in range(count)]

    def frame_locator(self, selector: str) -> "AsyncFrameElement":  # type: ignore[override]  # pyright: ignore[reportIncompatibleMethodOverride]
        """进入子 iframe，返回 AsyncFrameElement（原生返回 AsyncFrameLocator）"""
        return AsyncFrameElement(
            self._owner,
            selector=self._selector,
            desc=self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            frame=self.native.frame_locator(selector),
        )

    def __getattr__(self, name):
        """白名单外的成员直通原生 AsyncLocator"""
        if name.startswith("_"):
            raise AttributeError(name)
        # 同 Element：绕过 __getattr__ 钩子取 native，否则求值失败会变成 RecursionError
        native = object.__getattribute__(self, "native")
        return getattr(native, name)

    if TYPE_CHECKING:  # pragma: no cover
        # 与 Element 同理：动作方法的签名来自 AsyncLocator 基类。
        # 注意链式定位在 async 版里仍是同步方法（返回 AsyncElement），不要写成 async def；
        # 只有 all 是协程，因为要先 await native.count()。
        def filter(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def nth(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def locator(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_alt_text(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_label(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_placeholder(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_role(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_test_id(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_text(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_title(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def describe(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        # normalize 在原生 AsyncLocator 上是协程，必须 await 后才有 Locator。
        # 注意：这里用 asyncio.iscoroutinefunction 判不出来（TYPE_CHECKING 期不执行），
        # 实际实现在 _make_async_child 里按 _ASYNC_AWAIT_CHILD 分支生成。
        async def normalize(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        # frame_locator / visible / content_frame 有真实方法体，不在这里重复声明
        def and_(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def or_(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def within(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...


def _make_async_action(name, label, has_value):
    async def action(self, *args, **kwargs):
        return await self._run(name, label, has_value, args, kwargs)

    action.__name__ = name
    action.__qualname__ = f"AsyncElement.{name}"
    action.__doc__ = f"{label}元素（自动记日志，需 await）"
    return action


def _make_async_child(name):
    """异步链式定位：普通方法（原生 AsyncLocator 上也是普通方法）"""
    def child(self, *args, **kwargs):
        args, kwargs = _unwrap_args(args, kwargs)
        method = getattr(self.native, name, None)
        if method is None:
            raise AttributeError(f"当前 Playwright 版本不支持 Locator.{name}()")
        return self._derive(method(*args, **kwargs))

    child.__name__ = name
    child.__qualname__ = f"AsyncElement.{name}"
    child.__doc__ = "链式定位，返回包装后的 AsyncElement"
    return child


def _make_async_await_child(name):
    """协程版链式定位（normalize）：先 await 原生方法，再包装结果"""
    async def child(self, *args, **kwargs):
        args, kwargs = _unwrap_args(args, kwargs)
        method = getattr(self.native, name, None)
        if method is None:
            raise AttributeError(f"当前 Playwright 版本不支持 Locator.{name}()")
        return self._derive(await method(*args, **kwargs))

    child.__name__ = name
    child.__qualname__ = f"AsyncElement.{name}"
    child.__doc__ = "链式定位（原生为协程），返回包装后的 AsyncElement"
    return child


for _name, (_label, _has_value) in _ACTION_LABELS.items():
    setattr(Element, _name, _make_action(_name, _label, _has_value))
    setattr(AsyncElement, _name, _make_async_action(_name, _label, _has_value))

for _name in _CHILD_METHODS:
    setattr(Element, _name, _make_child(_name))
    # normalize 在原生 AsyncLocator 上是协程，必须 await 后再包装；其余是普通方法
    if _name in _ASYNC_AWAIT_CHILD:
        setattr(AsyncElement, _name, _make_async_await_child(_name))
    else:
        setattr(AsyncElement, _name, _make_async_child(_name))

# visible / describe / content_frame / frame_locator 只存在于其中一边或需要额外处理：
# - visible / content_frame 是属性（见类体里的 @property）
# - describe 两类都是普通方法，由上面的循环注入
# - frame_locator 返回包装后的 FrameElement，见类体里的实现


class FrameElement(_SyncFrameLocatorBase):
    """iframe 包装：只有子定位能力（locator / get_by_*），没有 click 那套动作。

    Playwright 的 FrameLocator 本就不提供 click / inner_text 等动作，直接包成 Element
    会让这些调用以「当前 Playwright 版本不支持 Locator.click()」这种误导性文案报错。
    子定位结果（Locator）仍然包成 Element，日志与 allure 步骤不丢。
    """

    def __init__(self, owner, selector=None, desc=None, attr=None, sensitive=None, frame=None):
        self._owner = owner
        self._selector = selector
        self._desc = desc or attr or selector or ""
        self._attr = attr
        self._sensitive = sensitive
        self._raw_frame = frame

    @property
    def native(self):
        """原生 FrameLocator"""
        if self._raw_frame is not None:
            return self._raw_frame
        return self._owner.page.frame_locator(self._selector)

    @property
    def selector(self):
        return self._selector

    @property
    def desc(self):
        return self._desc

    @property
    def first(self) -> "FrameElement":
        """第一个匹配的 iframe"""
        return self._derive_frame(self.native.first)

    @property
    def last(self) -> "FrameElement":
        """最后一个匹配的 iframe"""
        return self._derive_frame(self.native.last)

    def _wrap_locator(self, locator, desc=None):
        """子定位结果是 Locator，包成 Element（desc 带上子选择器，日志才认得出是哪个元素）"""
        return Element(
            self._owner,
            selector=self._selector,
            desc=desc or self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            locator=locator,
        )

    def _derive_frame(self, frame):
        """仍然是 FrameLocator（嵌套 iframe），保持 FrameElement"""
        return FrameElement(
            self._owner,
            selector=self._selector,
            desc=self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            frame=frame,
        )

    def __repr__(self):
        return f"<FrameElement {self._desc}({self._selector or 'derived'})>"

    def __getattr__(self, name):
        """未包装的成员直通原生 FrameLocator（on / once 等）"""
        if name.startswith("_"):
            raise AttributeError(name)
        # 只把「原生对象确实没这个成员」翻译成 iframe 提示；
        # native 自身求值失败是另一回事，原样抛出，别掩盖真实错误
        native = object.__getattribute__(self, "native")
        try:
            return getattr(native, name)
        except AttributeError:
            raise AttributeError(_frame_action_hint(name, self._desc)) from None

    if TYPE_CHECKING:  # pragma: no cover
        # 子定位返回 Element（原生 FrameLocator.locator 返回 Locator），
        # 声明在这里是为了让 frame.locator(...).click() 在 IDE 里有补全
        def locator(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_alt_text(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_label(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_placeholder(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_role(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_test_id(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_text(self, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_title(self, *args: Any, **kwargs: Any) -> "Element": ...
        # 嵌套 iframe 仍返回 FrameElement
        def nth(self, *args: Any, **kwargs: Any) -> "FrameElement": ...
        def frame_locator(self, *args: Any, **kwargs: Any) -> "FrameElement": ...


class AsyncFrameElement(_AsyncFrameLocatorBase):
    """异步 iframe 包装：子定位返回 AsyncElement，日志与 allure 步骤行为同 FrameElement。"""

    def __init__(self, owner, selector=None, desc=None, attr=None, sensitive=None, frame=None):
        self._owner = owner
        self._selector = selector
        self._desc = desc or attr or selector or ""
        self._attr = attr
        self._sensitive = sensitive
        self._raw_frame = frame

    @property
    def native(self):
        """原生 AsyncFrameLocator"""
        if self._raw_frame is not None:
            return self._raw_frame
        return self._owner.page.frame_locator(self._selector)

    @property
    def selector(self):
        return self._selector

    @property
    def desc(self):
        return self._desc

    @property
    def first(self) -> "AsyncFrameElement":
        """第一个匹配的 iframe"""
        return self._derive_frame(self.native.first)

    @property
    def last(self) -> "AsyncFrameElement":
        """最后一个匹配的 iframe"""
        return self._derive_frame(self.native.last)

    def _wrap_locator(self, locator, desc=None):
        """子定位结果是 AsyncLocator，包成 AsyncElement"""
        return AsyncElement(
            self._owner,
            selector=self._selector,
            desc=desc or self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            locator=locator,
        )

    def _derive_frame(self, frame):
        """仍然是 AsyncFrameLocator（嵌套 iframe），保持 AsyncFrameElement"""
        return AsyncFrameElement(
            self._owner,
            selector=self._selector,
            desc=self._desc,
            attr=self._attr,
            sensitive=self._sensitive,
            frame=frame,
        )

    def __repr__(self):
        return f"<AsyncFrameElement {self._desc}({self._selector or 'derived'})>"

    def __getattr__(self, name):
        """未包装的成员直通原生 AsyncFrameLocator"""
        if name.startswith("_"):
            raise AttributeError(name)
        # 同 FrameElement：native 求值失败要原样抛出，不能翻译成 iframe 提示
        native = object.__getattribute__(self, "native")
        try:
            return getattr(native, name)
        except AttributeError:
            raise AttributeError(_frame_action_hint(name, self._desc)) from None

    if TYPE_CHECKING:  # pragma: no cover
        # 与 FrameElement 同理；异步 FrameLocator 的子定位同样是普通方法（不是协程），
        # 只有拿到的元素上的动作才需要 await
        def locator(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_alt_text(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_label(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_placeholder(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_role(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_test_id(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_text(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def get_by_title(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        def nth(self, *args: Any, **kwargs: Any) -> "AsyncFrameElement": ...
        def frame_locator(self, *args: Any, **kwargs: Any) -> "AsyncFrameElement": ...


def _make_frame_child(name):
    def child(self, *args, **kwargs):
        args, kwargs = _unwrap_args(args, kwargs)
        method = getattr(self.native, name, None)
        if method is None:
            raise AttributeError(f"当前 Playwright 版本不支持 FrameLocator.{name}()")
        return self._wrap_locator(method(*args, **kwargs))

    child.__name__ = name
    child.__qualname__ = f"FrameElement.{name}"
    child.__doc__ = "iframe 内的子定位，返回包装后的 Element"
    return child


def _make_frame_frame(name):
    def child(self, *args, **kwargs):
        method = getattr(self.native, name, None)
        if method is None:
            raise AttributeError(f"当前 Playwright 版本不支持 FrameLocator.{name}()")
        return self._derive_frame(method(*args, **kwargs))

    child.__name__ = name
    child.__qualname__ = f"FrameElement.{name}"
    child.__doc__ = "嵌套 iframe 定位，返回包装后的 FrameElement"
    return child


for _name in _FRAME_LOCATOR_METHODS:
    setattr(FrameElement, _name, _make_frame_child(_name))
    setattr(AsyncFrameElement, _name, _make_frame_child(_name))

for _name in _FRAME_FRAME_METHODS:
    setattr(FrameElement, _name, _make_frame_frame(_name))
    setattr(AsyncFrameElement, _name, _make_frame_frame(_name))


class _ElementDescriptor:
    """元素描述符：__set_name__ 拿到属性名，__get__ 返回包装后的 Element。

    描述符是类级单例，状态只存 selector/desc/attr；Element 每次访问新建，很轻。
    """

    def __init__(self, selector, desc=None, sensitive=None, is_async=False):
        self.selector = selector
        self.desc = desc
        self.sensitive = sensitive
        self.is_async = is_async
        self.attr = None

    def __set_name__(self, owner, name):
        self.attr = name

    @overload
    def __get__(self, obj: None, objtype: type | None = ...) -> "_ElementDescriptor": ...

    @overload
    def __get__(self, obj: Any, objtype: type | None = ...) -> "Element | AsyncElement": ...

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        cls = AsyncElement if self.is_async else Element
        return cls(
            obj,
            selector=self.selector,
            desc=self.desc or self.attr,
            attr=self.attr,
            sensitive=self.sensitive,
        )


def element(selector, desc=None, sensitive=None) -> "Element":
    """声明同步元素：selector 必填，desc 是日志里的中文名。

    参数：
        selector: Playwright 定位表达式，如 "[name='username']"
        desc: 日志/报告里的元素名，不传则用属性名
        sensitive: True 时值在日志里显示为 ***；默认按属性名自动判断
            （含 password / pwd / token / 密码 等关键词自动脱敏）
    """
    return cast("Element", _ElementDescriptor(selector, desc, sensitive, is_async=False))


def async_element(selector, desc=None, sensitive=None) -> "AsyncElement":
    """声明异步元素：用法同 element，方法调用需 await"""
    return cast("AsyncElement", _ElementDescriptor(selector, desc, sensitive, is_async=True))
