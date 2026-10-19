#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/5/14 10:25
# @Author   :luye
import os
import pytest
import csv
from _pytest.nodes import Item
from _pytest.python import Function
from typing import Dict, List, Optional
from lets_go.settings import ROOTDIR


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
                        script_id = row.get('脚本ID', '').strip()
                        case_id = row.get('用例ID', '').strip()
                        if script_id != case_id:
                            raise Exception(f"脚本ID({script_id})与用例ID({case_id})不一致")
                        tags[script_id] = {k: v.strip() for k, v in row.items()}
                if tags:
                    self.TEST_TAGS_CACHE[csv_path] = tags
                    # logger.info(f"已加载CSV文件: {csv_path}, 包含 {len(tags)} 个用例标记")
            except Exception as e:
                pytest.exit(f"错误: {str(e)}")

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
        test_file_path = item.location[0]
        module_dir = os.path.dirname(test_file_path)
        module_dir = module_dir.replace('cases', 'tag')
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
                      if v and k not in ['废弃', '跳过原因']]

        def evaluate(tokens):
            stack = []
            operators = []

            precedence = {'and': 2, 'or': 1, '(': 0}

            def apply_operator():
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
