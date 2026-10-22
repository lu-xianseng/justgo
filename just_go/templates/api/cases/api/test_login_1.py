#!/usr/bin/env python3
# coding=utf-8
"""API 登录用例（cases/api/test_login_1.py）

约定：
- 文件名：test_<模块>_<用例ID>.py
- 用例函数名：test_<模块>_<用例ID>，与 tag/api.csv 的用例ID 对应
- API 用例直接调接口封装，不需要 page fixture
"""
from apis import user_manager_api


def test_login_1():
    """正确账号密码登录"""
    data = user_manager_api.login("admin", "123456")
    assert data["code"] == 0
