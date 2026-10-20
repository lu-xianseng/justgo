#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:50
# @Author   :luye

import functools
from typing import Any, Callable, TypeVar

try:
    import allure
    from playwright.sync_api import (
        APIResponse,
        APIResponseAssertions,
        Locator,
        LocatorAssertions,
        Page,
        PageAssertions,
        Response,
        expect,
        sync_playwright,
    )
except ImportError as e:
    from just_go.exceptions import SoftwareNotInstallError

    missing = "allure" if e.name == "allure" else "playwright"
    raise SoftwareNotInstallError(missing) from e
from just_go.logger import logger

F = TypeVar("F", bound=Callable[..., Any])

# 统一导出：框架向测试项目 re-export 的 playwright 常用名字（`from just_go import *`）
__all__ = [
    "WebUI",
    "Page",
    "Response",
    "expect",
    "Locator",
    "APIResponse",
    "PageAssertions",
    "LocatorAssertions",
    "APIResponseAssertions",
    "sync_playwright",
]


class WebUI:
    def __init__(self, page: Page, only_keep_one: bool = False):
        self.page = page
        pages = self.page.context.pages
        if only_keep_one:
            for p in pages:
                if id(p) != id(self.page):
                    p.close()

    @classmethod
    def intercept_response(cls, api) -> Callable[[F], Callable[..., Response]]:
        """
        __获取响应对象
        """

        def decorator(func) -> Callable[..., Response]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Response:
                """__"""

                def response_handler(response: Response):
                    """__"""
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
        """
        __创建一个新页面实例，默认创建最新页面实例，默认其它tab页面
        Args:
            page: 页面对象
            close_other_tabs: 关闭其它tab

        Returns: instance, page_obj

        """
        new_page = page if page else self.page.context.pages[-1]
        return self.__class__(new_page, only_keep_one=close_other_tabs), new_page

    def all_tabs(self):
        """
        __返回所有页面tab对象
        Returns: page_obj: list

        """
        return self.page.context.pages

    def sleep(self, _time):
        """__等待"""
        logger.info(f"等待{_time}秒")
        self.page.wait_for_timeout(int(_time) * 1000)

    # ------------------------------------------------------------------
    # 高频页面能力（页面对象基类 BasePage 继承本类，自动获得这些能力）
    # ------------------------------------------------------------------

    def scroll_to_bottom(self):
        """滚动到页面底部（无限滚动列表/长页面）"""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    def scroll_to(self, locator):
        """滚动使元素进入视口"""
        self.page.locator(locator).scroll_into_view_if_needed()

    def upload_file(self, locator, path):
        """上传文件（支持单文件 str 或多文件 list[str]）"""
        self.page.locator(locator).set_input_files(path)

    def screenshot(self, name="screenshot", full_page=False):
        """截图并附加到 allure 报告（关键步骤主动留证）

        失败自动截图由框架处理；本方法用于业务关键步骤留证。
        """
        png = self.page.screenshot(full_page=full_page)
        allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)

    def switch_to_frame(self, locator):
        """进入 iframe：返回 FrameLocator，直接调用其 fill/click 等

        用法：
            frame = webui.switch_to_frame("#main-iframe")
            frame.fill("#user", "admin")
        退出 iframe 用 exit_frame()（回到主文档操作）。
        """
        return self.page.frame_locator(locator)

    def exit_frame(self):
        """退出 iframe，回到主文档"""
        return self.page

    def wait_for_text(self, text, timeout=10_000):
        """等待文本出现（元素可见），超时抛 playwright TimeoutError"""
        self.page.get_by_text(text, exact=False).first.wait_for(
            state="visible", timeout=timeout
        )

    def get_attribute(self, locator, name):
        """获取元素属性值（如 href/value/class）"""
        return self.page.locator(locator).get_attribute(name)

    def execute_js(self, script, arg=None):
        """执行 JavaScript，返回结果"""
        return self.page.evaluate(script, arg)

    def mock_route(self, pattern, json=None, body=None, status=200, content_type="application/json"):
        """拦截并模拟接口响应（接口未就绪/联调时用）

        用法：
            webui.mock_route("**/api/login", json={"code": 0, "token": "mock-token"})
        持续生效，直到 unroute() 或页面关闭。
        """
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
        """拖拽：把 source 选择器元素拖到 target 选择器元素"""
        self.page.drag_and_drop(source, target)
