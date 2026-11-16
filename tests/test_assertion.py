# -*- coding: utf-8 -*-
"""AssertCommon 断言单元测试"""
import pytest

from just_go._internal.asserts import AssertCommon


class TestAssertCommon:
    def setup_method(self):
        self.assertor = AssertCommon()

    def test_equal_ok(self):
        self.assertor.assert_equal(1, 1)

    def test_equal_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_equal(1, 2)

    def test_not_equal_ok(self):
        self.assertor.assert_not_equal(1, 2)

    def test_not_equal_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_not_equal(1, 1)

    def test_in_ok(self):
        self.assertor.assert_in("abc", "xxabcxx")

    def test_in_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_in("zzz", "abc")

    def test_not_in_ok(self):
        self.assertor.assert_not_in("zzz", "abc")

    def test_true_ok(self):
        self.assertor.assert_true(1 == 1)

    def test_false_ok(self):
        self.assertor.assert_false(1 == 2)

    def test_re_check_equal_ok(self):
        self.assertor.assert_re_check_equal(r"\d{4}", "订单号 1234")

    def test_re_check_equal_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_re_check_equal(r"\d{4}", "无数字")

    def test_re_check_not_equal_ok(self):
        self.assertor.assert_re_check_not_equal(r"\d{4}", "无数字")

    def test_re_check_not_equal_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_re_check_not_equal(r"\d{4}", "订单号 1234")


class TestLocatorConversion:
    """断言可直接传 element() / async_element() 声明的元素"""

    @staticmethod
    def _owner():
        class FakePage:
            @staticmethod
            def locator(selector):
                return f"native:{selector}"

        class Owner:
            page = FakePage()

        return Owner()

    def test_to_locator_unwraps_async_element(self):
        """异步用例用 async_element 声明元素后，await page.assert_visible(el) 不能报类型错误"""
        from just_go._internal.asserts import _to_locator
        from just_go._internal.element import AsyncElement

        element = AsyncElement(self._owner(), selector="#a", desc="按钮")
        assert _to_locator(element) == "native:#a"

    def test_to_locator_unwraps_sync_element(self):
        from just_go._internal.asserts import _to_locator
        from just_go._internal.element import Element

        element = Element(self._owner(), selector="#b", desc="按钮")
        assert _to_locator(element) == "native:#b"

    def test_to_page_unwraps_page_export(self):
        """expect() 只认原生 Page，传 PageExport 会被判为 Unsupported type"""
        from just_go._internal.asserts import _to_page
        from just_go._internal.web import SyncWebUI

        class FakeContext:
            pages = []
            request = object()

            def on(self, event, handler):
                pass

        class FakePage:
            context = FakeContext()

            def wait_for_timeout(self, ms):
                pass

        class PageExport(SyncWebUI):
            def __init__(self, page):
                super().__init__(page)

        raw = FakePage()
        assert _to_page(PageExport(raw)) is raw
        assert _to_page(raw) is raw
