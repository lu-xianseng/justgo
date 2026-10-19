#!/usr/bin/env python3
# coding=utf-8
# @Time     :2026/10/16
# @Author   :luye
"""
lets-go 命令行入口。

用法：
    lets-go add <名称> <测试项目路径>    注册一个测试项目
    lets-go init <项目目录>             初始化一个 PO 模式的测试项目骨架
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


# 默认锁定的 allure 版本（已验证可用）；版本与框架解耦，用户可随时升级/降级
DEFAULT_ALLURE_VERSION = "2.24.1"


def _install_allure(version: str = None) -> int:
    """下载安装 allure 报告工具到用户目录 ~/.lets-go/allure（版本与框架解耦）

    安装位置会被 settings 的自动查找逻辑识别（config.ini allure_path 留空即可）。
    需要 Java（allure 为 Java 工具）；可指定版本：lets-go install allure 2.30.0
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
                print("  安装完成但当前终端尚未刷新 PATH，请新开终端后重新运行 lets-go install allure")
                return 1
        else:
            print("  系统无 winget，请手动安装：")
            print("    下载 https://adoptium.net/ 并确保 java 在 PATH")
            return 1
    print(f"  [OK] Java：{java}")

    install_dir = os.path.join(os.path.expanduser("~"), ".lets-go", "allure")
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

        req = urllib.request.Request(url, headers={"User-Agent": "lets-go-installer"})
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
    print("\n安装检查完成。浏览器安装后即可运行：lets-go run <项目>")
    return 0


# ---------------------------------------------------------------------------
# lets-go init：初始化一个 PO 模式的测试项目骨架
# 生成：cases(用例) / pages(页面对象) / tag(标记，可选) + conftest/pytest.ini/README
# 模板文件全部内联于此，保证打包后 init 命令零依赖可用。
# ---------------------------------------------------------------------------
INIT_TEMPLATES = {
    "conftest.py": '''#!/usr/bin/env python3
# coding=utf-8
"""测试项目根 conftest：让 lets-go 框架插件生效，并向框架注入本项目配置。

- pytest_plugins：声明框架插件（lets-go run 会自行注入，此条兼容直接在项目里敲 pytest 的场景）
- LETSGO_TEST_BASE_URL：被测系统地址，框架写入 allure 报告环境信息，页面对象跳转时也读取它
- LETSGO_TEST_CASE_BASE_URL：测试管理平台（如禅道）用例链接前缀，写入报告的用例链接（可选）
"""
import os

# TODO: 改成被测系统的实际地址（本机服务可用 http://127.0.0.1:端口）
os.environ.setdefault("LETSGO_TEST_BASE_URL", "http://127.0.0.1:8000")
# TODO: 可选，例如 https://zentao.example.com/case-view-{id}.html
os.environ.setdefault("LETSGO_TEST_CASE_BASE_URL", "")

pytest_plugins = ["lets_go.plugin"]
''',
    "pytest.ini": '''[pytest]
addopts=
    -s
    --color=auto
    --no-header
    --import-mode=importlib
    # 默认开启录屏（Playwright 内置，零依赖，产出 webm 自动附到报告）；不需要可删除本行
    --record=yes
console_output_style = count
testpaths = cases
python_files = test_*.py
python_classes = Test*
python_functions = test_*
''',
    "cases/base_case.py": '''#!/usr/bin/env python3
# coding=utf-8
"""BaseCase：用例基类。

把用例的**公共样板代码**下沉到这里（实例化被测页面对象、打开页面），
具体用例类只需：
1. 设置 page_cls（被测页面对象类）；
2. 写业务步骤 + 断言——不关心页面怎么打开、对象怎么实例化。
"""
import allure


class BaseCase:
    """用例基类：子类设置 page_cls 后，open_page 等公共能力直接复用"""

    page_cls = None  # 子类指定被测页面对象类（如 HomePage）

    def open_page(self, page, path: str = ""):
        """实例化被测页面对象并打开页面（样板代码进基类，用例只关注业务）"""
        if self.page_cls is None:
            raise RuntimeError(f"{type(self).__name__} 需要设置 page_cls（被测页面对象类）")
        po = self.page_cls(page)
        po.goto(path)
        return po

    # 更多公共逻辑按需在此扩展，例如：统一登录、公共数据准备、公共断言辅助等
''',
    "cases/home/test_home_1001.py": '''#!/usr/bin/env python3
# coding=utf-8
"""首页搜索用例（PO 模式示例）。

开发一个用例的步骤：
1. 在 pages/<页面>/page.py 写页面对象（继承 BasePage，通用操作直接用）：
   元素定位器 + 业务操作 + 返回业务结果，并在 pages/__init__.py 统一导出；
2. 在 cases/<模块>/test_<模块>_<用例ID>.py 写用例（继承 BaseCase）：
   - 用例函数名：test_<模块>_<用例ID>，用例ID 与 tag CSV 里的 用例ID 一致；
   - 类属性 page_cls 指定被测页面对象类；
   - 通过框架的 page fixture 拿页面，调业务方法 + 断言；
3. 需要 tag 管理时，在 tag/<模块>/<模块名>.csv 登记该用例（本示例已登记）；
4. 运行：lets-go run <项目>（或直接在项目根敲 pytest）。
"""
import allure

from cases.base_case import BaseCase
from pages import HomePage


@allure.feature("首页")
@allure.story("搜索")
class TestHome(BaseCase):
    page_cls = HomePage  # 被测页面对象类：open_page 由基类统一实例化并打开

    @allure.title("首页搜索功能验证")
    def test_home_search_1001(self, page):
        """首页搜索功能验证"""
        home = self.open_page(page)  # 基类样板：实例化 HomePage 并打开首页
        home.search("手机")          # 只写业务步骤
        assert "手机" in home.get_search_result(), "搜索结果应包含搜索关键词"
''',
    "pages/__init__.py": '''#!/usr/bin/env python3
# coding=utf-8
"""页面对象统一出口（pages 包）。

新增页面对象后，在这里集中导出，用例统一从 pages 导入，不直接 import 具体文件：

    from pages import HomePage   # 而不是 from pages.home_page.page import HomePage

好处：页面文件路径/类名调整时，只需要改这里，用例层无需改动。
"""
from pages.base_page import BasePage
from pages.home_page.page import HomePage

__all__ = ["BasePage", "HomePage"]
''',
    "pages/base_page.py": '''#!/usr/bin/env python3
# coding=utf-8
"""BasePage：页面对象基类。

PO 模式的核心收益在这里：把**业务无关**的通用操作下沉到基类——
输入、点击、等待、取文本、判断可见，以及系统高频按钮（确认/取消/保存等）。

具体页面对象（如 HomePage）只需继承 BasePage，然后**只写业务**：
元素定位器 + 业务操作组合，不用重复封装通用动作。

同步用例传入 playwright.sync_api 的 Page；异步用例传入 playwright.async_api
的 Page（其中方法需 await）。本示例为同步写法。
"""
from playwright.sync_api import Page


class BasePage:
    """页面对象基类：提供通用元素操作与常用按钮，业务页面继承后直接复用。"""

    def __init__(self, page: Page):
        self.page = page

    # ---- 通用元素操作（业务无关，各页面直接复用）----
    def fill(self, locator: str, text: str):
        """输入框填值"""
        self.page.fill(locator, text)

    def click(self, locator: str):
        """点击元素"""
        self.page.click(locator)

    def wait_visible(self, locator: str, timeout: int = 10000):
        """等待元素可见（页面加载、弹层出现等统一走这里）"""
        self.page.wait_for_selector(locator, state="visible", timeout=timeout)

    def get_text(self, locator: str) -> str:
        """取元素文本（供断言）"""
        return self.page.text_content(locator) or ""

    def is_visible(self, locator: str) -> bool:
        """元素是否可见"""
        return self.page.is_visible(locator)

    # ---- 常用按钮（业务无关的高频操作，按需在基类扩展）----
    def click_confirm(self):
        """点击确认按钮"""
        self.page.get_by_role("button", name="确认").click()

    def click_cancel(self):
        """点击取消按钮"""
        self.page.get_by_role("button", name="取消").click()

    def click_save(self):
        """点击保存按钮"""
        self.page.get_by_role("button", name="保存").click()
''',
    "pages/home_page/page.py": '''#!/usr/bin/env python3
# coding=utf-8
"""HomePage：首页页面对象（PO 模式示例）。

PO（Page Object）模式的核心约定：
1. 一个页面一个类，类名与页面语义对应（HomePage -> 首页）；
2. **继承 BasePage**：输入/点击/等待/取文本等通用操作直接复用基类，
   本类只写业务（元素定位器 + 业务操作组合）；
3. 元素定位器集中写在类顶部，页面结构变化时只改这里；
4. 业务方法返回业务结果给用例断言，用例层不出现定位器或浏览器细节。
"""
import os

from pages.base_page import BasePage


class HomePage(BasePage):
    """首页页面对象：只写业务逻辑，通用操作继承 BasePage。"""

    # ---- 元素定位器：集中维护，页面结构变了只改这里 ----
    _search_input = 'input[placeholder*="搜索"]'
    _search_button = 'button:has-text("搜索")'
    _search_result = ".search-result"

    # ---- 页面操作（业务逻辑）----
    def goto(self, path: str = ""):
        """打开首页。基址来自项目 conftest 注入的 LETSGO_TEST_BASE_URL。"""
        base = os.environ.get("LETSGO_TEST_BASE_URL", "http://127.0.0.1:8000")
        self.page.goto(f"{base}{path}")

    def search(self, keyword: str):
        """输入关键词并点击搜索，等待结果出现（通用动作来自 BasePage）。"""
        self.fill(self._search_input, keyword)
        self.click(self._search_button)
        self.wait_visible(self._search_result)

    def get_search_result(self) -> str:
        """返回搜索结果文本（业务结果，供用例断言）。"""
        return self.get_text(self._search_result)
''',
    "tag/home.csv": '''脚本ID,用例ID,用例级别,场景,跳过原因,废弃,其它
1001,1001,L1,首页搜索,,,
''',
    "README.md": '''# {name} 自动化测试项目

基于 lets-go 框架、遵循 **PO（Page Object）模式** 的 Web 自动化测试项目骨架。

## 目录结构

```
{name}/
├─ conftest.py            # 项目根配置：声明框架插件 + 注入被测地址（必改）
├─ pytest.ini             # pytest 配置：收集规则 / 默认录屏
├─ cases/                 # 测试用例（一个用例文件 = 一个页面/功能的一组用例）
│  ├─ base_case.py        # 用例基类：公共样板（打开页面/实例化页面对象）下沉到这里
│  └─ home/
│     └─ test_home_1001.py
├─ pages/                 # 页面对象（PO 核心：每个页面一个类）
│  ├─ __init__.py         # 统一出口：所有页面对象在此导出，用例从 pages 导入
│  ├─ base_page.py        # 页面基类：通用元素操作/常用按钮（业务无关）
│  └─ home_page/
│     └─ page.py
└─ tag/                   # 用例标记（可选：tag 机制启用后支持 --tag 筛选）
   └─ home.csv            # 一个模块目录一个 CSV，登记该目录下所有用例
```

> 说明：框架约定标记目录名为 `tag`（单数），位于项目根；项目没有 `tag/` 目录时
> 不启用 tag 机制，用例不校验、不筛选，全部直接执行。

## 核心思路：基类下沉公共逻辑，页面/用例只写业务

自动化开发大量代码是重复的（输入、点击、等待、打开页面、实例化对象……）。
本骨架用**两个基类**把这些业务无关的逻辑收拢，写页面和用例时只需要关注业务：

| 基类 | 位置 | 收拢什么 |
| --- | --- | --- |
| `BasePage` | pages/base_page.py | 通用元素操作（fill/click/wait_visible/get_text/is_visible）、常用按钮（确认/取消/保存） |
| `BaseCase` | cases/base_case.py | 用例公共样板（实例化页面对象、打开页面 open_page），后续可加登录/数据准备等 |

## 怎么开发自动化用例（PO 模式三步走）

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
from pages.home_page.page import HomePage

__all__ = ["BasePage", "HomePage"]
```

### 2. 写用例（cases/）
继承 `BaseCase`，设置 `page_cls` 指定被测页面，**只写业务步骤 + 断言**：

```python
import allure
from cases.base_case import BaseCase
from pages import HomePage

@allure.feature("首页")
class TestHome(BaseCase):
    page_cls = HomePage  # 被测页面对象类

    def test_home_search_1001(self, page):
        """首页搜索功能验证"""
        home = self.open_page(page)  # 基类样板：实例化 HomePage 并打开
        home.search("手机")          # 业务步骤
        assert "手机" in home.get_search_result(), "搜索结果应包含关键词"
```

约定：
- 用例函数名 `test_<模块>_<用例ID>`，用例ID（如 1001）与 tag CSV 中的 用例ID 对应；
- `page` 是框架提供的 fixture（Playwright 页面）：同步用例直接调用，
  异步用例 `async def test_xxx(page)` 用 `await page.xxx()`，两种写法都支持；
- 通用能力按需在 `BasePage`/`BaseCase` 扩展（如公共登录、表格操作），页面和用例保持只写业务。

### 3. 登记 tag（可选）
启用 tag 机制后，用例必须先在 `tag/` 中登记，否则运行会提示"缺少tag信息"。
**一个模块目录对应一个 CSV**（文件名 = 模块目录名），登记该目录下所有用例：

```
tag/home.csv:
脚本ID,用例ID,用例级别,场景,跳过原因,废弃,其它
1001,1001,L1,首页搜索,,,
```

- 脚本ID 必须等于 用例ID（框架校验）；
- 运行时可筛选：`lets-go run <项目> --tag "L1 and 首页"`；
- 不想用 tag：删掉 `tag/` 目录即可，用例直接全部执行。

## 运行

```bash
# 首次：注册项目（把 <名称> 换成你的项目名）
lets-go add <名称> .

# 执行全部用例
lets-go run <名称>

# 只收集不执行（快速验证骨架）
lets-go run <名称> --collect-only

# 带 tag 筛选
lets-go run <名称> --tag "smoke and L1"
```

或直接在项目根敲 pytest（conftest 已声明框架插件）：

```bash
pytest
```

## 配置

| 配置项 | 位置 | 说明 |
| --- | --- | --- |
| 被测系统地址 | conftest.py 的 LETSGO_TEST_BASE_URL | 必改，页面跳转基址 + 报告环境信息 |
| 用例链接前缀 | conftest.py 的 LETSGO_TEST_CASE_BASE_URL | 可选 |
| 录屏开关 | pytest.ini 的 --record | 默认开；删掉该行即关闭 |
| 慢速/是否显示浏览器 | 框架 configs/config.ini 的 [run] 节 | 全局生效 |

## 运行产物

默认输出到项目根下：`logs/`（日志）、`reports/`（allure 报告）、`cache/`（临时/截图/录屏）。
可重定向：`lets-go run <名称> --output D:\\产物目录`。

## 依赖

框架依赖由 lets-go 管理：`lets-go install`（core/playwright/allure/ffmpeg 可选）。
测试项目自身的 Python 依赖（如 redis、pymysql）由项目自行安装到运行环境。
''',
}


def cmd_init(args) -> int:
    """初始化测试项目骨架：目标目录不存在则创建（区别于 add 要求目录已存在）"""
    target = os.path.abspath(os.path.expanduser(args.target))
    if os.path.exists(target) and os.listdir(target):
        raise SystemExit(f"错误：目录已存在且非空，请选择新目录：{target}")
    os.makedirs(target, exist_ok=True)
    for rel, content in INIT_TEMPLATES.items():
        path = os.path.join(target, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content.replace("{name}", os.path.basename(target)))
    print(f"已在 {target} 创建测试项目骨架：")
    for rel in INIT_TEMPLATES:
        print(f"  {os.path.join(target, rel)}")
    print("\n下一步：")
    print(f"  1. 编辑 {os.path.join(target, 'conftest.py')} 里的 LETSGO_TEST_BASE_URL 为被测系统实际地址")
    print(f"  2. 注册并运行：lets-go add <名称> {target}")
    print("     lets-go run <名称>")
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
        help="透传给 pytest 的参数，如 --record=yes(录屏) --tag \"smoke and L1\" --collect-only",
    )
    p_run.set_defaults(func=cmd_run)

    p_init = sub.add_parser(
        "init", help="初始化一个 PO 模式的测试项目骨架（含示例用例/页面对象/tag）"
    )
    p_init.add_argument(
        "target",
        help="项目目录名或路径（不存在则创建），如：lets-go init SHOP-TEST",
    )
    p_init.set_defaults(func=cmd_init)

    p_install = sub.add_parser("install", help="安装/检查框架依赖（pipenv 管理虚拟环境）")
    p_install.add_argument(
        "component",
        nargs="?",
        choices=["core", "playwright", "allure", "ffmpeg", "all"],
        default="all",
        help="安装组件：core(框架核心Python依赖)/playwright(浏览器+录制编码器)/"
        "allure(报告工具，下载到用户目录~/.lets-go/allure)/ffmpeg(桌面录屏，可选)/all(全部，默认)",
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
