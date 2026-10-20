#!/usr/bin/env python3
# coding=utf-8
# @Time     :2026/10/16
# @Author   :luye
"""
just-go 命令行入口。

用法：
    just-go add <名称> <测试项目路径>    注册一个测试项目
    just-go init <项目目录[类型]>        初始化测试项目骨架（类型可选 api/gui/all，默认 gui，如 "shop-test[all]"）
    just-go list                         列出已注册项目
    just-go remove <名称>                取消注册
    just-go run <名称|路径> [pytest参数] 执行指定测试项目的自动化测试

run 内部机制：
    1. 解析目标为已注册名称或直接路径，得到测试项目根目录；
    2. 设置环境变量 JUSTGO_PROJECT_ROOT 指向测试项目根（框架据此定位 tag/日志/报告）；
    3. 注入 PYTHONPATH（含框架根），保证未安装时 just_go 也可导入；
    4. 以测试项目根为工作目录调用 `python -m pytest -p just_go.plugin <参数>`。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

# 保证任何目录下都能 import just_go（框架根 = 本文件所在目录，即 just-go 项目根）
FRAMEWORK_ROOT = os.path.dirname(os.path.abspath(__file__))
if FRAMEWORK_ROOT not in sys.path:
    sys.path.insert(0, FRAMEWORK_ROOT)

REGISTRY_DIR = os.path.join(os.path.expanduser("~"), ".just-go")
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
        raise SystemExit("错误：请提供项目名称，例如：just-go add office D:\\ProjectCode\\web_auto_test")
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
        print("暂无已注册项目。使用 just-go add <名称> <路径> 注册。")
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
    env["JUSTGO_PROJECT_ROOT"] = project_root
    env["JUSTGO_PROJECT_NAME"] = project_name
    if args.output:
        env["JUSTGO_OUTPUT_ROOT"] = os.path.abspath(os.path.expanduser(args.output))
        print(f"运行产物输出目录：{env['JUSTGO_OUTPUT_ROOT']}")
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
        "just_go.plugin",
        "-p",
        "no:playwright",
    ] + args.pytest_args

    print(f"执行测试项目：{project_root}")
    print(f"命令：{' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=project_root, env=env)
    return result.returncode


# ---------------------------------------------------------------------------
# just-go install：框架依赖安装 / 检查（pipenv 管理虚拟环境）
# 组件：core（框架核心 Python 依赖）| playwright（浏览器）|
#       allure（报告工具）| ffmpeg（桌面录屏编码器，录屏必需）| all（全部，默认）
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
    - 已运行在虚拟环境（含 pipenv venv）或显式跳过（JUSTGO_SKIP_PIPENV）时直接继续；
    - 否则通过 `pipenv run python cli.py <argv>` 重新执行，保证依赖与 pytest
      都落在 pipenv 虚拟环境中（sys.executable = venv python）。
    """
    if _is_venv() or os.environ.get("JUSTGO_SKIP_PIPENV"):
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
                "just-go 使用 pipenv 管理虚拟环境，但未检测到 pipenv。\n"
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
                "尚未创建 pipenv 虚拟环境，请先运行：just-go install"
            )
    # 重新进入 pipenv 环境执行（pipenv run 会设置 PIPENV_ACTIVE=1，不会再次引导）
    print("进入 pipenv 虚拟环境执行...")
    cmd = [pipenv, "run", "python", os.path.abspath(__file__)] + argv
    sys.exit(subprocess.call(cmd))


def _pipenv_install(packages: list | None, title: str) -> int:
    """安装依赖：
    - 有 pipenv（源码开发环境）：pipenv install 安装到 pipenv 虚拟环境；
    - 无 pipenv 但在虚拟环境内（发布版：wheel 已自动装好 Python 依赖，且无 Pipfile）：
      退化用 pip 安装到当前 venv；packages 为空（Pipfile 全量）时说明依赖已随 wheel 安装并跳过；
    - 其余情况给出 pipenv 安装指引。
    """
    pipenv = shutil.which("pipenv")
    if pipenv:
        cmd = [pipenv, "install", "--skip-lock"]
        if packages:
            cmd += packages
    elif _is_venv():
        # 发布版环境：依赖已在 pip install <wheel> 时安装
        if not packages:
            print("  当前为安装版环境（无 Pipfile），Python 依赖已随 wheel 安装，跳过")
            return 0
        cmd = [sys.executable, "-m", "pip", "install"] + packages
    else:
        raise SystemExit("未检测到 pipenv，请先执行：python -m pip install pipenv")
    print(f"==> {title}")
    print(f"    {' '.join(cmd)}")
    return subprocess.call(cmd)


def _parse_pyproject_deps() -> list:
    """从 pyproject.toml 解析框架核心依赖清单；发布版（无 pyproject.toml）返回空，
    依赖已随 wheel 安装，由 _pipenv_install 的退化分支处理"""
    pyproject = os.path.join(FRAMEWORK_ROOT, "pyproject.toml")
    if not os.path.exists(pyproject):
        return []
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
    """安装 Playwright 浏览器（Chromium）"""
    print("==> 安装 Playwright 浏览器（Chromium）")
    cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
    print(f"    {' '.join(cmd)}")
    rc = subprocess.call(cmd)
    if rc != 0:
        print(f"    [失败] Chromium 安装未完成（退出码 {rc}），可稍后重试本命令")
        return rc
    print("    已安装到 %LOCALAPPDATA%\\ms-playwright；版本与框架 playwright 库自动匹配")
    return 0


# 默认锁定的 allure 版本（已验证可用）；版本与框架解耦，用户可随时升级/降级
DEFAULT_ALLURE_VERSION = "2.24.1"


def _install_allure(version: str = None) -> int:
    """下载安装 allure 报告工具到用户目录 ~/.just-go/allure（版本与框架解耦）

    安装位置会被 settings 的自动查找逻辑识别（config.ini allure_path 留空即可）。
    需要 Java（allure 为 Java 工具）；可指定版本：just-go install allure 2.30.0
    """
    ver = version or DEFAULT_ALLURE_VERSION
    print(f"==> 安装 allure 报告工具（版本 {ver}，安装到用户目录，与框架解耦）")
    # Java 仅在生成 HTML 报告时需要（allure CLI 为 Java 工具）；原始结果产出不需要
    java = shutil.which("java")
    if not java:
        print("  [缺失] Java 运行时（生成 HTML 报告需要，仅报告环节需要）")
        winget = shutil.which("winget")
        if winget:
            cmd = [
                "winget", "install", "--id", "EclipseAdoptium.Temurin.17.JDK", "-e",
                "--accept-source-agreements", "--accept-package-agreements",
            ]
            print("  尝试 winget 自动安装 Temurin JDK：")
            print(f"    {' '.join(cmd)}")
            rc = subprocess.call(cmd)
            if rc != 0:
                print(f"  winget 安装未完成（退出码 {rc}），可稍后重试或手动安装")
                print("    手动下载 https://adoptium.net/ 并确保 java 在 PATH")
                return 1
            java = shutil.which("java")
            if not java:
                print("  安装完成但当前终端尚未刷新 PATH，请新开终端后重新运行 just-go install allure")
                return 1
        else:
            print("  系统无 winget，请手动安装：")
            print("    下载 https://adoptium.net/ 并确保 java 在 PATH")
            return 1
    print(f"  [OK] Java：{java}")

    install_dir = os.path.join(os.path.expanduser("~"), ".just-go", "allure")
    exe_name = "allure.bat" if os.name == "nt" else "allure"
    allure_exe = os.path.join(install_dir, f"allure-{ver}", "bin", exe_name)
    if os.path.exists(allure_exe):
        print(f"  [OK] allure {ver} 已安装：{allure_exe}")
        print("      框架自动发现：config.ini 的 allure_path 留空即可")
        return 0

    url = f"https://github.com/allure-framework/allure2/releases/download/{ver}/allure-{ver}.zip"
    print(f"  下载 {url}")
    os.makedirs(install_dir, exist_ok=True)
    zip_path = os.path.join(install_dir, f"allure-{ver}.zip")
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "just-go-installer"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(zip_path, "wb") as f:
            shutil.copyfileobj(resp, f)
    except Exception as e:
        print(f"  [失败] 下载失败：{e}")
        print(f"    可手动下载该 zip 并解压到：{install_dir}")
        print(f"    要求解压后目录为 allure-{ver}，内含 bin/{exe_name}")
        return 1

    try:
        import zipfile

        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(install_dir)
    except Exception as e:
        print(f"  [失败] 解压失败：{e}")
        return 1
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    if not os.path.exists(allure_exe):
        print(f"  [失败] 解压后未找到 {allure_exe}，请检查下载完整性")
        return 1
    print(f"  [OK] allure {ver} 已安装：{allure_exe}")
    print("      框架自动发现：config.ini 的 allure_path 留空即可")
    return 0


def _install_ffmpeg() -> int:
    """检查/安装系统 ffmpeg（桌面录屏必需）"""
    print("==> 检查系统 ffmpeg（桌面录屏必需）")
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
        rc = subprocess.call(cmd)
        if rc == 0:
            exe = shutil.which("ffmpeg")
            if not exe:
                print("  安装完成但当前终端尚未刷新 PATH，请新开终端后重新运行本命令")
                return 1
            print(f"  [OK] ffmpeg：{exe}")
            return 0
        print(f"  winget 安装未完成（退出码 {rc}），可稍后重试或手动安装：")
        print("    下载 https://www.gyan.dev/ffmpeg/builds/ 的 release 版 zip，解压后把 bin 目录加入 PATH")
        return 1
    print("  未检测到 ffmpeg 且系统无 winget，请手动安装：")
    print("    下载 https://www.gyan.dev/ffmpeg/builds/ 的 release 版 zip，解压后把 bin 目录加入 PATH")
    return 1


def cmd_install(args) -> int:
    comp = args.component or "all"
    version = getattr(args, "version", None)
    steps = {
        "all": [
            ("all", _install_all_py),
            ("playwright", _install_playwright),
            ("allure", lambda: _install_allure(version)),
            ("ffmpeg", _install_ffmpeg),
        ],
        "core": [("core", _install_core)],
        "playwright": [("playwright", _install_playwright)],
        "allure": [("allure", lambda: _install_allure(version))],
        "ffmpeg": [("ffmpeg", _install_ffmpeg)],
    }
    for name, fn in steps[comp]:
        print(f"\n---------- 组件：{name} ----------")
        fn()
    print("\n安装检查完成。浏览器安装后即可运行：just-go run <项目>")
    return 0


# ---------------------------------------------------------------------------
# just-go init：初始化测试项目骨架
# 支持类型后缀 [api|gui|all]（默认 gui）：
#   gui -> cases(页面用例) / pages(页面对象) / tag
#   api -> cases(接口用例) / apis(接口封装) / tag
#   all -> 以上全部
# 模板文件位于 just_go/templates/（随包打包，发布版零依赖可用），与代码分离。
# ---------------------------------------------------------------------------
TEMPLATE_DIR = os.path.join(FRAMEWORK_ROOT, "just_go", "templates")


def _load_template(rel_path: str) -> str:
    """读取模板文件内容（utf-8）"""
    with open(os.path.join(TEMPLATE_DIR, rel_path), encoding="utf-8") as f:
        return f.read()


def _build_templates(mode: str) -> tuple:
    """按类型加载骨架模板：返回 (模板 dict[相对路径->内容], README 段落)"""
    templates = {
        "conftest.py": _load_template(os.path.join("common", "conftest.py")),
        "pytest.ini": _load_template(os.path.join("common", "pytest.ini")),
        "cases/base_case.py": _load_template(
            os.path.join("common", "cases", "base_case.py")
        ),
        "README.md": _load_template(os.path.join("common", "README.md")),
    }
    sections = ""
    if mode in ("gui", "all"):
        templates.update(
            {
                "cases/module/test_xxx.py": _load_template(
                    os.path.join("gui", "cases", "module", "test_xxx.py")
                ),
                "pages/__init__.py": _load_template(
                    os.path.join("gui", "pages", "__init__.py")
                ),
                "pages/base_page.py": _load_template(
                    os.path.join("gui", "pages", "base_page.py")
                ),
                "pages/module_page/page.py": _load_template(
                    os.path.join("gui", "pages", "module_page", "page.py")
                ),
                "tag/module.csv": _load_template(
                    os.path.join("gui", "tag", "module.csv")
                ),
            }
        )
        sections += _load_template(os.path.join("gui", "README_section.md"))
    if mode in ("api", "all"):
        templates.update(
            {
                "apis/__init__.py": _load_template(
                    os.path.join("api", "apis", "__init__.py")
                ),
                "apis/module/api.py": _load_template(
                    os.path.join("api", "apis", "module", "api.py")
                ),
                "cases/api/test_xxx.py": _load_template(
                    os.path.join("api", "cases", "api", "test_xxx.py")
                ),
                "tag/api.csv": _load_template(os.path.join("api", "tag", "api.csv")),
            }
        )
        sections += _load_template(os.path.join("api", "README_section.md"))
    return templates, sections


def cmd_init(args) -> int:
    """初始化测试项目骨架：目标目录不存在则创建（区别于 add 要求目录已存在）

    支持类型后缀 [api|gui|all]，如 just-go init "shop-test[all]"，默认 gui：
    - gui：生成页面对象 + 页面用例（pages/、cases/module/、tag/module.csv）
    - api：生成接口封装 + 接口用例（apis/、cases/api/、tag/api.csv）
    - all：两套都生成
    """
    m = re.match(r"^(?P<name>.+)\[(?P<mode>api|gui|all)\]$", args.target)
    if m:
        name_part, mode = m.group("name"), m.group("mode")
    else:
        name_part, mode = args.target, "gui"
    target = os.path.abspath(os.path.expanduser(name_part))
    if os.path.exists(target) and os.listdir(target):
        raise SystemExit(f"错误：目录已存在且非空，请选择新目录：{target}")
    os.makedirs(target, exist_ok=True)

    templates, sections = _build_templates(mode)

    base_name = os.path.basename(target)
    mode_label = {"gui": "GUI", "api": "API", "all": "GUI + API"}[mode]

    for rel, content in templates.items():
        path = os.path.join(target, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # 注意替换顺序：先替换 {sections}（其内部还含 {name} 占位），
        # 再替换 {name}/{mode_label}，确保 README 目录树中的项目名也生效。
        content = (
            content.replace("{sections}", sections)
            .replace("{name}", base_name)
            .replace("{mode_label}", mode_label)
        )
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    print(f"已在 {target} 创建测试项目骨架（类型：{mode}）：")
    for rel in templates:
        print(f"  {os.path.join(target, rel)}")
    print("\n下一步：")
    print(f"  1. 编辑 {os.path.join(target, 'conftest.py')} 里的 JUSTGO_TEST_BASE_URL 为被测系统实际地址")
    print(f"  2. 注册并运行：just-go add <名称> {target}")
    print("     just-go run <名称>")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="just-go",
        description="just-go Web 自动化测试框架：以命令方式指定测试项目执行自动化测试。",
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
        help="透传给 pytest 的参数，如 --record=yes(录屏) --tag \"smoke and L1\" --collect-only",
    )
    p_run.set_defaults(func=cmd_run)

    p_init = sub.add_parser(
        "init", help="初始化测试项目骨架（默认 gui；支持 [api|gui|all] 类型后缀）"
    )
    p_init.add_argument(
        "target",
        help="项目目录名或路径，可带类型后缀 [api|gui|all]（默认 gui），如："
        'just-go init "shop-test[all]"（gui=页面对象用例，api=接口封装用例，all=两者都有）',
    )
    p_init.set_defaults(func=cmd_init)

    p_install = sub.add_parser("install", help="安装/检查框架依赖（pipenv 管理虚拟环境）")
    p_install.add_argument(
        "component",
        nargs="?",
        choices=["core", "playwright", "allure", "ffmpeg", "all"],
        default="all",
        help="安装组件：core(框架核心Python依赖)/playwright(浏览器)/"
        "allure(报告工具，下载到用户目录~/.just-go/allure)/ffmpeg(桌面录屏编码器，录屏必需)/all(全部，默认)",
    )
    p_install.add_argument(
        "version",
        nargs="?",
        default=None,
        help="仅用于 allure：指定安装版本（如 2.30.0），默认安装锁定版本",
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
