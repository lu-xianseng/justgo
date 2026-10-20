#!/usr/bin/env python3
# coding=utf-8
"""API 用例文件（cases/api/test_<模块>_<用例ID>.py）

约定：
- 文件名：test_<模块>_<用例ID>.py，例如 test_login_1001.py（本文件为占位骨架，请重命名）
- 用例函数名：test_<模块>_<用例ID>，用例ID 与 tag/<模块>/<模块名>.csv 里的 用例ID 对应
- API 用例直接调接口封装方法，不需要 page fixture

开发步骤（详见项目 README）：
1. 接口封装写在 apis/<模块>/api.py，并在 apis/__init__.py 导出；
2. 用例 import 接口方法，调接口 + 断言；
3. 需要 tag 管理时，在 tag/<模块>/<模块名>.csv 登记该用例。
"""

# 在这里写你的用例，例如：
#   from apis.module import api as module_api
#
#   def test_login_1001():
#       data = module_api.login("admin", "123456")
#       assert data["code"] == 0
