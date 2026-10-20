#!/usr/bin/env python3
# coding=utf-8
"""接口封装（apis/<模块>.py）

职责：把被测系统的接口按模块封装成方法，供用例调用。
继承 apis/base.py 的 BaseApi（即框架 Request），通用请求能力直接用，**只写业务**：
一个接口一个方法：请求地址 + 参数 + 返回业务结果给用例断言。

写法参考项目 README「API 用例怎么开发」。
"""
from .base import BaseApi


class ModuleApi(BaseApi):
    """模块接口封装（示例：用户模块，请按实际模块重命名/替换）"""

    def login(self, username, password):
        """登录：POST /api/login"""
        resp = self.post(
            self._url("/api/login"),
            json={"username": username, "password": password},
        )
        return resp.json()

    def get_user_info(self, user_id):
        """获取用户信息：GET /api/user/{id}"""
        resp = self.get(self._url(f"/api/user/{user_id}"))
        return resp.json()


module_api = ModuleApi()
