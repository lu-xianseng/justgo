"""核心工具：配置、日志、mock 数据、用例控制、环境切换。

用法：
    from just_go.core import config, logger, log, CaseControl, setup_env

    setup_env({"dev": "http://192.168.1.10:8080", "prod": "https://example.com"})
    logger.info("开始执行")
    base_url = config.run.base_url
"""
import os

from just_go._internal.controller import CaseControl
from just_go._internal.logger import log, logger
from just_go._internal.settings import config

__all__ = ["config", "logger", "log", "CaseControl", "setup_env"]


def setup_env(base_urls: dict, case_base_url: str = "") -> None:
    """根据运行环境设置被测系统地址。

    在项目 conftest.py 顶部调用，传入多环境地址字典即可，
    框架自动根据 --env 参数（JUSTGO_ENV 环境变量）选择对应地址。

    Args:
        base_urls: 环境地址字典，如 {"dev": "http://...", "prod": "https://..."}
        case_base_url: 测试管理平台用例链接前缀（可选），如禅道地址
    """
    env = os.environ.get("JUSTGO_ENV", "dev")
    os.environ.setdefault(
        "JUSTGO_TEST_BASE_URL", base_urls.get(env, base_urls.get("dev", ""))
    )
    os.environ.setdefault("JUSTGO_TEST_CASE_BASE_URL", case_base_url)
