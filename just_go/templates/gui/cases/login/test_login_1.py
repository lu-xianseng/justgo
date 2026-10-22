#!/usr/bin/env python3
# coding=utf-8
"""登录用例（cases/login/test_login_1.py）

约定：
- 文件名：test_<模块>_<用例ID>.py
- 用例函数名：test_<模块>_<用例ID>，与 tag/login.csv 的用例ID 对应
- page fixture 已包装成 PageExport，直接调 page.xxx() 即可
"""
from cases.case_base import CaseBase


class TestLogin(CaseBase):
    """登录模块用例"""

    def test_login_1(self, page):
        """输入正确账号密码，登录系统"""
        page.input_account("admin")
        page.input_password("password")
        page.submit()
        page.assert_visible(".welcome")
