#!/usr/bin/env python3
# coding=utf-8
"""页面对象基类（pages/base_page.py）

职责：把**业务无关**的通用操作收拢到这里，让具体页面对象只写业务。
适合下沉的通用能力（按你的项目需要取舍）：
- 输入 / 点击 / 等待可见 / 取文本 / 判断可见
- 系统高频按钮（确认 / 取消 / 保存 / 查询……）
- 表格操作、切换标签页等

同步用例传入 playwright.sync_api 的 Page；异步用例传入 playwright.async_api
的 Page（其中方法需 await）。写法参考项目 README「三步走」。
"""

# 在这里定义你的页面基类，例如：
#   from playwright.sync_api import Page
#
#   class BasePage:
#       def __init__(self, page: Page):
#           self.page = page
#       def fill(self, locator, text):
#           self.page.fill(locator, text)
#       def click(self, locator):
#           self.page.click(locator)
#       ...
