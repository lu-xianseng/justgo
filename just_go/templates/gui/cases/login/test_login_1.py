#!/usr/bin/env python3
"""登录用例（cases/login/test_login_1.py）

约定：
- 文件名：test_<模块>_<用例ID>.py
- 用例函数名：test_<模块>_<用例ID>，与 tag/login.csv 的用例ID 对应
  （CaseControl 要求方法名包含用例文件名，一个文件只放同 ID 的用例；
   新用例请复制成本目录下的 test_login_2.py 等新文件）
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
