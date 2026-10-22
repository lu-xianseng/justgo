#!/usr/bin/env python3
# coding=utf-8
"""页面对象统一出口（pages/__init__.py）

PageExport 多继承所有页面对象 + 断言类，用例里 def test_xxx(page) 直接调：
    page.login_input_account("admin")
    page.assert_visible("#submit")
    page.assert_equal("ok", resp["status"])

新增页面对象后：
1. 在 pages/ 下新建 xxx_page.py，写类继承 BasePage
2. 在这里 import 并加到 PageExport 的继承列表
"""
import pytest
from just_go.core import log
from just_go.asserts import SyncAssert, AssertCommon
from .base_page import BasePage
from .login_page import LoginPage


@log
class PageExport(LoginPage, SyncAssert, AssertCommon):
    """页面对象 + 断言统一出口：conftest.py 自动把 page fixture 包装成此类型"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
