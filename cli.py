#!/usr/bin/env python3
# coding=utf-8
# @Time     :2026/10/16
# @Author   :luye
"""
lets-go 命令行入口。

用法：
    lets-go add <名称> <测试项目路径>    注册一个测试项目
    lets-go list                         列出已注册项目
    lets-go remove <名称>                取消注册
    lets-go run <名称|路径> [pytest参数] 执行指定测试项目的自动化测试

run 内部机制：
    1. 解析目标为已注册名称或直接路径，得到测试项目根目录；
    2. 设置环境变量 LETSGO_PROJECT_ROOT 指向测试项目根（框架据此定位 tag/日志/报告）；
    3. 注入 PYTHONPATH（含框架根），保证未安装时 lets_go 也可导入；
    4. 以测试项目根为工作目录调用 `python -m pytest -p lets_go.plugin <参数>`。
"""
import argparse
import json
import os
import subprocess
import sys

# 保证任何目录下都能 import lets_go（框架根 = 本文件所在目录，即 lets-go 项目根）
FRAMEWORK_ROOT = os.path.dirname(os.path.abspath(__file__))
if FRAMEWORK_ROOT not in sys.path:
    sys.path.insert(0, FRAMEWORK_ROOT)

REGISTRY_DIR = os.path.join(os.path.expanduser("~"), ".lets-go")
REGISTRY_FILE = os.path.join(REGISTRY_DIR, "projects.json")


def load_registry() -> dict:
    """读取项目注册表"""
    if os.path.exists(REGISTRY_FILE):
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_registry(data: dict) -> None:
    """写回项目注册表"""
    os.makedirs(REGISTRY_DIR, exist_ok=True)
    with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_path(path: str) -> str:
    """规范化路径并校验存在"""
    path = os.path.abspath(os.path.expanduser(path))
    if not os.path.isdir(path):
        raise SystemExit(f"错误：路径不存在或不是目录：{path}")
    return path


def cmd_add(args) -> int:
    if not args.name:
        raise SystemExit("错误：请提供项目名称，例如：lets-go add office D:\\ProjectCode\\web_auto_test")
    path = normalize_path(args.path)
    registry = load_registry()
    if args.name in registry:
        print(f"项目 '{args.name}' 已存在，路径将覆盖为：{path}")
    registry[args.name] = path
    save_registry(registry)
    print(f"已注册项目：{args.name} -> {path}")
    return 0


def cmd_list(_args) -> int:
    registry = load_registry()
    if not registry:
        print("暂无已注册项目。使用 lets-go add <名称> <路径> 注册。")
        return 0
    print(f"已注册项目（{len(registry)} 个）：")
    for name, path in registry.items():
        mark = "OK " if os.path.isdir(path) else "!! "
        print(f"  {mark}{name}: {path}")
    return 0


def cmd_remove(args) -> int:
    registry = load_registry()
    if args.name not in registry:
        print(f"项目 '{args.name}' 未注册。")
        return 1
    del registry[args.name]
    save_registry(registry)
    print(f"已取消注册项目：{args.name}")
    return 0


def cmd_run(args) -> int:
    # 1. 解析目标：已注册名称优先，否则视为路径
    registry = load_registry()
    if args.target in registry:
        project_root = registry[args.target]
    else:
        project_root = args.target
    project_root = normalize_path(project_root)

    # 2. 环境：注入测试项目根 + PYTHONPATH
    env = os.environ.copy()
    env["LETSGO_PROJECT_ROOT"] = project_root
    pythonpath = FRAMEWORK_ROOT
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath

    # 3. 组装 pytest 命令：插件由 CLI 注入，其余参数透传
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "lets_go.plugin",
    ] + args.pytest_args

    print(f"执行测试项目：{project_root}")
    print(f"命令：{' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root, env=env)
    return result.returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lets-go",
        description="lets-go Web 自动化测试框架：以命令方式指定测试项目执行自动化测试。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="注册测试项目")
    p_add.add_argument("name", help="项目名称（如 office_automation）")
    p_add.add_argument("path", help="测试项目根目录路径")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="列出已注册项目")
    p_list.set_defaults(func=cmd_list)

    p_remove = sub.add_parser("remove", help="取消注册项目")
    p_remove.add_argument("name", help="项目名称")
    p_remove.set_defaults(func=cmd_remove)

    p_run = sub.add_parser("run", help="执行指定测试项目的自动化测试")
    p_run.add_argument("target", help="已注册的项目名称，或测试项目根目录路径")
    p_run.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="透传给 pytest 的参数，如 --tag \"smoke and L1\" --collect-only",
    )
    p_run.set_defaults(func=cmd_run)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
