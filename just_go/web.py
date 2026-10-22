"""Web UI 页面对象基类：同步 / 异步两套。"""
from just_go._internal.web import AsyncWebUI, SyncWebUI

__all__ = ["SyncWebUI", "AsyncWebUI"]
