"""配置与环境切换
"""
import os
import sys

from just_go._internal.settings import config

__all__ = ["config", "setup_env", "apply_env"]

# 环境标识 → 被测地址；None 表示还没调用过 setup_env()
_env_base_urls: dict = None
_env_case_base_url = ""

#: 由本模块写入的环境变量值，用于区分「框架写的」与「用户显式设置的」：
#: 用户自己 export 的 JUSTGO_TEST_BASE_URL 必须优先，不能被 --env 覆盖
_managed_env = {}

_BASE_URL_ENV = "JUSTGO_TEST_BASE_URL"
_CASE_BASE_URL_ENV = "JUSTGO_TEST_CASE_BASE_URL"


def _env_from_argv(argv=None):
    """从命令行参数里取 --env 的值（setup_env 执行时 pytest 还没解析参数）"""
    args = list(sys.argv[1:] if argv is None else argv)
    for index, arg in enumerate(args):
        if arg == "--env" and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--env="):
            return arg.split("=", 1)[1]
    return None


def _set_managed(name, value):
    """写入环境变量，但不覆盖用户自己设置的值"""
    current = os.environ.get(name)
    if current and current != _managed_env.get(name):
        return False
    os.environ[name] = value
    _managed_env[name] = value
    return True


def apply_env(env: str = None) -> None:
    """按当前环境标识刷新被测地址环境变量。

    Args:
        env: 环境标识（如 prod）。传了就先写入 JUSTGO_ENV，再据此取地址；
             不传则沿用已有的 JUSTGO_ENV（缺省 dev）

    幂等：用户显式设置过 JUSTGO_TEST_BASE_URL 时保持用户值不变。
    setup_env() 没被调用过时只更新 JUSTGO_ENV，不做其它事。
    """
    if env:
        os.environ["JUSTGO_ENV"] = env
    if _env_base_urls is None:
        return
    current = os.environ.get("JUSTGO_ENV") or "dev"
    base_url = _env_base_urls.get(current, _env_base_urls.get("dev", ""))
    _set_managed(_BASE_URL_ENV, base_url)
    _set_managed(_CASE_BASE_URL_ENV, _env_case_base_url)


def setup_env(base_urls: dict, case_base_url: str = "") -> None:
    """根据运行环境设置被测系统地址。

    在项目 conftest.py 顶部调用，传入多环境地址字典即可，
    框架自动根据 --env 参数（JUSTGO_ENV 环境变量）选择对应地址。

    setup_env() 执行时 pytest 尚未解析 --env，这里先从命令行原样取一次；
    插件随后在 pytest_configure 用解析后的值再调 apply_env()，两者共同
    保证 `just-go run demo --env prod` / `pytest --env prod` 都能切到对应地址。

    Args:
        base_urls: 环境地址字典，如 {"dev": "http://...", "prod": "https://..."}
        case_base_url: 测试管理平台用例链接前缀（可选），如禅道地址
    """
    global _env_base_urls, _env_case_base_url
    _env_base_urls = dict(base_urls or {})
    _env_case_base_url = case_base_url or ""
    # JUSTGO_ENV 可能是插件提前写入的，也可能是命令行直接给的（conftest 早于解析）
    if not os.environ.get("JUSTGO_ENV"):
        argv_env = _env_from_argv()
        if argv_env:
            os.environ["JUSTGO_ENV"] = argv_env
    apply_env()
