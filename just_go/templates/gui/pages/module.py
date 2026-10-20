#!/usr/bin/env python3
# coding=utf-8
"""页面对象（pages/<模块>.py）

职责：把被测页面的元素定位器 + 业务操作收拢成类，供用例调用。
继承 pages/base_page.py 的 BasePage（即框架 WebUI + 便捷方法），
通用操作直接用 Playwright 原生方法（self.page.fill/click/press 等）或框架能力，
**只写业务**。

写法参考项目 README「怎么开发 GUI 用例」。
"""
from .base_page import BasePage


class ModulePage(BasePage):
    """模块页面对象（示例，请按实际页面重命名/替换）"""

    # ① 元素定位器：集中维护，页面结构变了只改这里
    _search_input = 'input[placeholder*="搜索"]'

    # ② 业务操作：组合通用动作，只写业务步骤
    def search(self, keyword):
        self.page.fill(self._search_input, keyword)
        self.page.press(self._search_input, "Enter")

    # ③ 返回业务结果：供用例层断言
    def get_search_result(self):
        return self.get_text(".search-result")
