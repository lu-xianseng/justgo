#!/usr/bin/env python3
# coding=utf-8
"""页面对象基类（pages/base_page.py）

职责：把**业务无关**的通用操作收拢到这里，让具体页面对象只写业务。
本文件提供**可直接使用**的默认实现（基于 playwright 自动等待的 locator）：

- fill / click / wait_visible / get_text / is_visible
- select_option / press / 多标签页切换

同步用例传入 playwright.sync_api 的 Page，方法直接调用；
异步用例传入 playwright.async_api 的 Page，把要 await 的方法改成
`async def` + `await`（playwright async 方法均为协程）。
"""


class BasePage:
    def __init__(self, page):
        """page：playwright Page（sync_api 或 async_api，按用例写法传入）"""
        self.page = page

    def fill(self, locator, text):
        """输入框填入文本（locator 为字符串选择器，下同）"""
        self.page.locator(locator).fill(text)

    def click(self, locator):
        """点击元素（自动等待可点击）"""
        self.page.locator(locator).click()

    def wait_visible(self, locator, timeout=10_000):
        """等待元素可见，默认 10 秒"""
        self.page.locator(locator).wait_for(state="visible", timeout=timeout)

    def get_text(self, locator, strip=True):
        """获取元素文本，默认去除首尾空白"""
        text = self.page.locator(locator).inner_text()
        return text.strip() if strip else text

    def is_visible(self, locator):
        """判断元素是否可见（不抛异常）"""
        return self.page.locator(locator).is_visible()

    def select_option(self, locator, value):
        """下拉框按值选择"""
        self.page.locator(locator).select_option(value)

    def press(self, locator, key):
        """对元素按键，如 Enter / Tab"""
        self.page.locator(locator).press(key)

    def switch_to_latest_tab(self):
        """切到最新打开的标签页（点击后弹出新 tab 时用）"""
        self.page = self.page.context.pages[-1]

    def close_current_tab(self):
        """关闭当前标签页并切到最新剩余页"""
        self.page.close()
        self.page = self.page.context.pages[-1]
