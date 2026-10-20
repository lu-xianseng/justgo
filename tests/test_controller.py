# -*- coding: utf-8 -*-
"""CaseControl 元类：用例文件与用例方法名一致性校验"""
import pytest

from just_go.controller import CaseControl
from just_go.exceptions import CaseError


def _make_case(module_name="test_login", **attrs):
    defaults = {"__module__": module_name}
    defaults.update(attrs)
    return CaseControl("MyCase", (object,), defaults)


def test_matching_method_name_passes():
    # 模块名 test_login，方法 test_login_1001 含模块名 -> 通过
    _make_case(test_login_1001=lambda self: None)


def test_data_attribute_not_checked():
    # 类内数据属性（非方法，如 tag 变量）不应触发命名校验
    _make_case(
        test_login_1001=lambda self: None,
        TAG="L1",
        params=[1, 2],
    )


def test_mismatched_method_name_raises():
    with pytest.raises(CaseError, match="不一致"):
        _make_case(test_other=lambda self: None)
