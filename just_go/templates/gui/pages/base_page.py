#!/usr/bin/env python3
# coding=utf-8
"""页面对象基类（pages/base_page.py）

职责：把**业务无关**的通用能力收拢到这里，让具体页面对象只写业务。

根据用例写法选择继承的基类：
- 同步用例（def test_xxx(page)）：继承 BasePage（继承 SyncWebUI）
- 异步用例（async def test_xxx(page)）：继承 AsyncBasePage（继承 AsyncWebUI）

框架层提供的通用能力（同步/异步各一套）：
- 滚动：scroll_to_bottom / scroll_to
- 上传：upload_file；拖拽：drag_and_drop
- 截图：screenshot（自动附加 allure）
- iframe：switch_to_frame / exit_frame
- 文本等待 / 属性 / JS：wait_for_text / get_attribute / execute_js
- 接口 mock：mock_route / unroute
- 响应拦截：intercept_response；多标签页：all_tabs / create_new_instance
"""
from just_go.web import AsyncWebUI, SyncWebUI


class BasePage(SyncWebUI):
    """同步用例使用的页面对象基类。page：playwright.sync_api.Page"""

    def __init__(self, page):
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
        """切到最新打开的标签页"""
        self.page = self.page.context.pages[-1]

    def close_current_tab(self):
        """关闭当前标签页并切到最新剩余页"""
        self.page.close()
        self.page = self.page.context.pages[-1]


class AsyncBasePage(AsyncWebUI):
    """异步用例使用的页面对象基类。page：playwright.async_api.Page，所有方法需 await"""

    def __init__(self, page):
        super().__init__(page)

    async def wait_visible(self, locator, timeout=10_000):
        """等待元素可见，默认 10 秒"""
        await self.page.locator(locator).wait_for(state="visible", timeout=timeout)

    async def get_text(self, locator, strip=True):
        """获取元素文本，默认去除首尾空白"""
        text = await self.page.locator(locator).inner_text()
        return text.strip() if strip else text

    async def is_visible(self, locator):
        """判断元素是否可见（不抛异常）"""
        return await self.page.locator(locator).is_visible()

    def switch_to_latest_tab(self):
        """切到最新打开的标签页（属性访问，同步）"""
        self.page = self.page.context.pages[-1]

    async def close_current_tab(self):
        """关闭当前标签页并切到最新剩余页"""
        await self.page.close()
        self.page = self.page.context.pages[-1]
