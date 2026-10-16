#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:20
# @Author   :luye
import os.path

from lets_go.browser_utils import *
from lets_go.request_utils import *
from lets_go.assertion import AssertCommon
from lets_go.controller import CaseControl
from lets_go.logger import *
from lets_go.tag_manage import *
from lets_go.tools import *
from lets_go.settings import *
from lets_go.mock import *

if os.path.exists(TMP_REPORT_PATH):
    shutil.rmtree(TMP_REPORT_PATH)

folder_list = [LOG_PATH, TEMP_PATH, REPORT_PATH, TMP_REPORT_PATH]
for folder in folder_list:
    if not os.path.exists(folder):
        os.makedirs(folder)
