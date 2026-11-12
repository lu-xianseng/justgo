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

    def __init__(self, software_name, hint=""):
        """software_name 为缺失组件名；hint 为可选的补救指引（如安装命令）"""
        msg = f"'{software_name}' 未安装"
        if hint:
            msg = f"{msg}：{hint}"
        super().__init__(msg)


class FileNotExistsError(JustGoError):
    """文件不存在：配置文件、数据文件、产物文件缺失"""

    def __init__(self, file):
        super().__init__(f"文件不存在: '{file}'")


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


class ImageRecognitionError(JustGoError):
    """图像识别错误：模板缺失、匹配未命中、截屏失败等"""


class TemplateNotFoundError(ImageRecognitionError):
    """图片文件不存在，或存在但无法解码"""

    def __init__(self, raw_path, searched=None, what="可用的图片文件"):
        self.raw_path = raw_path
        self.searched = list(searched or [])
        self.what = what
        msg = f"找不到{what}：{raw_path}"
        if self.searched:
            msg += "\n已尝试以下路径：\n  " + "\n  ".join(self.searched)
        super().__init__(msg)


class MatchNotFoundError(ImageRecognitionError):
    """重试结束后仍未在画面中找到目标图片"""


class ScreenCaptureError(ImageRecognitionError):
    """截屏失败：无图形界面、权限不足、后端不可用"""
