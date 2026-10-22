#!/usr/bin/env python3
# coding=utf-8
"""接口封装统一出口（apis/__init__.py）

新增接口模块后：
1. 在 apis/ 下新建 xxx_api.py，写类继承 BaseApi
2. 在这里 import 并挂载实例
"""
from just_go.core import log
from .user_manager_api import user_manager_api


@log
class ApiExport:
    """接口封装统一出口"""

    def __init__(self):
        self.user_manager_api = user_manager_api
