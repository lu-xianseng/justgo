#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/5/14 10:25
# @Author   :luye
import csv
import os
from typing import Dict, List, Optional

import pytest
from _pytest.nodes import Item
from _pytest.python import Function

from just_go.exceptions import TagError
from just_go.settings import ROOTDIR

# 限定 star import 只导出公共类，避免框架命名空间被辅助符号污染
__all__ = ["ParseTag", "UpdateTag"]


class UpdateTag:
    """tag 维护工具：为用例自动创建对应的 tag CSV 文件（含表头）"""

    def create_tag_file(self, item: Item) -> Optional[str]:
        """获取测试用例对应的CSV标记文件路径"""
        module_dir = ParseTag._module_dir(item)
        # 仅把路径首段 cases 替换为 tag（避免误伤模块目录名中含 cases 的情况）
        module_dir = (
            "tag" + module_dir[len("cases"):]
            if module_dir.startswith("cases")
            else module_dir
        )
        csv_path = os.path.join(ROOTDIR, module_dir + ".csv")
        if not os.path.exists(csv_path):
            os.makedirs(os.path.dirname(csv_path), exist_ok=True)
            with open(csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["用例ID", "用例级别", "场景", "跳过原因"]
                )
        return csv_path


class ParseTag:
    TEST_TAGS_CACHE = {}

    @staticmethod
    def find_all_csv_files(root_dir: str) -> List[str]:
        """查找 tag 目录下所有的 CSV 标记文件。

        仅扫描 <项目根>/tag 目录：tag 机制是可选的，只有项目显式提供 tag 数据
        才启用；项目内其他位置的 .csv（如数据文件）不会被误判为 tag 文件。
        """
        tag_dir = os.path.join(root_dir, "tag")
        csv_files = []
        if os.path.isdir(tag_dir):
            for dirpath, _, filenames in os.walk(tag_dir):
                for filename in filenames:
                    if filename.endswith(".csv"):
                        csv_files.append(os.path.join(dirpath, filename))
        return csv_files

    def load_all_test_tags(self, session) -> None:
        """加载所有测试用例的标记数据到缓存"""
        csv_files = self.find_all_csv_files(ROOTDIR)
        for csv_path in csv_files:
            try:
                tags = {}
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # logger.debug(row)
                        case_id = row.get('用例ID', '').strip()
                        if not case_id:
                            raise TagError("用例ID不能为空")
                        tags[case_id] = {k: v.strip() for k, v in row.items()}
                if tags:
                    self.TEST_TAGS_CACHE[csv_path] = tags
                    # logger.info(f"已加载CSV文件: {csv_path}, 包含 {len(tags)} 个用例标记")
            except Exception as e:
                pytest.exit(f"错误: {str(e)}")

    @staticmethod
    def _module_dir(item: Item) -> str:
        """用例文件所在目录（相对项目根）。

        pytest 的 item.location[0] 在部分收集模式（如 --import-mode=importlib）
        下可能是绝对路径，先相对化再判前缀，避免 tag 路径拼到项目外。
        """
        test_file_path = item.location[0]
        if os.path.isabs(test_file_path):
            test_file_path = os.path.relpath(test_file_path, ROOTDIR)
        return os.path.dirname(test_file_path)

    @staticmethod
    def get_test_case_id(item: Function) -> Optional[str]:
        """从测试用例中提取ID"""
        test_name = item.name
        parts = test_name.split('_')
        if len(parts) >= 3:
            # 尝试从测试名中提取ID
            test_id_part = parts[-1].split('[')[0]  # 处理带参数化的情况
            return test_id_part
        return None

    def get_module_csv_path(self, item: Item) -> Optional[str]:
        """获取测试用例对应的CSV标记文件路径"""
        module_dir = self._module_dir(item)
        # 仅把路径首段 cases 替换为 tag（避免误伤模块目录名中含 cases 的情况）
        module_dir = (
            "tag" + module_dir[len("cases"):]
            if module_dir.startswith("cases")
            else module_dir
        )
        csv_path = os.path.join(ROOTDIR, module_dir + ".csv")
        if csv_path in self.TEST_TAGS_CACHE:
            return csv_path
        pytest.exit(f"用例[{item.name}]，缺少tag信息")

    @staticmethod
    def evaluate_expression(expression: str, tag_info: Dict[str, str]) -> bool:
        """
        逻辑表达式，支持and、or、括号操作符
        例如: "smoke and (L1 or L2)"
        """
        expression = expression.lower()
        tag_values = [str(v).lower() for k, v in tag_info.items()
                      if v and k not in ['跳过原因']]

        def evaluate(tokens):
            stack = []
            operators = []

            precedence = {'and': 2, 'or': 1, '(': 0}

            def apply_operator():
                if len(stack) < 2 or not operators:
                    return
                op = operators.pop()
                right = stack.pop()
                left = stack.pop()
                if op == 'and':
                    stack.append(left and right)
                elif op == 'or':
                    stack.append(left or right)

            i = 0
            while i < len(tokens):
                token = tokens[i]
                if token == '(':
                    operators.append(token)
                    i += 1
                elif token == ')':
                    while operators and operators[-1] != '(':
                        apply_operator()
                    # 防御：表达式括号不匹配（多右括号）时栈已空，无法继续求值
                    if not operators:
                        return False
                    operators.pop()  # 弹出左括号
                    i += 1
                elif token in {'and', 'or'}:
                    while (operators and operators[-1] != '(' and
                           precedence[operators[-1]] >= precedence[token]):
                        apply_operator()
                    operators.append(token)
                    i += 1
                else:
                    # 检查token是否在任意标签值中
                    matched = any(token in value for value in tag_values)
                    stack.append(matched)
                    i += 1

            while operators:
                # 防御：残留左括号（多左括号）或操作数不足（如 "L1 or"）时
                # 表达式不完整，直接判定为不匹配，避免死循环
                if operators[-1] == '(' or len(stack) < 2:
                    return False
                apply_operator()

            return stack[0] if stack else False

        # 简单分词，支持括号
        tokens = []
        current = ''
        i = 0
        while i < len(expression):
            if expression[i] in {'(', ')', ' ', '\t'}:
                if current:
                    tokens.append(current.strip())
                    current = ''
                if expression[i] in {'(', ')'}:
                    tokens.append(expression[i])
            else:
                current += expression[i]
            i += 1
        if current:
            tokens.append(current.strip())

        # 过滤掉空token
        tokens = [t for t in tokens if t]

        return evaluate(tokens)
