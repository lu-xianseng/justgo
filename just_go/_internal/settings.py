#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/8/21 17:30
# @Author   :luye
import os
import shutil
from configparser import ConfigParser, SectionProxy
from typing import Any, Dict, Optional


class SectionWrapper:
    """封装配置文件中的单个节，提供属性式访问与运行时覆盖

    支持用户编程式设置：config.run.slow_time = 1000（写入缓存，运行时生效，
    优先于 config.ini 文件值）。可在测试项目 conftest.py 顶部导入赋值。
    """

    def __init__(self, section: SectionProxy):
        """初始化节包装器并转换布尔值配置项"""
        self._section = section
        self._cache: Dict[str, Any] = {}

        # 预解析所有配置项
        for option in section:
            self._parse_and_cache(option)

    def __setattr__(self, name: str, value: Any) -> None:
        """支持用户覆盖配置：写入缓存（_section/_cache 等内部属性走默认逻辑）"""
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        self._cache[name] = value

    def _parse_and_cache(self, option: str) -> None:
        """解析配置值并缓存结果"""
        value = self._section[option].lower()
        if value == "true":
            self._cache[option] = True
        elif value == "false":
            self._cache[option] = False
        else:
            self._cache[option] = self._section[option]

    def __getattr__(self, name: str) -> Any:
        """获取配置值，支持属性式访问"""
        if name in self._cache:
            return self._cache[name]

        # 检查配置项是否存在
        if name in self._section:
            self._parse_and_cache(name)
            return self._cache[name]

        # 配置项不存在，尝试访问SectionProxy的原生属性或方法
        try:
            return getattr(self._section, name)
        except AttributeError:
            raise AttributeError(f"配置节 '{self._section.name}' 中没有配置项 '{name}'")


class ConfigWrapper:
    """封装ConfigParser，为每个节创建SectionWrapper"""

    def __init__(self, config: ConfigParser):
        """初始化配置包装器，为每个节创建包装器"""
        self._config = config
        self._sections: Dict[str, SectionWrapper] = {}

        # 为每个节创建SectionWrapper
        for section in config.sections():
            self._sections[section] = SectionWrapper(config[section])

    def __getattr__(self, name: str) -> SectionWrapper:
        """获取配置节，支持属性式访问"""
        if name in self._sections:
            return self._sections[name]

        # 尝试访问ConfigParser的原生属性或方法
        try:
            return getattr(self._config, name)
        except AttributeError:
            raise AttributeError(f"配置中没有节 '{name}'")

    def get_section(self, section_name: str) -> Optional[SectionWrapper]:
        """获取指定名称的配置节，不存在时返回None"""
        return self._sections.get(section_name)


# just_go 包目录：框架自带 configs/、templates/ 都在它下面，
# 工具类配置的相对路径（allure_path / ffmpeg_path）也基于此解析
FRAMEWORK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 测试项目根目录：运行时通过 CLI 指定（环境变量 JUSTGO_PROJECT_ROOT 优先，否则取当前工作目录）
ROOTDIR = os.environ.get("JUSTGO_PROJECT_ROOT") or os.getcwd()

config_parser = ConfigParser()
config_path = os.path.join(FRAMEWORK_ROOT, "configs", "config.ini")
# 先读框架默认配置，再用测试项目根下的 config.ini 叠加（后读的覆盖同名项）。
# 用户装的是 site-packages 里的框架，改不了也不该改框架自带配置，
# 项目差异一律写到 <项目根>/config.ini，只写要改的项，其余沿用框架默认。
config_parser.read(filenames=config_path, encoding="utf-8")
project_config_path = os.path.join(ROOTDIR, "config.ini")
if os.path.isfile(project_config_path):
    config_parser.read(filenames=project_config_path, encoding="utf-8")
config = ConfigWrapper(config_parser)

# 产物输出根目录：默认跟随测试项目根；发布/CI 场景可通过 JUSTGO_OUTPUT_ROOT 重定向，
# 指定时按项目名分子目录输出（logs/reports/cache），多个项目互不串扰
OUTPUT_ROOT = os.environ.get("JUSTGO_OUTPUT_ROOT") or ROOTDIR

# 项目标识名：用于 OUTPUT_ROOT 下的产物子目录（JUSTGO_PROJECT_NAME 优先，否则取项目根目录名）
PROJECT_NAME = os.environ.get("JUSTGO_PROJECT_NAME") or os.path.basename(ROOTDIR)

# 产物基准目录：未指定输出根时直接位于项目根（保持拆分前行为），指定时位于 输出根/项目名
OUTPUT_BASE = (
    os.path.join(OUTPUT_ROOT, PROJECT_NAME) if OUTPUT_ROOT != ROOTDIR else ROOTDIR
)

# 运行产物（日志/报告/缓存）
TEMP_PATH = os.path.join(OUTPUT_BASE, config.framework.cache_path, "temp")
LOG_PATH = os.path.join(OUTPUT_BASE, config.framework.log_path)
TMP_REPORT_PATH = os.path.join(OUTPUT_BASE, config.framework.cache_path, "report")
REPORT_PATH = os.path.join(OUTPUT_BASE, config.framework.report_path)

# allure 工具解析优先级：
# 1) config.framework.allure_path 为绝对路径 → 直接使用；
# 2) 为相对路径 → 基于框架根解析（兼容旧版随框架内置的配置）；
# 3) 留空 → 自动查找：PATH 上的 allure 命令，其次用户目录 ~/.just-go/allure/*/bin
#    （just-go install allure 的安装位置）。都找不到时返回空串，报告生成降级跳过。
def _resolve_allure_path() -> str:
    import glob

    _configured = (config.framework.allure_path or "").strip()
    if _configured:
        candidate = (
            _configured
            if os.path.isabs(_configured)
            else os.path.join(FRAMEWORK_ROOT, _configured)
        )
        if os.path.exists(candidate):
            return candidate

    # 自动查找：PATH 上的 allure 命令
    found = shutil.which("allure")
    if found:
        return found

    # 用户目录安装（just-go install allure 的安装位置），多版本并存时取最新
    user_allure_dir = os.path.join(os.path.expanduser("~"), ".just-go", "allure")
    exe_name = "allure.bat" if os.name == "nt" else "allure"
    hits = sorted(
        glob.glob(os.path.join(user_allure_dir, "*", "bin", exe_name)),
        key=_version_key,
    )
    if hits:
        return hits[-1]
    return ""


def _version_key(path: str) -> tuple:
    """按 (主, 次, 修订) 数值排序版本目录（避免 2.9.0 排在 2.10.0 之后的字典序问题）"""
    import re as _re

    dir_name = os.path.basename(os.path.dirname(os.path.dirname(path)))
    nums = _re.findall(r"\d+", dir_name)
    return tuple(int(n) for n in nums[:3]) or (0, 0, 0)


ALLURE_PATH = _resolve_allure_path()


# ffmpeg 工具解析优先级（桌面录屏）：
# 1) config.framework.ffmpeg_path 为绝对路径 → 直接使用；
# 2) 为相对路径 → 基于框架根解析；
# 3) 留空 → 自动查找：PATH 上的 ffmpeg 命令，其次用户目录 ~/.just-go/ffmpeg
#    （just-go install ffmpeg 的共享安装位置，一次安装供所有项目与虚拟环境复用）。
#    都找不到时返回空串，录屏启动时抛出带安装指引的异常。
def _resolve_ffmpeg_path() -> str:
    _configured = (getattr(config.framework, "ffmpeg_path", "") or "").strip()
    if _configured:
        candidate = (
            _configured
            if os.path.isabs(_configured)
            else os.path.join(FRAMEWORK_ROOT, _configured)
        )
        if os.path.exists(candidate):
            return candidate

    # 自动查找：PATH 上的 ffmpeg（系统已安装时直接复用，不额外下载）
    found = shutil.which("ffmpeg")
    if found:
        return found

    # 共享安装位置：just-go install ffmpeg 下载的二进制，所有项目通用
    user_ffmpeg_dir = os.path.join(os.path.expanduser("~"), ".just-go", "ffmpeg")
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    candidate = os.path.join(user_ffmpeg_dir, exe_name)
    if os.path.exists(candidate):
        return candidate
    return ""


FFMPEG_PATH = _resolve_ffmpeg_path()


# 图像识别模板图的解析根：就是测试项目根目录。
# 模板图放哪、用什么目录名由用户自己拼（如 "images/btn"、"assets/img/btn"），框架不预设目录。
IMAGE_PATH = ROOTDIR
