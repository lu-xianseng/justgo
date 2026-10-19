#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:20
# @Author   :luye
"""
lets-go 框架的 pytest 插件入口。

原为测试项目根目录的 conftest.py，框架独立后迁移至此。
通过 `lets-go run <项目>` 执行时由 CLI 注入 `-p lets_go.plugin` 加载；
也可在测试项目 conftest.py 中声明 `pytest_plugins = ["lets_go.plugin"]` 后直接敲 pytest。
"""
from lets_go import *

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


def pytest_runtest_call(item):
    logger.info(item.obj.__doc__)


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
                if "page" in item.funcargs:
                    screenshot_path = f"{TEMP_PATH}/screenshot-{item.name}.png"
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


@pytest.fixture
def page():
    import tempfile
    import shutil
    from playwright.sync_api import (
        sync_playwright,
        BrowserType,
        Browser,
        BrowserContext,
    )

    driver = sync_playwright().start()
    temp_dir = tempfile.mkdtemp(prefix="playwright_temp_")
    page_setup = {
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
        page_setup["record_video_dir"] = video_dir
        page_setup["record_video_size"] = {"width": 1280, "height": 720}
    if config.framework.browser_path:
        page_setup["executable_path"] = config.framework.browser_path
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
    shutil.rmtree(temp_dir, ignore_errors=True)
