"""用例机制：用例命名校验的 metaclass。

用法：
    from just_go.case import CaseControl

    class CaseBase(metaclass=CaseControl):
        ...
"""
from just_go._internal.controller import CaseControl

__all__ = ["CaseControl"]
