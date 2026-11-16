#!/usr/bin/env python3
"""页面级接口请求封装：复用浏览器会话调接口（同步 / 异步两套）。

与 `just_go.http.Request`（requests 实现）的分工：

- `page.api`（本模块）：GUI 用例执行过程中造数据 / 取数据。复用浏览器 context 的
  cookie 与登录态，自动拼 base_url、带全局 headers，返回统一的 `ApiResponse`
- `Request`：纯接口套件、大文件下载（流式）、需要请求级代理与证书的场景

Playwright 的入参语义与 requests 不同，这里已对齐（写法与 `Request` 一致）：

    json={...}   → JSON 请求体（自动设 Content-Type: application/json）
    data={...}   → 表单（application/x-www-form-urlencoded，同 requests 的 data=dict）
    data="..."   → 原始请求体（字符串 / 字节）

默认**不因非 2xx 抛异常**（`fail_on_status=False`）：有些接口的正常业务返回就是
非 2xx，应在用例里用 `resp.assert_status(...)` 显式表达期望。

注意：APIResponse 只能整体读入内存，大文件下载请用 `Request.download()`。
"""
import asyncio
import json as _json
import mimetypes
import os
import time

try:
    from playwright.async_api import APIRequestContext as AsyncAPIRequestContext
    from playwright.async_api import Error as AsyncPlaywrightError
    from playwright.sync_api import APIRequestContext
    from playwright.sync_api import Error as PlaywrightError
except ImportError as e:  # pragma: no cover - 环境缺 playwright
    from just_go._internal.errors import SoftwareNotInstallError

    raise SoftwareNotInstallError("playwright") from e

from just_go._internal.errors import ConfigError, RequestError
from just_go._internal.logger import logger

__all__ = ["APIRequest", "AsyncAPIRequest", "ApiResponse", "AsyncApiResponse"]

# 日志里需要打码的请求头（大小写不敏感）
_SENSITIVE_HEADER_KEYS = (
    "authorization",
    "cookie",
    "set-cookie",
    "token",
    "x-token",
    "x-access-token",
)

# 自动沿用页面鉴权时识别的头（大小写不敏感）
_AUTH_HEADER_NAMES = ("authorization", "x-access-token", "x-token")


def _mask_headers(headers):
    """脱敏请求头，用于错误日志：鉴权类值替换成 ***"""
    if not headers:
        return {}
    return {
        k: ("***" if k.lower() in _SENSITIVE_HEADER_KEYS else v)
        for k, v in headers.items()
    }


def _resolve_base_url(base_url):
    """base_url 缺省取 JUSTGO_TEST_BASE_URL（setup_env 写入），并去掉尾斜杠"""
    if base_url is None:
        base_url = os.environ.get("JUSTGO_TEST_BASE_URL", "")
    return (base_url or "").rstrip("/")


def _to_millis(seconds):
    """秒 → 毫秒。Playwright 的超时单位是毫秒，直接用秒会被当成 30ms 立刻超时。

    0 原样保留：Playwright 里 `timeout=0` 表示不超时，改成 1ms 会让调用方
    本想「关闭超时」的请求立刻失败。
    """
    if seconds is None:
        return None
    millis = int(float(seconds) * 1000)
    return millis if millis <= 0 else max(1, millis)


def _join_url(base_url, path):
    """拼接接口地址：完整 URL 原样返回；相对路径缺 base_url 时明确报错"""
    if path is None:
        raise ValueError("接口地址不能为 None")
    path = str(path)
    if path.startswith(("http://", "https://")):
        return path
    if not base_url:
        raise ConfigError(
            f"接口地址是相对路径，但 base_url 为空：{path}\n"
            "请在 conftest.py 的 setup_env() 里为当前环境配置被测地址，"
            "或调用 page.api.set_base_url(...)"
        )
    return f"{base_url}/{str(path).lstrip('/')}"


def _build_payload(data, json, files=None):
    """把 requests 语义的 data / json / files 转成 Playwright 的载荷参数。

    Playwright 没有 files 参数，文件上传走 multipart；requests 的 files 在这里
    被还原成 multipart 的 FilePayload，写法与 `just_go.http.Request` 保持一致。
    """
    if files is not None:
        if json is not None:
            raise ValueError("files 与 json 不能同时传")
        if data is not None and not isinstance(data, dict):
            raise ValueError("files 与 data 同时传时，data 必须是 dict（附加表单字段）")
        multipart = dict(data or {})
        multipart.update(_build_files(files))
        return {"multipart": multipart}, {}
    if json is not None:
        if data is not None:
            raise ValueError("data 与 json 不能同时传")
        if isinstance(json, dict):
            # Playwright 收到 dict 会序列化为 JSON 并自动设 Content-Type
            return {"data": json}, {}
        body = _json.dumps(json, ensure_ascii=False)
        return {"data": body}, {"Content-Type": "application/json"}
    if isinstance(data, dict):
        # requests 的 data=dict 是表单；Playwright 对应参数是 form
        return {"form": data}, {}
    if data is not None:
        return {"data": data}, {}
    return {}, {}


def _build_files(files):
    """把 requests 风格的 files 转成 Playwright multipart 的 FilePayload。

    支持 requests 的两种写法：
        {"f": ("a.txt", b"...", "text/plain")}   三元组（文件名、内容、MIME）
        {"f": (b"...", "a.txt")}                 或 (文件名, 内容)
        {"f": b"..."}                            原始字节
        {"f": "/path/a.txt"}                     本地文件路径
    """
    if not isinstance(files, dict):
        raise ValueError("files 必须是 dict：{字段名: 文件内容}")
    payload = {}
    for field, value in files.items():
        if isinstance(value, (str, os.PathLike)):
            path = str(value)
            try:
                with open(path, "rb") as stream:
                    buffer = stream.read()
            except OSError as exc:
                raise ValueError(f"读取上传文件失败：{path}（{exc}）") from exc
            name = os.path.basename(path)
            mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        elif isinstance(value, (bytes, bytearray)):
            buffer, name, mime = bytes(value), f"{field}.bin", "application/octet-stream"
        elif isinstance(value, tuple):
            parts = list(value)
            # requests 允许 (filename, content[, content_type])
            if len(parts) == 2:
                first, second = parts
                if isinstance(first, str):
                    name, content = first, second
                else:
                    content, name = first, second
                mime = None
            elif len(parts) == 3:
                name, content, mime = parts
            else:
                raise ValueError(f"files[{field!r}] 元组长度只能是 2 或 3")
            buffer = content
            if isinstance(content, str):
                buffer = content.encode("utf-8")
            elif hasattr(content, "read"):
                buffer = content.read()
                # requests 的元组里，第二个元素也可以是文件对象
            if not isinstance(buffer, (bytes, bytearray)):
                raise ValueError(f"files[{field!r}] 的内容必须是 str / bytes / 文件对象")
            buffer = bytes(buffer)
            name = str(name or f"{field}.bin")
            mime = mime or mimetypes.guess_type(name)[0] or "application/octet-stream"
        else:
            raise ValueError(
                f"files[{field!r}] 不支持的类型：{type(value).__name__}"
                "（支持 路径 / bytes / (文件名, 内容[, MIME])）"
            )
        payload[field] = {"name": name, "mimeType": mime, "buffer": buffer}
    return payload


# ======================================================================
# 同步版
# ======================================================================
class ApiResponse:
    """统一响应对象：字段与 requests.Response 对齐，两条链路写法一致。

    status_code / ok / headers / url 为属性，json() / body() 为方法，text 为属性。
    raw 是 Playwright 的 APIResponse，需要框架未覆盖的能力时可直接取用。
    """

    def __init__(self, raw):
        self.raw = raw
        self._body = None
        self._text = None

    @property
    def status_code(self):
        return self.raw.status

    @property
    def ok(self):
        return self.raw.ok

    @property
    def headers(self):
        return dict(self.raw.headers)

    @property
    def url(self):
        return self.raw.url

    def body(self) -> bytes:
        """原始响应字节（只取一次，后续复用）"""
        if self._body is None:
            self._body = self.raw.body()
        return self._body

    @property
    def text(self) -> str:
        """响应文本（只取一次，后续复用）"""
        if self._text is None:
            self._text = self.raw.text()
        return self._text

    def json(self):
        """解析 JSON，解析失败抛原生 json.JSONDecodeError（与 requests 一致）"""
        return _json.loads(self.text)

    def assert_status(self, *expected):
        """断言状态码命中期望值之一，不命中抛 RequestError（带 url 与响应片段）"""
        if self.status_code not in expected:
            raise RequestError(
                f"接口状态码不符合预期：{self.url} 返回 {self.status_code}，"
                f"期望 {expected}\n响应体前 200 字：{self.text[:200]}"
            )
        return True

    def assert_ok(self):
        """断言 2xx"""
        if not self.ok:
            raise RequestError(
                f"接口返回失败状态：{self.url} 返回 {self.status_code}\n"
                f"响应体前 200 字：{self.text[:200]}"
            )
        return True

    def __repr__(self):
        return f"<ApiResponse {getattr(self.raw, 'status', '?')} {getattr(self.raw, 'url', '')}>"


class APIRequest:
    """复用浏览器 context 会话的接口客户端（同步）。

    由 `SyncWebUI.__init__` 自动挂载为 `page.api`，用例里直接：

        r = page.api.get("/admin-api/autolib/batch-task/page",
                         params={"pageNo": 1, "pageSize": 20})
        r.assert_status(200)
        rows = r.json()["data"]["list"]

    浏览器登录态（cookie）由 context 自动携带；Bearer 类鉴权用 set_token / set_headers。
    """

    def __init__(
        self,
        context: APIRequestContext,
        base_url=None,
        headers=None,
        timeout: float = 30,
        retry_times: int = 0,
        fail_on_status: bool = False,
    ):
        """
        Args:
            context: Playwright 的 APIRequestContext（由 page.context.request 提供）
            base_url: 接口基址，缺省取环境变量 JUSTGO_TEST_BASE_URL
            headers: 全局请求头（每次请求自动携带，调用时可覆盖同名项）
            timeout: 超时秒数（内部转毫秒），默认 30
            retry_times: 网络错误重试次数（Playwright 内置 max_retries，只重试网络层错误，不重试 5xx）
            fail_on_status: 非 2xx 是否抛异常，默认 False（业务返回非 2xx 的接口不受影响）
        """
        if int(retry_times) < 0:
            raise ValueError(f"retry_times 不能为负数，收到 {retry_times}")
        self.context = context
        self.base_url = _resolve_base_url(base_url)
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.retry_times = int(retry_times)
        self.fail_on_status = fail_on_status
        # 构造时显式给了 headers 就视为用户指定，不再自动沿用页面鉴权
        self._auth_pinned = bool(self.headers)
        # 是否真的从页面请求里抓到过鉴权头：wait_auth 不能拿 headers 是否为空
        # 当判据——调用方 update_headers 加过任意业务头也会让 headers 非空
        self._auth_captured = False
        self._auth_handler = None
        self._auth_page = None
        self._auth_context = None

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------
    def set_base_url(self, base_url):
        """切换接口基址（如多环境切换）"""
        self.base_url = (base_url or "").rstrip("/")

    def set_headers(self, headers):
        """整体替换全局请求头（之后不再自动沿用页面鉴权，以本次设置为准）"""
        self.headers = dict(headers or {})
        self._auth_pinned = True

    def update_headers(self, headers):
        """合并全局请求头"""
        self.headers.update(headers or {})

    def set_token(self, token, header_name="Authorization", prefix=""):
        """注入登录令牌：写入全局请求头，后续请求自动携带（并停止自动沿用）"""
        self.headers[header_name] = f"{prefix}{token}"
        self._auth_pinned = True

    def bind_auth(self, context, header_names=_AUTH_HEADER_NAMES, origin=None, page=None):
        """把 context 内同源请求携带的鉴权头同步进全局请求头。

        token 型鉴权的系统（cookie 为空、token 只在前端请求头里）用它就不必手工注入：
        登录后的业务请求一旦发出，Authorization 会自动进入 headers。

        显式调用 set_headers / set_token 之后不再自动覆盖，以调用方设置为准。
        origin 缺省用 base_url，用它可以避免把第三方请求的头也抓进来。
        page 用于 wait_auth 推动 Playwright 派发事件，可不传（那就只能被动等）。
        """
        base = self.base_url if origin is None else (origin or "").rstrip("/")
        keys = {name.lower() for name in header_names}
        # 同一实例重复 bind_auth（换 page / 换 origin）时先摘掉旧监听
        self.unbind_auth()

        def _on_request(request):
            if self._auth_pinned:
                return
            if base and not request.url.startswith(base):
                return
            for name, value in request.headers.items():
                if name.lower() in keys:
                    # 保留原始大小写，避免后端对头名大小写敏感
                    self.headers[name] = value
                    self._auth_captured = True
                    return

        self._auth_handler = _on_request
        self._auth_page = page
        self._auth_context = context
        self._auth_captured = False
        context.on("request", _on_request)
        return self

    def unbind_auth(self):
        """解除 bind_auth 注册的监听（重建客户端 / 换 context 前调用）。

        Playwright 的 on() 会一直持有 handler，不注销的话 refresh_api() 与
        每次 create_new_instance 都会在同一个 context 上叠加一份监听。
        """
        if self._auth_handler is None:
            return
        context = self._auth_context
        if context is not None:
            try:
                context.remove_listener("request", self._auth_handler)
            except Exception:  # pragma: no cover - context 已关闭
                pass
        self._auth_handler = None

    def wait_auth(self, timeout: float = 5):
        """等待页面发出带鉴权头的同源请求，返回是否已拿到。

        复用登录态时，首屏业务请求在页面对象构造之后才发出；同步 Playwright 的
        request 事件只在 API 调用期间派发，所以必须靠 page.wait_for_timeout 推动，
        单纯 sleep 等不到。cookie 型鉴权的系统不需要调用，headers 空也能用。

        判据是「抓到过鉴权头」而不是 headers 非空：调用方用 update_headers
        加过任意业务头时，headers 一开始就非空，旧写法会误报成功。
        """
        deadline = time.monotonic() + timeout
        while not self._auth_captured and time.monotonic() < deadline:
            if self._auth_page is None:
                time.sleep(0.1)
            else:
                self._auth_page.wait_for_timeout(100)
        return self._auth_captured

    # ------------------------------------------------------------------
    # 请求
    # ------------------------------------------------------------------
    def request(
        self,
        method,
        url,
        params=None,
        data=None,
        json=None,
        files=None,
        headers=None,
        timeout=None,
        fail_on_status=None,
        **kwargs,
    ):
        """发送请求，返回 ApiResponse。入参语义与 just_go.http.Request 一致。

        files 写法同 requests：{"file": ("a.txt", b"...", "text/plain")}、
        {"file": "/path/a.txt"} 或 {"file": b"..."}，内部转成 Playwright 的 multipart。
        """
        full_url = _join_url(self.base_url, url)
        merged_headers = dict(self.headers)
        payload, extra_headers = _build_payload(data, json, files)
        merged_headers.update(extra_headers)
        merged_headers.update(headers or {})
        fail = self.fail_on_status if fail_on_status is None else fail_on_status
        millis = _to_millis(self.timeout if timeout is None else timeout)

        started = time.monotonic()
        kwargs.setdefault("max_retries", self.retry_times)
        try:
            raw = self.context.fetch(
                full_url,
                method=str(method).upper(),
                headers=merged_headers or None,
                params=params,
                timeout=millis,
                fail_on_status_code=fail,
                **payload,
                **kwargs,
            )
        except (PlaywrightError, TypeError) as e:
            # TypeError 来自 fetch 的参数校验（如传了 Playwright 不支持的
            # 关键字）：同样是调用方视角的「请求失败」，一并包成框架异常
            logger.error(
                f"接口请求失败: {str(method).upper()} {full_url} "
                f"headers={_mask_headers(merged_headers)} 原因: {e}"
            )
            raise RequestError(f"接口请求失败: {str(method).upper()} {full_url} -> {e}") from e

        cost = int((time.monotonic() - started) * 1000)
        logger.info(f"接口 {str(method).upper()} {url} -> {raw.status} ({cost}ms)")
        return ApiResponse(raw)

    def get(self, url, params=None, headers=None, **kwargs):
        """GET"""
        return self.request("GET", url, params=params, headers=headers, **kwargs)

    def post(self, url, data=None, json=None, files=None, headers=None, **kwargs):
        """POST"""
        return self.request(
            "POST", url, data=data, json=json, files=files, headers=headers, **kwargs
        )

    def put(self, url, data=None, json=None, files=None, headers=None, **kwargs):
        """PUT"""
        return self.request(
            "PUT", url, data=data, json=json, files=files, headers=headers, **kwargs
        )

    def patch(self, url, data=None, json=None, files=None, headers=None, **kwargs):
        """PATCH"""
        return self.request(
            "PATCH", url, data=data, json=json, files=files, headers=headers, **kwargs
        )

    def delete(self, url, headers=None, **kwargs):
        """DELETE"""
        return self.request("DELETE", url, headers=headers, **kwargs)

    def __repr__(self):
        return f"<APIRequest base_url={self.base_url!r}>"


# ======================================================================
# 异步版
# ======================================================================
class AsyncApiResponse:
    """异步统一响应对象：除 body/text/json/assert_* 需 await 外，字段与 ApiResponse 一致"""

    def __init__(self, raw):
        self.raw = raw
        self._body = None
        self._text = None

    @property
    def status_code(self):
        return self.raw.status

    @property
    def ok(self):
        return self.raw.ok

    @property
    def headers(self):
        return dict(self.raw.headers)

    @property
    def url(self):
        return self.raw.url

    async def body(self) -> bytes:
        if self._body is None:
            self._body = await self.raw.body()
        return self._body

    async def text(self) -> str:
        if self._text is None:
            self._text = await self.raw.text()
        return self._text

    async def json(self):
        return _json.loads(await self.text())

    async def assert_status(self, *expected):
        if self.status_code not in expected:
            raise RequestError(
                f"接口状态码不符合预期：{self.url} 返回 {self.status_code}，"
                f"期望 {expected}\n响应体前 200 字：{(await self.text())[:200]}"
            )
        return True

    async def assert_ok(self):
        if not self.ok:
            raise RequestError(
                f"接口返回失败状态：{self.url} 返回 {self.status_code}\n"
                f"响应体前 200 字：{(await self.text())[:200]}"
            )
        return True

    def __repr__(self):
        return f"<AsyncApiResponse {getattr(self.raw, 'status', '?')} {getattr(self.raw, 'url', '')}>"


class AsyncAPIRequest:
    """复用浏览器 context 会话的接口客户端（异步）。

    由 `AsyncWebUI.__init__` 自动挂载为 `page.api`，用例里所有方法都要 await：

        r = await page.api.get("/admin-api/...", params={"pageNo": 1})
        data = await r.json()
    """

    def __init__(
        self,
        context: AsyncAPIRequestContext,
        base_url=None,
        headers=None,
        timeout: float = 30,
        retry_times: int = 0,
        fail_on_status: bool = False,
    ):
        if int(retry_times) < 0:
            raise ValueError(f"retry_times 不能为负数，收到 {retry_times}")
        self.context = context
        self.base_url = _resolve_base_url(base_url)
        self.headers = dict(headers or {})
        self.timeout = timeout
        self.retry_times = int(retry_times)
        self.fail_on_status = fail_on_status
        self._auth_pinned = bool(self.headers)
        self._auth_captured = False
        self._auth_handler = None
        self._auth_page = None
        self._auth_context = None

    def set_base_url(self, base_url):
        """切换接口基址"""
        self.base_url = (base_url or "").rstrip("/")

    def set_headers(self, headers):
        """整体替换全局请求头（之后不再自动沿用页面鉴权）"""
        self.headers = dict(headers or {})
        self._auth_pinned = True

    def update_headers(self, headers):
        """合并全局请求头"""
        self.headers.update(headers or {})

    def set_token(self, token, header_name="Authorization", prefix=""):
        """注入登录令牌（并停止自动沿用）"""
        self.headers[header_name] = f"{prefix}{token}"
        self._auth_pinned = True

    def bind_auth(self, context, header_names=_AUTH_HEADER_NAMES, origin=None, page=None):
        """把 context 内同源请求携带的鉴权头同步进全局请求头（异步版，理由同同步版）"""
        base = self.base_url if origin is None else (origin or "").rstrip("/")
        keys = {name.lower() for name in header_names}
        # 同一实例重复 bind_auth（换 page / 换 origin）时先摘掉旧监听
        self.unbind_auth()

        def _on_request(request):
            if self._auth_pinned:
                return
            if base and not request.url.startswith(base):
                return
            for name, value in request.headers.items():
                if name.lower() in keys:
                    self.headers[name] = value
                    self._auth_captured = True
                    return

        self._auth_handler = _on_request
        self._auth_page = page
        self._auth_context = context
        self._auth_captured = False
        context.on("request", _on_request)
        return self

    def unbind_auth(self):
        """解除 bind_auth 注册的监听（异步版）"""
        if self._auth_handler is None:
            return
        context = self._auth_context
        if context is not None:
            try:
                # AsyncEventEmitter.on / remove_listener 都是同步方法
                context.remove_listener("request", self._auth_handler)
            except Exception:  # pragma: no cover - context 已关闭
                pass
        self._auth_handler = None

    async def wait_auth(self, timeout: float = 5):
        """等待页面发出带鉴权头的同源请求（异步版，判据同同步版）"""
        deadline = time.monotonic() + timeout
        while not self._auth_captured and time.monotonic() < deadline:
            if self._auth_page is None:
                await asyncio.sleep(0.1)
            else:
                await self._auth_page.wait_for_timeout(100)
        return self._auth_captured

    async def request(
        self,
        method,
        url,
        params=None,
        data=None,
        json=None,
        files=None,
        headers=None,
        timeout=None,
        fail_on_status=None,
        **kwargs,
    ):
        """发送异步请求，返回 AsyncApiResponse（files 语义同同步版）"""
        full_url = _join_url(self.base_url, url)
        merged_headers = dict(self.headers)
        payload, extra_headers = _build_payload(data, json, files)
        merged_headers.update(extra_headers)
        merged_headers.update(headers or {})
        fail = self.fail_on_status if fail_on_status is None else fail_on_status
        millis = _to_millis(self.timeout if timeout is None else timeout)

        started = time.monotonic()
        kwargs.setdefault("max_retries", self.retry_times)
        try:
            raw = await self.context.fetch(
                full_url,
                method=str(method).upper(),
                headers=merged_headers or None,
                params=params,
                timeout=millis,
                fail_on_status_code=fail,
                **payload,
                **kwargs,
            )
        except (AsyncPlaywrightError, TypeError) as e:
            logger.error(
                f"接口请求失败: {str(method).upper()} {full_url} "
                f"headers={_mask_headers(merged_headers)} 原因: {e}"
            )
            raise RequestError(f"接口请求失败: {str(method).upper()} {full_url} -> {e}") from e

        cost = int((time.monotonic() - started) * 1000)
        logger.info(f"接口 {str(method).upper()} {url} -> {raw.status} ({cost}ms)")
        return AsyncApiResponse(raw)

    async def get(self, url, params=None, headers=None, **kwargs):
        """GET"""
        return await self.request("GET", url, params=params, headers=headers, **kwargs)

    async def post(self, url, data=None, json=None, files=None, headers=None, **kwargs):
        """POST"""
        return await self.request(
            "POST", url, data=data, json=json, files=files, headers=headers, **kwargs
        )

    async def put(self, url, data=None, json=None, files=None, headers=None, **kwargs):
        """PUT"""
        return await self.request(
            "PUT", url, data=data, json=json, files=files, headers=headers, **kwargs
        )

    async def patch(self, url, data=None, json=None, files=None, headers=None, **kwargs):
        """PATCH"""
        return await self.request(
            "PATCH", url, data=data, json=json, files=files, headers=headers, **kwargs
        )

    async def delete(self, url, headers=None, **kwargs):
        """DELETE"""
        return await self.request("DELETE", url, headers=headers, **kwargs)

    def __repr__(self):
        return f"<AsyncAPIRequest base_url={self.base_url!r}>"
