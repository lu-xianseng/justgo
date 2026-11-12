#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/28 17:02
# @Author   :luye
import contextvars
import inspect
import os
import re
import time
from functools import wraps

import allure
from loguru import logger as llog

from just_go._internal.settings import LOG_PATH

# 当前用例标识（如 "L1-正确账号登录"）。由 pytest 插件在每条用例开始/结束时设置，
# 日志 sink 的 format 通过 {extra[case]} 把它带进每一行，便于从日志区分所属用例。
_case_label: contextvars.ContextVar = contextvars.ContextVar(
    "justgo_case", default=""
)

LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[case]}- {message}"


def set_case_label(label: str) -> None:
    """设置当前用例标识；空串表示清除（此时日志与未启用标识时完全一致）"""
    _case_label.set(label or "")


def _patch_case(record) -> None:
    """给每条日志记录注入 case 字段：有用例时形如 "[L1-正确账号登录] "，无则空串"""
    label = _case_label.get()
    record["extra"]["case"] = f"[{label}] " if label else ""


class CustomLogger:
    def __init__(self, log_path=LOG_PATH):
        log_name = f"{time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())}.log"
        os.makedirs(log_path, exist_ok=True)
        llog.remove()
        llog.configure(patcher=_patch_case)
        self.logs = []
        self.add_console_sink()
        self.add_file_sink(os.path.join(log_path, log_name))
        # 收集 sink 只在此添加一次，避免 get_logger() 重复调用导致日志重复收集
        llog.add(
            self.collect_logs,
            format=LOG_FORMAT,
        )

    def __call__(self, msg):
        self.logs.append(msg)

    @staticmethod
    def add_console_sink():
        """
        添加控制台sink。
        """
        llog.add(
            sink=lambda msg: print(msg, end="", flush=True),
            format=LOG_FORMAT,
            level="DEBUG",
        )

    @staticmethod
    def add_file_sink(file_path):
        """
        添加文件sink。
        """
        llog.add(
            file_path,
            format=LOG_FORMAT,
            level="INFO",
            rotation="10 MB",
            retention="7 days",
        )

    def collect_logs(self, message):
        """
        自定义sink函数，用于收集日志信息。
        """
        self.logs.append(message)

    def attach_logs_to_allure(self, section_name):
        """
        将收集到的日志附加到Allure报告中。
        """
        if self.logs:
            all_logs = "\n".join(str(x) for x in self.logs)  # 逐条转字符串并用换行分隔
            allure.attach(
                all_logs, name=section_name, attachment_type=allure.attachment_type.TEXT
            )
            self.logs.clear()

    def get_logger(self):
        """
        返回配置好的logger实例（收集sink已在初始化时添加，不会重复）。
        """
        return llog


def log(cls):
    """
    类装饰器，用于将装饰器应用到类及其父类的所有方法上，
    使得方法仅在被调用时记录其文档注释。
    """

    def method_log_decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 记录方法文档
            signature = inspect.signature(func)
            bound_args = signature.bind(*args, **kwargs)
            bound_args.apply_defaults()
            params = bound_args.arguments
            doc = func.__doc__
            if doc:
                formatted_doc = re.sub(
                    r"{{(\w+)}}", lambda m: str(params.get(m.group(1), m.group(0))), doc
                )
                logger.info(formatted_doc)
            return func(*args, **kwargs)

        return wrapper

    collected: dict = {}
    for base_cls in reversed(cls.mro()):  # 从基类到自身：子类方法（含同名覆盖）最后收集，天然优先
        if base_cls.__name__ == "object":
            continue
        for name, attr in base_cls.__dict__.items():
            if not callable(attr) or name.startswith("__"):
                continue
            if name.startswith("_"):
                continue  # 内部方法不记录日志，也不强制要求 docstring
            if attr.__doc__ is None:
                raise TypeError(f"{cls.__name__}.{name} 缺少文档字符串")
            if attr.__doc__.strip().startswith("__"):
                continue
            collected[name] = attr
    for name, attr in collected.items():
        setattr(cls, name, method_log_decorator(attr))
    return cls


def get_logger():
    """
    返回一个预配置的 Loguru Logger 实例。
    """
    return custom_logger.get_logger()


custom_logger = CustomLogger()
logger = get_logger()
