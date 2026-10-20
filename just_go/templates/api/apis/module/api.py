#!/usr/bin/env python3
# coding=utf-8
"""接口封装（apis/<模块>/api.py）

职责：把被测系统的接口按模块封装成方法，供用例调用。
一个接口一个方法：请求地址 + 参数 + 返回业务结果给用例断言。
接口基址用 conftest 注入的 JUSTGO_TEST_BASE_URL，未配时为空。

写法参考项目 README「API 用例怎么开发」。
"""

# 在这里封装你的接口，例如：
#   import os
#   import requests  # 需要先安装：pip install requests
#
#   BASE = os.environ.get("JUSTGO_TEST_BASE_URL", "")
#
#   def login(username, password):
#       resp = requests.post(f"{BASE}/api/login", json={"username": username, "password": password})
#       return resp.json()
