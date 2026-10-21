# -*- coding: utf-8 -*-
"""GenerateReport：allure 版本探测与命令组装（单文件 / 中文 / 项目名）"""
import just_go.tools as tools
from just_go.tools import GenerateReport


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
