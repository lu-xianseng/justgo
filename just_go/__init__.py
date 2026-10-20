#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:20
# @Author   :luye
import os
import shutil

from just_go.assertion import AssertCommon

# 统一导出：`from just_go import *` 或按需 `from just_go import config, logger, ParseTag`
from just_go.browser_utils import (
    APIResponse,
    APIResponseAssertions,
    Locator,
    LocatorAssertions,
    Page,
    PageAssertions,
    Response,
    WebUI,
    expect,
    sync_playwright,
)
from just_go.controller import CaseControl
from just_go.data import load_csv_cases, load_json_cases
from just_go.exceptions import (
    BrowserError,
    CaseError,
    ConfigError,
    FileNotExistsError,
    JustGoError,
    RecordError,
    RequestError,
    SoftwareNotInstallError,
    TagError,
)
from just_go.logger import CustomLogger, custom_logger, get_logger, log, logger
from just_go.mock import MockData, mock
from just_go.parse_tag import ParseTag, UpdateTag
from just_go.request_utils import Request
from just_go.settings import (
    ALLURE_PATH,
    FRAMEWORK_ROOT,
    LOG_PATH,
    OUTPUT_BASE,
    OUTPUT_ROOT,
    PROJECT_NAME,
    REPORT_PATH,
    ROOTDIR,
    TEMP_PATH,
    TMP_REPORT_PATH,
    config,
    config_parser,
)
from just_go.tools import GenerateReport, Record, generate_report, record

__all__ = [
    # browser_utils
    "WebUI", "Page", "Response", "expect", "Locator", "APIResponse",
    "PageAssertions", "LocatorAssertions", "APIResponseAssertions", "sync_playwright",
    # request_utils
    "Request",
    # assertion / controller
    "AssertCommon", "CaseControl",
    # data
    "load_json_cases", "load_csv_cases",
    # logger
    "CustomLogger", "logger", "custom_logger", "log", "get_logger",
    # parse_tag
    "ParseTag", "UpdateTag",
    # tools
    "GenerateReport", "Record", "generate_report", "record",
    # settings
    "ALLURE_PATH", "FRAMEWORK_ROOT", "LOG_PATH", "OUTPUT_BASE", "OUTPUT_ROOT",
    "PROJECT_NAME", "REPORT_PATH", "ROOTDIR", "TEMP_PATH", "TMP_REPORT_PATH",
    "config", "config_parser",
    # exceptions
    "BrowserError", "CaseError", "ConfigError", "FileNotExistsError", "JustGoError",
    "RecordError", "RequestError", "SoftwareNotInstallError", "TagError",
    # mock
    "MockData", "mock",
]

if os.path.exists(TMP_REPORT_PATH):
    shutil.rmtree(TMP_REPORT_PATH)

folder_list = [LOG_PATH, TEMP_PATH, REPORT_PATH, TMP_REPORT_PATH]
for folder in folder_list:
    if not os.path.exists(folder):
        os.makedirs(folder)
