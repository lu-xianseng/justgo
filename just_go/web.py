"""Web UI 页面对象基类 + 属性式元素封装 + 页面级接口客户端
"""
from just_go._internal.api import ApiResponse, AsyncApiResponse
from just_go._internal.element import (
    AsyncElement,
    AsyncFrameElement,
    Element,
    FrameElement,
    async_element,
    element,
)
from just_go._internal.web import AsyncWebUI, SyncWebUI

__all__ = [
    "SyncWebUI",
    "AsyncWebUI",
    "Element",
    "AsyncElement",
    "FrameElement",
    "AsyncFrameElement",
    "element",
    "async_element",
    "ApiResponse",
    "AsyncApiResponse",
]
