#!/usr/bin/env python3
"""登录用例 2（cases/login/test_login_2.py）

一个用例文件只放同 ID 的用例：CaseControl 要求方法名包含用例文件名，
所以第二条用例放在 test_login_2.py，而不是塞进 test_login_1.py。
"""
from cases.case_base import CaseBase
from pages import PageExport


class TestLogin2(CaseBase):
    """登录模块用例 2"""

    def test_login_2(self, page: PageExport):
        """勾选记住账号后登录"""
        page.login_page.login_remember("admin", "123456")
        page.assert_visible(page.login_page.login_btn)
