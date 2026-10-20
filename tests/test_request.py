# -*- coding: utf-8 -*-
"""Request 接口封装单元测试（仅测请求头构造，不发真实请求）"""
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
