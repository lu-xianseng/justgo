# -*- coding: utf-8 -*-
"""ParseTag 单元测试：tag 表达式筛选与 CSV 加载"""
import os

from just_go.parse_tag import ParseTag, UpdateTag


class TestEvaluateExpression:
    """evaluate_expression：and/or/括号表达式求值"""

    def setup_method(self):
        self.tags = {
            "用例ID": "1001",
            "用例级别": "L1",
            "场景": "登录接口",
            "跳过原因": "",
        }

    def test_single_token_match(self):
        assert ParseTag.evaluate_expression("L1", self.tags) is True

    def test_single_token_no_match(self):
        assert ParseTag.evaluate_expression("L2", self.tags) is False

    def test_and_both_match(self):
        assert ParseTag.evaluate_expression("L1 and 登录", self.tags) is True

    def test_and_one_missing(self):
        assert ParseTag.evaluate_expression("L1 and smoke", self.tags) is False

    def test_or_any_match(self):
        assert ParseTag.evaluate_expression("smoke or L1", self.tags) is True

    def test_parentheses_precedence(self):
        # (L1 or L2) and 登录 -> True and True
        assert ParseTag.evaluate_expression("(L1 or L2) and 登录", self.tags) is True
        # L1 or (L2 and 登录) -> True or False -> True
        assert ParseTag.evaluate_expression("L1 or (L2 and 登录)", self.tags) is True
        # (smoke and L2) or 登录 -> False or True
        assert ParseTag.evaluate_expression("(smoke and L2) or 登录", self.tags) is True

    def test_case_insensitive(self):
        assert ParseTag.evaluate_expression("l1", self.tags) is True
        assert ParseTag.evaluate_expression("登录接口", self.tags) is True

    def test_empty_expression(self):
        assert ParseTag.evaluate_expression("", self.tags) is False

    def test_token_in_value_substring(self):
        # 子串匹配：token "登录" 命中 "登录接口"
        assert ParseTag.evaluate_expression("登录", self.tags) is True


class TestFindAllCsvFiles:
    def test_no_tag_dir_returns_empty(self, tmp_path):
        (tmp_path / "cases").mkdir()
        assert ParseTag.find_all_csv_files(str(tmp_path)) == []

    def test_finds_csv_under_tag_dir(self, tmp_path):
        tag_dir = tmp_path / "tag" / "module"
        tag_dir.mkdir(parents=True)
        (tag_dir / "module.csv").write_text("a,b\n", encoding="utf-8")
        # 非 csv 文件忽略
        (tag_dir / "notes.txt").write_text("x", encoding="utf-8")
        # tag 目录外的 csv 不扫描
        (tmp_path / "data.csv").write_text("a\n", encoding="utf-8")

        found = ParseTag.find_all_csv_files(str(tmp_path))
        assert len(found) == 1
        assert found[0].endswith(os.path.join("tag", "module", "module.csv"))


class TestGetTestCaseId:
    def test_standard_name(self):
        class FakeItem:
            name = "test_login_1001"

        assert ParseTag.get_test_case_id(FakeItem()) == "1001"

    def test_parametrized_name(self):
        class FakeItem:
            name = "test_login_1001[case2]"

        assert ParseTag.get_test_case_id(FakeItem()) == "1001"

    def test_short_name_returns_none(self):
        class FakeItem:
            name = "test_login"

        assert ParseTag.get_test_case_id(FakeItem()) is None


class TestUpdateTag:
    def test_create_tag_file_writes_header(self, tmp_path, monkeypatch):

        monkeypatch.setattr("just_go.parse_tag.ROOTDIR", str(tmp_path))
        cases = tmp_path / "cases" / "module"
        cases.mkdir(parents=True)

        class FakeItem:
            location = (str(cases / "test_xxx.py"), 0, None)

        updater = UpdateTag()
        csv_path = updater.create_tag_file(FakeItem())
        assert os.path.basename(csv_path) == "module.csv"
        assert csv_path.startswith(str(tmp_path))
        content = open(csv_path, encoding="utf-8").read()
        assert "用例ID,用例级别,场景,跳过原因" in content
        # 再次调用不覆盖、不重复表头
        updater.create_tag_file(FakeItem())
        content2 = open(csv_path, encoding="utf-8").read()
        assert content2 == content
