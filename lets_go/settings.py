#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/8/21 17:30
# @Author   :luye
import os
from configparser import ConfigParser
from typing import Optional, Dict, Any

import allure


class SectionWrapper:
    """封装配置文件中的单个节，提供属性式访问"""

    def __init__(self, section: ConfigParser.sections):
        """初始化节包装器并转换布尔值配置项"""
        self._section = section
        self._cache: Dict[str, Any] = {}

        # 预解析所有配置项
        for option in section:
            self._parse_and_cache(option)

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


config_parser = ConfigParser()
config_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "configs", "config.ini"
)
config_parser.read(filenames=config_path, encoding="utf-8")
config = ConfigWrapper(config_parser)

# 框架根目录：lets_go 包所在项目的上级（tools/allure 等框架资源随框架走）
FRAMEWORK_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 测试项目根目录：运行时通过 CLI 指定（环境变量 LETSGO_PROJECT_ROOT 优先，否则取当前工作目录）
ROOTDIR = os.environ.get("LETSGO_PROJECT_ROOT") or os.getcwd()

# 产物输出根目录：默认跟随测试项目根；发布/CI 场景可通过 LETSGO_OUTPUT_ROOT 重定向，
# 指定时按项目名分子目录输出（logs/reports/cache），多个项目互不串扰
OUTPUT_ROOT = os.environ.get("LETSGO_OUTPUT_ROOT") or ROOTDIR

# 项目标识名：用于 OUTPUT_ROOT 下的产物子目录（LETSGO_PROJECT_NAME 优先，否则取项目根目录名）
PROJECT_NAME = os.environ.get("LETSGO_PROJECT_NAME") or os.path.basename(ROOTDIR)

# 产物基准目录：未指定输出根时直接位于项目根（保持拆分前行为），指定时位于 输出根/项目名
OUTPUT_BASE = (
    os.path.join(OUTPUT_ROOT, PROJECT_NAME) if OUTPUT_ROOT != ROOTDIR else ROOTDIR
)

# 运行产物（日志/报告/缓存）
TEMP_PATH = os.path.join(OUTPUT_BASE, config.framework.cache_path, "temp")
LOG_PATH = os.path.join(OUTPUT_BASE, config.framework.log_path)
TMP_REPORT_PATH = os.path.join(OUTPUT_BASE, config.framework.cache_path, "report")
REPORT_PATH = os.path.join(OUTPUT_BASE, config.framework.report_path)

# allure 工具随框架安装位置走：相对路径基于框架根解析，绝对路径直接使用
_allure_path = config.framework.allure_path
ALLURE_PATH = (
    _allure_path
    if os.path.isabs(_allure_path)
    else os.path.join(FRAMEWORK_ROOT, _allure_path)
)
