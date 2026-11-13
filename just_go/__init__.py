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

# 这里刻意不做任何目录创建 / 清理。
# 旧实现会在 import 时无条件 shutil.rmtree(TMP_REPORT_PATH) 并创建四个产物目录，
# 导致 IDE 索引、`just-go --help`、以及另一个进程正在跑测试时都会删除
# 正在使用的报告目录；产物目录只读时更会直接让 import 失败。
# 目录改由真正使用它们的时机创建：
#   LOG_PATH          -> CustomLogger 初始化（写日志前）
#   TMP_REPORT_PATH   -> pytest_configure（会话开始，此时才允许清理上一轮结果）
#   TEMP_PATH         -> 录屏启动前 / 失败截图前
#   REPORT_PATH       -> 生成 HTML 报告前

