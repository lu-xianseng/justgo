#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/7/30 13:31
# @Author   :luye


class SoftwareNotInstallError(Exception):
    def __init__(self, software_name):
        super().__init__(f"'{software_name}' Not install")


class FileNotExistsError(Exception):
    def __init__(self, file):
        super().__init__(f"'{file}' Not Exists")


class CaseError(Exception):
    def __init__(self, msg):
        super().__init__(msg)
