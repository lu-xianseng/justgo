#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/27 14:28
# @Author   :luye
"""断言类：纯数据断言 + playwright UI 断言。

- AssertCommon：纯数据断言（同步异步通用，不依赖 playwright）
- SyncAssert：同步用例用，数据断言 + UI 断言
- AsyncAssert：异步用例用，数据断言 + UI 断言（UI 方法需 await）

UI 断言写法：正向断言调用 Playwright 的 to_xxx，配套的 assert_not_xxx 紧写在它下面、
调用 not_to_xxx——**必须是真实的方法定义**，不要改成运行时 setattr 动态生成：动态生成的
属性 IDE / mypy 看不见，用 page.assert_not_visible() 时没有补全、跳转与参数提示。

新增能力要在 SyncAssert / AsyncAssert 各加一对正向 + 反向断言——不要只补其中一边，
tests/test_assertion.py 会校验两边方法集合一致、反向方法齐全、正反签名一致。
"""
import re

from playwright.async_api import expect as async_expect
from playwright.sync_api import expect as sync_expect

from just_go._internal.element import AsyncElement, Element
from just_go._internal.logger import logger


def _to_locator(obj):
    """Element / AsyncElement 还原成原生 Locator，selector 字符串或 Page 原样返回

    FrameElement / AsyncFrameElement 的原生对象是 FrameLocator，Playwright 的 expect()
    不认（抛 "Unsupported type"），这里转成指向 iframe 元素的 Locator —— 对 iframe
    本身断言可见/挂载是常见需求，比让用户自己 .native 好用。
    """
    from just_go._internal.element import AsyncFrameElement, FrameElement

    if isinstance(obj, (FrameElement, AsyncFrameElement)):
        # FrameLocator.owner 是指向 iframe 元素的 Locator；个别版本/替身可能没有，
        # 拿不到时退回 FrameLocator 本身（至少报错信息不会从类型错误变成 AttributeError）
        return getattr(obj.native, "owner", None) or obj.native
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


class SyncAssert(AssertCommon):
    """同步断言：纯数据断言 + playwright UI 断言。配合 def test_xxx(page) 使用。

    每个 assert_xxx 都在下一行写着配套的 assert_not_xxx（显式方法，IDE 可补全/跳转），
    反向断言同样走 Playwright 的自动等待重试，不必自己取文本再比较。
    """

    # ---- 可见性 / 存在 ----
    def assert_visible(self, locator, timeout=None):
        """断言元素可见"""
        sync_expect(_to_locator(locator)).to_be_visible(timeout=timeout)
        logger.info(f"元素可见: {locator}")

    def assert_not_visible(self, locator, timeout=None):
        """断言元素不可见（存在但不可见，或不存在）；断言元素可从 DOM 上彻底消失用 assert_not_attached"""
        sync_expect(_to_locator(locator)).not_to_be_visible(timeout=timeout)
        logger.info(f"元素不可见: {locator}")

    def assert_hidden(self, locator, timeout=None):
        """断言元素隐藏（不存在或不可见）；只想断言「存在但不可见」用 assert_not_visible"""
        sync_expect(_to_locator(locator)).to_be_hidden(timeout=timeout)
        logger.info(f"元素隐藏: {locator}")

    def assert_not_hidden(self, locator, timeout=None):
        """断言元素未隐藏（存在且可见）"""
        sync_expect(_to_locator(locator)).not_to_be_hidden(timeout=timeout)
        logger.info(f"元素未隐藏: {locator}")

    def assert_attached(self, locator, timeout=None):
        """断言元素已挂载到 DOM（不要求可见）"""
        sync_expect(_to_locator(locator)).to_be_attached(timeout=timeout)
        logger.info(f"元素已挂载: {locator}")

    def assert_not_attached(self, locator, timeout=None):
        """断言元素未挂载到 DOM（从 DOM 上移除）"""
        sync_expect(_to_locator(locator)).not_to_be_attached(timeout=timeout)
        logger.info(f"元素未挂载: {locator}")

    def assert_empty(self, locator, timeout=None):
        """断言元素内没有子节点/文本（空列表、空表格）"""
        sync_expect(_to_locator(locator)).to_be_empty(timeout=timeout)
        logger.info(f"元素为空: {locator}")

    def assert_not_empty(self, locator, timeout=None):
        """断言元素内有子节点/文本（列表、表格非空）"""
        sync_expect(_to_locator(locator)).not_to_be_empty(timeout=timeout)
        logger.info(f"元素不为空: {locator}")

    def assert_count(self, locator, count, timeout=None):
        """断言匹配的元素数量等于 count"""
        sync_expect(_to_locator(locator)).to_have_count(count, timeout=timeout)
        logger.info(f"元素数量等于 {count}: {locator}")

    def assert_not_count(self, locator, count, timeout=None):
        """断言匹配的元素数量不等于 count"""
        sync_expect(_to_locator(locator)).not_to_have_count(count, timeout=timeout)
        logger.info(f"元素数量不等于 {count}: {locator}")

    # ---- 文本 / 值 ----
    def assert_text(self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None):
        """断言元素文本等于 expected（支持正则与列表，与 Playwright 一致）"""
        sync_expect(_to_locator(locator)).to_have_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本等于 '{expected}': {locator}")

    def assert_not_text(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本不等于 expected（支持正则与列表）"""
        sync_expect(_to_locator(locator)).not_to_have_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本不等于 '{expected}': {locator}")

    def assert_text_contains(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本包含 expected（expected 可为子串、正则或它们的列表）"""
        sync_expect(_to_locator(locator)).to_contain_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本包含 '{expected}': {locator}")

    def assert_not_text_contains(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本不包含 expected（expected 可为子串、正则或它们的列表）"""
        sync_expect(_to_locator(locator)).not_to_contain_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本不包含 '{expected}': {locator}")

    def assert_value(self, locator, expected, timeout=None):
        """断言输入框值等于 expected"""
        sync_expect(_to_locator(locator)).to_have_value(expected, timeout=timeout)
        logger.info(f"输入框值等于 '{expected}': {locator}")

    def assert_not_value(self, locator, expected, timeout=None):
        """断言输入框值不等于 expected"""
        sync_expect(_to_locator(locator)).not_to_have_value(expected, timeout=timeout)
        logger.info(f"输入框值不等于 '{expected}': {locator}")

    def assert_values(self, locator, expected, timeout=None):
        """断言多选控件（如 multiple select）的选中值等于 expected 列表"""
        sync_expect(_to_locator(locator)).to_have_values(expected, timeout=timeout)
        logger.info(f"多选值等于 {expected}: {locator}")

    def assert_not_values(self, locator, expected, timeout=None):
        """断言多选控件（如 multiple select）的选中值不等于 expected 列表"""
        sync_expect(_to_locator(locator)).not_to_have_values(expected, timeout=timeout)
        logger.info(f"多选值不等于 {expected}: {locator}")

    # ---- 状态 ----
    def assert_checked(self, locator, timeout=None):
        """断言复选框/单选框已选中"""
        sync_expect(_to_locator(locator)).to_be_checked(timeout=timeout)
        logger.info(f"元素已选中: {locator}")

    def assert_not_checked(self, locator, timeout=None):
        """断言复选框/单选框未选中"""
        sync_expect(_to_locator(locator)).not_to_be_checked(timeout=timeout)
        logger.info(f"元素未选中: {locator}")

    def assert_enabled(self, locator, timeout=None):
        """断言元素可用"""
        sync_expect(_to_locator(locator)).to_be_enabled(timeout=timeout)
        logger.info(f"元素可用: {locator}")

    def assert_not_enabled(self, locator, timeout=None):
        """断言元素不可用（disabled）"""
        sync_expect(_to_locator(locator)).not_to_be_enabled(timeout=timeout)
        logger.info(f"元素不可用: {locator}")

    def assert_disabled(self, locator, timeout=None):
        """断言元素禁用"""
        sync_expect(_to_locator(locator)).to_be_disabled(timeout=timeout)
        logger.info(f"元素禁用: {locator}")

    def assert_not_disabled(self, locator, timeout=None):
        """断言元素未禁用（可用）"""
        sync_expect(_to_locator(locator)).not_to_be_disabled(timeout=timeout)
        logger.info(f"元素未禁用: {locator}")

    def assert_editable(self, locator, timeout=None):
        """断言元素可编辑（readonly / disabled 时为 False）"""
        sync_expect(_to_locator(locator)).to_be_editable(timeout=timeout)
        logger.info(f"元素可编辑: {locator}")

    def assert_not_editable(self, locator, timeout=None):
        """断言元素不可编辑（readonly / disabled）"""
        sync_expect(_to_locator(locator)).not_to_be_editable(timeout=timeout)
        logger.info(f"元素不可编辑: {locator}")

    def assert_focused(self, locator, timeout=None):
        """断言元素已获得焦点"""
        sync_expect(_to_locator(locator)).to_be_focused(timeout=timeout)
        logger.info(f"元素获得焦点: {locator}")

    def assert_not_focused(self, locator, timeout=None):
        """断言元素未获得焦点"""
        sync_expect(_to_locator(locator)).not_to_be_focused(timeout=timeout)
        logger.info(f"元素未获得焦点: {locator}")

    # ---- 属性 / 标识 ----
    def assert_attribute(self, locator, name, value=None, timeout=None):
        """断言元素属性 name 等于 value；value 省略时只断言属性存在"""
        sync_expect(_to_locator(locator)).to_have_attribute(name, value, timeout=timeout)
        logger.info(f"元素属性 {name}={value}: {locator}")

    def assert_not_attribute(self, locator, name, value=None, timeout=None):
        """断言元素属性 name 不等于 value；value 省略时断言属性不存在"""
        sync_expect(_to_locator(locator)).not_to_have_attribute(name, value, timeout=timeout)
        logger.info(f"元素属性 {name} 不等于 {value}: {locator}")

    def assert_id(self, locator, expected, timeout=None):
        """断言元素 id 等于 expected"""
        sync_expect(_to_locator(locator)).to_have_id(expected, timeout=timeout)
        logger.info(f"元素 id 等于 '{expected}': {locator}")

    def assert_not_id(self, locator, expected, timeout=None):
        """断言元素 id 不等于 expected"""
        sync_expect(_to_locator(locator)).not_to_have_id(expected, timeout=timeout)
        logger.info(f"元素 id 不等于 '{expected}': {locator}")

    def assert_class(self, locator, expected, timeout=None):
        """断言元素 class 属性与 expected 完全一致（顺序无关）；只关心部分 class 用 assert_class_contains"""
        sync_expect(_to_locator(locator)).to_have_class(expected, timeout=timeout)
        logger.info(f"元素 class 完全匹配 '{expected}': {locator}")

    def assert_not_class(self, locator, expected, timeout=None):
        """断言元素 class 属性与 expected 不完全一致（顺序无关）"""
        sync_expect(_to_locator(locator)).not_to_have_class(expected, timeout=timeout)
        logger.info(f"元素 class 不匹配 '{expected}': {locator}")

    def assert_class_contains(self, locator, expected, timeout=None):
        """断言元素 class 包含 expected 里的全部类名（expected 可为空格分隔字符串或列表）"""
        sync_expect(_to_locator(locator)).to_contain_class(expected, timeout=timeout)
        logger.info(f"元素 class 包含 '{expected}': {locator}")

    def assert_not_class_contains(self, locator, expected, timeout=None):
        """断言元素 class 不包含 expected 里的全部类名"""
        sync_expect(_to_locator(locator)).not_to_contain_class(expected, timeout=timeout)
        logger.info(f"元素 class 不包含 '{expected}': {locator}")

    # ---- 页面 ----
    def assert_url(self, page, expected, timeout=None, ignore_case=None):
        """断言页面 URL（支持正则）；page 可直接传 PageExport"""
        sync_expect(_to_page(page)).to_have_url(expected, timeout=timeout, ignore_case=ignore_case)
        logger.info(f"页面 URL 匹配: {expected}")

    def assert_not_url(self, page, expected, timeout=None, ignore_case=None):
        """断言页面 URL 不匹配（支持正则）；page 可直接传 PageExport"""
        sync_expect(_to_page(page)).not_to_have_url(
            expected, timeout=timeout, ignore_case=ignore_case
        )
        logger.info(f"页面 URL 不匹配: {expected}")

    def assert_title(self, page, expected, timeout=None):
        """断言页面标题（支持正则）；page 可直接传 PageExport"""
        sync_expect(_to_page(page)).to_have_title(expected, timeout=timeout)
        logger.info(f"页面标题匹配: {expected}")

    def assert_not_title(self, page, expected, timeout=None):
        """断言页面标题不匹配（支持正则）；page 可直接传 PageExport"""
        sync_expect(_to_page(page)).not_to_have_title(expected, timeout=timeout)
        logger.info(f"页面标题不匹配: {expected}")


class AsyncAssert(AssertCommon):
    """异步断言：纯数据断言 + UI 断言（UI 方法需 await）。配合 async def test_xxx(page) 使用。

    方法集合与 SyncAssert 完全一致，反向断言同样写在正向断言下面。
    """

    # ---- 可见性 / 存在 ----
    async def assert_visible(self, locator, timeout=None):
        """断言元素可见"""
        await async_expect(_to_locator(locator)).to_be_visible(timeout=timeout)
        logger.info(f"元素可见: {locator}")

    async def assert_not_visible(self, locator, timeout=None):
        """断言元素不可见（存在但不可见，或不存在）；断言元素可从 DOM 上彻底消失用 assert_not_attached"""
        await async_expect(_to_locator(locator)).not_to_be_visible(timeout=timeout)
        logger.info(f"元素不可见: {locator}")

    async def assert_hidden(self, locator, timeout=None):
        """断言元素隐藏（不存在或不可见）；只想断言「存在但不可见」用 assert_not_visible"""
        await async_expect(_to_locator(locator)).to_be_hidden(timeout=timeout)
        logger.info(f"元素隐藏: {locator}")

    async def assert_not_hidden(self, locator, timeout=None):
        """断言元素未隐藏（存在且可见）"""
        await async_expect(_to_locator(locator)).not_to_be_hidden(timeout=timeout)
        logger.info(f"元素未隐藏: {locator}")

    async def assert_attached(self, locator, timeout=None):
        """断言元素已挂载到 DOM（不要求可见）"""
        await async_expect(_to_locator(locator)).to_be_attached(timeout=timeout)
        logger.info(f"元素已挂载: {locator}")

    async def assert_not_attached(self, locator, timeout=None):
        """断言元素未挂载到 DOM（从 DOM 上移除）"""
        await async_expect(_to_locator(locator)).not_to_be_attached(timeout=timeout)
        logger.info(f"元素未挂载: {locator}")

    async def assert_empty(self, locator, timeout=None):
        """断言元素内没有子节点/文本（空列表、空表格）"""
        await async_expect(_to_locator(locator)).to_be_empty(timeout=timeout)
        logger.info(f"元素为空: {locator}")

    async def assert_not_empty(self, locator, timeout=None):
        """断言元素内有子节点/文本（列表、表格非空）"""
        await async_expect(_to_locator(locator)).not_to_be_empty(timeout=timeout)
        logger.info(f"元素不为空: {locator}")

    async def assert_count(self, locator, count, timeout=None):
        """断言匹配的元素数量等于 count"""
        await async_expect(_to_locator(locator)).to_have_count(count, timeout=timeout)
        logger.info(f"元素数量等于 {count}: {locator}")

    async def assert_not_count(self, locator, count, timeout=None):
        """断言匹配的元素数量不等于 count"""
        await async_expect(_to_locator(locator)).not_to_have_count(count, timeout=timeout)
        logger.info(f"元素数量不等于 {count}: {locator}")

    # ---- 文本 / 值 ----
    async def assert_text(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本等于 expected（支持正则与列表，与 Playwright 一致）"""
        await async_expect(_to_locator(locator)).to_have_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本等于 '{expected}': {locator}")

    async def assert_not_text(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本不等于 expected（支持正则与列表）"""
        await async_expect(_to_locator(locator)).not_to_have_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本不等于 '{expected}': {locator}")

    async def assert_text_contains(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本包含 expected（expected 可为子串、正则或它们的列表）"""
        await async_expect(_to_locator(locator)).to_contain_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本包含 '{expected}': {locator}")

    async def assert_not_text_contains(
        self, locator, expected, timeout=None, ignore_case=None, use_inner_text=None
    ):
        """断言元素文本不包含 expected（expected 可为子串、正则或它们的列表）"""
        await async_expect(_to_locator(locator)).not_to_contain_text(
            expected, timeout=timeout, ignore_case=ignore_case, use_inner_text=use_inner_text
        )
        logger.info(f"元素文本不包含 '{expected}': {locator}")

    async def assert_value(self, locator, expected, timeout=None):
        """断言输入框值等于 expected"""
        await async_expect(_to_locator(locator)).to_have_value(expected, timeout=timeout)
        logger.info(f"输入框值等于 '{expected}': {locator}")

    async def assert_not_value(self, locator, expected, timeout=None):
        """断言输入框值不等于 expected"""
        await async_expect(_to_locator(locator)).not_to_have_value(expected, timeout=timeout)
        logger.info(f"输入框值不等于 '{expected}': {locator}")

    async def assert_values(self, locator, expected, timeout=None):
        """断言多选控件（如 multiple select）的选中值等于 expected 列表"""
        await async_expect(_to_locator(locator)).to_have_values(expected, timeout=timeout)
        logger.info(f"多选值等于 {expected}: {locator}")

    async def assert_not_values(self, locator, expected, timeout=None):
        """断言多选控件（如 multiple select）的选中值不等于 expected 列表"""
        await async_expect(_to_locator(locator)).not_to_have_values(expected, timeout=timeout)
        logger.info(f"多选值不等于 {expected}: {locator}")

    # ---- 状态 ----
    async def assert_checked(self, locator, timeout=None):
        """断言复选框/单选框已选中"""
        await async_expect(_to_locator(locator)).to_be_checked(timeout=timeout)
        logger.info(f"元素已选中: {locator}")

    async def assert_not_checked(self, locator, timeout=None):
        """断言复选框/单选框未选中"""
        await async_expect(_to_locator(locator)).not_to_be_checked(timeout=timeout)
        logger.info(f"元素未选中: {locator}")

    async def assert_enabled(self, locator, timeout=None):
        """断言元素可用"""
        await async_expect(_to_locator(locator)).to_be_enabled(timeout=timeout)
        logger.info(f"元素可用: {locator}")

    async def assert_not_enabled(self, locator, timeout=None):
        """断言元素不可用（disabled）"""
        await async_expect(_to_locator(locator)).not_to_be_enabled(timeout=timeout)
        logger.info(f"元素不可用: {locator}")

    async def assert_disabled(self, locator, timeout=None):
        """断言元素禁用"""
        await async_expect(_to_locator(locator)).to_be_disabled(timeout=timeout)
        logger.info(f"元素禁用: {locator}")

    async def assert_not_disabled(self, locator, timeout=None):
        """断言元素未禁用（可用）"""
        await async_expect(_to_locator(locator)).not_to_be_disabled(timeout=timeout)
        logger.info(f"元素未禁用: {locator}")

    async def assert_editable(self, locator, timeout=None):
        """断言元素可编辑（readonly / disabled 时为 False）"""
        await async_expect(_to_locator(locator)).to_be_editable(timeout=timeout)
        logger.info(f"元素可编辑: {locator}")

    async def assert_not_editable(self, locator, timeout=None):
        """断言元素不可编辑（readonly / disabled）"""
        await async_expect(_to_locator(locator)).not_to_be_editable(timeout=timeout)
        logger.info(f"元素不可编辑: {locator}")

    async def assert_focused(self, locator, timeout=None):
        """断言元素已获得焦点"""
        await async_expect(_to_locator(locator)).to_be_focused(timeout=timeout)
        logger.info(f"元素获得焦点: {locator}")

    async def assert_not_focused(self, locator, timeout=None):
        """断言元素未获得焦点"""
        await async_expect(_to_locator(locator)).not_to_be_focused(timeout=timeout)
        logger.info(f"元素未获得焦点: {locator}")

    # ---- 属性 / 标识 ----
    async def assert_attribute(self, locator, name, value=None, timeout=None):
        """断言元素属性 name 等于 value；value 省略时只断言属性存在"""
        await async_expect(_to_locator(locator)).to_have_attribute(name, value, timeout=timeout)
        logger.info(f"元素属性 {name}={value}: {locator}")

    async def assert_not_attribute(self, locator, name, value=None, timeout=None):
        """断言元素属性 name 不等于 value；value 省略时断言属性不存在"""
        await async_expect(_to_locator(locator)).not_to_have_attribute(
            name, value, timeout=timeout
        )
        logger.info(f"元素属性 {name} 不等于 {value}: {locator}")

    async def assert_id(self, locator, expected, timeout=None):
        """断言元素 id 等于 expected"""
        await async_expect(_to_locator(locator)).to_have_id(expected, timeout=timeout)
        logger.info(f"元素 id 等于 '{expected}': {locator}")

    async def assert_not_id(self, locator, expected, timeout=None):
        """断言元素 id 不等于 expected"""
        await async_expect(_to_locator(locator)).not_to_have_id(expected, timeout=timeout)
        logger.info(f"元素 id 不等于 '{expected}': {locator}")

    async def assert_class(self, locator, expected, timeout=None):
        """断言元素 class 属性与 expected 完全一致（顺序无关）；只关心部分 class 用 assert_class_contains"""
        await async_expect(_to_locator(locator)).to_have_class(expected, timeout=timeout)
        logger.info(f"元素 class 完全匹配 '{expected}': {locator}")

    async def assert_not_class(self, locator, expected, timeout=None):
        """断言元素 class 属性与 expected 不完全一致（顺序无关）"""
        await async_expect(_to_locator(locator)).not_to_have_class(expected, timeout=timeout)
        logger.info(f"元素 class 不匹配 '{expected}': {locator}")

    async def assert_class_contains(self, locator, expected, timeout=None):
        """断言元素 class 包含 expected 里的全部类名（expected 可为空格分隔字符串或列表）"""
        await async_expect(_to_locator(locator)).to_contain_class(expected, timeout=timeout)
        logger.info(f"元素 class 包含 '{expected}': {locator}")

    async def assert_not_class_contains(self, locator, expected, timeout=None):
        """断言元素 class 不包含 expected 里的全部类名"""
        await async_expect(_to_locator(locator)).not_to_contain_class(expected, timeout=timeout)
        logger.info(f"元素 class 不包含 '{expected}': {locator}")

    # ---- 页面 ----
    async def assert_url(self, page, expected, timeout=None, ignore_case=None):
        """断言页面 URL（支持正则）；page 可直接传 PageExport"""
        await async_expect(_to_page(page)).to_have_url(
            expected, timeout=timeout, ignore_case=ignore_case
        )
        logger.info(f"页面 URL 匹配: {expected}")

    async def assert_not_url(self, page, expected, timeout=None, ignore_case=None):
        """断言页面 URL 不匹配（支持正则）；page 可直接传 PageExport"""
        await async_expect(_to_page(page)).not_to_have_url(
            expected, timeout=timeout, ignore_case=ignore_case
        )
        logger.info(f"页面 URL 不匹配: {expected}")

    async def assert_title(self, page, expected, timeout=None):
        """断言页面标题（支持正则）；page 可直接传 PageExport"""
        await async_expect(_to_page(page)).to_have_title(expected, timeout=timeout)
        logger.info(f"页面标题匹配: {expected}")

    async def assert_not_title(self, page, expected, timeout=None):
        """断言页面标题不匹配（支持正则）；page 可直接传 PageExport"""
        await async_expect(_to_page(page)).not_to_have_title(expected, timeout=timeout)
        logger.info(f"页面标题不匹配: {expected}")
