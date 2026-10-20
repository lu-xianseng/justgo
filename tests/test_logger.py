# -*- coding: utf-8 -*-
"""@log 类装饰器行为测试"""
from unittest import mock

from just_go import log


class TestLogDecorator:
    def test_self_method_logged_with_param_replacement(self):
        @log
        class Home:
            def search(self, keyword):
                """搜索关键词：{{keyword}}"""
                return keyword

        home = Home()
        with mock.patch("just_go.logger.logger.info") as info:
            assert home.search("手机") == "手机"
        info.assert_called_once_with("搜索关键词：手机")

    def test_missing_docstring_raises_typeerror(self):
        with mock.patch("just_go.logger.logger.info"):
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
        with mock.patch("just_go.logger.logger.info") as info:
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
        with mock.patch("just_go.logger.logger.info") as info:
            assert home.action() == 2
        info.assert_called_once_with("子类动作")
