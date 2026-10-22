#!/usr/bin/env python3
# coding=utf-8
"""用例基类（cases/case_base.py）

所有用例类继承此类，公共逻辑（登录、数据准备等）写在这里。
metaclass=CaseControl 开启用例命名校验（方法名须包含用例文件名）。
"""
from just_go.core import CaseControl, mock


class CaseBase(metaclass=CaseControl):
    """用例基类：所有用例类继承此类"""

    mock = mock
