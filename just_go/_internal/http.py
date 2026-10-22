#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/6/12 17:51
# @Author   :luye
import os
import time
from typing import Any, Dict, Optional, Union

import requests
from requests import Response
from requests.exceptions import RequestException

from just_go._internal.errors import RequestError
from just_go._internal.logger import logger


class Request:
    """自定义封装的 requests session 类，处理 HTTP 请求。

    能力：
    - get/post/put/delete/request：基础请求（session 连接复用）
    - upload_file：multipart 文件上传；download：文件下载保存
    - set_token / set_cookie / get_cookies：鉴权信息注入与读取
    - set_proxy：代理配置
    - 失败自动重试（retry_times + retry_delay，默认关闭）
    - 统一异常：RequestException -> RequestError（含日志）
    """

    def __init__(
        self,
        headers: Dict[str, str] = None,
        timeout: Optional[Union[int, float]] = 30,
        retry_times: int = 0,
        retry_delay: Union[int, float] = 1.0,
    ):
        """
        Args:
            headers: 全局请求头（后续请求自动携带）
            timeout: 请求超时秒数（默认 30，避免用例无限挂起）
            retry_times: 失败自动重试次数（默认 0 不重试；幂等请求建议开启）
            retry_delay: 重试间隔秒数
        """
        self.session = requests.Session()
        self.headers = {}
        if headers:
            self.headers.update(headers)
        self.timeout = timeout
        self.retry_times = retry_times
        self.retry_delay = retry_delay

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
        retries: Optional[int] = None,
        **kwargs,
    ) -> Response:
        """
        发送 HTTP 请求（支持失败自动重试）

        Args:
            method: HTTP方法(GET, POST, PUT, DELETE等)
            url: API端点
            params: 查询参数
            data: 表单数据
            json: JSON数据
            headers: 请求头（合并进全局请求头）
            timeout: 超时时间(秒)，缺省用实例默认值
            retries: 本次请求重试次数，缺省用实例 retry_times
            **kwargs: 其他 requests 参数

        Returns:
            requests.Response 对象
        """
        if headers:
            merged_headers = {**self.headers, **headers}
        else:
            merged_headers = self.headers
        _timeout = timeout if timeout is not None else self.timeout
        _retries = self.retry_times if retries is None else retries
        last_exc = None
        for attempt in range(_retries + 1):
            try:
                return self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    json=json,
                    headers=merged_headers,
                    timeout=_timeout,
                    **kwargs,
                )
            except RequestException as e:
                last_exc = e
                if attempt < _retries:
                    logger.warning(
                        f"请求失败（第 {attempt + 1}/{_retries + 1} 次）: {e}，"
                        f"{self.retry_delay} 秒后重试"
                    )
                    time.sleep(self.retry_delay)
        logger.error(f"请求错误: {str(last_exc)}")
        raise RequestError(f"请求错误: {str(last_exc)}")

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
        return self.request(
            "PUT", url, data=data, json=json, headers=headers, **kwargs
        )

    def patch(
        self,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: Dict[str, str] = None,
        **kwargs,
    ) -> Response:
        """发送PATCH请求（部分更新）"""
        return self.request(
            "PATCH", url, data=data, json=json, headers=headers, **kwargs
        )

    def delete(self, url: str, headers: Dict[str, str] = None, **kwargs) -> Response:
        """发送DELETE请求"""
        return self.request("DELETE", url, headers=headers, **kwargs)

    def upload_file(
        self,
        url: str,
        files: Dict[str, Any],
        data: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> Response:
        """上传文件（multipart/form-data）

        Args:
            url: 上传地址
            files: 文件字典，如 {"file": ("a.txt", open("a.txt", "rb"), "text/plain")}
                   或 {"file": open("a.txt", "rb")}（requests 两种格式均支持）
            data: 其他表单字段
        """
        if headers:
            merged_headers = {**self.headers, **headers}
        else:
            merged_headers = self.headers
        _timeout = timeout if timeout is not None else self.timeout
        try:
            return self.session.post(
                url,
                files=files,
                data=data,
                headers=merged_headers,
                timeout=_timeout,
                **kwargs,
            )
        except RequestException as e:
            logger.error(f"上传失败: {str(e)}")
            raise RequestError(f"上传失败: {str(e)}")

    def download(
        self,
        url: str,
        save_path: str,
        params: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> str:
        """下载文件并保存到本地，返回保存路径

        Args:
            url: 下载地址
            save_path: 保存路径（父目录自动创建）
        """
        if headers:
            merged_headers = {**self.headers, **headers}
        else:
            merged_headers = self.headers
        _timeout = timeout if timeout is not None else self.timeout
        try:
            with self.session.get(
                url,
                params=params,
                headers=merged_headers,
                timeout=_timeout,
                stream=True,
                **kwargs,
            ) as resp:
                resp.raise_for_status()
                os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
            return save_path
        except (RequestException, OSError) as e:
            logger.error(f"下载失败: {str(e)}")
            raise RequestError(f"下载失败: {str(e)}")

    def set_token(self, token: str, header_name: str = "Authorization", prefix: str = "") -> None:
        """注入登录令牌：写入全局请求头，后续所有请求自动携带。

        Args:
            token: 令牌值
            header_name: 请求头名（默认 Authorization）
            prefix: 值前缀，如 "Bearer " 则最终值为 "Bearer <token>"
        """
        self.headers[header_name] = f"{prefix}{token}"

    def set_cookie(self, name: str, value: str, domain: str = "", path: str = "/") -> None:
        """手动写入 Cookie（如登录接口返回 token 后注入）

        Args:
            domain: 所属域名；缺省空字符串表示对所有域发送（requests supercookie 语义）
        """
        self.session.cookies.set(name, value, domain=domain, path=path)

    def get_cookies(self) -> Dict[str, str]:
        """获取当前会话全部 Cookie（name -> value）"""
        return {c.name: c.value for c in self.session.cookies}

    def set_proxy(self, http: str = None, https: str = None) -> None:
        """配置代理（requests 透传）

        Args:
            http: HTTP 代理地址，如 "http://127.0.0.1:8888"
            https: HTTPS 代理地址（缺省复用 http）
        """
        if http:
            self.session.proxies = {"http": http, "https": https or http}
        else:
            self.session.proxies = {}
