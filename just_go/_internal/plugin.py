#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:20
# @Author   :luye
"""
just-go 框架的 pytest 插件入口。

原为测试项目根目录的 conftest.py，框架独立后迁移至此。
通过 `just-go run <项目>` 执行时由 CLI 注入 `-p just_go._internal.plugin` 加载；
也可在测试项目 conftest.py 中声明 `pytest_plugins = ["just_go._internal.plugin"]` 后直接敲 pytest。

用例写法支持两种：
- 同步：def test_xxx(page)，page 为 playwright.sync_api 页面（默认，原有方式）
- 异步：async def test_xxx(page)，page 为 playwright.async_api 页面，可 await page.xxx()
  异步用例由 pytest_pyfunc_call 在事件循环中执行，无需安装 pytest-asyncio。
"""
import asyncio
import inspect
import os
import time

import allure
import pytest
from _pytest.python import Function

from just_go._internal.errors import ConfigError
from just_go._internal.logger import custom_logger, logger, set_case_label
from just_go._internal.parse_tag import ParseTag  # 显式导入，确保使用 tag/ 目录限定的新版 ParseTag
from just_go._internal.settings import ROOTDIR, TEMP_PATH, TMP_REPORT_PATH, config
from just_go._internal.tools import generate_report, record

parse_tag = ParseTag()
enable_record = False
# storage_state 缺失只在首次提示一次，避免每个用例启动浏览器都刷一遍警告
_storage_state_missing_warned = False


def pytest_runtest_logstart(nodeid, location):
    print("\n")


def pytest_runtest_setup(item):
    """用例 setup（含 fixture 启动）前写入用例标识并打印用例标题

    日志每行前缀为用例ID（非 tag 模式的用例退回方法名），标题单独打印一行，
    这样从日志开头就能看出当前跑的是哪条用例，步骤日志也不必重复长标题。
    """
    test_id = parse_tag.get_test_case_id(item)
    set_case_label(test_id or item.name)
    doc = (item.obj.__doc__ or "").strip().splitlines()
    logger.info(f"用例标题：{doc[0].strip() if doc else '未命名用例'}")


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """fixture 清理（含关闭浏览器、停录屏）也带本用例标识，清理完再清除"""
    yield
    set_case_label("")


def pytest_sessionstart(session):
    """在测试会话开始时加载所有标记数据"""
    logger.info("开始加载测试用例标记数据...")
    # 多环境：--env 指定环境标识（dev/test/prod），写入 JUSTGO_ENV 供测试项目
    # conftest 按环境加载被测地址（详见骨架 conftest.py 的 BASE_URLS 示例）
    env = session.config.getoption("--env")
    if env:
        os.environ["JUSTGO_ENV"] = env
    parse_tag.load_all_test_tags(session)


def pytest_collection_modifyitems(session, config, items):
    """pytest收集用例后修改用例列表"""
    deselected = []
    skipped = []

    tag_expression = config.getoption("--tag")
    # tag 模式为可选项：项目根存在 tag/*.csv 数据（pytest_sessionstart 已加载进缓存）时启用；
    # 未配置 tag 数据的项目不校验、不筛选，用例直接执行——不强制任何测试项目的组织方式
    tag_mode = bool(parse_tag.TEST_TAGS_CACHE)
    if tag_expression:
        if tag_mode:
            logger.info(f"应用标签筛选表达式: {tag_expression}")
        else:
            logger.warning(
                "项目未配置 tag 数据（未发现 tag/*.csv），--tag 筛选不可用，将执行全部用例"
            )

    for item in items:
        if not isinstance(item, Function):
            continue
        if not tag_mode:
            # 未采用 tag 管理模式：用例直接执行，不要求用例名含 ID、不校验 tag
            continue

        test_id = parse_tag.get_test_case_id(item)
        if not test_id:
            logger.debug(f"无法从测试名提取ID: {item.name}")
            deselected.append(item)
            continue

        csv_path = parse_tag.get_module_csv_path(item)
        if not csv_path:
            logger.debug(f"无法获取模块CSV路径: {item.name}")
            deselected.append(item)
            continue

        tags = parse_tag.TEST_TAGS_CACHE.get(csv_path)
        if not tags or test_id not in tags:
            pytest.exit(f"用例[{item.name}]，缺少tag信息")

        tag_info = tags[test_id]
        skip_reason = tag_info.get("跳过原因", "").strip()
        if skip_reason:
            item.add_marker(pytest.mark.skip(reason=f"{skip_reason}"))
            skipped.append(item)
            continue

        if tag_expression:
            matches = parse_tag.evaluate_expression(tag_expression, tag_info)
            if not matches:
                deselected.append(item)
                continue

        generate_report.add_mark(item, config, tag_info)

    for item in deselected:
        items.remove(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
        logger.info(f"已过滤 {len(deselected)} 个测试用例")
        custom_logger.logs.clear()


def pytest_addoption(parser):
    group = parser.getgroup("tag-filtering")
    group.addoption("--tag", action="store", help="按标签表达式筛选，支持and/or逻辑")
    parser.addoption(
        "--record",
        action="store",
        default="no",
        choices=["yes", "no"],
        help="启用录屏功能 (yes/no)",
    )
    parser.addoption(
        "--env",
        action="store",
        default=None,
        help="运行环境标识（如 dev/test/prod），写入 JUSTGO_ENV 供测试项目按环境加载配置",
    )
    parser.addoption(
        "--report-single-mode",
        action="store",
        default="yes",
        choices=["yes", "no"],
        help="报告生成模式：yes=单文件 HTML，no=目录模式",
    )


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    if session.config.getoption("collectonly"):
        return
    generate_report.run()


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    config.option.allure_report_dir = TMP_REPORT_PATH
    if config.getoption("--record") == "yes":
        global enable_record
        enable_record = True
    generate_report.single_file = config.getoption("--report-single-mode") != "no"


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """支持 async def 测试用例：在绑定的事件循环中执行协程。

    异步用例的 page fixture 会在 request.node 上挂载 _justgo_loop（其浏览器
    driver 绑定该循环），此处复用同一循环执行用例；未请求 page 的纯异步用例
    则自建临时循环。返回 True 表示函数已由插件执行完毕。
    """
    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None
    loop = getattr(pyfuncitem, "_justgo_loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        pyfuncitem._justgo_loop = loop
        own_loop = True
    else:
        own_loop = False
    # 与 pytest 原生行为一致：只传用例声明的 fixture 参数（避免注入未声明的自动 fixture）
    testargs = {
        arg: pyfuncitem.funcargs[arg]
        for arg in pyfuncitem._fixtureinfo.argnames
    }
    try:
        loop.run_until_complete(pyfuncitem.obj(**testargs))
    finally:
        if own_loop:
            loop.close()
    return True


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    test_id = parse_tag.get_test_case_id(item)
    doc_string = item.obj.__doc__ or "未命名用例"
    # 未采用 tag 模式（或用例名无 ID）时，标题直接用用例描述
    allure.dynamic.title(f"{test_id}-{doc_string}" if test_id else doc_string)
    report = outcome.get_result()
    custom_logger.attach_logs_to_allure(
        report.when if report.when != "call" else "case"
    )
    if report.when == "call":
        item._justgo_failed = report.failed
        if report.failed and "page" in item.funcargs:
            page = item.funcargs["page"]
            raw_page = getattr(page, "page", page)
            try:
                screenshot_path = f"{TEMP_PATH}/screenshot-{item.name}.png"
                target_page = raw_page.context.pages[-1]
                loop = getattr(item, "_justgo_loop", None)
                if loop is not None and not loop.is_closed():
                    loop.run_until_complete(target_page.screenshot(path=screenshot_path))
                else:
                    target_page.screenshot(path=screenshot_path)
                allure.attach.file(
                    screenshot_path,
                    name="Failure Screenshot",
                    attachment_type=allure.attachment_type.PNG,
                )
                os.remove(screenshot_path)
            except Exception as e:
                logger.error(f"无法添加附件: {e}")

    if report.when == "teardown" and "page" in item.funcargs:
        video_file = record.record_file
        if video_file:
            if getattr(item, "_justgo_failed", False):
                allure.attach.file(
                    video_file,
                    name="Test Record",
                    attachment_type=record.attachment_type,
                )
            try:
                os.remove(video_file)
            except Exception:
                time.sleep(2)
                try:
                    os.remove(video_file)
                except OSError:
                    logger.warning(f"录屏文件未能删除，已保留: {video_file}")


def _page_setup() -> dict:
    """构造浏览器启动与上下文参数（同步/异步共用）

    - browser_type：config.run.browser_type 指定 chromium/firefox/webkit；
    - launch：浏览器进程参数（args / headless / slow_mo / 沙箱 / 可执行文件路径）；
    - context：上下文参数（视口 / CSP / 证书 / 登录态）。storage_state 只对
      new_context() 生效，launch_persistent_context() 不接受该参数。
    """

    browser_type = (config.run.browser_type or "chromium").strip().lower()
    if browser_type not in ("chromium", "firefox", "webkit"):
        raise ConfigError(
            f"不支持的浏览器类型: {browser_type}（仅支持 chromium/firefox/webkit）"
        )

    launch_setup = {
        "args": [
            "--start-maximized",
        ],
        # Playwright 默认 chromiumSandbox=False 会自动追加 --no-sandbox，
        # 浏览器顶部会出现“不受支持的命令行标记”横幅；显式开启沙箱即可消除。
        "chromium_sandbox": True,
        "headless": not config.run.show_browser,
        "slow_mo": int(config.run.slow_time),
    }
    if config.framework.browser_path:
        launch_setup["executable_path"] = config.framework.browser_path

    context_setup = {
        "bypass_csp": True,
        "ignore_https_errors": True,
        "no_viewport": True,
    }

    storage_state = (config.run.storage_state or "").strip()
    if storage_state:
        state_path = (
            storage_state
            if os.path.isabs(storage_state)
            else os.path.join(ROOTDIR, storage_state)
        )
        # 首次运行时登录态文件还没生成（要等登录用例保存后才存在），
        # 这里不能中断整个套件：跳过加载，保存后下次运行自动生效
        if os.path.isfile(state_path):
            context_setup["storage_state"] = state_path
        else:
            global _storage_state_missing_warned
            if not _storage_state_missing_warned:
                _storage_state_missing_warned = True
                logger.warning(
                    f"storage_state 文件不存在，已跳过登录态加载：{state_path}"
                    "（首次运行属正常，登录用例保存后下次生效）"
                )

    return {
        "browser_type": browser_type,
        "launch": launch_setup,
        "context": context_setup,
    }


def _dump_running_loop() -> None:
    """Sync API 不可用时的诊断：把运行中的事件循环和活动协程打到日志。

    Playwright 同步 API 要求当前线程没有运行中的事件循环。若 pytest 环境里有
    插件（或宿主的 sitecustomize/PYTHONPATH）提前起了 loop，报错只会指向
    playwright，看不出 loop 从哪来，这里补上 loop 里的活动任务和栈。
    正常环境调用无副作用，不产生任何日志。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    import sys
    import threading

    logger.error(
        f"检测到运行中的 asyncio 事件循环（线程 {threading.current_thread().name}）："
        f"{loop!r}"
    )
    logger.error(f"解释器：{sys.executable}")
    tasks = asyncio.all_tasks(loop)
    logger.error(f"活动协程任务数：{len(tasks)}")
    for task in list(tasks)[:10]:
        logger.error(f"  任务：{task!r}")
        try:
            frames = task.get_stack()
        except Exception:
            frames = []
        for frame in frames[-3:]:
            logger.error(
                f"    {frame.f_code.co_filename}:{frame.f_lineno}"
                f" in {frame.f_code.co_name}"
            )

    # 任务里出现 PlaywrightContextManager / PipeTransport，说明这个 loop 是
    # 上一次 sync_playwright().start() 失败后没清理干净留下的，不是外部插件起的。
    if any(
        "PlaywrightContextManager" in repr(task) or "PipeTransport" in repr(task)
        for task in tasks
    ):
        logger.error(
            "该事件循环由 Playwright 自身启动后残留：上一次 start() 失败未清理 loop。"
            "当前上报的是二次错误，首次失败的真实原因请加 --reruns=0 单独运行查看。"
        )


def _sync_page_lifecycle(page_setup: dict):
    """同步模式：playwright.sync_api 单进程驱动（原有方式）"""
    from playwright.sync_api import sync_playwright

    browser_type = page_setup["browser_type"]
    launch_kwargs = page_setup["launch"]
    context_kwargs = page_setup["context"]
    _dump_running_loop()
    driver = None
    browser = None
    context = None
    recording = False
    try:
        # rerun 会把首次失败的原因覆盖成随后的 loop 残留错误，这里先落一条完整栈，
        # 保证 --reruns>0 时日志里仍能看到真正的失败原因。
        driver = sync_playwright().start()
        browser = getattr(driver, browser_type).launch(**launch_kwargs)
        context = browser.new_context(**context_kwargs)
        _page = context.new_page()
        if enable_record:
            try:
                record.start(TEMP_PATH)
                recording = True
            except Exception as exc:
                # 录屏是可选增强：缺 ffmpeg 不该让用例连 setup 都过不去
                logger.warning(f"录屏启动失败，本次跳过录屏：{exc}")
        yield _page
        if recording:
            record.stop()
    except Exception:
        logger.exception("Playwright 同步浏览器会话异常（首次失败的真实原因）")
        raise
    finally:
        # 任何退出路径（yield 前抛异常、用例中断、正常结束）都必须关闭上下文、
        # 浏览器与 driver，否则 start() 建的事件循环会留在 running 状态，后续用例
        # 全部报 "Playwright Sync API inside the asyncio loop"。
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if driver is not None:
            try:
                driver.stop()
            except Exception:
                pass


def _async_page_lifecycle(request, page_setup: dict):
    """异步模式：playwright.async_api 协程驱动，事件循环挂载到 request.node。

    浏览器 driver 与用例执行共用同一事件循环（_justgo_loop），用例中 await
    page.xxx() 与 fixture 的启动/关闭在同一 loop 内完成。
    """
    from playwright.async_api import async_playwright

    browser_type = page_setup["browser_type"]
    launch_kwargs = page_setup["launch"]
    context_kwargs = page_setup["context"]
    loop = asyncio.new_event_loop()
    request.node._justgo_loop = loop
    driver = None
    browser = None
    context = None
    recording = False
    try:
        driver = loop.run_until_complete(async_playwright().start())
        browser = loop.run_until_complete(
            getattr(driver, browser_type).launch(**launch_kwargs)
        )
        context = loop.run_until_complete(browser.new_context(**context_kwargs))
        _page = loop.run_until_complete(context.new_page())
        if enable_record:
            try:
                record.start(TEMP_PATH)
                recording = True
            except Exception as exc:
                # 录屏是可选增强：缺 ffmpeg 不该让用例连 setup 都过不去
                logger.warning(f"录屏启动失败，本次跳过录屏：{exc}")
        yield _page
        if recording:
            record.stop()
    except Exception:
        logger.exception("Playwright 异步浏览器会话异常（首次失败的真实原因）")
        raise
    finally:
        if context is not None:
            try:
                loop.run_until_complete(context.close())
            except Exception:
                pass
        if browser is not None:
            try:
                loop.run_until_complete(browser.close())
            except Exception:
                pass
        if driver is not None:
            try:
                loop.run_until_complete(driver.stop())
            except Exception:
                pass
        try:
            loop.close()
        except Exception:
            pass


@pytest.fixture
def _pw_page(request):
    """底层 Playwright Page fixture（同步/异步自动路由）。

    用户一般不直接用，通过覆盖 `page` fixture 包装成自己的 PageExport。
    """
    page_setup = _page_setup()
    if inspect.iscoroutinefunction(request.node.obj):
        yield from _async_page_lifecycle(request, page_setup)
    else:
        yield from _sync_page_lifecycle(page_setup)


@pytest.fixture
def page(_pw_page):
    """页面 fixture：默认直接返回底层 Playwright Page。

    在 conftest.py 中覆盖此 fixture 可包装成 PageExport：
        @pytest.fixture
        def page(_pw_page):
            return PageExport(_pw_page)
    """
    return _pw_page
