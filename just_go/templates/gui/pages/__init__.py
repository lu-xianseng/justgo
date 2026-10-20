#!/usr/bin/env python3
# coding=utf-8
"""页面对象统一出口（pages/__init__.py）

新增页面对象后，在这里集中导出，用例统一从 pages 导入：
    from pages import 你的页面类

好处：页面文件路径/类名调整时只改这里，用例层不动。
"""

# 在这里导出你的页面对象，例如：
#   from pages.base_page import BasePage
#   from pages.module_page.page import ModulePage
#   __all__ = ["BasePage", "ModulePage"]
