#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/3/17 13:21
# @Author   :luye
from just_go._internal.errors import CaseError


class CaseControl(type):
    def __init__(cls, name, bases, dic):
        super().__init__(name, bases, dic)
        cls.__check_case(dic)

    @staticmethod
    def __check_case(dic):
        module_path = dic["__module__"]
        # 基类本身不校验方法名（open_page 等通用方法不需要包含模块名）；
        # 兼容模板文件名的两种写法：case_base / base_case
        if "case_base" in module_path or "base_case" in module_path:
            return
        # 用例文件（模块）与用例方法名校验：取模块名最后一段（即文件名，
        # 兼容 --import-mode=importlib 下模块名为完整路径的情况）匹配方法名。
        # 只校验函数（方法），类内数据属性（tag、data、settings = Settings 等）不受约束；
        # 注意不能用 callable() 判断：类、模块、可调用对象都满足 callable，会被误判为用例方法。
        import inspect

        module_name = module_path.split(".")[-1]
        for k, v in dic.items():
            if not (
                inspect.isfunction(v)
                and not (
                    k.startswith("__")
                    or k.startswith("setup")
                    or k.startswith("teardown")
                )
            ):
                continue
            if module_name not in k:
                raise CaseError(
                    f"用例文件：{dic['__module__']}，与用例方法：{k}，不一致"
                )
