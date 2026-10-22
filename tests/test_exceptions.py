# -*- coding: utf-8 -*-
"""exceptions 异常体系单元测试"""
import pytest

from just_go._internal.errors import (
    BrowserError,
    CaseError,
    ConfigError,
    JustGoError,
    RecordError,
    RequestError,
    SoftwareNotInstallError,
    TagError,
)


class TestExceptionHierarchy:
    def test_all_exceptions_inherit_justgoerror(self):
        for exc in (
            CaseError,
            TagError,
            RecordError,
            RequestError,
            BrowserError,
            ConfigError,
            SoftwareNotInstallError,
        ):
            assert issubclass(exc, JustGoError)

    def test_justgoerror_is_exception(self):
        assert issubclass(JustGoError, Exception)

    def test_catch_base_class(self):
        """except JustGoError 可统一捕获所有框架异常"""
        with pytest.raises(JustGoError):
            raise TagError("bad tag")

    def test_message_preserved(self):
        with pytest.raises(ConfigError, match="浏览器类型"):
            raise ConfigError("不支持的浏览器类型: safari")

    def test_software_not_install_message(self):
        exc = SoftwareNotInstallError("ffmpeg")
        assert "ffmpeg" in str(exc)
