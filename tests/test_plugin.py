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
