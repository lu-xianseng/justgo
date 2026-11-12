#!/usr/bin/env python3
"""登录页面元素（pages/login_page/login_page_ele.py）

只写元素，不写业务动作。元素声明要点：
1. selector 用 Playwright 定位表达式
2. 第二个参数是日志里的中文名，不传就用属性名
3. 密码/验证码这类值加 sensitive=True，日志里显示 ***（属性名含 password 也会自动脱敏）

元素类不需要继承任何基类：element 描述符只要求页面实例上有 page 属性，
由 login_page.py 的 __init__ 绑定。

用例访问方式：page.login_page.account.fill("admin")
"""
from just_go.web import element


class LoginPageEle:
    """登录页面"""

    account = element("[name='username']", "账号输入框")
    password = element("[name='password']", "密码输入框", sensitive=True)
    remember_account = element(":text-is('记住账号')", "记住账号复选框")
    login_btn = element("button:has-text('登录')", "登录按钮")
