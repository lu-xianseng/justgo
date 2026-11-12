#!/usr/bin/env python3
"""登录页面对象（pages/login_page/login_page.py）

继承元素类，只写业务动作组合。__init__ 只有一件事：把 page 交给元素描述符，
不需要继承 BasePage。方法 docstring 会被 @log 记为业务级日志，元素动作再由
Element 记元素级日志，两层互补：
    INFO | - 登录：输入 admin 后提交
    INFO | - [登录页面对象] 账号输入框(account) 输入 "admin"
"""
from just_go.log import log

from .login_page_ele import LoginPageEle


@log
class LoginPage(LoginPageEle):
    """登录页面对象"""

    def __init__(self, page):
        self.page = page

    def login(self, account, password):
        """登录：输入 {{account}} 后提交（密码不写进日志，避免明文泄露）"""
        self.account.fill(account)
        self.password.fill(password)
        self.login_btn.click()

    def login_remember(self, account, password):
        """勾选记住账号后登录：{{account}}"""
        self.remember_account.check()
        self.login(account, password)
