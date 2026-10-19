#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:20
# @Author   :luye
"""
lets-go 框架的 pytest 插件入口。

原为测试项目根目录的 conftest.py，框架独立后迁移至此。
通过 `lets-go run <项目>` 执行时由 CLI 注入 `-p lets_go.plugin` 加载；
也可在测试项目 conftest.py 中声明 `pytest_plugins = ["lets_go.plugin"]` 后直接敲 pytest。

用例写法支持两种：
- 同步：def test_xxx(page)，page 为 playwright.sync_api 页面（默认，原有方式）
- 异步：async def test_xxx(page)，page 为 playwright.async_api 页面，可 await page.xxx()
  异步用例由 pytest_pyfunc_call 在事件循环中执行，无需安装 pytest-asyncio。
"""
import asyncio
import inspect
from lets_go import *
from lets_go.parse_tag import ParseTag  # 显式使用新版 ParseTag（tag/ 目录限定 + 可选模式），
# 覆盖 from lets_go import * 可能绑定到 tag_manage 旧版 ParseTag 的情况
from lets_go.settings import config as letsgo_config  # pytest_configure 参数名遮蔽 config，用别名

parse_tag = ParseTag()
enable_record = False


def pytest_runtest_logstart(nodeid, location):
    print("\n")


def pytest_sessionstart(session):
    """在测试会话开始时加载所有标记数据"""
    logger.info("开始加载测试用例标记数据...")
    parse_tag.load_all_test_tags(session)


def pytest_collection_modifyitems(session, config, items):
    """pytest收集用例后修改用例列表"""
    deselected = []
    skipped = []
    registered_marks = [mark.split(":")[0].strip() for mark in config.getini("markers")]

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

        is_deprecated = tag_info.get("废弃", None)
        if is_deprecated and not is_deprecated.strip().lower() in ["true", "yes"]:
            pytest.exit(f"用例[{item.name}]，标记废弃关键字错误，仅支持：true/yes")
        if is_deprecated:
            item.add_marker(pytest.mark.skip(reason="用例废弃"))
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
    # 录屏后端由测试项目在 pytest.ini 指定（默认 playwright 内置录屏；ffmpeg 需安装）
    parser.addini(
        "record_backend",
        "录屏后端：playwright（内置，默认）或 ffmpeg（桌面录屏，需安装 ffmpeg）",
        default="playwright",
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
    # 录屏后端：项目 pytest.ini 的 record_backend 优先，写入运行时配置供 Record 实时读取
    letsgo_config.run.record_backend = config.getini("record_backend")


def pytest_runtest_call(item):
    logger.info(item.obj.__doc__)


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem):
    """支持 async def 测试用例：在绑定的事件循环中执行协程。

    异步用例的 page fixture 会在 request.node 上挂载 _letsgo_loop（其浏览器
    driver 绑定该循环），此处复用同一循环执行用例；未请求 page 的纯异步用例
    则自建临时循环。返回 True 表示函数已由插件执行完毕。
    """
    if not inspect.iscoroutinefunction(pyfuncitem.obj):
        return None
    loop = getattr(pyfuncitem, "_letsgo_loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        pyfuncitem._letsgo_loop = loop
    # 与 pytest 原生行为一致：只传用例声明的 fixture 参数（避免注入未声明的自动 fixture）
    testargs = {
        arg: pyfuncitem.funcargs[arg]
        for arg in pyfuncitem._fixtureinfo.argnames
    }
    loop.run_until_complete(pyfuncitem.obj(**testargs))
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
        if report.failed and "page" in item.funcargs:
            page: Page = item.funcargs["page"]
            pages = page.context.pages
            try:
                screenshot_path = f"{TEMP_PATH}/screenshot-{item.name}.png"
                loop = getattr(item, "_letsgo_loop", None)
                if loop is not None and not loop.is_closed():
                    # 异步模式：screenshot 是协程，需在事件循环中执行
                    loop.run_until_complete(pages[-1].screenshot(path=screenshot_path))
                else:
                    pages[-1].screenshot(path=screenshot_path)
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
            allure.attach.file(
                video_file,
                name=f"Test Record",
                attachment_type=record.attachment_type,
            )
            try:
                os.remove(video_file)
            except Exception:
                time.sleep(2)
                os.remove(video_file)


def _page_setup() -> dict:
    """构造浏览器启动参数（同步/异步共用）"""
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix="playwright_temp_")
    setup = {
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
        ],
        "headless": not config.run.show_browser,
        "slow_mo": int(config.run.slow_time),
        "bypass_csp": True,
        "ignore_https_errors": True,
        "no_viewport": True,
        "user_data_dir": temp_dir,
    }
    if enable_record and record.backend == "playwright":
        # Playwright 内置录屏：零依赖，产出 webm；视频目录独立于 user_data_dir
        video_dir = tempfile.mkdtemp(prefix="playwright_video_")
        setup["record_video_dir"] = video_dir
        setup["record_video_size"] = {"width": 1280, "height": 720}
    if config.framework.browser_path:
        setup["executable_path"] = config.framework.browser_path
    return setup


def _sync_page_lifecycle(page_setup: dict):
    """同步模式：playwright.sync_api 单进程驱动（原有方式）"""
    import shutil
    from playwright.sync_api import sync_playwright

    driver = sync_playwright().start()
    browser = driver.chromium.launch_persistent_context(**page_setup)
    _page = browser.pages[0]
    if enable_record:
        record.start(TEMP_PATH)
    yield _page
    if enable_record:
        record.stop()
    browser.close()
    if enable_record and record.backend == "playwright":
        # 视频在浏览器上下文关闭后 finalize，需在 driver 停止前读取路径
        try:
            record.set_record_file(_page.video.path())
        except Exception as e:
            logger.error(f"获取录屏文件失败: {e}")
    driver.stop()
    shutil.rmtree(page_setup["user_data_dir"], ignore_errors=True)


def _async_page_lifecycle(request, page_setup: dict):
    """异步模式：playwright.async_api 协程驱动，事件循环挂载到 request.node。

    浏览器 driver 与用例执行共用同一事件循环（_letsgo_loop），用例中 await
    page.xxx() 与 fixture 的启动/关闭在同一 loop 内完成。
    """
    import shutil
    from playwright.async_api import async_playwright

    loop = asyncio.new_event_loop()
    request.node._letsgo_loop = loop
    driver = loop.run_until_complete(async_playwright().start())
    browser = loop.run_until_complete(
        driver.chromium.launch_persistent_context(**page_setup)
    )
    _page = browser.pages[0]
    if enable_record:
        record.start(TEMP_PATH)
    yield _page
    if enable_record:
        record.stop()
    loop.run_until_complete(browser.close())
    if enable_record and record.backend == "playwright":
        try:
            # async API 的 Video.path() 是协程，需在事件循环中执行
            video_path = loop.run_until_complete(_page.video.path())
            record.set_record_file(video_path)
        except Exception as e:
            logger.error(f"获取录屏文件失败: {e}")
    loop.run_until_complete(driver.stop())
    loop.close()
    shutil.rmtree(page_setup["user_data_dir"], ignore_errors=True)


@pytest.fixture
def page(request):
    """页面 fixture：按用例写法自动路由到同步/异步 Playwright 驱动。

    - def test_xxx(page)：同步驱动（原有方式）；
    - async def test_xxx(page)：异步驱动，用例内可 await page.xxx()。
    """
    page_setup = _page_setup()
    if inspect.iscoroutinefunction(request.node.obj):
        yield from _async_page_lifecycle(request, page_setup)
    else:
        yield from _sync_page_lifecycle(page_setup)
