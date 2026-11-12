"""框架异常体系：所有自定义异常统一继承 JustGoError。"""
from just_go._internal.errors import (
    BrowserError,
    CaseError,
    ConfigError,
    FileNotExistsError,
    ImageRecognitionError,
    JustGoError,
    MatchNotFoundError,
    RecordError,
    RequestError,
    ScreenCaptureError,
    SoftwareNotInstallError,
    TagError,
    TemplateNotFoundError,
)

__all__ = [
    "JustGoError",
    "SoftwareNotInstallError",
    "FileNotExistsError",
    "CaseError",
    "TagError",
    "RecordError",
    "RequestError",
    "BrowserError",
    "ConfigError",
    "ImageRecognitionError",
    "TemplateNotFoundError",
    "MatchNotFoundError",
    "ScreenCaptureError",
]
