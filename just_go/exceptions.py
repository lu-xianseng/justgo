#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/7/30 13:31
# @Author   :luye
"""just-go 框架自定义异常体系。

所有框架异常统一继承 JustGoError（继承 Exception），使用方式：
- 精确捕获：except RecordError 等具体异常；
- 统一捕获：except JustGoError 捕获框架所有自定义异常；
- 兜底捕获：except Exception 不受影响（JustGoError 仍是 Exception 子类）。

测试项目可在用例中抛出/捕获这些异常做自定义处理。
"""


class JustGoError(Exception):
    """框架异常基类：所有 just-go 自定义异常的公共父类"""

    def __init__(self, message=""):
        super().__init__(message)


class SoftwareNotInstallError(JustGoError):
    """软件未安装：ffmpeg、allure、playwright 等运行依赖缺失"""

    def __init__(self, software_name):
        super().__init__(f"'{software_name}' Not install")


class FileNotExistsError(JustGoError):
    """文件不存在：配置文件、数据文件、产物文件缺失"""

    def __init__(self, file):
        super().__init__(f"'{file}' Not Exists")


class CaseError(JustGoError):
    """用例错误：用例文件与用例方法命名不一致等"""

    def __init__(self, msg):
        super().__init__(msg)


class TagError(JustGoError):
    """tag 标记数据错误：CSV 加载失败、用例ID缺失/非法、筛选表达式错误等"""

    def __init__(self, msg):
        super().__init__(msg)


class RecordError(JustGoError):
    """录屏错误：录屏启动/停止失败、未开始录屏、录屏文件产出异常"""

    def __init__(self, msg):
        super().__init__(msg)


class RequestError(JustGoError):
    """接口请求错误：网络不通、超时、响应异常"""

    def __init__(self, msg):
        super().__init__(msg)


class BrowserError(JustGoError):
    """浏览器操作错误：页面加载失败、元素交互异常、浏览器驱动异常"""

    def __init__(self, msg):
        super().__init__(msg)


class ConfigError(JustGoError):
    """配置错误：配置文件缺失、配置项非法或类型错误"""

    def __init__(self, msg):
        super().__init__(msg)
