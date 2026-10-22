#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/6/20 15:11
# @Author   :luye
import os

from faker import Faker

from just_go._internal.settings import ROOTDIR


class MockData:
    def __init__(self, locale="zh_CN"):
        self.fake: Faker = Faker(locale=locale)

    # 运行产物 / 虚拟环境目录：查找时跳过，避免深挖无用子树（尤其 ROOTDIR
    # 解析异常指向盘符根时，可避免误扫整个磁盘）
    _SKIP_DIRS = {
        ".git", ".venv", "venv", "node_modules", "__pycache__",
        ".pytest_cache", "cache", "logs", "reports", "temp",
    }

    @classmethod
    def get_file_path(cls, filename, base_dir=None):
        """在被测项目根下按文件名查找，返回绝对路径；找不到返回 None。

        Args:
            filename: 目标文件名（含扩展名）
            base_dir: 指定搜索目录（绝对路径）；缺省使用被测项目根 ROOTDIR。
                      只在被测项目内查找，并跳过运行产物/虚拟环境目录。
        """
        root = os.path.abspath(base_dir or ROOTDIR)
        if not os.path.isdir(root):
            return None
        for dirpath, dirs, files in os.walk(root):
            # 剪枝：跳过隐藏目录与运行产物/虚拟环境目录
            dirs[:] = [
                d for d in dirs
                if d not in cls._SKIP_DIRS and not d.startswith(".")
            ]
            if filename in files:
                return os.path.join(dirpath, filename)
        return None


mock = MockData()
