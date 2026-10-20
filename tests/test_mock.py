# -*- coding: utf-8 -*-
"""MockData.get_file_path：限定被测项目内查找，跳过产物/虚拟环境目录"""
from just_go.mock import MockData


class TestGetFilePath:
    def test_file_in_root_found(self, tmp_path):
        (tmp_path / "data.json").write_text("{}", encoding="utf-8")
        assert MockData.get_file_path("data.json", base_dir=str(tmp_path)) == str(
            tmp_path / "data.json"
        )

    def test_file_in_subdir_found(self, tmp_path):
        sub = tmp_path / "data"
        sub.mkdir()
        (sub / "users.csv").write_text("a\n", encoding="utf-8")
        result = MockData.get_file_path("users.csv", base_dir=str(tmp_path))
        assert result == str(sub / "users.csv")

    def test_file_in_product_dir_skipped(self, tmp_path):
        # 运行产物目录不参与查找（避免深挖无用子树）
        (tmp_path / "reports").mkdir(parents=True)
        (tmp_path / "reports" / "x.txt").write_text("r", encoding="utf-8")
        assert MockData.get_file_path("x.txt", base_dir=str(tmp_path)) is None

    def test_file_in_venv_skipped(self, tmp_path):
        (tmp_path / ".venv" / "site-packages").mkdir(parents=True)
        (tmp_path / ".venv" / "site-packages" / "y.txt").write_text("y", encoding="utf-8")
        assert MockData.get_file_path("y.txt", base_dir=str(tmp_path)) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert MockData.get_file_path("no_such.txt", base_dir=str(tmp_path)) is None

    def test_invalid_base_dir_returns_none(self):
        assert MockData.get_file_path("a.txt", base_dir="_no_such_dir_xx") is None
