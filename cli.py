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
# 模板文件全部内联于此，保证打包后 init 命令零依赖可用。
# ---------------------------------------------------------------------------
# 公共模板：所有类型（gui/api/all）都生成
COMMON_TEMPLATES = {
    "conftest.py": '''#!/usr/bin/env python3
# coding=utf-8
"""测试项目根 conftest：让 just-go 框架插件生效，并向框架注入本项目配置。

必改项（按你的项目填写）：
- JUSTGO_TEST_BASE_URL：被测系统实际地址（写入报告环境信息；页面对象跳转时也读取它）
- JUSTGO_TEST_CASE_BASE_URL：测试管理平台（如禅道）用例链接前缀，写入报告用例链接（可选）

可选配置（在项目里改，不用动框架）：
- 录屏：pytest.ini 的 --record=yes 开启 ffmpeg 桌面录屏（需系统已安装 ffmpeg）
- 其他框架配置项也可在此赋值：config.run.slow_time、config.run.show_browser 等
"""
import os

from just_go import config

# TODO: 填写被测系统的实际地址，例如 http://192.168.1.10:8080
os.environ.setdefault("JUSTGO_TEST_BASE_URL", "")
# TODO: 可选，例如 https://zentao.example.com/case-view-{id}.html
os.environ.setdefault("JUSTGO_TEST_CASE_BASE_URL", "")

# 示例：慢速操作等待毫秒数 / 无头模式
# config.run.slow_time = 1000
# config.run.show_browser = False

pytest_plugins = ["just_go.plugin"]
''',
    "pytest.ini": '''[pytest]
addopts=
    -s
    --color=auto
    --no-header
    --import-mode=importlib
    # 默认开启录屏（ffmpeg 桌面录屏，产出 mp4 自动附到报告；需系统已安装 ffmpeg）；不需要可删除本行
    --record=yes
console_output_style = count
testpaths = cases
python_files = test_*.py
python_classes = Test*
python_functions = test_*
''',
    "cases/base_case.py": '''#!/usr/bin/env python3
# coding=utf-8
"""用例基类（cases/base_case.py）

职责：把用例的公共样板代码收拢到这里，让具体用例只写业务步骤和断言。
适合下沉的公共逻辑（按你的项目需要取舍）：
- 实例化被测页面对象并打开页面（如 open_page 方法）
- 统一登录 / 公共数据准备
- 公共断言辅助

写法参考项目 README「三步走」。在这里定义你自己的用例基类，
具体用例类继承它并指定被测页面对象（如 page_cls 类属性）。
"""

# 在这里定义你的用例基类，例如：
#   from just_go.controller import CaseControl
#
#   class BaseCase(metaclass=CaseControl):
#       page_cls = None
#       def open_page(self, page, path=""):
#           ...
# 说明：metaclass=CaseControl 可开启用例命名校验（用例方法名须包含用例文件名），
#      不需要该校验时直接用 class BaseCase: 即可。
''',
    "README.md": '''# {name} 自动化测试项目

基于 just-go 框架的测试项目骨架（类型：{mode_label}）。

> **骨架说明**：本命令生成的是**空白脚手架**——目录结构、配置、开发指南都在，
> 但所有代码文件的类名、方法名、业务逻辑留空，由你按本指南自行填充。
> 填充后即可运行；未填充时 `pytest --collect-only` 收集到 0 个用例属正常现象。

> 说明：框架约定标记目录名为 `tag`（单数），位于项目根；项目没有 `tag/` 目录时
> 不启用 tag 机制，用例不校验、不筛选，全部直接执行。

{sections}

## 运行

```bash
# 首次：注册项目（把 <名称> 换成你的项目名）
just-go add <名称> .

# 执行全部用例
just-go run <名称>

# 只收集不执行（快速验证骨架）
just-go run <名称> --collect-only

# 带 tag 筛选
just-go run <名称> --tag "smoke and L1"
```

或直接在项目根敲 pytest（conftest 已声明框架插件）：

```bash
pytest
```

## 配置

| 配置项 | 位置 | 说明 |
| --- | --- | --- |
| 被测系统地址 | conftest.py 的 JUSTGO_TEST_BASE_URL | 必改，页面跳转基址 + 报告环境信息 |
| 用例链接前缀 | conftest.py 的 JUSTGO_TEST_CASE_BASE_URL | 可选 |
| 录屏开关 | pytest.ini 的 --record | 默认开；删掉该行即关闭 |
| 录屏方式 | 框架内置 | 统一使用系统 ffmpeg 桌面录屏（gdigrab），产出 mp4 附到报告；需已安装 ffmpeg（`just-go install ffmpeg`） |
| 慢速/是否显示浏览器 | conftest.py 里 config.run.xxx | 运行时覆盖，优先级高于框架配置文件 |

## 运行产物

默认输出到项目根下：`logs/`（日志）、`reports/`（allure HTML 报告）、
`cache/`（allure 原始结果 report/、临时录屏与截图 temp/）。
可重定向：`just-go run <名称> --output D:\\产物目录`。

## 依赖

框架依赖由 just-go 管理：`just-go install`（core/playwright/allure/ffmpeg 可选）。
测试项目自身的 Python 依赖（如 redis、pymysql）由项目自行安装到运行环境。
''',
}


# GUI 模板：页面对象 + 页面用例（gui/all 类型生成）
GUI_TEMPLATES = {
    "cases/module/test_xxx.py": '''#!/usr/bin/env python3
# coding=utf-8
"""用例文件（cases/<模块>/test_<模块>_<用例ID>.py）

约定：
- 文件名：test_<模块>_<用例ID>.py，例如 test_module_1001.py（本文件为占位骨架，请重命名）
- 用例函数名：test_<模块>_<用例ID>，用例ID 与 tag/<模块>/<模块名>.csv 里的 用例ID 对应
- 通过框架的 page fixture 拿页面；同步用例直接调用，异步用例 async def + await

开发步骤（详见项目 README）：
1. 页面对象写在 pages/<页面>/page.py（继承你的 BasePage），并在 pages/__init__.py 导出；
2. 用例继承你的用例基类，只写业务步骤 + 断言；
3. 需要 tag 管理时，在 tag/<模块>/<模块名>.csv 登记该用例。
"""

# 在这里写你的用例，例如：
#   import allure
#   from pages import ModulePage
#   from cases.base_case import BaseCase
#
#   @allure.feature("模块")
#   class TestModule(BaseCase):
#       page_cls = ModulePage
#       def test_module_1001(self, page):
#           ...
''',
    "pages/__init__.py": '''#!/usr/bin/env python3
# coding=utf-8
"""页面对象统一出口（pages/__init__.py）

新增页面对象后，在这里集中导出，用例统一从 pages 导入：
    from pages import 你的页面类

好处：页面文件路径/类名调整时只改这里，用例层不动。
"""

# 在这里导出你的页面对象，例如：
#   from pages.base_page import BasePage
#   from pages.module_page.page import ModulePage
#   __all__ = ["BasePage", "ModulePage"]
''',
    "pages/base_page.py": '''#!/usr/bin/env python3
# coding=utf-8
"""页面对象基类（pages/base_page.py）

职责：把**业务无关**的通用操作收拢到这里，让具体页面对象只写业务。
适合下沉的通用能力（按你的项目需要取舍）：
- 输入 / 点击 / 等待可见 / 取文本 / 判断可见
- 系统高频按钮（确认 / 取消 / 保存 / 查询……）
- 表格操作、切换标签页等

同步用例传入 playwright.sync_api 的 Page；异步用例传入 playwright.async_api
的 Page（其中方法需 await）。写法参考项目 README「三步走」。
"""

# 在这里定义你的页面基类，例如：
#   from playwright.sync_api import Page
#
#   class BasePage:
#       def __init__(self, page: Page):
#           self.page = page
#       def fill(self, locator, text):
#           self.page.fill(locator, text)
#       def click(self, locator):
#           self.page.click(locator)
#       ...
''',
    "pages/module_page/page.py": '''#!/usr/bin/env python3
# coding=utf-8
"""页面对象（pages/<页面>/page.py）

职责：一个页面一个类，继承你的 BasePage，**只写业务**：
- 元素定位器集中写在类顶部
- 业务操作组合成方法（打开、搜索、下单……）
- 返回业务结果给用例断言

写完后在 pages/__init__.py 统一导出。写法参考项目 README「三步走」。
"""

# 在这里写你的页面对象，例如：
#   from pages.base_page import BasePage
#
#   class HomePage(BasePage):
#       _search_input = 'input[placeholder*="搜索"]'
#       def goto(self, path=""):
#           ...
#       def search(self, keyword):
#           ...
#       def get_search_result(self):
#           ...
''',
    "tag/module.csv": '''用例ID,用例级别,场景,跳过原因
''',
}


# API 模板：接口封装 + 接口用例（api/all 类型生成）
API_TEMPLATES = {
    "apis/__init__.py": '''#!/usr/bin/env python3
# coding=utf-8
"""接口封装统一出口（apis/__init__.py）

新增接口封装后，在这里集中导出，用例统一从 apis 导入：
    from apis import module_api
"""

# 在这里导出你的接口封装，例如：
#   from apis.module import api as module_api
#   __all__ = ["module_api"]
''',
    "apis/module/api.py": '''#!/usr/bin/env python3
# coding=utf-8
"""接口封装（apis/<模块>/api.py）

职责：把被测系统的接口按模块封装成方法，供用例调用。
一个接口一个方法：请求地址 + 参数 + 返回业务结果给用例断言。
接口基址用 conftest 注入的 JUSTGO_TEST_BASE_URL，未配时为空。

写法参考项目 README「API 用例怎么开发」。
"""

# 在这里封装你的接口，例如：
#   import os
#   import requests  # 需要先安装：pip install requests
#
#   BASE = os.environ.get("JUSTGO_TEST_BASE_URL", "")
#
#   def login(username, password):
#       resp = requests.post(f"{BASE}/api/login", json={"username": username, "password": password})
#       return resp.json()
''',
    "cases/api/test_xxx.py": '''#!/usr/bin/env python3
# coding=utf-8
"""API 用例文件（cases/api/test_<模块>_<用例ID>.py）

约定：
- 文件名：test_<模块>_<用例ID>.py，例如 test_login_1001.py（本文件为占位骨架，请重命名）
- 用例函数名：test_<模块>_<用例ID>，用例ID 与 tag/<模块>/<模块名>.csv 里的 用例ID 对应
- API 用例直接调接口封装方法，不需要 page fixture

开发步骤（详见项目 README）：
1. 接口封装写在 apis/<模块>/api.py，并在 apis/__init__.py 导出；
2. 用例 import 接口方法，调接口 + 断言；
3. 需要 tag 管理时，在 tag/<模块>/<模块名>.csv 登记该用例。
"""

# 在这里写你的用例，例如：
#   from apis.module import api as module_api
#
#   def test_login_1001():
#       data = module_api.login("admin", "123456")
#       assert data["code"] == 0
''',
    "tag/api.csv": '''用例ID,用例级别,场景,跳过原因
''',
}


# GUI 开发指南段落（嵌入项目 README）
GUI_SECTION = '''
## 目录结构（GUI）

```
{name}/
├─ conftest.py            # 项目根配置：声明框架插件 + 注入被测地址（必改）
├─ pytest.ini             # pytest 配置：收集规则 / 默认录屏
├─ cases/                 # 测试用例（一个用例文件 = 一个模块/功能的一组用例）
│  ├─ base_case.py        # 用例基类：公共样板（打开页面/实例化页面对象）下沉到这里
│  └─ module/
│     └─ test_xxx.py      # 用例占位文件：按命名约定重命名并填充（见三步走）
├─ pages/                 # 页面对象（PO 核心：每个页面一个类）
│  ├─ __init__.py         # 统一出口：所有页面对象在此导出，用例从 pages 导入
│  ├─ base_page.py        # 页面基类：通用元素操作/常用按钮（业务无关）
│  └─ module_page/
│     └─ page.py
└─ tag/                   # 用例标记（可选：tag 机制启用后支持 --tag 筛选）
   └─ module.csv          # 一个模块目录一个 CSV，登记该目录下所有用例
```

## 核心思路：基类下沉公共逻辑，页面/用例只写业务

自动化开发大量代码是重复的（输入、点击、等待、打开页面、实例化对象……）。
本骨架用**两个基类**把这些业务无关的逻辑收拢，写页面和用例时只需要关注业务：

| 基类 | 位置 | 收拢什么 |
| --- | --- | --- |
| `BasePage` | pages/base_page.py | 通用元素操作（fill/click/wait_visible/get_text/is_visible）、常用按钮（确认/取消/保存） |
| `BaseCase` | cases/base_case.py | 用例公共样板（实例化页面对象、打开页面 open_page），后续可加登录/数据准备等 |

## 怎么开发 GUI 用例（三步走）

### 1. 写页面对象（pages/）
继承 `BasePage`，通用操作直接用，**只写业务**（定位器 + 业务操作组合）：

```python
from pages.base_page import BasePage

class HomePage(BasePage):
    # ① 元素定位器：集中维护，页面结构变了只改这里
    _search_input = 'input[placeholder*="搜索"]'

    # ② 业务操作：组合 BasePage 的通用动作，只写业务步骤
    def search(self, keyword):
        self.fill(self._search_input, keyword)   # BasePage 提供
        self.click(self._search_button)          # BasePage 提供

    # ③ 返回业务结果：供用例层断言
    def get_search_result(self):
        return self.get_text(self._search_result)  # BasePage 提供
```

写完后在 `pages/__init__.py` 统一导出（新增页面也这样做）：

```python
from pages.base_page import BasePage
from pages.module_page.page import ModulePage

__all__ = ["BasePage", "ModulePage"]
```

### 2. 写用例（cases/）
继承 `BaseCase`，设置 `page_cls` 指定被测页面，**只写业务步骤 + 断言**：

```python
import allure
from cases.base_case import BaseCase
from pages import ModulePage

@allure.feature("模块")
class TestModule(BaseCase):
    page_cls = ModulePage  # 被测页面对象类

    def test_module_search_1001(self, page):
        """模块搜索功能验证"""
        module = self.open_page(page)  # 基类样板：实例化 ModulePage 并打开
        module.search("手机")          # 业务步骤
        assert "手机" in module.get_search_result(), "搜索结果应包含关键词"
```

约定：
- 用例函数名 `test_<模块>_<用例ID>`，用例ID（如 1001）与 tag CSV 中的 用例ID 对应；
- `page` 是框架提供的 fixture（Playwright 页面）：同步用例直接调用，
  异步用例 `async def test_xxx(page)` 用 `await page.xxx()`，两种写法都支持；
- 通用能力按需在 `BasePage`/`BaseCase` 扩展（如公共登录、表格操作），页面和用例保持只写业务。

### 4. 登记 tag（可选）
不需要筛选可以跳过。需要时在 `tag/<模块>/<模块名>.csv` 登记该用例（4 列）：

```
用例ID,用例级别,场景,跳过原因
1001,L1,模块搜索,
```

- 用例ID 与用例函数名 `test_<模块>_<用例ID>` 中的 ID 对应（框架按此匹配）；
- `跳过原因` 填写后该用例自动跳过；
- 登记后即可筛选：`just-go run <名称> --tag "L1 and 模块"`（支持 and/or/括号）；
- 不想用 tag：删掉 `tag/` 目录即可，用例直接全部执行。
'''


# API 开发指南段落（嵌入项目 README）
API_SECTION = '''
## 目录结构（API）

```
{name}/
├─ conftest.py            # 项目根配置：声明框架插件 + 注入被测地址（必改）
├─ pytest.ini             # pytest 配置：收集规则
├─ apis/                  # 接口封装（一个模块一个文件，把接口封装成方法）
│  ├─ __init__.py         # 统一出口：接口封装在此导出，用例从 apis 导入
│  └─ module/
│     └─ api.py           # 接口占位文件：按模块封装接口方法
├─ cases/                 # 测试用例
│  ├─ base_case.py        # 用例基类（API 用例通常用不到，保留备用）
│  └─ api/
│     └─ test_xxx.py      # 用例占位文件：按命名约定重命名并填充
└─ tag/                   # 用例标记（可选：tag 机制启用后支持 --tag 筛选）
   └─ api.csv             # 一个模块目录一个 CSV，登记该目录下所有用例
```

## 怎么开发 API 用例

### 1. 封装接口（apis/）
把被测系统的接口按模块封装成方法，一个接口一个方法，返回业务结果给用例断言：

```python
import os
import requests  # 需要先安装：pip install requests

BASE = os.environ.get("JUSTGO_TEST_BASE_URL", "")

def login(username, password):
    resp = requests.post(f"{BASE}/api/login", json={"username": username, "password": password})
    return resp.json()
```

写完后在 `apis/__init__.py` 统一导出（新增模块也这样做）。

### 2. 写用例（cases/api/）
API 用例不需要 page fixture，直接调接口方法 + 断言：

```python
from apis.module import api as module_api

def test_login_1001():
    data = module_api.login("admin", "123456")
    assert data["code"] == 0
```

约定：用例函数名 `test_<模块>_<用例ID>`，用例ID 与 tag CSV 中的 用例ID 对应。

### 3. 登记 tag（可选）
和 GUI 一样，在 `tag/<模块>/<模块名>.csv` 登记该用例：

```
用例ID,用例级别,场景,跳过原因
1001,L1,登录接口,
```

- 用例ID 与用例函数名 `test_<模块>_<用例ID>` 中的 ID 对应（框架按此匹配）；
- 运行时可筛选：`just-go run <项目> --tag "L1 and 登录"`；
- 不想用 tag：删掉 `tag/` 目录即可，用例直接全部执行。
'''


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

    templates = dict(COMMON_TEMPLATES)
    if mode in ("gui", "all"):
        templates.update(GUI_TEMPLATES)
    if mode in ("api", "all"):
        templates.update(API_TEMPLATES)

    base_name = os.path.basename(target)
    mode_label = {"gui": "GUI", "api": "API", "all": "GUI + API"}[mode]
    sections = ""
    if mode in ("gui", "all"):
        sections += GUI_SECTION
    if mode in ("api", "all"):
        sections += API_SECTION

    for rel, content in templates.items():
        path = os.path.join(target, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = (
            content.replace("{name}", base_name)
            .replace("{mode_label}", mode_label)
            .replace("{sections}", sections)
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
