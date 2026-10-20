#!/usr/bin/env python3
# coding=utf-8
"""页面对象基类（pages/base_page.py）

职责：把**业务无关**的通用能力收拢到这里，让具体页面对象只写业务。

本类继承框架的 WebUI（just_go.browser_utils），自动获得框架层通用能力：
- 滚动：scroll_to_bottom / scroll_to
- 上传：upload_file（文件上传）；拖拽：drag_and_drop
- 截图：screenshot（关键步骤主动截图，附加 allure）
- iframe：switch_to_frame / exit_frame
- 文本等待 / 属性 / JS：wait_for_text / get_attribute / execute_js
- 接口 mock：mock_route / unroute
- 响应拦截：intercept_response；多标签页：all_tabs / create_new_instance

其余高频操作直接用 Playwright Page 原生方法（同名同参数，页面对象内
self.page.fill(...)/self.page.click(...)/self.page.press(...)/self.page.select_option(...) 等），
不再重复封装。

本类只补充 Playwright 原生没有的便捷方法：
- wait_visible / get_text / is_visible（等待可见、取文本、判断可见）
- switch_to_latest_tab / close_current_tab（多标签页管理）

同步用例传入 playwright.sync_api 的 Page，方法直接调用；
异步用例传入 playwright.async_api 的 Page，把要 await 的方法改成
`async def` + `await`（playwright async 方法均为协程）。
"""
from just_go import WebUI


class BasePage(WebUI):
    def __init__(self, page):
        """page：playwright Page（sync_api 或 async_api，按用例写法传入）"""
        super().__init__(page)

    def wait_visible(self, locator, timeout=10_000):
        """等待元素可见，默认 10 秒"""
        self.page.locator(locator).wait_for(state="visible", timeout=timeout)

    def get_text(self, locator, strip=True):
        """获取元素文本，默认去除首尾空白"""
        text = self.page.locator(locator).inner_text()
        return text.strip() if strip else text

    def is_visible(self, locator):
        """判断元素是否可见（不抛异常）"""
        return self.page.locator(locator).is_visible()

    def switch_to_latest_tab(self):
        """切到最新打开的标签页（点击后弹出新 tab 时用）"""
        self.page = self.page.context.pages[-1]

    def close_current_tab(self):
        """关闭当前标签页并切到最新剩余页"""
        self.page.close()
        self.page = self.page.context.pages[-1]
