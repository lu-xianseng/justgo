#!/usr/bin/env python3
# coding=utf-8
"""用例基类（cases/base_case.py）

职责：把用例的公共样板下沉到这里（实例化页面对象、打开页面），
后续可继续加公共登录、数据准备等，用例只写业务步骤 + 断言。
"""
import os

from just_go.controller import CaseControl


class BaseCase(metaclass=CaseControl):
    """用例基类：page_cls 指向被测页面对象类（不用页面对象则留 None）

    metaclass=CaseControl 开启用例命名校验（用例方法名须包含用例文件名），
    不需要该校验时直接用 class BaseCase: 即可。
    """

    page_cls = None

    def open_page(self, page, path=""):
        """打开被测页面并返回页面对象实例

        地址 = conftest 注入的 JUSTGO_TEST_BASE_URL + path；
        page_cls 未设置时仅执行跳转，返回 None。
        """
        base = os.environ.get("JUSTGO_TEST_BASE_URL", "").rstrip("/")
        page.goto(f"{base}/{path.lstrip('/')}")
        return self.page_cls(page) if self.page_cls else None
