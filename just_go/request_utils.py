#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/6/12 17:51
# @Author   :luye
from typing import Any, Dict, Optional, Union

import requests
from requests import Response
from requests.exceptions import RequestException

from just_go.exceptions import RequestError
from just_go.logger import logger


class Request:
    """自定义封装的requests session类，处理HTTP请求"""

    def __init__(
        self,
        headers: Dict[str, str] = None,
        timeout: Optional[Union[int, float]] = None,
    ):
        self.session = requests.Session()
        self.headers = {}
        if headers:
            self.headers.update(headers)
        self.timeout = timeout

    def __del__(self):
        try:
            self.session_close()
        except Exception:
            pass

    def session_close(self):
        """关闭连接"""
        self.session.close()

    def request(
        self,
        method: str,
        url: str,
        params: Dict[str, Any] = None,
        data: Any = None,
        json: Any = None,
        headers: Dict[str, str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Response:
        """
        发送HTTP请求

        Args:
            method: HTTP方法(GET, POST, PUT, DELETE等)
            url: API端点
            params: 查询参数
            data: 表单数据
            json: JSON数据
            headers: 请求头
            timeout: 超时时间(秒)
            **kwargs: 其他requests参数

        Returns:
            包含响应信息的字典
        """
        if headers:
            self.headers.update(headers)
        if timeout:
            self.timeout = timeout
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                data=data,
                json=json,
                headers=self.headers,
                timeout=self.timeout,
                **kwargs,
            )
            return response
        except RequestException as e:
            logger.error(f"请求错误: {str(e)}")
            raise RequestError(f"请求错误: {str(e)}")

    def get(
        self,
        url: str,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        **kwargs,
    ) -> Response:
        """发送GET请求"""
        return self.request("GET", url, params=params, headers=headers, **kwargs)

    def post(
        self,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: Dict[str, str] = None,
        **kwargs,
    ) -> Response:
        """发送POST请求"""
        return self.request(
            "POST", url, data=data, json=json, headers=headers, **kwargs
        )

    def put(
        self,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: Dict[str, str] = None,
        **kwargs,
    ) -> Response:
        """发送PUT请求"""
        return self.request("PUT", url, data=data, json=json, headers=headers, **kwargs)

    def delete(self, url: str, headers: Dict[str, str] = None, **kwargs) -> Response:
        """发送DELETE请求"""
        return self.request("DELETE", url, headers=headers, **kwargs)

    def set_token(self, token: str, header_name: str = "Authorization", prefix: str = "") -> None:
        """注入登录令牌：写入全局请求头，后续所有请求自动携带。

        Args:
            token: 令牌值
            header_name: 请求头名（默认 Authorization）
            prefix: 值前缀，如 "Bearer " 则最终值为 "Bearer <token>"
        """
        self.headers[header_name] = f"{prefix}{token}"
