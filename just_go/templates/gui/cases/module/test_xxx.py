#!/usr/bin/env python3
# coding=utf-8
"""用例文件（cases/<模块>/test_<模块>_<用例ID>.py）

约定：
- 文件名：test_<模块>_<用例ID>.py，例如 test_module_1001.py（本文件为占位骨架，请重命名）
- 用例函数名：test_<模块>_<用例ID>，用例ID 与 tag/<模块>/<模块名>.csv 里的 用例ID 对应
- 通过框架的 page fixture 拿页面；同步用例直接调用，异步用例 async def + await

开发步骤（详见项目 README）：
1. 页面对象写在 pages/<模块>.py（继承 pages/base_page.py 的 BasePage），并在 pages/__init__.py 导出；
2. 用例继承你的用例基类，只写业务步骤 + 断言；
3. 需要 tag 管理时，在 tag/<模块>/<模块名>.csv 登记该用例。
"""

# 在这里写你的用例，例如：
#   import allure
#   from pages import ModulePage
#   from cases.base_case import BaseCase
#
#   @allure.feature("模块")
#   class TestModule(BaseCase):
#       page_cls = ModulePage
#       def test_module_1001(self, page):
#           ...
