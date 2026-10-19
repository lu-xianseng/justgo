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
import re
import shutil
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
        project_name = args.target
    else:
        project_root = args.target
        project_name = os.path.basename(os.path.abspath(args.target))
    project_root = normalize_path(project_root)

    # 2. 环境：注入测试项目根 + 输出根 + PYTHONPATH
    env = os.environ.copy()
    env["LETSGO_PROJECT_ROOT"] = project_root
    env["LETSGO_PROJECT_NAME"] = project_name
    if args.output:
        env["LETSGO_OUTPUT_ROOT"] = os.path.abspath(os.path.expanduser(args.output))
        print(f"运行产物输出目录：{env['LETSGO_OUTPUT_ROOT']}")
    pythonpath = FRAMEWORK_ROOT
    if env.get("PYTHONPATH"):
        pythonpath = pythonpath + os.pathsep + env["PYTHONPATH"]
    env["PYTHONPATH"] = pythonpath

    # 3. 组装 pytest 命令：插件由 CLI 注入；禁用 pytest-playwright（浏览器由框架
    #    自行通过 playwright 库管理，避免其 page/browser fixture 与框架冲突）
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "lets_go.plugin",
        "-p",
        "no:playwright",
    ] + args.pytest_args

    print(f"执行测试项目：{project_root}")
    print(f"命令：{' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root, env=env)
    return result.returncode


# ---------------------------------------------------------------------------
# lets-go install：框架依赖安装 / 检查（pipenv 管理虚拟环境）
# 组件：core（框架核心 Python 依赖）| playwright（浏览器 + 录制编码器）|
#       allure（报告工具）| ffmpeg（桌面录屏后端，可选）| all（全部，默认）
# ---------------------------------------------------------------------------

def _pipenv_venv_path() -> str | None:
    """查询 pipenv 虚拟环境路径（未创建返回 None）"""
    pipenv = shutil.which("pipenv")
    if not pipenv:
        return None
    r = subprocess.run([pipenv, "--venv"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    p = r.stdout.strip()
    return p if p and os.path.isdir(p) else None


def _is_venv() -> bool:
    """是否已运行在虚拟环境中（pipenv venv 或普通 venv 都适用）"""
    return getattr(sys, "base_prefix", sys.prefix) != sys.prefix


def _ensure_pipenv_runtime(argv: list) -> None:
    """引导到 pipenv 环境：
    - 已运行在虚拟环境（含 pipenv venv）或显式跳过（LETSGO_SKIP_PIPENV）时直接继续；
    - 否则通过 `pipenv run python cli.py <argv>` 重新执行，保证依赖与 pytest
      都落在 pipenv 虚拟环境中（sys.executable = venv python）。
    """
    if _is_venv() or os.environ.get("LETSGO_SKIP_PIPENV"):
        return
    if any(a in ("-h", "--help") for a in argv):
        return
    if not os.path.exists(os.path.join(FRAMEWORK_ROOT, "Pipfile")):
        return
    pipenv = shutil.which("pipenv")
    if not pipenv:
        if argv and argv[0] == "install":
            print("未检测到 pipenv，自动安装（python -m pip install pipenv）...")
            rc = subprocess.call([sys.executable, "-m", "pip", "install", "-U", "pipenv"])
            if rc != 0:
                raise SystemExit("pipenv 安装失败，请手动执行：python -m pip install pipenv")
            pipenv = shutil.which("pipenv")
        else:
            raise SystemExit(
                "lets-go 使用 pipenv 管理虚拟环境，但未检测到 pipenv。\n"
                "请先安装：python -m pip install pipenv"
            )
    if not _pipenv_venv_path():
        if argv and argv[0] == "install":
            print("首次使用：创建 pipenv 虚拟环境（使用当前 Python）...")
            rc = subprocess.call([pipenv, "--python", "3"])
            if rc != 0:
                raise SystemExit("pipenv 虚拟环境创建失败，请检查 Python 环境")
        else:
            raise SystemExit(
                "尚未创建 pipenv 虚拟环境，请先运行：lets-go install"
            )
    # 重新进入 pipenv 环境执行（pipenv run 会设置 PIPENV_ACTIVE=1，不会再次引导）
    print("进入 pipenv 虚拟环境执行...")
    cmd = [pipenv, "run", "python", os.path.abspath(__file__)] + argv
    sys.exit(subprocess.call(cmd))


def _pipenv_install(packages: list | None, title: str) -> int:
    """pipenv install 安装依赖：packages 为空时按 Pipfile 全量安装"""
    pipenv = shutil.which("pipenv")
    if not pipenv:
        raise SystemExit("未检测到 pipenv，请先执行：python -m pip install pipenv")
    cmd = [pipenv, "install", "--skip-lock"]
    if packages:
        cmd += packages
    print(f"==> {title}")
    print(f"    {' '.join(cmd)}")
    return subprocess.call(cmd)


def _parse_pyproject_deps() -> list:
    """从 pyproject.toml 解析框架核心依赖清单"""
    pyproject = os.path.join(FRAMEWORK_ROOT, "pyproject.toml")
    with open(pyproject, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if not m:
        return []
    return [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip()]


def _install_core() -> int:
    core = _parse_pyproject_deps()
    return _pipenv_install(core, "安装框架核心 Python 依赖（pipenv）")


def _install_all_py() -> int:
    """按 Pipfile 全量安装框架 Python 依赖"""
    return _pipenv_install(None, "安装全部 Python 依赖（按 Pipfile）")


def _install_playwright() -> int:
    """安装 Playwright 浏览器与录制编码器（webm 录屏依赖）"""
    print("==> 安装 Playwright 浏览器与录制编码器")
    rc = 0
    for target, desc in (
        ("chromium", "Chromium 浏览器"),
        ("ffmpeg", "录制编码器 ffmpeg（webm 视频必需）"),
    ):
        cmd = [sys.executable, "-m", "playwright", "install", target]
        print(f"    {' '.join(cmd)}")
        r = subprocess.call(cmd)
        if r != 0:
            print(f"    [失败] {desc} 安装未完成（退出码 {r}），可稍后重试本命令")
            rc = r
    if rc == 0:
        print("    已安装到 %LOCALAPPDATA%\\ms-playwright；版本与框架 playwright 库自动匹配")
    return rc


def _install_allure() -> int:
    """检查/指引 allure 报告工具（生成 HTML 报告需要 Java + allure CLI）"""
    print("==> 检查 allure 报告工具")
    ok = True
    java = shutil.which("java")
    if not java:
        ok = False
        print("  [缺失] Java 运行时（allure 生成 HTML 报告必需）")
        print("    安装：winget install EclipseAdoptium.Temurin.17.JDK")
        print("    或手动下载 https://adoptium.net/ 并确保 java 在 PATH")
    else:
        print(f"  [OK] Java：{java}")
    allure_bat = os.path.join(FRAMEWORK_ROOT, "tools", "allure", "bin", "allure.bat")
    if not os.path.exists(allure_bat):
        ok = False
        print(f"  [缺失] allure CLI：{allure_bat}")
        print("    下载 allure-commandline 并解压到 tools/allure：")
        print("    https://github.com/allure-framework/allure2/releases （allure-commandline-*.zip）")
    else:
        print(f"  [OK] allure CLI：{allure_bat}")
    if ok:
        print("  allure 报告工具已就绪")
    else:
        print("  按上方指引补装后即可生成 HTML 报告；不装不影响用例执行与 allure 原始结果")
    return 0 if ok else 1


def _install_ffmpeg() -> int:
    """检查/安装系统 ffmpeg（仅 record_backend=ffmpeg 桌面录屏后端需要）"""
    print("==> 检查系统 ffmpeg（桌面录屏后端使用；Playwright 录制无需）")
    exe = shutil.which("ffmpeg")
    if exe:
        print(f"  [OK] ffmpeg：{exe}")
        return 0
    winget = shutil.which("winget")
    if winget:
        cmd = [
            "winget", "install", "--id", "Gyan.FFmpeg", "-e",
            "--accept-source-agreements", "--accept-package-agreements",
        ]
        print("  未检测到 ffmpeg，尝试 winget 安装：")
        print(f"    {' '.join(cmd)}")
        return subprocess.call(cmd)
    print("  未检测到 ffmpeg 且系统无 winget，请手动安装：")
    print("    下载 https://www.gyan.dev/ffmpeg/builds/ 的 release 版 zip，解压后把 bin 目录加入 PATH")
    return 1


def cmd_install(args) -> int:
    comp = args.component or "all"
    steps = {
        "all": [
            ("all", _install_all_py),
            ("playwright", _install_playwright),
            ("allure", _install_allure),
            ("ffmpeg", _install_ffmpeg),
        ],
        "core": [("core", _install_core)],
        "playwright": [("playwright", _install_playwright)],
        "allure": [("allure", _install_allure)],
        "ffmpeg": [("ffmpeg", _install_ffmpeg)],
    }
    for name, fn in steps[comp]:
        print(f"\n---------- 组件：{name} ----------")
        fn()
    print("\n安装检查完成。浏览器安装后即可运行：lets-go run <项目>")
    return 0


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
        "--output",
        metavar="目录",
        help="运行产物（logs/reports/cache）输出根目录，默认输出到测试项目根下；指定时按 输出根/项目名 分子目录",
    )
    p_run.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="透传给 pytest 的参数，如 --tag \"smoke and L1\" --collect-only",
    )
    p_run.set_defaults(func=cmd_run)

    p_install = sub.add_parser("install", help="安装/检查框架依赖（pipenv 管理虚拟环境）")
    p_install.add_argument(
        "component",
        nargs="?",
        choices=["core", "playwright", "allure", "ffmpeg", "all"],
        default="all",
        help="安装组件：core(框架核心Python依赖)/playwright(浏览器+录制编码器)/"
        "allure(报告工具)/ffmpeg(桌面录屏，可选)/all(全部，默认)",
    )
    p_install.set_defaults(func=cmd_install)

    return parser


def _extract_output(argv: list) -> tuple:
    """从 run 命令参数流中提取 --output（支持 --output X / --output=X），
    避免被透传的 REMAINDER 参数吞掉。返回 (output 值, 剩余参数)"""
    output = None
    rest = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--output":
            if i + 1 >= len(argv):
                raise SystemExit("错误：--output 缺少目录参数")
            output = argv[i + 1]
            i += 2
            continue
        if arg.startswith("--output="):
            output = arg.split("=", 1)[1]
            i += 1
            continue
        rest.append(arg)
        i += 1
    return output, rest


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # 引导到 pipenv 虚拟环境（保证依赖与 pytest 在同一环境）
    _ensure_pipenv_runtime(argv)
    pre_output = None
    if argv and argv[0] == "run":
        # 先提取 --output（run 专属选项），避免与透传参数混在一起
        pre_output, argv = _extract_output(argv)
    parser = build_parser()
    args = parser.parse_args(argv)
    if pre_output is not None:
        args.output = pre_output
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
