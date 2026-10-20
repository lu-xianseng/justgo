#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/3/17 13:21
# @Author   :luye
from just_go.exceptions import CaseError


class CaseControl(type):
    def __init__(cls, name, bases, dic):
        super().__init__(name, bases, dic)
        cls.__check_case(dic)

    @staticmethod
    def __check_case(dic):
        if "case_base" not in dic["__module__"]:
            # 用例文件（模块）与用例方法名校验：取模块名最后一段（即文件名，
            # 兼容 --import-mode=importlib 下模块名为完整路径的情况）匹配方法名。
            # 只校验可调用对象（方法），类内数据属性（如 tag、data 等变量）不受约束。
            module_name = dic["__module__"].split(".")[-1]
            for k, v in dic.items():
                if not (
                    callable(v)
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
