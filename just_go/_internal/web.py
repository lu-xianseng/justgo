#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:50
# @Author   :luye
"""Web UI 页面对象基类：同步 / 异步两套。

- SyncWebUI：配合 def test_xxx(page) 同步用例
- AsyncWebUI：配合 async def test_xxx(page) 异步用例，所有方法需 await
"""
import functools
from typing import Any, Callable, TypeVar

try:
    import allure
    from playwright.async_api import Page as AsyncPage
    from playwright.async_api import Response as AsyncResponse
    from playwright.sync_api import Page, Response
except ImportError as e:
    from just_go._internal.errors import SoftwareNotInstallError

    missing = "allure" if e.name == "allure" else "playwright"
    raise SoftwareNotInstallError(missing) from e
from just_go._internal.logger import logger

F = TypeVar("F", bound=Callable[..., Any])

__all__ = ["SyncWebUI", "AsyncWebUI"]


# ======================================================================
# 同步版（对应 playwright.sync_api）
# ======================================================================
class SyncWebUI:
    """同步页面对象基类，配合 def test_xxx(page) 使用。"""

    def __init__(self, page: Page, only_keep_one: bool = False):
        self.page = page
        pages = self.page.context.pages
        if only_keep_one:
            for p in pages:
                if id(p) != id(self.page):
                    p.close()

    @classmethod
    def intercept_response(cls, api) -> Callable[[F], Callable[..., Response]]:
        """装饰器：拦截匹配 api 的响应，返回 Response 对象。"""

        def decorator(func) -> Callable[..., Response]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Response:
                def response_handler(response: Response):
                    if api in response.url:
                        obj._justgo_response = response

                obj = args[0]
                obj._justgo_response = None
                obj.page.on("response", response_handler)
                try:
                    func(*args, **kwargs)
                    obj.page.wait_for_load_state("domcontentloaded")
                finally:
                    obj.page.remove_listener("response", response_handler)
                    result = obj._justgo_response
                    obj._justgo_response = None
                return result

            return wrapper

        return decorator

    def create_new_instance(self, page=None, close_other_tabs=True):
        """创建新页面实例（通常用于新弹出的 tab）。Returns: (instance, page_obj)"""
        new_page = page if page else self.page.context.pages[-1]
        return self.__class__(new_page, only_keep_one=close_other_tabs), new_page

    def all_tabs(self):
        """返回所有页面 tab 对象列表"""
        return self.page.context.pages

    def sleep(self, _time):
        """等待 N 秒"""
        logger.info(f"等待{_time}秒")
        self.page.wait_for_timeout(int(_time) * 1000)

    def scroll_to_bottom(self):
        """滚动到页面底部"""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    def scroll_to(self, locator):
        """滚动使元素进入视口"""
        self.page.locator(locator).scroll_into_view_if_needed()

    def upload_file(self, locator, path):
        """上传文件（单文件 str 或多文件 list[str]）"""
        self.page.locator(locator).set_input_files(path)

    def screenshot(self, name="screenshot", full_page=False):
        """截图并附加到 allure 报告"""
        png = self.page.screenshot(full_page=full_page)
        allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)

    def switch_to_frame(self, locator):
        """进入 iframe，返回 FrameLocator"""
        return self.page.frame_locator(locator)

    def exit_frame(self):
        """退出 iframe，回到主文档"""
        return self.page

    def wait_for_text(self, text, timeout=10_000):
        """等待文本出现（元素可见）"""
        self.page.get_by_text(text, exact=False).first.wait_for(
            state="visible", timeout=timeout
        )

    def get_attribute(self, locator, name):
        """获取元素属性值"""
        return self.page.locator(locator).get_attribute(name)

    def execute_js(self, script, arg=None):
        """执行 JavaScript，返回结果"""
        return self.page.evaluate(script, arg)

    def mock_route(self, pattern, json=None, body=None, status=200, content_type="application/json"):
        """拦截并模拟接口响应"""
        def handler(route):
            if json is not None:
                route.fulfill(status=status, json=json, content_type=content_type)
            else:
                route.fulfill(status=status, body=body or "", content_type=content_type)

        self.page.route(pattern, handler)

    def unroute(self, pattern):
        """移除 mock_route 设置的接口拦截"""
        self.page.unroute(pattern)

    def drag_and_drop(self, source, target):
        """拖拽：source 元素拖到 target 元素"""
        self.page.drag_and_drop(source, target)


# ======================================================================
# 异步版（对应 playwright.async_api）
# ======================================================================
class AsyncWebUI:
    """异步页面对象基类，配合 async def test_xxx(page) 使用。所有方法需 await。"""

    def __init__(self, page: AsyncPage):
        """构造函数只保存 page 引用（__init__ 不能是 async）。
        若需关闭多余 tab，请在构造后调用 await close_other_tabs()。"""
        self.page = page

    async def close_other_tabs(self):
        """关闭除当前页外的其他标签页"""
        for p in self.page.context.pages:
            if id(p) != id(self.page):
                await p.close()

    @classmethod
    def intercept_response(cls, api):
        """装饰器：拦截匹配 api 的响应（异步版）。"""

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                def response_handler(response: AsyncResponse):
                    if api in response.url:
                        obj._justgo_response = response

                obj = args[0]
                obj._justgo_response = None
                self_page = obj.page
                self_page.on("response", response_handler)
                try:
                    await func(*args, **kwargs)
                    await self_page.wait_for_load_state("domcontentloaded")
                finally:
                    self_page.remove_listener("response", response_handler)
                    result = obj._justgo_response
                    obj._justgo_response = None
                return result

            return wrapper

        return decorator

    async def create_new_instance(self, page=None, close_other_tabs=True):
        """创建新页面实例。Returns: (AsyncWebUI 子类实例, AsyncPage)"""
        new_page = page if page else self.page.context.pages[-1]
        instance = self.__class__(new_page)
        if close_other_tabs:
            await instance.close_other_tabs()
        return instance, new_page

    def all_tabs(self):
        """返回所有页面 tab 对象列表（属性访问，同步）"""
        return self.page.context.pages

    async def sleep(self, _time):
        """等待 N 秒"""
        logger.info(f"等待{_time}秒")
        await self.page.wait_for_timeout(int(_time) * 1000)

    async def scroll_to_bottom(self):
        """滚动到页面底部"""
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    async def scroll_to(self, locator):
        """滚动使元素进入视口"""
        await self.page.locator(locator).scroll_into_view_if_needed()

    async def upload_file(self, locator, path):
        """上传文件"""
        await self.page.locator(locator).set_input_files(path)

    async def screenshot(self, name="screenshot", full_page=False):
        """截图并附加到 allure 报告"""
        png = await self.page.screenshot(full_page=full_page)
        allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)

    def switch_to_frame(self, locator):
        """进入 iframe，返回 AsyncFrameLocator，后续操作需 await"""
        return self.page.frame_locator(locator)

    def exit_frame(self):
        """退出 iframe，回到主文档"""
        return self.page

    async def wait_for_text(self, text, timeout=10_000):
        """等待文本出现（元素可见）"""
        await self.page.get_by_text(text, exact=False).first.wait_for(
            state="visible", timeout=timeout
        )

    async def get_attribute(self, locator, name):
        """获取元素属性值"""
        return await self.page.locator(locator).get_attribute(name)

    async def execute_js(self, script, arg=None):
        """执行 JavaScript，返回结果"""
        return await self.page.evaluate(script, arg)

    async def mock_route(self, pattern, json=None, body=None, status=200, content_type="application/json"):
        """拦截并模拟接口响应"""
        async def handler(route):
            if json is not None:
                await route.fulfill(status=status, json=json, content_type=content_type)
            else:
                await route.fulfill(status=status, body=body or "", content_type=content_type)

        await self.page.route(pattern, handler)

    async def unroute(self, pattern):
        """移除 mock_route 设置的接口拦截"""
        await self.page.unroute(pattern)

    async def drag_and_drop(self, source, target):
        """拖拽：source 元素拖到 target 元素"""
        await self.page.drag_and_drop(source, target)
