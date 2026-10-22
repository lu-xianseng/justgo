#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:20
# @Author   :luye
"""just-go 测试框架。

分类导入入口：
    from just_go._internal.web import SyncWebUI, AsyncWebUI                        # 页面对象基类
    from just_go._internal.asserts import AssertCommon, SyncAssert, AsyncAssert  # 断言
    from just_go._internal.http import Request                                     # HTTP 请求
    from just_go._internal.data import load_json_cases, load_csv_cases            # 数据驱动
    from just_go.core import config, logger, log, mock, CaseControl     # 配置/日志/mock
    from just_go._internal.errors import JustGoError, RequestError                 # 异常
"""
import os
import shutil

from just_go._internal.settings import LOG_PATH, REPORT_PATH, TEMP_PATH, TMP_REPORT_PATH

if os.path.exists(TMP_REPORT_PATH):
    shutil.rmtree(TMP_REPORT_PATH)

for folder in (LOG_PATH, TEMP_PATH, REPORT_PATH, TMP_REPORT_PATH):
    if not os.path.exists(folder):
        os.makedirs(folder)
