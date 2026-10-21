#!/usr/bin/env python3
# coding=utf-8
"""测试项目根 conftest：让 just-go 框架插件生效，并向框架注入本项目配置。

按你的项目填写：
- JUSTGO_TEST_BASE_URL：被测系统实际地址（写入报告环境信息；页面对象跳转时也读取它）
- JUSTGO_TEST_CASE_BASE_URL：测试管理平台（如禅道）用例链接前缀，写入报告用例链接（可选）

可选配置（在项目里改，不用动框架）：
- 录屏：pytest.ini 的 --record=yes 开启 ffmpeg 桌面录屏（需系统已安装 ffmpeg）
- 其他框架配置项也可在此赋值：config.run.slow_time、config.run.show_browser 等
"""
import os

from just_go import config

# 多环境被测地址（按需增删）：运行 `just-go run <名称> --env prod`（或 pytest --env prod）切换，默认 dev
BASE_URLS = {
    "dev": "http://192.168.1.10:8080",   # TODO: 填写实际地址
    "test": "http://test.example.com",   # TODO
    "prod": "https://www.example.com",   # TODO
}
ENV = os.environ.get("JUSTGO_ENV", "dev")
os.environ.setdefault("JUSTGO_TEST_BASE_URL", BASE_URLS.get(ENV, BASE_URLS["dev"]))
# TODO: 可选，例如 https://zentao.example.com/case-view-{id}.html
os.environ.setdefault("JUSTGO_TEST_CASE_BASE_URL", "")

# 示例：慢速操作等待毫秒数 / 无头模式 / 浏览器类型 / 登录态复用
# config.run.slow_time = 1000
# config.run.show_browser = False
# config.run.browser_type = "chromium"   # chromium / firefox / webkit
# config.run.storage_state = "state.json"  # 复用登录态：登录用例里执行
#                                            # page.context.storage_state(path="state.json") 保存

pytest_plugins = ["just_go.plugin"]
