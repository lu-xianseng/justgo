#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/6/20 15:11
# @Author   :luye
import os
from faker import Faker
from just_go.settings import ROOTDIR


class MockData:
    def __init__(self, locale="zh_CN"):
        self.fake: Faker = Faker(locale=locale)

    @staticmethod
    def get_file_path(filename):
        """根据文件名获取绝对路径"""
        for root, dirs, files in os.walk(ROOTDIR):
            if filename in files:
                return os.path.join(root, filename)
        return None


mock = MockData()
