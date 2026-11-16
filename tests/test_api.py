# -*- coding: utf-8 -*-
"""page.api 接口客户端单元测试（只测参数构造与行为，不发真实请求）"""
import asyncio

import pytest
from playwright.sync_api import Error as PlaywrightError

from just_go._internal.api import (
    APIRequest,
    ApiResponse,
    AsyncAPIRequest,
    AsyncApiResponse,
    _join_url,
    _to_millis,
)
from just_go._internal.errors import ConfigError, RequestError


class FakeResponse:
    """模拟 playwright.sync_api.APIResponse"""

    def __init__(self, status=200, text='{"code":0}', body=None, url="http://h/a"):
        self.status = status
        self.ok = 200 <= status < 400
        self.headers = {"Content-Type": "application/json"}
        self.url = url
        self._text = text
        self._body = body if body is not None else text.encode("utf-8")
        self.text_calls = 0
        self.body_calls = 0

    def text(self):
        self.text_calls += 1
        return self._text

    def body(self):
        self.body_calls += 1
        return self._body


class FakeAsyncResponse:
    """模拟 playwright.async_api.APIResponse（body/text 都是协程）"""

    def __init__(self, status=200, text='{"code":0}', url="http://h/a"):
        self.status = status
        self.ok = 200 <= status < 400
        self.headers = {"Content-Type": "application/json"}
        self.url = url
        self._text = text

    async def text(self):
        return self._text

    async def body(self):
        return self._text.encode("utf-8")


class FakeContext:
    """模拟 playwright.sync_api.APIRequestContext

    fetch 的关键字参数与真实 Playwright 一致（见 APIRequestContext.fetch 签名），
    不接受 files：Playwright 的文件上传参数是 multipart。旧版用 **kwargs 全盘
    接收，导致 `files=` 在假对象上「能跑」，真实环境却 TypeError。
    """

    _ALLOWED = {
        "data",
        "fail_on_status_code",
        "form",
        "headers",
        "ignore_https_errors",
        "max_redirects",
        "max_retries",
        "method",
        "multipart",
        "params",
        "timeout",
    }

    def __init__(self, response=None, error=None):
        self.calls = []
        self.response = response or FakeResponse()
        self.error = error

    def fetch(self, url, **kwargs):
        unknown = set(kwargs) - self._ALLOWED
        if unknown:
            raise TypeError(
                f"APIRequestContext.fetch() got an unexpected keyword argument "
                f"{sorted(unknown)[0]!r}"
            )
        self.calls.append({"url": url, **kwargs})
        if self.error:
            raise self.error
        return self.response


class FakeAsyncContext:
    """模拟 playwright.async_api.APIRequestContext（参数约束同同步版）"""

    def __init__(self, response=None, error=None):
        self.calls = []
        self.response = response or FakeAsyncResponse()
        self.error = error

    async def fetch(self, url, **kwargs):
        unknown = set(kwargs) - FakeContext._ALLOWED
        if unknown:
            raise TypeError(
                f"APIRequestContext.fetch() got an unexpected keyword argument "
                f"{sorted(unknown)[0]!r}"
            )
        self.calls.append({"url": url, **kwargs})
        if self.error:
            raise self.error
        return self.response


class TestUrl:
    def test_absolute_url_passthrough(self):
        assert _join_url("http://h", "https://other/x") == "https://other/x"

    def test_relative_path_joined(self):
        assert _join_url("http://h/api", "/list") == "http://h/api/list"
        assert _join_url("http://h/api", "list") == "http://h/api/list"

    def test_missing_base_url_reports_config_error(self):
        """相对路径但没有 base_url 时必须明确报错，不能把 /x 直接发出去"""
        with pytest.raises(ConfigError, match="base_url 为空"):
            _join_url("", "/x")


class TestTimeoutUnit:
    def test_seconds_to_millis(self):
        """Playwright 超时单位是毫秒，传秒不转换会被当成 30ms 立刻超时"""
        assert _to_millis(30) == 30000
        assert _to_millis(0.5) == 500

    def test_none_returns_none(self):
        assert _to_millis(None) is None


class TestDefaults:
    def test_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("JUSTGO_TEST_BASE_URL", "http://10.0.0.1:8080/")
        req = APIRequest(FakeContext())
        assert req.base_url == "http://10.0.0.1:8080"

    def test_base_url_absent_is_empty(self, monkeypatch):
        monkeypatch.delenv("JUSTGO_TEST_BASE_URL", raising=False)
        req = APIRequest(FakeContext())
        assert req.base_url == ""

    def test_security_defaults(self):
        req = APIRequest(FakeContext())
        assert req.timeout == 30
        assert req.fail_on_status is False  # 默认不因非 2xx 抛异常

    def test_set_token(self):
        req = APIRequest(FakeContext())
        req.set_token("abc", prefix="Bearer ")
        assert req.headers["Authorization"] == "Bearer abc"

    def test_set_headers_replaces_update_merges(self):
        req = APIRequest(FakeContext(), headers={"A": "1"})
        req.update_headers({"B": "2"})
        assert req.headers == {"A": "1", "B": "2"}
        req.set_headers({"C": "3"})
        assert req.headers == {"C": "3"}

    def test_set_base_url_strips_trailing_slash(self):
        req = APIRequest(FakeContext())
        req.set_base_url("http://h/api/")
        assert req.base_url == "http://h/api"


class TestRequestConstruction:
    def test_get_url_headers_params(self):
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h", headers={"A": "1"})
        req.get("/list", params={"pageNo": 1}, headers={"A": "2", "B": "3"})
        call = ctx.calls[0]
        assert call["url"] == "http://h/list"
        assert call["method"] == "GET"
        assert call["params"] == {"pageNo": 1}
        assert call["headers"] == {"A": "2", "B": "3"}  # 调用时覆盖全局同名项

    def test_timeout_and_fail_on_status_forwarded(self):
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h", timeout=30)
        req.get("/x")
        assert ctx.calls[0]["timeout"] == 30000
        # Playwright 的真实参数名是 fail_on_status_code
        assert ctx.calls[0]["fail_on_status_code"] is False
        req.get("/y", timeout=5, fail_on_status=True)
        assert ctx.calls[1]["timeout"] == 5000
        assert ctx.calls[1]["fail_on_status_code"] is True

    def test_retry_times_forwarded_as_max_retries(self):
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h", retry_times=2)
        req.get("/x")
        assert ctx.calls[0]["max_retries"] == 2

    def test_negative_retry_times_rejected(self):
        with pytest.raises(ValueError, match="retry_times"):
            APIRequest(FakeContext(), base_url="http://h", retry_times=-1)

    def test_dict_data_becomes_form(self):
        """requests 的 data=dict 是表单，Playwright 对应参数是 form"""
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h")
        req.post("/x", data={"a": 1})
        call = ctx.calls[0]
        assert call["form"] == {"a": 1}
        assert "data" not in call

    def test_json_dict_goes_to_data(self):
        """Playwright 收到 dict 会序列化为 JSON 并自动设 Content-Type"""
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h")
        req.post("/x", json={"a": 1})
        call = ctx.calls[0]
        assert call["data"] == {"a": 1}
        assert "form" not in call

    def test_json_non_dict_serialized_with_content_type(self):
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h")
        req.post("/x", json=[1, 2])
        call = ctx.calls[0]
        assert call["data"] == "[1, 2]"
        assert call["headers"]["Content-Type"] == "application/json"

    def test_string_data_passthrough(self):
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h")
        req.put("/x", data="raw-body")
        assert ctx.calls[0]["data"] == "raw-body"

    def test_data_and_json_conflict(self):
        req = APIRequest(FakeContext(), base_url="http://h")
        with pytest.raises(ValueError, match="data 与 json"):
            req.post("/x", data={"a": 1}, json={"b": 2})

    def test_playwright_error_wrapped(self):
        ctx = FakeContext(error=PlaywrightError("net down"))
        req = APIRequest(ctx, base_url="http://h")
        with pytest.raises(RequestError, match="接口请求失败"):
            req.get("/x")

    def test_delete_has_no_body(self):
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h")
        req.delete("/x")
        assert ctx.calls[0]["method"] == "DELETE"


class TestApiResponse:
    def test_fields_align_with_requests(self):
        resp = ApiResponse(FakeResponse(status=201, text='{"id":1}'))
        assert resp.status_code == 201
        assert resp.ok is True
        assert resp.headers["Content-Type"] == "application/json"
        assert resp.json() == {"id": 1}

    def test_text_and_body_cached(self):
        raw = FakeResponse()
        resp = ApiResponse(raw)
        assert resp.text == resp.text
        assert raw.text_calls == 1
        assert resp.body() == resp.body()
        assert raw.body_calls == 1

    def test_assert_status_pass(self):
        assert ApiResponse(FakeResponse(status=200)).assert_status(200, 201) is True

    def test_assert_status_fail_message(self):
        with pytest.raises(RequestError, match="状态码不符合预期"):
            ApiResponse(FakeResponse(status=401, text='{"msg":"未授权"}')).assert_status(200)

    def test_assert_ok_fail(self):
        with pytest.raises(RequestError, match="失败状态"):
            ApiResponse(FakeResponse(status=500)).assert_ok()

    def test_non_200_does_not_raise_by_default(self):
        """非 2xx 只是返回对象，不抛异常——有些接口正常业务返回就是非 2xx"""
        resp = ApiResponse(FakeResponse(status=404))
        assert resp.status_code == 404
        assert resp.ok is False


class TestAsyncClient:
    def test_async_get_and_json(self):
        ctx = FakeAsyncContext()

        async def _run():
            client = AsyncAPIRequest(ctx, base_url="http://h", headers={"A": "1"})
            resp = await client.get("/x", params={"p": 1})
            return resp, await resp.json()

        resp, data = asyncio.run(_run())
        assert isinstance(resp, AsyncApiResponse)
        assert resp.status_code == 200
        assert data == {"code": 0}
        assert ctx.calls[0]["params"] == {"p": 1}
        assert ctx.calls[0]["headers"] == {"A": "1"}

    def test_async_assert_status_raises(self):
        ctx = FakeAsyncContext(FakeAsyncResponse(status=500))

        async def _run():
            client = AsyncAPIRequest(ctx, base_url="http://h")
            resp = await client.post("/x", json={"a": 1})
            return await resp.assert_status(200)

        with pytest.raises(RequestError, match="状态码不符合预期"):
            asyncio.run(_run())

    def test_async_error_wrapped(self):
        ctx = FakeAsyncContext(error=PlaywrightError("boom"))

        async def _run():
            client = AsyncAPIRequest(ctx, base_url="http://h")
            await client.get("/x")

        with pytest.raises(RequestError, match="接口请求失败"):
            asyncio.run(_run())


class FakeRequest:
    def __init__(self, url, headers):
        self.url = url
        self.headers = headers


class FakeEventContext:
    """模拟 BrowserContext 的 request 事件"""

    def __init__(self):
        self.handlers = []

    def on(self, event, handler):
        self.handlers.append((event, handler))

    def remove_listener(self, event, handler):
        self.handlers = [
            (e, h) for (e, h) in self.handlers if not (e == event and h is handler)
        ]

    def emit(self, request):
        for event, handler in list(self.handlers):
            if event == "request":
                handler(request)


class TestBindAuth:
    def test_same_origin_auth_captured(self):
        """token 型鉴权：页面业务请求里的 Authorization 自动进入 api.headers"""
        page_ctx = FakeEventContext()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.bind_auth(page_ctx)
        page_ctx.emit(FakeRequest("http://h/api/list", {"Authorization": "Bearer t1"}))
        assert req.headers["Authorization"] == "Bearer t1"

    def test_token_refreshed_on_later_request(self):
        page_ctx = FakeEventContext()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.bind_auth(page_ctx)
        page_ctx.emit(FakeRequest("http://h/a", {"Authorization": "old"}))
        page_ctx.emit(FakeRequest("http://h/b", {"Authorization": "new"}))
        assert req.headers["Authorization"] == "new"

    def test_cross_origin_ignored(self):
        page_ctx = FakeEventContext()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.bind_auth(page_ctx)
        page_ctx.emit(FakeRequest("http://third/a", {"Authorization": "other"}))
        assert "Authorization" not in req.headers

    def test_header_name_case_kept(self):
        page_ctx = FakeEventContext()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.bind_auth(page_ctx)
        page_ctx.emit(FakeRequest("http://h/a", {"authorization": "raw"}))
        assert req.headers == {"authorization": "raw"}

    def test_x_token_also_captured(self):
        page_ctx = FakeEventContext()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.bind_auth(page_ctx)
        page_ctx.emit(FakeRequest("http://h/a", {"X-Token": "t"}))
        assert req.headers["X-Token"] == "t"

    def test_explicit_headers_pin_and_stop_capture(self):
        """显式 set_headers 之后以调用方设置为准，不被页面请求覆盖"""
        page_ctx = FakeEventContext()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.set_headers({"Authorization": "Bearer mine"})
        req.bind_auth(page_ctx)
        page_ctx.emit(FakeRequest("http://h/a", {"Authorization": "Bearer page"}))
        assert req.headers["Authorization"] == "Bearer mine"

    def test_constructor_headers_pin(self):
        req = APIRequest(FakeContext(), base_url="http://h", headers={"A": "1"})
        assert req._auth_pinned is True


class FakePumpPage:
    """最小 page：只提供 wait_for_timeout（推动 Playwright 派发事件）"""

    def __init__(self):
        self.pumps = 0

    def wait_for_timeout(self, ms):
        self.pumps += 1

    def close(self):
        # 模拟关闭：把自己从 context.pages 里摘掉
        pages = getattr(getattr(self, "context", None), "pages", None)
        if pages and self in pages:
            pages.remove(self)


class FakePageForWeb(FakePumpPage):
    """SyncWebUI 构造所需的最小 page：context 上有 pages / request / on"""

    def __init__(self, pages=None):
        super().__init__()
        self.context = FakeEventContext()
        self.context.request = object()
        self.context.pages = pages if pages is not None else [self]


class TestWaitAuth:
    def test_returns_true_when_auth_already_captured(self):
        page_ctx = FakeEventContext()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.bind_auth(page_ctx, page=FakePumpPage())
        page_ctx.emit(FakeRequest("http://h/a", {"Authorization": "t"}))
        assert req.wait_auth(timeout=0.2) is True

    def test_times_out_without_auth_but_keeps_pumping(self):
        """同步 Playwright 的事件只在 API 调用期间派发，所以等待必须推动页面"""
        page = FakePumpPage()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.bind_auth(FakeEventContext(), page=page)
        assert req.wait_auth(timeout=0.2) is False
        assert page.pumps > 0

    def test_non_auth_headers_do_not_count_as_captured(self):
        """update_headers 加过业务头时 headers 非空，但还没拿到 token，不能算成功"""
        page = FakePumpPage()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.update_headers({"X-App": "demo"})
        req.bind_auth(FakeEventContext(), page=page)
        assert req.wait_auth(timeout=0.1) is False
        # 真正抓到鉴权头之后才返回 True
        req.bind_auth(FakeEventContext(), page=page)
        req.headers["Authorization"] = "t"
        req._auth_captured = True
        assert req.wait_auth(timeout=0.1) is True

    def test_async_non_auth_headers_do_not_count(self):
        async def _run():
            req = AsyncAPIRequest(FakeAsyncContext(), base_url="http://h")
            req.update_headers({"X-App": "demo"})
            req.bind_auth(FakeEventContext())
            return await req.wait_auth(timeout=0.1)

        assert asyncio.run(_run()) is False

    def test_syncwebui_binds_auth_on_construction(self, monkeypatch):
        """构造页面对象时就绑定监听，才抓得到首屏那批带 token 的请求"""
        monkeypatch.setenv("JUSTGO_TEST_BASE_URL", "http://h")
        from just_go.web import SyncWebUI

        page = FakePageForWeb()
        view = SyncWebUI(page)
        page.context.emit(FakeRequest("http://h/a", {"Authorization": "t"}))
        assert view.api.headers["Authorization"] == "t"

    def test_bind_auth_is_idempotent(self):
        """重复 bind_auth 不能在同一 context 上叠监听"""
        page_ctx = FakeEventContext()
        req = APIRequest(FakeContext(), base_url="http://h")
        req.bind_auth(page_ctx)
        req.bind_auth(page_ctx)
        assert len(page_ctx.handlers) == 1

    def test_refresh_api_unbinds_old_listener(self, monkeypatch):
        """refresh_api 重建客户端前先摘旧监听，避免 context 上越挂越多"""
        monkeypatch.setenv("JUSTGO_TEST_BASE_URL", "http://h")
        from just_go.web import SyncWebUI

        page = FakePageForWeb()
        view = SyncWebUI(page)
        view.refresh_api()
        view.refresh_api()
        assert len(page.context.handlers) == 1


class TestCreateNewInstance:
    def test_subclass_with_page_only_ctor(self):
        """模板 BasePage / PageExport 的 __init__ 只收 page，透传 only_keep_one 会 TypeError"""
        from just_go.web import SyncWebUI

        class PageExport(SyncWebUI):
            def __init__(self, page):
                super().__init__(page)

        first = FakePageForWeb()
        second = FakePageForWeb(pages=[first])
        second.context = first.context
        second.context.pages = [first, second]
        instance, raw = PageExport(first).create_new_instance(second)
        assert isinstance(instance, PageExport)
        assert raw is second
        assert first.context.pages == [second]

    def test_keeps_other_tabs_when_requested(self):
        from just_go.web import SyncWebUI

        class PageExport(SyncWebUI):
            def __init__(self, page):
                super().__init__(page)

        first = FakePageForWeb()
        first.context.pages = [first]
        instance, raw = PageExport(first).create_new_instance(close_other_tabs=False)
        assert raw is first
        assert first.context.pages == [first]


class TestSleepFraction:
    def test_sleep_accepts_fractional_seconds(self):
        """sleep(0.5) 必须等 500ms，不能被 int() 截成 0"""
        from just_go.web import SyncWebUI

        page = FakePageForWeb()
        waited = []
        page.wait_for_timeout = lambda ms: waited.append(ms)
        SyncWebUI(page).sleep(0.5)
        assert waited == [500]


class TestFilesConversion:
    def test_files_tuple_becomes_multipart(self):
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h")
        req.post("/upload", files={"f": ("a.txt", "内容", "text/plain")})
        call = ctx.calls[0]
        assert "files" not in call
        assert call["multipart"]["f"] == {
            "name": "a.txt",
            "mimeType": "text/plain",
            "buffer": "内容".encode("utf-8"),
        }

    def test_files_path_and_bytes(self, tmp_path):
        path = tmp_path / "b.csv"
        path.write_bytes(b"a,b\n")
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h")
        req.post("/upload", files={"a": str(path), "b": b"\x00"})
        multipart = ctx.calls[0]["multipart"]
        assert multipart["a"]["buffer"] == b"a,b\n"
        assert multipart["a"]["name"] == "b.csv"
        assert multipart["b"]["buffer"] == b"\x00"

    def test_files_with_form_fields(self):
        ctx = FakeContext()
        req = APIRequest(ctx, base_url="http://h")
        req.post("/upload", data={"name": "x"}, files={"f": b"1"})
        assert ctx.calls[0]["multipart"]["name"] == "x"
        assert "form" not in ctx.calls[0]

    def test_files_with_json_conflict(self):
        req = APIRequest(FakeContext(), base_url="http://h")
        with pytest.raises(ValueError, match="files 与 json"):
            req.post("/x", files={"f": b"1"}, json={"a": 1})

    def test_async_files_conversion(self):
        ctx = FakeAsyncContext()

        async def _run():
            client = AsyncAPIRequest(ctx, base_url="http://h")
            await client.post("/x", files={"f": ("a.txt", b"1")})

        asyncio.run(_run())
        assert ctx.calls[0]["multipart"]["f"]["buffer"] == b"1"


class TestTimeoutZero:
    def test_zero_means_no_timeout(self):
        """Playwright 里 timeout=0 表示不超时，不能被改写成 1ms"""
        assert _to_millis(0) == 0
        assert _to_millis(0.0) == 0

    def test_positive_still_converts(self):
        assert _to_millis(30) == 30000
        assert _to_millis(0.001) == 1


class TestUrlNone:
    def test_none_url_reports_value_error(self):
        req = APIRequest(FakeContext(), base_url="http://h")
        with pytest.raises(ValueError, match="不能为 None"):
            req.get(None)


class TestEnsureApi:
    """切标签通常仍在同一 context：此时不能重建客户端，否则已抓到的 token 会丢"""

    def test_same_context_keeps_client(self, monkeypatch):
        monkeypatch.setenv("JUSTGO_TEST_BASE_URL", "http://h")
        from just_go.web import SyncWebUI

        page = FakePageForWeb()
        view = SyncWebUI(page)
        page.context.emit(FakeRequest("http://h/a", {"Authorization": "Bearer t"}))
        client = view.api
        assert client.headers["Authorization"] == "Bearer t"
        page.context.pages.append(FakePageForWeb(pages=[]))
        assert view.ensure_api() is client
        assert client.headers["Authorization"] == "Bearer t"

    def test_new_context_rebuilds(self, monkeypatch):
        monkeypatch.setenv("JUSTGO_TEST_BASE_URL", "http://h")
        from just_go.web import SyncWebUI

        first = FakePageForWeb()
        view = SyncWebUI(first)
        old_client = view.api
        second = FakePageForWeb()
        view.page = second
        new_client = view.ensure_api()
        assert new_client is not old_client
        # 旧监听已从旧 context 摘掉，新 context 上只有一个
        assert first.context.handlers == []
        assert len(second.context.handlers) == 1


class TestInitApiDegrades:
    """_init_api 只是预绑定优化：任何失败都必须降级为懒创建，不能打断页面对象构造。

    真实场景：同步 fixture 里构造异步页面对象时没有运行中的事件循环，
    Playwright 的 context.on() 会抛 RuntimeError。
    """

    def test_async_init_failure_falls_back_to_lazy(self, monkeypatch):
        monkeypatch.setenv("JUSTGO_TEST_BASE_URL", "http://h")

        class ExplodingContext(FakeEventContext):
            def on(self, event, handler):
                raise RuntimeError("There is no current event loop in thread 'MainThread'.")

            request = object()
            pages = []

        class Page:
            context = ExplodingContext()

        from just_go.web import AsyncWebUI

        view = AsyncWebUI(Page())     # 不能抛异常
        assert view._AsyncWebUI__api is None

    def test_sync_init_failure_falls_back_to_lazy(self):
        class ExplodingContext(FakeEventContext):
            def on(self, event, handler):
                raise RuntimeError("boom")

            request = object()
            pages = []

        class Page:
            context = ExplodingContext()

        from just_go.web import SyncWebUI

        view = SyncWebUI(Page())
        assert view._SyncWebUI__api is None
