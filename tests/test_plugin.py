# -*- coding: utf-8 -*-
"""plugin._page_setup：浏览器类型与登录态参数构造（不启动浏览器）"""
import os
import shutil

import pytest

from just_go.exceptions import ConfigError
from just_go.plugin import _page_setup, config


def _clean(setup):
    shutil.rmtree(setup["user_data_dir"], ignore_errors=True)


def _restore():
    config.run.browser_type = "chromium"
    config.run.storage_state = ""


def test_default_browser_type():
    try:
        _restore()
        setup = _page_setup()
        try:
            assert setup["browser_type"] == "chromium"
            assert "storage_state" not in setup
        finally:
            _clean(setup)
    finally:
        _restore()


def test_switch_browser_type():
    try:
        _restore()
        config.run.browser_type = "firefox"
        setup = _page_setup()
        try:
            assert setup["browser_type"] == "firefox"
        finally:
            _clean(setup)
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
        try:
            assert setup["storage_state"] == state
        finally:
            _clean(setup)
    finally:
        _restore()


def test_storage_state_relative_resolves_against_rootdir():
    try:
        _restore()
        from just_go.settings import ROOTDIR

        config.run.storage_state = os.path.relpath(__file__, ROOTDIR)
        setup = _page_setup()
        try:
            assert os.path.isabs(setup["storage_state"])
            assert os.path.exists(setup["storage_state"])
        finally:
            _clean(setup)
    finally:
        _restore()


def test_storage_state_missing_file_raises():
    try:
        _restore()
        config.run.storage_state = "_no_such_state_xxx.json"
        with pytest.raises(ConfigError, match="storage_state"):
            _page_setup()
    finally:
        _restore()
