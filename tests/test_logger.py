# -*- coding: utf-8 -*-
"""@log 类装饰器行为测试"""
from unittest import mock

from just_go.log import log


class TestLogDecorator:
    def test_self_method_logged_with_param_replacement(self):
        @log
        class Home:
            def search(self, keyword):
                """搜索关键词：{{keyword}}"""
                return keyword

        home = Home()
        with mock.patch("just_go._internal.logger.logger.info") as info:
            assert home.search("手机") == "手机"
        info.assert_called_once_with("搜索关键词：手机")

    def test_missing_docstring_raises_typeerror(self):
        with mock.patch("just_go._internal.logger.logger.info"):
            try:

                @log
                class Bad:
                    def f(self):
                        return 1

            except TypeError as e:
                assert "缺少文档字符串" in str(e)
            else:
                raise AssertionError("缺少 docstring 未抛 TypeError")

    def test_parent_method_wrapped_too(self):
        class BasePage:
            def click_btn(self):
                """点击按钮"""

        @log
        class Home(BasePage):
            def open(self):
                """打开页面"""

        home = Home()
        with mock.patch("just_go._internal.logger.logger.info") as info:
            home.click_btn()
            home.open()
        assert info.call_count == 2

    def test_child_override_wins(self):
        class BasePage:
            def action(self):
                """父类动作"""

        @log
        class Home(BasePage):
            def action(self):
                """子类动作"""
                return 2

        home = Home()
        with mock.patch("just_go._internal.logger.logger.info") as info:
            assert home.action() == 2
        info.assert_called_once_with("子类动作")

    def test_staticmethod_keeps_binding(self):
        """静态方法被包装后仍是 staticmethod：通过实例调用不会把 self 传进去"""

        @log
        class Util:
            @staticmethod
            def add(a, b):
                """相加 {{a}}+{{b}}"""
                return a + b

        with mock.patch("just_go._internal.logger.logger.info") as info:
            assert Util.add(1, 2) == 3
            assert Util().add(1, 2) == 3
        assert info.call_count == 2

    def test_classmethod_keeps_binding(self):
        """类方法被包装后仍是 classmethod：第一个参数是 cls"""

        @log
        class Factory:
            @classmethod
            def make(cls, name):
                """创建 {{name}}"""
                return (cls.__name__, name)

        with mock.patch("just_go._internal.logger.logger.info"):
            assert Factory.make("x") == ("Factory", "x")
            assert Factory().make("y") == ("Factory", "y")

    def test_sensitive_param_masked_in_docstring(self):
        """docstring 里的 {{password}} 不能把真实密码写进日志"""

        @log
        class Login:
            def sign_in(self, password):
                """登录密码：{{password}}"""
                return password

        with mock.patch("just_go._internal.logger.logger.info") as info:
            Login().sign_in("secret123")
        info.assert_called_once_with("登录密码：***")

    def test_property_not_wrapped(self):
        """property 不是普通方法调用，装饰器不应替换它"""

        @log
        class Home:
            def open(self):
                """打开页面"""

            @property
            def title(self):
                return "首页"

        assert Home().title == "首页"
