#!/usr/bin/env python3
# coding=utf-8
"""登录页面对象（pages/login_page.py）

写法：
1. 元素定位器集中维护（_xxx），页面结构变了只改这里
2. 业务操作组合通用动作，只写业务步骤
3. 方法 docstring 会被 @log 装饰器记为日志，{{参数}} 自动替换实参
"""
from .base_page import BasePage


class LoginPage(BasePage):
    """登录页面对象"""

    # 元素定位器
    _account_input = "#username"
    _password_input = "#password"
    _submit_btn = "#submit"

    def input_account(self, account):
        """输入账号 {{account}}"""
        self.page.fill(self._account_input, account)

    def input_password(self, password):
        """输入密码 {{password}}"""
        self.page.fill(self._password_input, password)

    def submit(self):
        """点击登录按钮"""
        self.page.click(self._submit_btn)
