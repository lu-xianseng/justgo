# -*- coding: utf-8 -*-
"""just_go.data 数据加载工具单元测试"""
import pytest

from just_go._internal.data import load_csv_cases, load_json_cases


class TestLoadJsonCases:
    def test_load_list(self, tmp_path):
        f = tmp_path / "cases.json"
        f.write_text('[{"username": "admin", "password": "123456"}]', encoding="utf-8")
        data = load_json_cases(str(f))
        assert data[0]["username"] == "admin"

    def test_relative_resolves_against_rootdir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("just_go._internal.data.ROOTDIR", str(tmp_path))
        f = tmp_path / "cases.json"
        f.write_text("[]", encoding="utf-8")
        assert load_json_cases("cases.json") == []

    def test_not_list_raises(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text('{"a": 1}', encoding="utf-8")
        with pytest.raises(ValueError, match="数组"):
            load_json_cases(str(f))


class TestLoadCsvCases:
    def test_dict_reader_with_header(self, tmp_path):
        f = tmp_path / "cases.csv"
        f.write_text("username,password\nadmin,123456\n", encoding="utf-8")
        rows = load_csv_cases(str(f))
        assert len(rows) == 1
        assert rows[0]["username"] == "admin"
        assert rows[0]["password"] == "123456"
