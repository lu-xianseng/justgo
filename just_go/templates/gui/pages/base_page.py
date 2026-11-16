#!/usr/bin/env python3
"""页面对象基类（pages/base_page.py）

职责：把**业务无关**的通用能力收拢到这里，让具体页面对象只写业务。

本模块只给 pages/__init__.py 的 PageExport 使用，元素类（xxx_page_ele.py）不需要继承它：
- 同步：PageExport 继承 BasePage（继承 SyncWebUI）
- 异步：PageExport 继承 AsyncBasePage（继承 AsyncWebUI）

元素声明从 just_go.web import：
    from just_go.web import element
    from just_go.web import async_element

locator 入参统一：下面这些方法既接受选择器字符串，也接受 element() 声明的 Element 对象：
    page.wait_visible(page.login_page.account)   # 传 Element
    page.wait_visible("[name='username']")       # 传字符串
归一化由 SyncWebUI._as_locator 完成，子类不用自己再写兼容层。

框架层提供的通用能力（同步/异步各一套）：
- 滚动：scroll_to_bottom / scroll_to
- 上传：upload_file；拖拽：drag_and_drop
- 截图：screenshot（自动附加 allure）
- iframe：switch_to_frame / exit_frame
- 文本等待 / 属性 / JS：wait_for_text / get_attribute / execute_js
- 接口 mock：mock_route / unroute
- 响应拦截：intercept_response；多标签页：all_tabs / create_new_instance
- 接口请求：self.api（get/post/put/patch/delete，复用当前页面登录态，返回 ApiResponse）

    r = self.api.get("/admin-api/autolib/batch-task/page", params={"pageNo": 1})
    r.assert_status(200)
    rows = r.json()["data"]["list"]

鉴权头自动沿用：框架监听页面同源请求，把 Authorization / X-Token 同步进 self.api.headers，
token 型鉴权的项目（cookie 为空）不必在 conftest 里手工抓 token 再注入；
显式 set_headers / set_token 之后以调用方设置为准。

接口造数据后页面不会自动刷新，需要重新 goto / reload 再断言。
"""
from just_go.web import AsyncWebUI, SyncWebUI, async_element, element

__all__ = ["AsyncBasePage", "BasePage", "async_element", "element"]


class BasePage(SyncWebUI):
    """同步用例使用的页面对象基类。page：playwright.sync_api.Page"""

    def __init__(self, page):
        super().__init__(page)

    def wait_visible(self, locator, timeout=10_000):
        """等待元素可见，默认 10 秒。locator 可传 Element"""
        self._as_locator(locator).wait_for(state="visible", timeout=timeout)

    def get_text(self, locator, strip=True):
        """获取元素文本，默认去除首尾空白。locator 可传 Element"""
        text = self._as_locator(locator).inner_text()
        return text.strip() if strip else text

    def is_visible(self, locator):
        """判断元素是否可见（不抛异常）。locator 可传 Element"""
        return self._as_locator(locator).is_visible()

    def switch_to_latest_tab(self):
        """切到最新打开的标签页；page.api 只在 context 真的变了时重建，已抓到的鉴权头不丢"""
        self.page = self.page.context.pages[-1]
        self.ensure_api()

    def close_current_tab(self):
        """关闭当前标签页并切到最新剩余页；只剩一个标签时抛错，避免拿到已关闭的页"""
        pages = self.page.context.pages
        if len(pages) <= 1:
            raise RuntimeError("当前只有一个标签页，没有可切换的目标，已取消关闭")
        self.page.close()
        self.page = self.page.context.pages[-1]
        self.ensure_api()


class AsyncBasePage(AsyncWebUI):
    """异步用例使用的页面对象基类。page：playwright.async_api.Page，所有方法需 await"""

    def __init__(self, page):
        super().__init__(page)

    async def wait_visible(self, locator, timeout=10_000):
        """等待元素可见，默认 10 秒。locator 可传 AsyncElement"""
        await self._as_locator(locator).wait_for(state="visible", timeout=timeout)

    async def get_text(self, locator, strip=True):
        """获取元素文本，默认去除首尾空白。locator 可传 AsyncElement"""
        text = await self._as_locator(locator).inner_text()
        return text.strip() if strip else text

    async def is_visible(self, locator):
        """判断元素是否可见（不抛异常）。locator 可传 AsyncElement"""
        return await self._as_locator(locator).is_visible()

    def switch_to_latest_tab(self):
        """切到最新打开的标签页；page.api 只在 context 真的变了时重建"""
        self.page = self.page.context.pages[-1]
        self.ensure_api()

    async def close_current_tab(self):
        """关闭当前标签页并切到最新剩余页；只剩一个标签时抛错，避免拿到已关闭的页"""
        pages = self.page.context.pages
        if len(pages) <= 1:
            raise RuntimeError("当前只有一个标签页，没有可切换的目标，已取消关闭")
        await self.page.close()
        self.page = self.page.context.pages[-1]
        self.ensure_api()
