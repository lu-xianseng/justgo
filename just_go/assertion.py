#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/27 14:28
# @Author   :luye
import re
from just_go.logger import logger


class AssertCommon:
    def assert_equal(self, expect, actual):
        """断言预期和实际相等"""
        if expect != actual:
            raise AssertionError(f"{expect} 不等于 {actual}")
        logger.info(f"{expect} 等于 {actual}")

    def assert_not_equal(self, expect, actual):
        """断言预期和实际不相等"""
        if expect == actual:
            raise AssertionError(f"{expect} 等于 {actual}")
        logger.info(f"{expect} 不等于 {actual}")

    def assert_in(self, expect, actual):
        """断言预期在实际中"""
        if expect not in actual:
            raise AssertionError(f"{expect} 不在 {actual}")
        logger.info(f"{expect} 在 {actual}")

    def assert_not_in(self, expect, actual):
        """断言预期在实际中不存在"""
        if expect in actual:
            raise AssertionError(f"{expect} 在 {actual}")
        logger.info(f"{expect} 不在 {actual}")

    def assert_true(self, actual):
        """断言实际为真"""
        if not actual:
            raise AssertionError(f"{actual} 不为真")
        logger.info(f"{actual} 为真")

    def assert_false(self, actual):
        """断言实际为假"""
        if actual:
            raise AssertionError(f"{actual} 不为假")
        logger.info(f"{actual} 为假")

    def assert_re_check_equal(self, pattern, actual_text):
        """正则匹配相等"""
        if not re.search(pattern, actual_text):
            raise AssertionError(
                f"正则匹配失败，pattern: {pattern}, actual_text: {actual_text}"
            )
        logger.info(f"正则匹配成功，pattern: {pattern}, actual_text: {actual_text}")

    def assert_re_check_not_equal(self, pattern, actual_text):
        """断言实际文本不匹配正则（反向断言）"""
        if re.search(pattern, actual_text):
            raise AssertionError(
                f"正则不应匹配但实际匹配，pattern: {pattern}, actual_text: {actual_text}"
            )
        logger.info(f"正则未匹配（符合预期），pattern: {pattern}")
