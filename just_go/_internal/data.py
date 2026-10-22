#!/usr/bin/env python3
# coding=utf-8
# @Time     :2026/10/20
# @Author   :luye
"""测试数据加载工具：把用例数据从代码抽离到 JSON/CSV 文件，供 pytest 参数化使用。

用法（数据驱动用例）：
    import pytest
    from just_go._internal.data import load_json_cases

    @pytest.mark.parametrize("case", load_json_cases("login_cases.json"))
    def test_login(case):
        data = login(case["username"], case["password"])
        assert data["code"] == 0

数据文件相对路径基于测试项目根（ROOTDIR）解析，也支持绝对路径。
"""
import csv
import json
import os
from typing import Any, Dict, List

from just_go._internal.settings import ROOTDIR

__all__ = ["load_json_cases", "load_csv_cases"]


def _resolve(path: str) -> str:
    """相对路径基于测试项目根解析，绝对路径直接用"""
    return path if os.path.isabs(path) else os.path.join(ROOTDIR, path)


def load_json_cases(path: str) -> List[Dict[str, Any]]:
    """读取 JSON 数组测试数据（每项一组用例参数）"""
    file_path = _resolve(path)
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"JSON 测试数据必须是数组（顶层为 [ ... ]）: {file_path}")
    return data


def load_csv_cases(path: str) -> List[Dict[str, str]]:
    """读取 CSV 测试数据（首行为表头），返回 dict 列表（值均为字符串）"""
    file_path = _resolve(path)
    with open(file_path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))
