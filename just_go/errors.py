"""框架异常体系：所有自定义异常统一继承 JustGoError。"""
from just_go._internal.errors import (
    CaseError,
    ConfigError,
    FileNotExistsError,
    JustGoError,
    RequestError,
)

__all__ = ["JustGoError", "FileNotExistsError", "CaseError", "RequestError", "ConfigError",]
