# -*- coding: utf-8 -*-
"""GenerateReport：allure 版本探测与命令组装（单文件 / 中文 / 项目名）"""
import pytest

import just_go._internal.tools as tools
from just_go._internal.tools import GenerateReport


class FakeResult:
    def __init__(self, out):
        self.stdout = out
        self.stderr = ""


def test_allure_version_parse_normal(monkeypatch):
    """--version 输出标准版本号时正确解析为元组"""
    monkeypatch.setattr(tools.subprocess, "run", lambda *a, **k: FakeResult("2.30.0\n"))
    assert GenerateReport._allure_version() == (2, 30, 0)


def test_allure_version_parse_unexpected(monkeypatch):
    """输出异常/缺失时降级为 (0,0,0)，不抛异常"""
    monkeypatch.setattr(tools.subprocess, "run", lambda *a, **k: FakeResult(""))
    assert GenerateReport._allure_version() == (0, 0, 0)


def test_build_cmd_2_30_has_single_name_lang(monkeypatch):
    """allure>=2.30：单文件 + 报告名 + 中文语言"""
    monkeypatch.setattr(tools.subprocess, "run", lambda *a, **k: FakeResult("2.30.0\n"))
    monkeypatch.setattr(tools, "ALLURE_PATH", "allure")
    monkeypatch.setattr(tools, "TMP_REPORT_PATH", "cache/report")
    monkeypatch.setattr(tools, "PROJECT_NAME", "AutoLib")
    g = GenerateReport()
    g._GenerateReport__report_path = "reports/x"
    cmd = g._build_cmd()
    assert cmd[:5] == ["allure", "generate", "cache/report", "-c", "-o"]
    assert cmd[5:] == ["reports/x", "--single-file", "--name", "AutoLib", "--lang", "zh"]


def test_build_cmd_2_24_only_single(monkeypatch):
    """allure 2.24-2.29：只加单文件，不加 --name/--lang（避免被当结果目录）"""
    monkeypatch.setattr(tools.subprocess, "run", lambda *a, **k: FakeResult("2.24.1\n"))
    monkeypatch.setattr(tools, "ALLURE_PATH", "allure")
    monkeypatch.setattr(tools, "TMP_REPORT_PATH", "cache/report")
    g = GenerateReport()
    g._GenerateReport__report_path = "reports/x"
    cmd = g._build_cmd()
    assert cmd == ["allure", "generate", "cache/report", "-c", "-o", "reports/x", "--single-file"]


def test_build_cmd_old_version_no_extra(monkeypatch):
    """allure<2.24：不加任何新选项，兼容老版本"""
    monkeypatch.setattr(tools.subprocess, "run", lambda *a, **k: FakeResult("2.23.0\n"))
    monkeypatch.setattr(tools, "ALLURE_PATH", "allure")
    monkeypatch.setattr(tools, "TMP_REPORT_PATH", "cache/report")
    g = GenerateReport()
    g._GenerateReport__report_path = "reports/x"
    cmd = g._build_cmd()
    assert cmd == ["allure", "generate", "cache/report", "-c", "-o", "reports/x"]


def test_report_name_fallback_to_project(monkeypatch):
    """config 未配 report_name 时回退到被测项目名"""
    monkeypatch.setattr(tools, "PROJECT_NAME", "AutoLib")
    g = GenerateReport()
    assert g.report_name == "AutoLib"
    assert g.report_language == "zh"


def test_safe_version_returns_unknown(monkeypatch):
    """包未安装时报告环境信息降级为 unknown，不抛异常中断收尾"""

    def boom(_name):
        raise RuntimeError("not installed")

    monkeypatch.setattr(tools, "version", boom)
    assert tools._safe_version("requests") == "unknown"


class _MarkItem:
    def __init__(self):
        self.markers = []

    def add_marker(self, marker):
        self.markers.append(marker)


class _MarkConfig:
    def __init__(self):
        self.marker_lines = []

    def addinivalue_line(self, name, line):
        self.marker_lines.append(line)


@pytest.mark.filterwarnings("ignore::pytest.PytestUnknownMarkWarning")
def test_add_mark_only_registers_level_column():
    """只有枚举型列（用例级别）注册成 pytest marker，自由文本列不注册"""
    GenerateReport._registered_markers.clear()
    item, cfg = _MarkItem(), _MarkConfig()
    tags = {
        "用例ID": "1001",
        "用例级别": "L1",
        "场景": "登录接口",
        "步骤": "1. 打开页面",
    }
    GenerateReport().add_mark(item, cfg, tags)
    assert cfg.marker_lines == ["L1: L1"]


def test_take_record_file_clears_reference(tmp_path):
    """录屏文件取出后不再返回，避免删不掉时被下一条用例重复 attach"""
    out = tmp_path / "case.mp4"
    out.write_bytes(b"x")
    rec = tools.Record()
    rec._Record__out_file = str(out)
    assert rec.record_file == str(out)
    assert rec.take_record_file() == str(out)
    assert rec.record_file is None
