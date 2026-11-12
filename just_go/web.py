"""Web UI 页面对象基类 + 属性式元素封装。

- SyncWebUI / AsyncWebUI：页面对象基类
- Element / AsyncElement：元素包装，动作自动记日志
- element / async_element：元素声明描述符
"""
from just_go._internal.element import AsyncElement, Element, async_element, element
from just_go._internal.web import AsyncWebUI, SyncWebUI

__all__ = [
    "SyncWebUI",
    "AsyncWebUI",
    "Element",
    "AsyncElement",
    "element",
    "async_element",
]
