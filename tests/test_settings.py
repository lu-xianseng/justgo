# -*- coding: utf-8 -*-
"""settings 配置包装单元测试：属性访问 / 布尔解析 / 运行时覆盖"""
import pytest

from just_go._internal.settings import ConfigWrapper
from just_go.core import config


def make_config(text: str):
    from configparser import ConfigParser

    parser = ConfigParser()
    parser.read_string(text)
    return ConfigWrapper(parser)


class TestSectionWrapper:
    def test_boolean_parsing(self):
        cfg = make_config("[run]\nshow_browser = True\nslow_time = 500\n")
        assert cfg.run.show_browser is True
        assert cfg.run.slow_time == "500"  # 非布尔值保留原字符串

    def test_false_parsing(self):
        cfg = make_config("[run]\nshow_browser = false\n")
        assert cfg.run.show_browser is False

    def test_runtime_override(self):
        cfg = make_config("[run]\nslow_time = 500\n")
        cfg.run.slow_time = 1000
        assert cfg.run.slow_time == 1000

    def test_missing_option_raises(self):
        cfg = make_config("[run]\nshow_browser = True\n")
        with pytest.raises(AttributeError):
            _ = cfg.run.not_exist_option


class TestConfigWrapper:
    def test_get_section_exists(self):
        cfg = make_config("[run]\na = 1\n")
        assert cfg.get_section("run") is not None
        assert cfg.get_section("run")._section["a"] == "1"

    def test_get_section_missing(self):
        cfg = make_config("[run]\na = 1\n")
        assert cfg.get_section("missing") is None

    def test_missing_section_raises(self):
        cfg = make_config("[run]\na = 1\n")
        with pytest.raises(AttributeError):
            _ = cfg.no_such_section


class TestRealConfig:
    """框架实际配置（config.ini）的基本可用性"""

    def test_framework_section_present(self):
        assert config.framework.browser_path is not None
        assert config.framework.log_path == "logs"

    def test_run_section_has_new_options(self):
        # 本次新增：browser_type / storage_state 应存在于运行配置
        assert config.run.browser_type in ("chromium", "firefox", "webkit")
        # storage_state 默认为空（未启用）
        assert config.run.storage_state == ""
