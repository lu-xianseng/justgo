#!/usr/bin/env python3
"""登录用例（cases/login/test_login_1.py）

约定：
- 文件名：test_<模块>_<用例ID>.py
- 用例函数名：test_<模块>_<用例ID>，与 tag/login.csv 的用例ID 对应
- page fixture 已包装成 PageExport，page.login_page.xxx 访问元素
"""
from cases.case_base import CaseBase
from pages import PageExport


class TestLogin(CaseBase):
    """登录模块用例"""

    def test_login_1(self, page: PageExport):
        """输入正确账号密码，登录系统"""
        page.login_page.account.fill("admin")
        page.login_page.password.fill("123456")
        page.login_page.login_btn.click()
        page.assert_visible(page.login_page.login_btn)

    def test_login_2(self, page: PageExport):
        """勾选记住账号后登录"""
        page.login_page.login_remember("admin", "123456")
        page.assert_visible(page.login_page.login_btn)
