#!/usr/bin/env python3
"""页面对象统一出口（pages/__init__.py）

PageExport = 通用页面能力（BasePage）+ 所有子页面 + 一组可自定义的断言（Asserts）。
conftest.py 把 page fixture 包装成此类型，用例里 def test_xxx(page: PageExport) 直接调：
    page.login_page.account.fill("admin")       # 元素动作
    page.login_page.login("admin", "123456")    # 业务动作组合
    page.assert_visible(page.login_page.login_btn)

断言不挂在 PageExport 的继承链上，而是放在 pages/asserts/asserts.py 的 Asserts 里：
自己往里加 assert_xxx 方法即可，page.assert_xxx 会由下面的 __getattr__ 自动转发。

新增页面对象的步骤：
1. 在 pages/ 下新建 xxx_page/ 目录
2. xxx_page_ele.py 只写元素（element 声明，不需要继承基类）
3. xxx_page.py 继承元素类写业务动作，__init__ 里 self.page = page
4. 在下面的 PageExport.__init__ 里注册 self.xxx_page = XxxPage(self.page)
"""
from just_go.log import log

from pages.asserts.asserts import Asserts
from pages.base_page import BasePage
from pages.login_page.login_page import LoginPage


@log
class PageExport(BasePage):
    """页面对象 + 断言统一出口：conftest.py 自动把 page fixture 包装成此类型"""

    def __init__(self, page):
        super().__init__(page)
        # 断言独立成类：内置断言 + 项目自定义断言都在 Asserts 里
        self.asserts = Asserts()
        self.login_page = LoginPage(self.page)

    def __getattr__(self, name):
        """把 assert_xxx 转发给 self.asserts，用例保持 page.assert_visible(...) 写法"""
        asserts = self.__dict__.get("asserts")
        if asserts is not None and name.startswith("assert_"):
            return getattr(asserts, name)
        raise AttributeError(f"{type(self).__name__} 没有属性 {name!r}")
