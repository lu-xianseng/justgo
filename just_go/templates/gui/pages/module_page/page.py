#!/usr/bin/env python3
# coding=utf-8
"""页面对象（pages/<页面>/page.py）

职责：一个页面一个类，继承你的 BasePage，**只写业务**：
- 元素定位器集中写在类顶部
- 业务操作组合成方法（打开、搜索、下单……）
- 返回业务结果给用例断言

写完后在 pages/__init__.py 统一导出。写法参考项目 README「三步走」。
"""

# 在这里写你的页面对象，例如：
#   from pages.base_page import BasePage
#
#   class HomePage(BasePage):
#       _search_input = 'input[placeholder*="搜索"]'
#       def goto(self, path=""):
#           ...
#       def search(self, keyword):
#           ...
#       def get_search_result(self):
#           ...
