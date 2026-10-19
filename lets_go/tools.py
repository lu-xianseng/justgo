#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/6/25 17:02
# @Author   :luye
import os
import platform
import time
import shutil
import subprocess
from typing import Optional

import pytest
import allure
from importlib.metadata import version
from lets_go.settings import TMP_REPORT_PATH, REPORT_PATH, ROOTDIR, ALLURE_PATH, config
from lets_go.exceptions import SoftwareNotInstallError


class GenerateReport:
    LEVEL_MAP = {
        "L1": allure.severity_level.BLOCKER,
        "L2": allure.severity_level.CRITICAL,
        "L3": allure.severity_level.NORMAL,
        "L4": allure.severity_level.MINOR,
        "L5": allure.severity_level.TRIVIAL,
    }

    def __init__(self):
        self.__report_path = (
            rf"{REPORT_PATH}\{time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())}"
        )
        if not os.path.exists(self.__report_path):
            os.makedirs(self.__report_path)
        self.__cmd = [
            ALLURE_PATH,
            "generate",
            TMP_REPORT_PATH,
            # 注意：allure 2.24+ 已移除 generate 的 --lang/--name 选项（移入
            # profile 配置文件），旧参数会被误当成结果目录。只保留通用选项
            # -c(清理) -o(输出目录)，兼容所有 allure 2.x 版本。
            "-c",
            "-o",
            self.__report_path,
        ]

    def __del__(self):
        try:
            shutil.rmtree(TMP_REPORT_PATH)
        except FileNotFoundError:
            ...

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
        test_base_url = os.environ.get("LETSGO_TEST_BASE_URL")
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
            print("\n[lets-go] 未找到 allure 工具，跳过 HTML 报告生成。")
            print(f"[lets-go] allure 原始结果已保留：{TMP_REPORT_PATH}")
            print("[lets-go] 运行 `lets-go install allure` 安装报告工具后，重新执行测试即可生成 HTML 报告。")
            return
        res = subprocess.Popen(
            self.__cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out_bytes = res.stdout.read() if res.wait() == 0 else res.stderr.read()
        try:
            out = out_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Windows 中文系统下 allure 输出为系统代码页（GBK），utf-8 解码失败时回退
            out = out_bytes.decode("gbk", errors="replace")
        print(f"\n\n{out}")

    def add_mark(self, item, item_config, tags):
        level = tags.get("用例级别", "").upper()
        item.add_marker(allure.severity(self.LEVEL_MAP[level]))
        # 禅道用例地址属于测试项目，由测试项目通过环境变量注入，未配置时跳过用例链接
        test_case_base_url = os.environ.get("LETSGO_TEST_CASE_BASE_URL")
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
            if value and attr not in ["用例ID", "跳过原因", "废弃"]:
                item_config.addinivalue_line("markers", f"{value}: {value}")
                marker = getattr(pytest.mark, value, None)
                if marker:
                    item.add_marker(marker)


generate_report = GenerateReport()


class Record:
    """
    录屏管理器，支持两种后端（由 config.ini [run] record_backend 指定）：
    - playwright（默认，轻量）：Playwright 内置录屏产出 webm，无需安装 ffmpeg，
      录制由 page fixture 通过 record_video_dir 控制，视频文件在浏览器关闭后
      由 fixture 写入 record_file；
    - ffmpeg（备用）：调用 ffmpeg/gdigrab 抓取桌面，需要 ffmpeg 环境。
    """

    def __init__(self, framerate=15, source="desktop", out_type="mp4"):
        self.__backend = getattr(config.run, "record_backend", "playwright")
        if self.__backend not in ["playwright", "ffmpeg"]:
            raise ValueError("record_backend 仅支持 playwright 或 ffmpeg")
        # ffmpeg 延迟到 start() 时检查：仅启用 ffmpeg 后端录屏才需要，
        # 避免无 ffmpeg 环境下框架无法导入
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
        self.__record_file = None
        self.__recording = False

    @property
    def backend(self) -> str:
        return self.__backend

    @property
    def attachment_type(self):
        """allure 附件类型：playwright 产出 webm，ffmpeg 产出 mp4/webm"""
        if self.__backend == "playwright":
            return allure.attachment_type.WEBM
        return allure.attachment_type.MP4

    def set_record_file(self, path: str) -> None:
        """playwright 后端：由 page fixture 在浏览器关闭后写入视频文件路径"""
        self.__record_file = path

    def _ensure_ffmpeg(self):
        """确认 ffmpeg 可用并构造基础命令"""
        if self.__exe:
            return
        self.__exe = shutil.which("ffmpeg")
        if not self.__exe:
            raise SoftwareNotInstallError("ffmpeg")
        if self.__out_type == "mp4":
            self.__base_cmd = [
                self.__exe,
                "-f",
                "gdigrab",
                "-framerate",
                f"{self.__framerate}",
                "-i",
                f"{self.__source}",
                "-vf",
                "format=yuv420p",
                "-c:v",
                "libx264",
                "-crf",
                "15",
                "-b:v",
                "500k",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
            ]
        if self.__out_type == "webm":
            self.__base_cmd = [
                self.__exe,
                "-f",
                "gdigrab",
                "-framerate",
                f"{self.__framerate}",
                "-i",
                f"{self.__source}",
                "-vf",
                "format=yuv420p",
                "-c:v",
                "libvpx",
                "-crf",
                "15",
                "-b:v",
                "500k",
                "-c:a",
                "libvorbis",
                # "-loglevel", "error",
            ]

    @property
    def __generate_name(self):
        return f"{time.time()}.{self.__out_type}"

    def start(self, path):
        """启动录屏"""
        if self.__backend == "playwright":
            # playwright 后端：页面录制由 page fixture 的 record_video_dir 控制，
            # 这里仅记录开始状态
            self.__recording = True
            return
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
                raise Exception(f"录屏启动失败: {stderr}")
            time.sleep(0.1)
            self.__recording = True

    def stop(self):
        """停止录屏"""
        if self.__backend == "playwright":
            # playwright 后端：视频由浏览器关闭时自动 finalize，此处仅复位状态
            self.__recording = False
            return
        if self.__recording:
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
                self.__process.stdin.close()
                self.__process.stdout.close()
                self.__process.stderr.close()
                self.__process = None
        else:
            raise Exception("未开始录屏")

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
        if self.__backend == "playwright":
            # playwright 后端：由 page fixture 在浏览器关闭后设置
            if self.__record_file and os.path.exists(self.__record_file):
                return self.__record_file
            return None
        if not self.__out_file:
            return None
        if os.path.exists(self.__out_file):
            return self.__out_file
        return None


record = Record()
