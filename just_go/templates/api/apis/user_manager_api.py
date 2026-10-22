#!/usr/bin/env python3
# coding=utf-8
"""用户管理接口封装（apis/user_manager_api.py）

写法：一个接口一个方法，继承 BaseApi 自动获得全部 HTTP 能力。
"""
from .base import BaseApi


class UserManagerApi(BaseApi):
    """用户管理接口封装"""

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


user_manager_api = UserManagerApi()
