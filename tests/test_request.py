# -*- coding: utf-8 -*-
"""Request 接口封装单元测试（仅测参数构造与行为，不发真实请求）"""
from unittest import mock

import pytest
from requests.exceptions import ConnectionError

from just_go.exceptions import RequestError
from just_go.request_utils import Request


class TestSetToken:
    def test_default_header(self):
        req = Request()
        req.set_token("abc123")
        assert req.headers["Authorization"] == "abc123"

    def test_with_prefix(self):
        req = Request()
        req.set_token("abc123", prefix="Bearer ")
        assert req.headers["Authorization"] == "Bearer abc123"

    def test_custom_header_name(self):
        req = Request()
        req.set_token("tok", header_name="X-Token")
        assert req.headers["X-Token"] == "tok"
        assert "Authorization" not in req.headers


class TestDefaults:
    def test_default_timeout_is_30(self):
        """默认超时 30 秒，避免用例无限挂起"""
        req = Request()
        assert req.timeout == 30

    def test_retry_disabled_by_default(self):
        req = Request()
        assert req.retry_times == 0


class TestRetry:
    def test_retries_until_success(self):
        req = Request(retry_times=2, retry_delay=0)
        responses = [ConnectionError("conn"), ConnectionError("conn"), mock.Mock(status_code=200)]

        def fake_request(method, url, **kwargs):
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with mock.patch.object(req.session, "request", side_effect=fake_request):
            resp = req.request("GET", "http://x")
        assert resp.status_code == 200
        assert len(responses) == 0  # 三次尝试全部消费

    def test_retries_exhausted_raises(self):
        req = Request(retry_times=1, retry_delay=0)

        def boom(*a, **k):
            raise ConnectionError("fail")

        with mock.patch.object(req.session, "request", side_effect=boom):
            with pytest.raises(RequestError):
                req.request("GET", "http://x")

    def test_per_request_retries_override(self):
        req = Request(retry_times=0, retry_delay=0)
        calls = []

        def boom(*a, **k):
            calls.append(1)
            raise ConnectionError("fail")

        with mock.patch.object(req.session, "request", side_effect=boom):
            with pytest.raises(RequestError):
                req.request("GET", "http://x", retries=2)
        assert len(calls) == 3


class TestUploadDownload:
    def test_upload_passes_files_and_data(self, tmp_path):
        req = Request()
        f = tmp_path / "a.txt"
        f.write_text("hello", encoding="utf-8")
        fake_resp = mock.Mock(status_code=200)
        with mock.patch.object(req.session, "post", return_value=fake_resp) as m:
            resp = req.upload_file(
                "http://x/upload",
                files={"file": (f.name, f.open("rb"), "text/plain")},
                data={"note": "n"},
            )
        assert resp is fake_resp
        args, kwargs = m.call_args
        assert args[0] == "http://x/upload"
        assert "file" in kwargs["files"]
        assert kwargs["data"] == {"note": "n"}

    def test_download_saves_file(self, tmp_path):
        req = Request()
        fake_resp = mock.Mock()
        fake_resp.__enter__ = mock.Mock(return_value=fake_resp)
        fake_resp.__exit__ = mock.Mock(return_value=False)
        fake_resp.raise_for_status = mock.Mock()
        fake_resp.iter_content = mock.Mock(return_value=[b"abc", b"def"])
        with mock.patch.object(req.session, "get", return_value=fake_resp) as m:
            save = str(tmp_path / "sub" / "out.bin")
            result = req.download("http://x/dl", save_path=save)
        assert result == save
        assert (tmp_path / "sub" / "out.bin").read_bytes() == b"abcdef"
        _, kwargs = m.call_args
        assert kwargs["stream"] is True


class TestCookieProxy:
    def test_set_and_get_cookies(self):
        req = Request()
        req.set_cookie("token", "t1")
        cookies = req.get_cookies()
        assert cookies.get("token") == "t1"

    def test_set_proxy(self):
        req = Request()
        req.set_proxy(http="http://127.0.0.1:8888")
        assert req.session.proxies["https"] == "http://127.0.0.1:8888"

    def test_set_proxy_with_https(self):
        req = Request()
        req.set_proxy(http="http://h", https="http://s")
        assert req.session.proxies == {"http": "http://h", "https": "http://s"}


class TestPatchMethod:
    def test_patch_dispatches_to_session(self):
        req = Request()
        fake_resp = mock.Mock(status_code=200)
        with mock.patch.object(req.session, "request", return_value=fake_resp) as m:
            resp = req.patch("http://x", json={"a": 1})
        assert resp is fake_resp
        kwargs = m.call_args[1]
        assert kwargs["method"] == "PATCH"
        assert kwargs["url"] == "http://x"
        assert kwargs["json"] == {"a": 1}
