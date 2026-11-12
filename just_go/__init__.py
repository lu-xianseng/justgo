#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:20
# @Author   :luye
"""just-go 测试框架。

分类导入入口：
    from just_go.web import SyncWebUI, AsyncWebUI, Element, element           # 页面对象/元素封装
    from just_go.asserts import AssertCommon, SyncAssert, AsyncAssert         # 断言
    from just_go.http import Request                                          # HTTP 请求
    from just_go.data import load_json_cases, load_csv_cases, mock            # 数据驱动/mock
    from just_go.config import config, setup_env                              # 配置与环境切换
    from just_go.log import log                                               # 日志（带用例标识）
    from just_go.case import CaseControl                                      # 用例命名校验
    from just_go.image import find_image, wait_image                          # 屏幕找图（可选依赖）
    from just_go.errors import JustGoError, RequestError                      # 异常
"""
import os
import shutil

from just_go._internal.settings import LOG_PATH, REPORT_PATH, TEMP_PATH, TMP_REPORT_PATH

if os.path.exists(TMP_REPORT_PATH):
    shutil.rmtree(TMP_REPORT_PATH)

for folder in (LOG_PATH, TEMP_PATH, REPORT_PATH, TMP_REPORT_PATH):
    if not os.path.exists(folder):
        os.makedirs(folder)
