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
import os
from typing import TYPE_CHECKING, Any, cast, overload

import allure

from just_go._internal.logger import logger

__all__ = ["Element", "AsyncElement", "element", "async_element"]

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
    "frame_locator",
    "and_",
    "or_",
    "within",
)

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


def _unwrap_args(args, kwargs):
    """把 Element 参数还原成原生 Locator（drag_to / filter / drop 等要用）"""
    new_args = tuple(a.native if isinstance(a, Element) else a for a in args)
    new_kwargs = {
        k: (v.native if isinstance(v, Element) else v) for k, v in kwargs.items()
    }
    return new_args, new_kwargs


def _fmt_raw(raw):
    """值格式化：文件路径只留文件名，超长截断"""
    if isinstance(raw, Element):
        return repr(raw)
    if isinstance(raw, (list, tuple)):
        items = [
            os.path.basename(x) if isinstance(x, str) else str(x) for x in raw
        ]
        text = "[" + ", ".join(items) + "]"
    elif isinstance(raw, str) and ("\\" in raw or "/" in raw):
        # 单个文件路径只显示文件名，避免日志里泄露目录结构
        text = os.path.basename(raw)
    else:
        text = str(raw)
    if len(text) > _MAX_VALUE_LEN:
        text = text[: _MAX_VALUE_LEN - 3] + "..."
    return text if text.startswith("[") else f'"{text}"'


class Element:
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
    def all(self):
        """匹配结果的全部元素（list[Element]）"""
        return [self.nth(i) for i in range(self.native.count())]

    def __getattr__(self, name):
        """白名单外的成员直通原生 Locator"""
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.native, name)

    if TYPE_CHECKING:  # pragma: no cover
        # 动作方法与链式定位由文件末尾的 setattr 按 _ACTION_LABELS / _CHILD_METHODS
        # 注入，运行时类体里并不存在；这份声明只给 IDE 补全和类型检查用，不参与运行。
        # 新增白名单条目时同步补一行，否则补全会缺。
        def click(self, *args: Any, **kwargs: Any) -> Any: ...
        def dblclick(self, *args: Any, **kwargs: Any) -> Any: ...
        def tap(self, *args: Any, **kwargs: Any) -> Any: ...
        def fill(self, value: str, *args: Any, **kwargs: Any) -> Any: ...
        def clear(self, *args: Any, **kwargs: Any) -> Any: ...
        def type(self, text: str, *args: Any, **kwargs: Any) -> Any: ...
        def press(self, key: str, *args: Any, **kwargs: Any) -> Any: ...
        def press_sequentially(self, text: str, *args: Any, **kwargs: Any) -> Any: ...
        def select_text(self, *args: Any, **kwargs: Any) -> Any: ...
        def check(self, *args: Any, **kwargs: Any) -> Any: ...
        def uncheck(self, *args: Any, **kwargs: Any) -> Any: ...
        def set_checked(self, checked: bool, *args: Any, **kwargs: Any) -> Any: ...
        def select_option(self, *args: Any, **kwargs: Any) -> Any: ...
        def hover(self, *args: Any, **kwargs: Any) -> Any: ...
        def focus(self, *args: Any, **kwargs: Any) -> Any: ...
        def blur(self, *args: Any, **kwargs: Any) -> Any: ...
        def set_input_files(self, files: Any, *args: Any, **kwargs: Any) -> Any: ...
        def drop(self, *args: Any, **kwargs: Any) -> Any: ...
        def drag_to(self, target: Any, *args: Any, **kwargs: Any) -> Any: ...
        def scroll_into_view_if_needed(self, *args: Any, **kwargs: Any) -> Any: ...
        def wait_for(self, *args: Any, **kwargs: Any) -> Any: ...
        def dispatch_event(self, type: str, *args: Any, **kwargs: Any) -> Any: ...
        def evaluate(self, expression: str, *args: Any, **kwargs: Any) -> Any: ...
        def evaluate_all(self, expression: str, *args: Any, **kwargs: Any) -> Any: ...
        def evaluate_handle(self, expression: str, *args: Any, **kwargs: Any) -> Any: ...
        def screenshot(self, *args: Any, **kwargs: Any) -> Any: ...
        def highlight(self, *args: Any, **kwargs: Any) -> Any: ...
        def hide_highlight(self, *args: Any, **kwargs: Any) -> Any: ...

        def filter(self, *args: Any, **kwargs: Any) -> "Element": ...
        def nth(self, index: int, *args: Any, **kwargs: Any) -> "Element": ...
        def locator(self, selector: str, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_alt_text(self, text: Any, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_label(self, text: Any, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_placeholder(self, text: Any, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_role(self, role: Any, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_test_id(self, test_id: Any, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_text(self, text: Any, *args: Any, **kwargs: Any) -> "Element": ...
        def get_by_title(self, text: Any, *args: Any, **kwargs: Any) -> "Element": ...
        def frame_locator(self, selector: str, *args: Any, **kwargs: Any) -> "Element": ...
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


class AsyncElement:
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
        async with allure.step(f"{self._desc} {detail}"):
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

    def __getattr__(self, name):
        """白名单外的成员直通原生 AsyncLocator"""
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self.native, name)

    if TYPE_CHECKING:  # pragma: no cover
        # 与 Element 同理：方法体由 setattr 注入，这里只声明给 IDE 用。
        async def click(self, *args: Any, **kwargs: Any) -> Any: ...
        async def dblclick(self, *args: Any, **kwargs: Any) -> Any: ...
        async def tap(self, *args: Any, **kwargs: Any) -> Any: ...
        async def fill(self, value: str, *args: Any, **kwargs: Any) -> Any: ...
        async def clear(self, *args: Any, **kwargs: Any) -> Any: ...
        async def type(self, text: str, *args: Any, **kwargs: Any) -> Any: ...
        async def press(self, key: str, *args: Any, **kwargs: Any) -> Any: ...
        async def press_sequentially(self, text: str, *args: Any, **kwargs: Any) -> Any: ...
        async def select_text(self, *args: Any, **kwargs: Any) -> Any: ...
        async def check(self, *args: Any, **kwargs: Any) -> Any: ...
        async def uncheck(self, *args: Any, **kwargs: Any) -> Any: ...
        async def set_checked(self, checked: bool, *args: Any, **kwargs: Any) -> Any: ...
        async def select_option(self, *args: Any, **kwargs: Any) -> Any: ...
        async def hover(self, *args: Any, **kwargs: Any) -> Any: ...
        async def focus(self, *args: Any, **kwargs: Any) -> Any: ...
        async def blur(self, *args: Any, **kwargs: Any) -> Any: ...
        async def set_input_files(self, files: Any, *args: Any, **kwargs: Any) -> Any: ...
        async def drop(self, *args: Any, **kwargs: Any) -> Any: ...
        async def drag_to(self, target: Any, *args: Any, **kwargs: Any) -> Any: ...
        async def scroll_into_view_if_needed(self, *args: Any, **kwargs: Any) -> Any: ...
        async def wait_for(self, *args: Any, **kwargs: Any) -> Any: ...
        async def dispatch_event(self, type: str, *args: Any, **kwargs: Any) -> Any: ...
        async def evaluate(self, expression: str, *args: Any, **kwargs: Any) -> Any: ...
        async def evaluate_all(self, expression: str, *args: Any, **kwargs: Any) -> Any: ...
        async def evaluate_handle(self, expression: str, *args: Any, **kwargs: Any) -> Any: ...
        async def screenshot(self, *args: Any, **kwargs: Any) -> Any: ...
        async def highlight(self, *args: Any, **kwargs: Any) -> Any: ...
        async def hide_highlight(self, *args: Any, **kwargs: Any) -> Any: ...

        async def filter(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def nth(self, index: int, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def locator(self, selector: str, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def get_by_alt_text(self, text: Any, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def get_by_label(self, text: Any, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def get_by_placeholder(self, text: Any, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def get_by_role(self, role: Any, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def get_by_test_id(self, test_id: Any, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def get_by_text(self, text: Any, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def get_by_title(self, text: Any, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def frame_locator(self, selector: str, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def and_(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def or_(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...
        async def within(self, *args: Any, **kwargs: Any) -> "AsyncElement": ...


def _make_async_action(name, label, has_value):
    async def action(self, *args, **kwargs):
        return await self._run(name, label, has_value, args, kwargs)

    action.__name__ = name
    action.__qualname__ = f"AsyncElement.{name}"
    action.__doc__ = f"{label}元素（自动记日志，需 await）"
    return action


def _make_async_child(name):
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


for _name, (_label, _has_value) in _ACTION_LABELS.items():
    setattr(Element, _name, _make_action(_name, _label, _has_value))
    setattr(AsyncElement, _name, _make_async_action(_name, _label, _has_value))

for _name in _CHILD_METHODS:
    setattr(Element, _name, _make_child(_name))
    setattr(AsyncElement, _name, _make_async_child(_name))


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
