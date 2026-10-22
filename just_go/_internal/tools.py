#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/6/25 17:02
# @Author   :luye
import os
import platform
import re
import shutil
import subprocess
import time
from importlib.metadata import version
from typing import Optional

import allure
import pytest

from just_go._internal.errors import RecordError, SoftwareNotInstallError
from just_go._internal.settings import (
    ALLURE_PATH,
    PROJECT_NAME,
    REPORT_PATH,
    TMP_REPORT_PATH,
    config,
)


class GenerateReport:
    LEVEL_MAP = {
        "L1": allure.severity_level.BLOCKER,
        "L2": allure.severity_level.CRITICAL,
        "L3": allure.severity_level.NORMAL,
        "L4": allure.severity_level.MINOR,
        "L5": allure.severity_level.TRIVIAL,
    }
    _registered_markers = set()  # 跨用例去重，避免重复注册 marker 警告

    def __init__(self):
        self.__report_path = None
        self.__cmd = None
        self.single_file = True

    @staticmethod
    def _allure_version() -> tuple:
        """解析 allure CLI 版本号（allure --version 输出如 2.30.0 -> (2, 30, 0)）"""
        try:
            r = subprocess.run(
                [ALLURE_PATH, "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            m = re.search(r"(\d+)\.(\d+)\.(\d+)", r.stdout or r.stderr or "")
            if m:
                return tuple(int(x) for x in m.groups())
        except (OSError, subprocess.TimeoutExpired):
            pass
        return (0, 0, 0)

    @property
    def report_name(self) -> str:
        """报告标题：config.ini [framework] report_name 优先，缺省用被测项目名"""
        return (
            (config.framework.report_name or "").strip()
            or PROJECT_NAME
        )

    @property
    def report_language(self) -> str:
        """报告语言：config.ini [framework] report_language（默认 zh 中文）"""
        return (config.framework.report_language or "zh").strip() or "zh"

    def _build_cmd(self) -> list:
        """组装 allure generate 命令（按版本自动启用新选项）

        - --single-file：单文件 HTML 报告（allure >= 2.24 支持，实测 2.24.1 可用）
        - --name / --lang：报告标题与语言（allure 2.24-2.29 曾移除，2.30 恢复；
          老版本不传，避免被误当成结果目录参数）
        """
        cmd = [
            ALLURE_PATH,
            "generate",
            TMP_REPORT_PATH,
            "-c",
            "-o",
            self.__report_path,
        ]
        ver = self._allure_version()
        if self.single_file and ver >= (2, 24, 0):
            cmd.append("--single-file")
        if ver >= (2, 30, 0):
            cmd += ["--name", self.report_name, "--lang", self.report_language]
        return cmd

    @staticmethod
    def set_report_env():
        allure_env = {
            "PythonVersion": platform.python_version(),
            "Platform": platform.platform(),
            "PytestVersion": pytest.__version__,
            "PlaywrightVersion": version("playwright"),
            "RequestsVersion": version("requests"),
        }
        # 被测系统地址属于测试项目，由测试项目通过环境变量注入，未配置时省略
        test_base_url = os.environ.get("JUSTGO_TEST_BASE_URL")
        if test_base_url:
            allure_env["OperatingEnvironment"] = test_base_url
        if not os.path.exists(TMP_REPORT_PATH):
            os.makedirs(TMP_REPORT_PATH, exist_ok=True)
        allure_env_file = os.path.join(TMP_REPORT_PATH, "environment.properties")
        with open(allure_env_file, "w", encoding="utf-8") as f:
            for _k, _v in allure_env.items():
                f.write(f"{_k}={_v}\n")
        return allure_env

    def run(self):
        self.set_report_env()
        if not ALLURE_PATH:
            # allure 工具未安装（外部工具，与框架解耦）：降级为只保留 allure 原始结果
            print("\n[just-go] 未找到 allure 工具，跳过 HTML 报告生成。")
            print(f"[just-go] allure 原始结果已保留：{TMP_REPORT_PATH}")
            print("[just-go] 运行 `just-go install allure` 安装报告工具后，重新执行测试即可生成 HTML 报告。")
            return
        self.__report_path = os.path.join(
            REPORT_PATH, time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        )
        if not os.path.exists(self.__report_path):
            os.makedirs(self.__report_path)
        self.__cmd = self._build_cmd()
        res = subprocess.Popen(
            self.__cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out_bytes, err_bytes = res.communicate()
        out_bytes = out_bytes if res.returncode == 0 else err_bytes
        try:
            out = out_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Windows 中文系统下 allure 输出为系统代码页（GBK），utf-8 解码失败时回退
            out = out_bytes.decode("gbk", errors="replace")
        print(f"\n\n{out}")

    def add_mark(self, item, item_config, tags):
        level = tags.get("用例级别", "").upper()
        # 用例级别缺失/非法时降级为 NORMAL，避免收集阶段 KeyError 崩溃
        item.add_marker(
            allure.severity(self.LEVEL_MAP.get(level, allure.severity_level.NORMAL))
        )
        # 禅道用例地址属于测试项目，由测试项目通过环境变量注入，未配置时跳过用例链接
        test_case_base_url = os.environ.get("JUSTGO_TEST_CASE_BASE_URL")
        if test_case_base_url:
            item.add_marker(
                allure.testcase(
                    f"{test_case_base_url}/index.php?m=testcase&f=view&caseID={tags.get('用例ID')}"
                )
            )
        item.add_marker(allure.epic(tags.get("测试分类")))
        item.add_marker(allure.feature(tags.get("场景分类")))
        item.add_marker(allure.story(tags.get("场景描述")))
        for attr, value in tags.items():
            if value and attr not in ["用例ID", "跳过原因"]:
                if value not in self._registered_markers:
                    self._registered_markers.add(value)
                    item_config.addinivalue_line("markers", f"{value}: {value}")
                item.add_marker(getattr(pytest.mark, value))


generate_report = GenerateReport()


class Record:
    """
    录屏管理器：统一调用系统 ffmpeg 抓取桌面，产出 mp4/webm。
    - Windows：gdigrab 抓取整个桌面
    - Linux：x11grab 抓取 X11 显示服务器（默认 :0，可用 DISPLAY 环境变量覆盖）
    需要系统已安装 ffmpeg（`just-go install ffmpeg` 自动安装或手动加入 PATH）。
    """

    def __init__(self, framerate=10, source="desktop", out_type="mp4"):
        self.__exe = None
        if out_type not in ["webm", "mp4"]:
            raise ValueError("out_type must be webm or mp4")
        self.__out_type = out_type
        self.__framerate = framerate
        self.__source = source
        self.__base_cmd = []
        self.__cmd = ""
        self.__process: Optional[subprocess.Popen] = None
        self.__out_file = None
        self.__recording = False

    @property
    def attachment_type(self):
        """allure 附件类型：ffmpeg 产出 mp4/webm"""
        return allure.attachment_type.MP4 if self.__out_type == "mp4" else allure.attachment_type.WEBM

    def _ensure_ffmpeg(self):
        """确认 ffmpeg 可用并构造基础命令"""
        if self.__exe:
            return
        self.__exe = shutil.which("ffmpeg")
        if not self.__exe:
            raise SoftwareNotInstallError("ffmpeg")
        # 按平台选择抓屏后端：Windows 用 gdigrab（抓整个桌面），Linux 用 x11grab（X11 显示）
        if os.name == "nt":
            input_args = [
                "-f", "gdigrab",
                "-framerate", f"{self.__framerate}",
                "-i", f"{self.__source}",
            ]
        else:
            display = os.environ.get("DISPLAY") or ":0"
            input_args = [
                "-f", "x11grab",
                "-framerate", f"{self.__framerate}",
                "-i", display,
            ]
        if self.__out_type == "mp4":
            self.__base_cmd = [
                self.__exe,
                "-loglevel", "error",
                *input_args,
                "-vf",
                "format=yuv420p",
                "-c:v",
                "libx264",
                "-crf",
                "23",
                "-b:v",
                "200k",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
            ]
        if self.__out_type == "webm":
            self.__base_cmd = [
                self.__exe,
                "-loglevel", "error",
                *input_args,
                "-vf",
                "format=yuv420p",
                "-c:v",
                "libvpx",
                "-crf",
                "23",
                "-b:v",
                "200k",
                "-c:a",
                "libvorbis",
            ]

    @property
    def __generate_name(self):
        return f"{time.time()}.{self.__out_type}"

    def start(self, path):
        """启动录屏（ffmpeg：Windows gdigrab / Linux x11grab 抓取桌面）"""
        if not self.__recording:
            self._ensure_ffmpeg()
            self.__out_file = os.path.join(path, self.__generate_name)
            self.__cmd = self.__base_cmd + [self.__out_file]
            self.__process = subprocess.Popen(
                self.__cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if self.__process.poll() is not None:
                stderr = self.__process.stderr.read()
                raise RecordError(f"录屏启动失败: {stderr}")
            time.sleep(0.1)
            self.__recording = True

    def stop(self):
        """停止录屏（未开始录制时静默，避免 teardown 因启动失败被二次报错）"""
        if not self.__recording:
            return
        try:
            self.__process.stdin.write("q\n")
            self.__process.stdin.flush()
            try:
                self.__process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.__process.terminate()
                self.__process.wait(timeout=2)

        except BrokenPipeError:
            pass
        except Exception as e:
            print(f"停止录屏时出错: {e}")
        finally:
            self.__recording = False
            if self.__process is not None:
                for stream in (self.__process.stdin, self.__process.stdout, self.__process.stderr):
                    try:
                        stream.close()
                    except (AttributeError, OSError):
                        pass
            self.__process = None

    def restart(self, path):
        """重启录屏"""
        self.stop()
        temp = self.__out_file
        if temp and os.path.exists(temp):
            os.remove(temp)
        self.start(path)

    @property
    def record_file(self):
        """获取录屏文件"""
        if not self.__out_file:
            return None
        if os.path.exists(self.__out_file):
            return self.__out_file
        return None


record = Record()
