#!/usr/bin/env python3
# coding=utf-8
"""接口封装统一出口（apis/__init__.py）

新增接口封装后，在这里集中导出，用例统一从 apis 导入：
    from apis import module_api       # 直接导入接口实例
    from apis import ApiExport        # 或通过统一出口取用

与页面对象侧的 pages/__init__.py（PageExport）结构对称。
"""
from .module import module_api

__all__ = ["module_api", "ApiExport"]


class ApiExport:
    """接口封装统一出口"""

    def __init__(self):
        # 新增模块接口后在这里挂载，例如：self.user_api = user_api
        self.module_api = module_api
