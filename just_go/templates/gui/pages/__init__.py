#!/usr/bin/env python3
# coding=utf-8
"""页面对象统一出口（pages/__init__.py）

新增页面对象后，在这里集中导出，用例统一从 pages 导入：
    from pages import ModulePage      # 直接导入页面对象类
    from pages import PageExport      # 或通过统一出口取用

与接口封装侧的 apis/__init__.py（ApiExport）结构对称。
"""
from .base_page import BasePage
from .module import ModulePage

__all__ = ["BasePage", "ModulePage", "PageExport"]


class PageExport:
    """页面对象统一出口：先传 page（框架 fixture），再取各页面对象"""

    def __init__(self, page):
        self.page = page
        # 新增页面对象后在这里挂载，例如：self.home_page = HomePage(page)
        self.module_page = ModulePage(page)
