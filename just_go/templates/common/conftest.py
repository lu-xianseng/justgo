#!/usr/bin/env python3
# coding=utf-8
"""测试项目根 conftest：让 just-go 框架插件生效，并向框架注入本项目配置。

按你的项目填写 setup_env() 的多环境地址即可，
运行时用 `--env prod` 切换环境，框架自动设置被测地址。
"""
import pytest
from just_go.core import config, setup_env

# 多环境被测地址（按需增删）：运行 `just-go run <名称> --env prod` 切换，默认 dev
setup_env({
    "dev": "http://192.168.1.10:8080",   # TODO: 填写实际地址
    "test": "http://test.example.com",   # TODO
    "prod": "https://www.example.com",   # TODO
}, case_base_url="")  # TODO: 可选，如 https://zentao.example.com/case-view-{id}.html

# 示例：慢速操作等待毫秒数 / 无头模式 / 浏览器类型 / 登录态复用
# config.run.slow_time = 1000
# config.run.show_browser = False
# config.run.browser_type = "chromium"   # chromium / firefox / webkit
# config.run.storage_state = "state.json"  # 复用登录态

pytest_plugins = ["just_go._internal.plugin"]

# 将底层 Playwright Page 包装成 PageExport（页面对象 + 断言统一出口）
# 用例里 def test_xxx(page) 直接调 page.xxx()，不需要手动 import 页面对象
try:
    from pages import PageExport

    @pytest.fixture
    def page(_pw_page):
        return PageExport(_pw_page)
except ImportError:
    # API-only 项目没有 pages/ 目录时，page fixture 保持默认（裸 Playwright Page）
    pass
