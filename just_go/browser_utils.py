#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:50
# @Author   :luye

import os
import sys
import functools
from typing import Optional, Callable, Any, List, TypeVar

try:
    from playwright.sync_api import sync_playwright, Response
    from playwright.sync_api import Page
    from playwright.sync_api import LocatorAssertions
    from playwright.sync_api import expect as _expect
    from playwright.sync_api import Locator
    from playwright.sync_api import APIResponse
    from playwright.sync_api import Response
    from playwright.sync_api import PageAssertions
    from playwright.sync_api import APIResponseAssertions
except ImportError:
    print("Please install playwright")
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from just_go.logger import logger

F = TypeVar("F", bound=Callable[..., Any])


class WebUI:
    __response: Response = None

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
                        cls.__response = response

                obj = args[0]
                obj.page.on("response", response_handler)
                try:
                    func(*args, **kwargs)
                    obj.page.wait_for_load_state("domcontentloaded")
                finally:
                    obj.page.remove_listener("response", response_handler)
                    result = cls.__response
                    cls.__response = None
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
