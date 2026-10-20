#!/usr/bin/env python3
# coding=utf-8
"""接口封装基类（apis/base.py）

职责：把**业务无关**的通用能力收拢到这里，让具体接口封装只写业务。

本类直接继承框架的 Request（just_go.request_utils），自动获得全部 HTTP 能力：
- get/post/put/delete/upload_file/download
- set_token / set_cookie / get_cookies / set_proxy
- session 复用、默认超时、异常统一转 RequestError
- retry_times/retry_delay 失败自动重试

本类只额外提供两件事：
- base_url：conftest 注入的 JUSTGO_TEST_BASE_URL
- _url(path)：拼接完整接口地址（支持完整 URL / 以 / 开头的路径 / 不带斜杠的路径）

具体接口在 apis/<模块>.py 继承本类，只写业务接口方法。
"""
import os

from just_go import Request


class BaseApi(Request):
    """接口封装基类：继承框架 Request，额外提供基址拼接"""

    def __init__(self, retry_times=0, retry_delay=1.0):
        """
        Args:
            retry_times: 接口请求失败自动重试次数（默认 0；幂等接口建议开启）
            retry_delay: 重试间隔秒数
        """
        super().__init__(retry_times=retry_times, retry_delay=retry_delay)
        self.base_url = os.environ.get("JUSTGO_TEST_BASE_URL", "").rstrip("/")

    def _url(self, path):
        """拼接口地址：支持完整 URL / 以 / 开头的路径 / 不带斜杠的路径"""
        if path.startswith("http"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"
