# -*- coding: utf-8 -*-
"""plugin._page_setup：浏览器类型与登录态参数构造（不启动浏览器）"""
import os

import pytest

from just_go._internal.errors import ConfigError
from just_go._internal.plugin import _page_setup, config


def _restore():
    config.run.browser_type = "chromium"
    config.run.storage_state = ""


def test_default_browser_type():
    try:
        _restore()
        setup = _page_setup()
        assert setup["browser_type"] == "chromium"
        assert "storage_state" not in setup["context"]
    finally:
        _restore()


def test_switch_browser_type():
    try:
        _restore()
        config.run.browser_type = "firefox"
        setup = _page_setup()
        assert setup["browser_type"] == "firefox"
    finally:
        _restore()


def test_invalid_browser_type_raises():
    try:
        _restore()
        config.run.browser_type = "safari"
        with pytest.raises(ConfigError, match="浏览器类型"):
            _page_setup()
    finally:
        _restore()


def test_storage_state_absolute_path():
    try:
        _restore()
        state = os.path.abspath(__file__)  # 用存在的文件模拟 state
        config.run.storage_state = state
        setup = _page_setup()
        assert setup["context"]["storage_state"] == state
    finally:
        _restore()


def test_storage_state_relative_resolves_against_rootdir():
    try:
        _restore()
        from just_go._internal.settings import ROOTDIR

        config.run.storage_state = os.path.relpath(__file__, ROOTDIR)
        setup = _page_setup()
        assert os.path.isabs(setup["context"]["storage_state"])
        assert os.path.exists(setup["context"]["storage_state"])
    finally:
        _restore()


def test_storage_state_missing_file_skipped():
    """首次运行还没有登录态文件：跳过加载，不中断整个套件"""
    try:
        _restore()
        config.run.storage_state = "_no_such_state_xxx.json"
        setup = _page_setup()
        assert "storage_state" not in setup["context"]
    finally:
        _restore()


def test_parse_slow_mo_accepts_decimal_value():
    """配置写成 0.5（本意是秒）时按毫秒取整，而不是直接 ValueError"""
    from just_go._internal.plugin import _parse_slow_mo

    assert _parse_slow_mo("0.5") == 0
    assert _parse_slow_mo("500") == 500
    assert _parse_slow_mo(1000) == 1000


def test_parse_slow_mo_invalid_value_raises_config_error():
    from just_go._internal.plugin import _parse_slow_mo

    with pytest.raises(ConfigError, match="slow_time"):
        _parse_slow_mo("fast")


def test_case_title_tolerates_item_without_obj():
    """非 Function item（doctest 等）没有 obj，取标题不能抛 AttributeError"""
    from just_go._internal.plugin import _case_title

    class FakeItem:
        obj = None
        name = "test_x"

    assert _case_title(FakeItem()) == "未命名用例"


def test_pytest_configure_applies_parsed_env(monkeypatch, tmp_path):
    """--env 在 pytest_configure 才解析完成，要在那里再刷新一次被测地址。

    测试项目 conftest 顶部的 setup_env() 早于参数解析，只靠它会让 --env 永远落到 dev。
    """
    from just_go._internal import plugin

    monkeypatch.setattr(plugin, "TMP_REPORT_PATH", str(tmp_path / "report"))
    calls = []
    monkeypatch.setattr(plugin, "apply_env", lambda env=None: calls.append(env))

    class FakeConfig:
        option = type("Opt", (), {})()

        def getoption(self, name, default=None):
            return {"--env": "prod", "--record": "no", "numprocesses": None}.get(
                name, default
            )

    plugin.pytest_configure(FakeConfig())
    assert calls == ["prod"]
