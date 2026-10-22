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
