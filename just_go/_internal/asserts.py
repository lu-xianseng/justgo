#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/27 14:28
# @Author   :luye
"""断言类：纯数据断言 + playwright UI 断言。

- AssertCommon：纯数据断言（同步异步通用，不依赖 playwright）
- SyncAssert：同步用例用，数据断言 + UI 断言
- AsyncAssert：异步用例用，数据断言 + UI 断言（UI 方法需 await）
"""
import re

from playwright.async_api import expect as async_expect
from playwright.sync_api import expect as sync_expect

from just_go._internal.logger import logger


class AssertCommon:
    """纯数据断言（同步/异步通用，不依赖 playwright）。"""

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


class SyncAssert(AssertCommon):
    """同步断言：纯数据断言 + playwright UI 断言。配合 def test_xxx(page) 使用。"""

    def assert_visible(self, locator, timeout=None):
        """断言元素可见"""
        sync_expect(locator).to_be_visible(timeout=timeout)
        logger.info(f"元素可见: {locator}")

    def assert_hidden(self, locator, timeout=None):
        """断言元素隐藏"""
        sync_expect(locator).to_be_hidden(timeout=timeout)
        logger.info(f"元素隐藏: {locator}")

    def assert_text(self, locator, expected, timeout=None):
        """断言元素文本等于 expected"""
        sync_expect(locator).to_have_text(expected, timeout=timeout)
        logger.info(f"元素文本等于 '{expected}': {locator}")

    def assert_text_contains(self, locator, substring, timeout=None):
        """断言元素文本包含 substring"""
        sync_expect(locator).to_contain_text(substring, timeout=timeout)
        logger.info(f"元素文本包含 '{substring}': {locator}")

    def assert_value(self, locator, expected, timeout=None):
        """断言输入框值等于 expected"""
        sync_expect(locator).to_have_value(expected, timeout=timeout)
        logger.info(f"输入框值等于 '{expected}': {locator}")

    def assert_checked(self, locator, timeout=None):
        """断言复选框/单选框已选中"""
        sync_expect(locator).to_be_checked(timeout=timeout)
        logger.info(f"元素已选中: {locator}")

    def assert_not_checked(self, locator, timeout=None):
        """断言复选框/单选框未选中"""
        sync_expect(locator).not_to_be_checked(timeout=timeout)
        logger.info(f"元素未选中: {locator}")

    def assert_count(self, locator, count, timeout=None):
        """断言匹配的元素数量等于 count"""
        sync_expect(locator).to_have_count(count, timeout=timeout)
        logger.info(f"元素数量等于 {count}: {locator}")

    def assert_enabled(self, locator, timeout=None):
        """断言元素可用"""
        sync_expect(locator).to_be_enabled(timeout=timeout)
        logger.info(f"元素可用: {locator}")

    def assert_disabled(self, locator, timeout=None):
        """断言元素禁用"""
        sync_expect(locator).to_be_disabled(timeout=timeout)
        logger.info(f"元素禁用: {locator}")

    def assert_url(self, page, expected, timeout=None):
        """断言页面 URL"""
        sync_expect(page).to_have_url(expected, timeout=timeout)
        logger.info(f"页面 URL 匹配: {expected}")

    def assert_title(self, page, expected, timeout=None):
        """断言页面标题"""
        sync_expect(page).to_have_title(expected, timeout=timeout)
        logger.info(f"页面标题匹配: {expected}")


class AsyncAssert(AssertCommon):
    """异步断言：纯数据断言 + playwright UI 断言（UI 方法需 await）。配合 async def test_xxx(page) 使用。"""

    async def assert_visible(self, locator, timeout=None):
        """断言元素可见"""
        await async_expect(locator).to_be_visible(timeout=timeout)
        logger.info(f"元素可见: {locator}")

    async def assert_hidden(self, locator, timeout=None):
        """断言元素隐藏"""
        await async_expect(locator).to_be_hidden(timeout=timeout)
        logger.info(f"元素隐藏: {locator}")

    async def assert_text(self, locator, expected, timeout=None):
        """断言元素文本等于 expected"""
        await async_expect(locator).to_have_text(expected, timeout=timeout)
        logger.info(f"元素文本等于 '{expected}': {locator}")

    async def assert_text_contains(self, locator, substring, timeout=None):
        """断言元素文本包含 substring"""
        await async_expect(locator).to_contain_text(substring, timeout=timeout)
        logger.info(f"元素文本包含 '{substring}': {locator}")

    async def assert_value(self, locator, expected, timeout=None):
        """断言输入框值等于 expected"""
        await async_expect(locator).to_have_value(expected, timeout=timeout)
        logger.info(f"输入框值等于 '{expected}': {locator}")

    async def assert_checked(self, locator, timeout=None):
        """断言复选框/单选框已选中"""
        await async_expect(locator).to_be_checked(timeout=timeout)
        logger.info(f"元素已选中: {locator}")

    async def assert_not_checked(self, locator, timeout=None):
        """断言复选框/单选框未选中"""
        await async_expect(locator).not_to_be_checked(timeout=timeout)
        logger.info(f"元素未选中: {locator}")

    async def assert_count(self, locator, count, timeout=None):
        """断言匹配的元素数量等于 count"""
        await async_expect(locator).to_have_count(count, timeout=timeout)
        logger.info(f"元素数量等于 {count}: {locator}")

    async def assert_enabled(self, locator, timeout=None):
        """断言元素可用"""
        await async_expect(locator).to_be_enabled(timeout=timeout)
        logger.info(f"元素可用: {locator}")

    async def assert_disabled(self, locator, timeout=None):
        """断言元素禁用"""
        await async_expect(locator).to_be_disabled(timeout=timeout)
        logger.info(f"元素禁用: {locator}")

    async def assert_url(self, page, expected, timeout=None):
        """断言页面 URL"""
        await async_expect(page).to_have_url(expected, timeout=timeout)
        logger.info(f"页面 URL 匹配: {expected}")

    async def assert_title(self, page, expected, timeout=None):
        """断言页面标题"""
        await async_expect(page).to_have_title(expected, timeout=timeout)
        logger.info(f"页面标题匹配: {expected}")
