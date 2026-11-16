# -*- coding: utf-8 -*-
"""settings 配置包装单元测试：属性访问 / 布尔解析 / 运行时覆盖"""
import pytest

from just_go._internal.settings import ConfigWrapper
from just_go.config import config


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


class TestApplyEnv:
    """setup_env / apply_env：--env 必须在 conftest 导入时与 pytest_configure 后都生效"""

    @staticmethod
    def _reset(monkeypatch):
        from just_go import config as config_module

        monkeypatch.setattr(config_module, "_env_base_urls", None)
        monkeypatch.setattr(config_module, "_env_case_base_url", "")
        monkeypatch.setattr(config_module, "_managed_env", {})
        for name in (
            "JUSTGO_ENV",
            "JUSTGO_TEST_BASE_URL",
            "JUSTGO_TEST_CASE_BASE_URL",
        ):
            monkeypatch.delenv(name, raising=False)
        return config_module

    def test_setup_env_uses_argv_env(self, monkeypatch):
        """conftest 导入时 pytest 还没解析 --env，要能从命令行文本里取到"""
        module = self._reset(monkeypatch)
        monkeypatch.setattr(module.sys, "argv", ["pytest", "--env", "prod"])
        module.setup_env({"dev": "http://dev", "prod": "http://prod"})
        assert module.os.environ["JUSTGO_TEST_BASE_URL"] == "http://prod"

    def test_setup_env_supports_equals_form(self, monkeypatch):
        module = self._reset(monkeypatch)
        monkeypatch.setattr(module.sys, "argv", ["pytest", "--env=test"])
        module.setup_env({"dev": "http://dev", "test": "http://test"})
        assert module.os.environ["JUSTGO_TEST_BASE_URL"] == "http://test"

    def test_apply_env_overrides_conftest_time_value(self, monkeypatch):
        """pytest_configure 用解析后的 --env 再刷新一次，覆盖 conftest 时的默认 dev"""
        module = self._reset(monkeypatch)
        module.setup_env({"dev": "http://dev", "prod": "http://prod"})
        assert module.os.environ["JUSTGO_TEST_BASE_URL"] == "http://dev"
        module.apply_env("prod")
        assert module.os.environ["JUSTGO_ENV"] == "prod"
        assert module.os.environ["JUSTGO_TEST_BASE_URL"] == "http://prod"

    def test_user_exported_base_url_wins(self, monkeypatch):
        """用户自己 export 的 JUSTGO_TEST_BASE_URL 不能被 --env 覆盖"""
        module = self._reset(monkeypatch)
        monkeypatch.setenv("JUSTGO_TEST_BASE_URL", "http://manual")
        module.setup_env({"dev": "http://dev", "prod": "http://prod"})
        assert module.os.environ["JUSTGO_TEST_BASE_URL"] == "http://manual"
        module.apply_env("prod")
        assert module.os.environ["JUSTGO_TEST_BASE_URL"] == "http://manual"

    def test_apply_env_without_setup_env(self, monkeypatch):
        """没调用 setup_env 时只更新 JUSTGO_ENV，不碰地址"""
        module = self._reset(monkeypatch)
        module.apply_env("prod")
        assert module.os.environ["JUSTGO_ENV"] == "prod"
        assert "JUSTGO_TEST_BASE_URL" not in module.os.environ

    def test_unknown_env_falls_back_to_dev(self, monkeypatch):
        module = self._reset(monkeypatch)
        module.setup_env({"dev": "http://dev"})
        module.apply_env("staging")
        assert module.os.environ["JUSTGO_TEST_BASE_URL"] == "http://dev"
