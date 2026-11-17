#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/27 14:28
# @Author   :luye
"""断言类：纯数据断言 + playwright UI 断言。

- AssertCommon：纯数据断言（同步异步通用，不依赖 playwright）
- SyncAssert：同步用例用，数据断言 + UI 断言
- AsyncAssert：异步用例用，数据断言 + UI 断言（UI 方法需 await）

UI 断言写法：每个正向断言用 @negates("have_text") 标出等价的 Playwright 断言名，
类装饰器 @with_negations 在导入时按同一份签名生成配套的 assert_not_xxx。
新增能力要在 SyncAssert / AsyncAssert 各加一个正向断言——不要只补其中一边，
tests/test_assertion.py 会校验两边方法集合一致、反向方法齐全。
"""
import inspect
import re

from playwright.async_api import expect as async_expect
from playwright.sync_api import expect as sync_expect

from just_go._internal.element import AsyncElement, Element
from just_go._internal.logger import logger


def _to_locator(obj):
    """Element / AsyncElement 还原成原生 Locator，selector 字符串或 Page 原样返回"""
    if isinstance(obj, (Element, AsyncElement)):
        return obj.native
    return obj


def _to_page(obj):
    """页面对象（PageExport 等 SyncWebUI/AsyncWebUI 子类）还原成原生 Playwright Page。

    expect() 只认原生 Page，直接传 PageExport 会报 "Unsupported type"；
    用例里 page.assert_url(page, ...) 传的是包装对象，这里统一还原。
    """
    from just_go._internal.web import AsyncWebUI, SyncWebUI

    if isinstance(obj, (SyncWebUI, AsyncWebUI)):
        return obj.page
    return obj


class AssertCommon:
    """纯数据断言（同步/异步通用，不依赖 playwright）。"""

    def assert_equal(self, expect, actual):
        """断言预期和实际相等"""
        if expect != actual:
            raise AssertionError(f"{expect} 不等于 {actual}")
        logger.info(f"{expect} 等于 {actual}")

    def assert_not_equal(self, expect, actual):
        """断言预期和实际不相等"""
        if expect == actual:
            raise AssertionError(f"{expect} 等于 {actual}")
        logger.info(f"{expect} 不等于 {actual}")

    def assert_in(self, expect, actual):
        """断言预期在实际中"""
        if expect not in actual:
            raise AssertionError(f"{expect} 不在 {actual}")
        logger.info(f"{expect} 在 {actual}")

    def assert_not_in(self, expect, actual):
        """断言预期在实际中不存在"""
        if expect in actual:
            raise AssertionError(f"{expect} 在 {actual}")
        logger.info(f"{expect} 不在 {actual}")

    def assert_true(self, actual):
        """断言实际为真"""
        if not actual:
            raise AssertionError(f"{actual} 不为真")
        logger.info(f"{actual} 为真")

    def assert_false(self, actual):
        """断言实际为假"""
        if actual:
            raise AssertionError(f"{actual} 不为假")
        logger.info(f"{actual} 为假")

    def assert_re_check_equal(self, pattern, actual_text):
        """正则匹配相等"""
        if not re.search(pattern, actual_text):
            raise AssertionError(
                f"正则匹配失败，pattern: {pattern}, actual_text: {actual_text}"
            )
        logger.info(f"正则匹配成功，pattern: {pattern}, actual_text: {actual_text}")

    def assert_re_check_not_equal(self, pattern, actual_text):
        """断言实际文本不匹配正则（反向断言）"""
        if re.search(pattern, actual_text):
            raise AssertionError(
                f"正则不应匹配但实际匹配，pattern: {pattern}, actual_text: {actual_text}"
            )
        logger.info(f"正则未匹配（符合预期），pattern: {pattern}")

    def assert_image(
        self,
        *images,
        similarity=1.0,
        timeout=3.0,
        interval=0.5,
        source=None,
        method="ccoeff",
        search_dirs=None,
    ):
        """断言屏幕上能找到目标图片，返回命中结果（可继续取坐标）。

        参数：
            images      1 个或多个模板图路径，可省略 .png/.jpg/.jpeg 后缀（相对路径基于项目根）
            similarity  相似度阈值，默认 1.0（100%）；屏幕存在光标、悬停动画时可传 0.98
            timeout     等待秒数，默认 3；屏幕内容加载慢时调大
            interval    两轮检测的间隔秒数，默认 0.5
            source      搜索画面，默认全屏；也可传 (x, y, w, h) 屏幕区域或截图文件
            method      匹配算法：ccoeff（默认，抗亮度偏移）/ corr / sqdiff
            search_dirs 相对路径的搜索目录，默认项目根目录

        未命中抛 AssertionError，文案带尝试次数与最高相似度。
        需要 just-go[image] 可选依赖，未安装时抛 SoftwareNotInstallError。
        """
        from just_go.image import wait_image

        result = wait_image(
            *images,
            similarity=similarity,
            timeout=timeout,
            interval=interval,
            source=source,
            method=method,
            search_dirs=search_dirs,
        )
        if not result:
            raise AssertionError(
                f"未找到图片：{' / '.join(str(i) for i in images)}，"
                f"已尝试 {result.attempts} 次，最高相似度 {result.best_score:.4f}"
            )
        logger.info(f"图片匹配成功：{result.match.path} 相似度 {result.match.score:.4f}")
        return result

    def assert_not_image(
        self,
        *images,
        similarity=1.0,
        timeout=0,
        interval=0.5,
        source=None,
        method="ccoeff",
        search_dirs=None,
    ):
        """断言屏幕上找不到目标图片；timeout>0 时要求这段时间内一直未出现才算通过。

        参数与 assert_image 相同，区别是 timeout 默认 0（只检查一次）。
        适用于「按钮已消失」「弹窗已关闭」这类断言；要确认它「不会出现」就传 timeout。

        未出现时正常返回 FindResult；仍然出现时抛 AssertionError，文案带位置与相似度。
        """
        from just_go.image import wait_image

        result = wait_image(
            *images,
            similarity=similarity,
            timeout=timeout,
            interval=interval,
            source=source,
            method=method,
            search_dirs=search_dirs,
        )
        if result.found:
            raise AssertionError(
                f"图片不应存在但找到了：{result.match.path}，"
                f"相似度 {result.match.score:.4f}，位置 {result.match.center}"
            )
        logger.info(
            f"图片未出现（符合预期）：{' / '.join(str(i) for i in images)}，"
            f"最高相似度 {result.best_score:.4f}"
        )
        return result


# ---------------------------------------------------------------------------
# 反向断言自动生成
# ---------------------------------------------------------------------------
# 每个正向断言用 @negates("have_text") 标出对应的 Playwright 断言名，
# 类装饰器 @with_negations 据此生成配套的 assert_not_xxx
# （assert_text -> assert_not_text，内部调用 not_to_have_text）。
# 参数、timeout 与 ignore_case 之类的关键字按正向签名原样透传；同步/异步按方法
# 本身是否 async def 自动决定要不要 await，两套断言类共用同一份生成逻辑。

def negates(native):
    """标记正向断言对应的 Playwright 断言名（不含 to_ 前缀）：negates("have_text")"""
    def mark(func):
        func.__negate_native__ = native
        return func

    return mark


def _build_negation(func, native):
    """按正向断言生成反向断言：入参与正向完全一致，内部调用 not_to_xxx。

    参数先按正向签名完整绑定（支持位置传参与 locator= / page= 这类关键字传参），
    再决定怎么交给原生断言：
    - 第一个断言参数（expected / name / count / values）按位置传：
      Playwright 的 not_to_have_url / not_to_have_title 形参名是 url_or_reg_exp /
      title_or_reg_exp，用关键字会撞名；
    - 其余参数名与 Playwright 一致，按关键字传（ignore_case / use_inner_text / value）；
    - 未显式指定的参数（默认 None）不往下传，避免覆盖 Playwright 自己的默认行为。
    """
    not_native = "not_to_" + native
    sig = inspect.signature(func)
    params = list(sig.parameters)
    target = params[1] if len(params) > 1 else "locator"
    semantic = [p for p in params[2:] if p != "timeout"]  # 断言参数（含第一个 expected/name/count）
    payload = semantic[0] if semantic else None
    extra = semantic[1:]
    convert = _to_page if target == "page" else _to_locator
    neg_name = "assert_not_" + func.__name__[len("assert_"):]
    doc = f"[反向] {inspect.getdoc(func) or func.__name__}（{not_native}）"

    def prepare(self, args, kwargs):
        bound = sig.bind(self, *args, **kwargs)
        bound.apply_defaults()
        values = bound.arguments
        positional = ()
        if payload is not None and values.get(payload) is not None:
            positional = (values[payload],)
        kw = {k: values[k] for k in extra if values.get(k) is not None}
        if values.get("timeout") is not None:  # 显式 timeout 必须透传，None 时用 Playwright 默认
            kw["timeout"] = values["timeout"]
        return convert(values[target]), positional, kw

    if inspect.iscoroutinefunction(func):
        async def negation(self, *args, **kwargs):
            obj, positional, kw = prepare(self, args, kwargs)
            await getattr(async_expect(obj), not_native)(*positional, **kw)
            logger.info(f"{neg_name} 成立: {obj} {positional or ''}".rstrip())

    else:
        def negation(self, *args, **kwargs):
            obj, positional, kw = prepare(self, args, kwargs)
            getattr(sync_expect(obj), not_native)(*positional, **kw)
            logger.info(f"{neg_name} 成立: {obj} {positional or ''}".rstrip())

    negation.__name__ = neg_name
    negation.__qualname__ = f"{func.__qualname__.rsplit('.', 1)[0]}.{neg_name}"
    negation.__doc__ = doc
    negation.__wrapped__ = func
    # 保留正向签名：IDE 补全、inspect.signature 与关键字调用（locator= / page=）都能对齐
    negation.__signature__ = sig
    return negation


def with_negations(cls):
    """类装饰器：给标了 @negates 的正向断言自动补上 assert_not_xxx"""
    for name, func in list(vars(cls).items()):
        native = getattr(func, "__negate_native__", None)
        if not native or not name.startswith("assert_"):
            continue
        neg_name = "assert_not_" + name[len("assert_"):]
        if neg_name not in vars(cls):
            setattr(cls, neg_name, _build_negation(func, native))
    return cls


@with_negations
class SyncAssert(AssertCommon):
    """同步断言：纯数据断言 + playwright UI 断言。配合 def test_xxx(page) 使用。

    每个 assert_xxx 都有配套的 assert_not_xxx（由 @negates 自动生成），
    反向断言同样走 Playwright 的自动等待重试，不必自己取文本再比较。
    """

    # ---- 可见性 / 存在 ----
    @negates("be_visible")
    def assert_visible(self, locator, timeout=None):
        """断言元素可见"""
        sync_expect(_to_locator(locator)).to_be_visible(timeout=timeout)
        logger.info(f"元素可见: {locator}")

    @negates("be_hidden")
    def assert_hidden(self, locator, timeout=None):
        """断言元素隐藏（不存在或不可见）；只想断言「存在但不可见」用 assert_not_visible"""
        sync_expect(_to_locator(locator)).to_be_hidden(timeout=timeout)
        logger.info(f"元素隐藏: {locator}")

    @negates("be_attached")
    def assert_attached(self, locator, timeout=None):
        """断言元素已挂载到 DOM（不要求可见）"""
        sync_expect(_to_locator(locator)).to_be_attached(timeout=timeout)
        logger.info(f"元素已挂载: {locator}")

    @negates("be_empty")
    def assert_empty(self, locator, timeout=None):
        """断言元素内没有子节点/文本（空列表、空表格）"""
        sync_expect(_to_locator(locator)).to_be_empty(timeout=timeout)
        logger.info(f"元素为空: {locator}")

    @negates("have_count")
    def assert_count(self, locator, count, timeout=None):
        """断言匹配的元素数量等于 count"""
        sync_expect(_to_locator(locator)).to_have_count(count, timeout=timeout)
        logger.info(f"元素数量等于 {count}: {locator}")

    # ---- 文本 / 值 ----
    @negates("have_text")
    def assert_text(self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None):
        """断言元素文本等于 expected（支持正则与列表，与 Playwright 一致）"""
        sync_expect(_to_locator(locator)).to_have_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本等于 '{expected}': {locator}")

    @negates("contain_text")
    def assert_text_contains(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本包含 expected（expected 可为子串、正则或它们的列表）"""
        sync_expect(_to_locator(locator)).to_contain_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本包含 '{expected}': {locator}")

    @negates("have_value")
    def assert_value(self, locator, expected, timeout=None):
        """断言输入框值等于 expected"""
        sync_expect(_to_locator(locator)).to_have_value(expected, timeout=timeout)
        logger.info(f"输入框值等于 '{expected}': {locator}")

    @negates("have_values")
    def assert_values(self, locator, expected, timeout=None):
        """断言多选控件（如 multiple select）的选中值等于 expected 列表"""
        sync_expect(_to_locator(locator)).to_have_values(expected, timeout=timeout)
        logger.info(f"多选值等于 {expected}: {locator}")

    # ---- 状态 ----
    @negates("be_checked")
    def assert_checked(self, locator, timeout=None):
        """断言复选框/单选框已选中"""
        sync_expect(_to_locator(locator)).to_be_checked(timeout=timeout)
        logger.info(f"元素已选中: {locator}")

    @negates("be_enabled")
    def assert_enabled(self, locator, timeout=None):
        """断言元素可用"""
        sync_expect(_to_locator(locator)).to_be_enabled(timeout=timeout)
        logger.info(f"元素可用: {locator}")

    @negates("be_disabled")
    def assert_disabled(self, locator, timeout=None):
        """断言元素禁用"""
        sync_expect(_to_locator(locator)).to_be_disabled(timeout=timeout)
        logger.info(f"元素禁用: {locator}")

    @negates("be_editable")
    def assert_editable(self, locator, timeout=None):
        """断言元素可编辑（readonly / disabled 时为 False）"""
        sync_expect(_to_locator(locator)).to_be_editable(timeout=timeout)
        logger.info(f"元素可编辑: {locator}")

    @negates("be_focused")
    def assert_focused(self, locator, timeout=None):
        """断言元素已获得焦点"""
        sync_expect(_to_locator(locator)).to_be_focused(timeout=timeout)
        logger.info(f"元素获得焦点: {locator}")

    # ---- 属性 / 标识 ----
    @negates("have_attribute")
    def assert_attribute(self, locator, name, value=None, timeout=None):
        """断言元素属性 name 等于 value；value 省略时只断言属性存在"""
        sync_expect(_to_locator(locator)).to_have_attribute(name, value, timeout=timeout)
        logger.info(f"元素属性 {name}={value}: {locator}")

    @negates("have_id")
    def assert_id(self, locator, expected, timeout=None):
        """断言元素 id 等于 expected"""
        sync_expect(_to_locator(locator)).to_have_id(expected, timeout=timeout)
        logger.info(f"元素 id 等于 '{expected}': {locator}")

    @negates("have_class")
    def assert_class(self, locator, expected, timeout=None):
        """断言元素 class 属性与 expected 完全一致（顺序无关）；只关心部分 class 用 assert_class_contains"""
        sync_expect(_to_locator(locator)).to_have_class(expected, timeout=timeout)
        logger.info(f"元素 class 完全匹配 '{expected}': {locator}")

    @negates("contain_class")
    def assert_class_contains(self, locator, expected, timeout=None):
        """断言元素 class 包含 expected 里的全部类名（expected 可为空格分隔字符串或列表）"""
        sync_expect(_to_locator(locator)).to_contain_class(expected, timeout=timeout)
        logger.info(f"元素 class 包含 '{expected}': {locator}")

    # ---- 页面 ----
    @negates("have_url")
    def assert_url(self, page, expected, timeout=None, ignore_case=None):
        """断言页面 URL（支持正则）；page 可直接传 PageExport"""
        sync_expect(_to_page(page)).to_have_url(expected, timeout=timeout, ignore_case=ignore_case)
        logger.info(f"页面 URL 匹配: {expected}")

    @negates("have_title")
    def assert_title(self, page, expected, timeout=None):
        """断言页面标题（支持正则）；page 可直接传 PageExport"""
        sync_expect(_to_page(page)).to_have_title(expected, timeout=timeout)
        logger.info(f"页面标题匹配: {expected}")


@with_negations
class AsyncAssert(AssertCommon):
    """异步断言：纯数据断言 + UI 断言（UI 方法需 await）。配合 async def test_xxx(page) 使用。

    方法集合与 SyncAssert 完全一致，反向断言同样由 @negates 自动生成。
    """

    # ---- 可见性 / 存在 ----
    @negates("be_visible")
    async def assert_visible(self, locator, timeout=None):
        """断言元素可见"""
        await async_expect(_to_locator(locator)).to_be_visible(timeout=timeout)
        logger.info(f"元素可见: {locator}")

    @negates("be_hidden")
    async def assert_hidden(self, locator, timeout=None):
        """断言元素隐藏（不存在或不可见）；只想断言「存在但不可见」用 assert_not_visible"""
        await async_expect(_to_locator(locator)).to_be_hidden(timeout=timeout)
        logger.info(f"元素隐藏: {locator}")

    @negates("be_attached")
    async def assert_attached(self, locator, timeout=None):
        """断言元素已挂载到 DOM（不要求可见）"""
        await async_expect(_to_locator(locator)).to_be_attached(timeout=timeout)
        logger.info(f"元素已挂载: {locator}")

    @negates("be_empty")
    async def assert_empty(self, locator, timeout=None):
        """断言元素内没有子节点/文本（空列表、空表格）"""
        await async_expect(_to_locator(locator)).to_be_empty(timeout=timeout)
        logger.info(f"元素为空: {locator}")

    @negates("have_count")
    async def assert_count(self, locator, count, timeout=None):
        """断言匹配的元素数量等于 count"""
        await async_expect(_to_locator(locator)).to_have_count(count, timeout=timeout)
        logger.info(f"元素数量等于 {count}: {locator}")

    # ---- 文本 / 值 ----
    @negates("have_text")
    async def assert_text(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本等于 expected（支持正则与列表，与 Playwright 一致）"""
        await async_expect(_to_locator(locator)).to_have_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本等于 '{expected}': {locator}")

    @negates("contain_text")
    async def assert_text_contains(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本包含 expected（expected 可为子串、正则或它们的列表）"""
        await async_expect(_to_locator(locator)).to_contain_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本包含 '{expected}': {locator}")

    @negates("have_value")
    async def assert_value(self, locator, expected, timeout=None):
        """断言输入框值等于 expected"""
        await async_expect(_to_locator(locator)).to_have_value(expected, timeout=timeout)
        logger.info(f"输入框值等于 '{expected}': {locator}")

    @negates("have_values")
    async def assert_values(self, locator, expected, timeout=None):
        """断言多选控件（如 multiple select）的选中值等于 expected 列表"""
        await async_expect(_to_locator(locator)).to_have_values(expected, timeout=timeout)
        logger.info(f"多选值等于 {expected}: {locator}")

    # ---- 状态 ----
    @negates("be_checked")
    async def assert_checked(self, locator, timeout=None):
        """断言复选框/单选框已选中"""
        await async_expect(_to_locator(locator)).to_be_checked(timeout=timeout)
        logger.info(f"元素已选中: {locator}")

    @negates("be_enabled")
    async def assert_enabled(self, locator, timeout=None):
        """断言元素可用"""
        await async_expect(_to_locator(locator)).to_be_enabled(timeout=timeout)
        logger.info(f"元素可用: {locator}")

    @negates("be_disabled")
    async def assert_disabled(self, locator, timeout=None):
        """断言元素禁用"""
        await async_expect(_to_locator(locator)).to_be_disabled(timeout=timeout)
        logger.info(f"元素禁用: {locator}")

    @negates("be_editable")
    async def assert_editable(self, locator, timeout=None):
        """断言元素可编辑（readonly / disabled 时为 False）"""
        await async_expect(_to_locator(locator)).to_be_editable(timeout=timeout)
        logger.info(f"元素可编辑: {locator}")

    @negates("be_focused")
    async def assert_focused(self, locator, timeout=None):
        """断言元素已获得焦点"""
        await async_expect(_to_locator(locator)).to_be_focused(timeout=timeout)
        logger.info(f"元素获得焦点: {locator}")

    # ---- 属性 / 标识 ----
    @negates("have_attribute")
    async def assert_attribute(self, locator, name, value=None, timeout=None):
        """断言元素属性 name 等于 value；value 省略时只断言属性存在"""
        await async_expect(_to_locator(locator)).to_have_attribute(name, value, timeout=timeout)
        logger.info(f"元素属性 {name}={value}: {locator}")

    @negates("have_id")
    async def assert_id(self, locator, expected, timeout=None):
        """断言元素 id 等于 expected"""
        await async_expect(_to_locator(locator)).to_have_id(expected, timeout=timeout)
        logger.info(f"元素 id 等于 '{expected}': {locator}")

    @negates("have_class")
    async def assert_class(self, locator, expected, timeout=None):
        """断言元素 class 属性与 expected 完全一致（顺序无关）；只关心部分 class 用 assert_class_contains"""
        await async_expect(_to_locator(locator)).to_have_class(expected, timeout=timeout)
        logger.info(f"元素 class 完全匹配 '{expected}': {locator}")

    @negates("contain_class")
    async def assert_class_contains(self, locator, expected, timeout=None):
        """断言元素 class 包含 expected 里的全部类名（expected 可为空格分隔字符串或列表）"""
        await async_expect(_to_locator(locator)).to_contain_class(expected, timeout=timeout)
        logger.info(f"元素 class 包含 '{expected}': {locator}")

    # ---- 页面 ----
    @negates("have_url")
    async def assert_url(self, page, expected, timeout=None, ignore_case=None):
        """断言页面 URL（支持正则）；page 可直接传 PageExport"""
        await async_expect(_to_page(page)).to_have_url(
            expected, timeout=timeout, ignore_case=ignore_case
        )
        logger.info(f"页面 URL 匹配: {expected}")

    @negates("have_title")
    async def assert_title(self, page, expected, timeout=None):
        """断言页面标题（支持正则）；page 可直接传 PageExport"""
        await async_expect(_to_page(page)).to_have_title(expected, timeout=timeout)
        logger.info(f"页面标题匹配: {expected}")
