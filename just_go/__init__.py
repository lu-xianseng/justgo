#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:20
# @Author   :luye
import os.path

from just_go.browser_utils import *
from just_go.request_utils import *
from just_go.assertion import AssertCommon
from just_go.controller import CaseControl
from just_go.logger import *
from just_go.tag_manage import *
from just_go.tools import *
from just_go.settings import *
from just_go.mock import *

if os.path.exists(TMP_REPORT_PATH):
    shutil.rmtree(TMP_REPORT_PATH)

folder_list = [LOG_PATH, TEMP_PATH, REPORT_PATH, TMP_REPORT_PATH]
for folder in folder_list:
    if not os.path.exists(folder):
        os.makedirs(folder)
