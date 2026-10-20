#!/usr/bin/env python3
# coding=utf-8
"""用例基类（cases/base_case.py）

职责：把用例的公共样板代码收拢到这里，让具体用例只写业务步骤和断言。
适合下沉的公共逻辑（按你的项目需要取舍）：
- 实例化被测页面对象并打开页面（如 open_page 方法）
- 统一登录 / 公共数据准备
- 公共断言辅助

写法参考项目 README「三步走」。在这里定义你自己的用例基类，
具体用例类继承它并指定被测页面对象（如 page_cls 类属性）。
"""

# 在这里定义你的用例基类，例如：
#   from just_go.controller import CaseControl
#
#   class BaseCase(metaclass=CaseControl):
#       page_cls = None
#       def open_page(self, page, path=""):
#           ...
# 说明：metaclass=CaseControl 可开启用例命名校验（用例方法名须包含用例文件名），
#      不需要该校验时直接用 class BaseCase: 即可。
