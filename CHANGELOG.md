# 更新日志

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
版本号递增规则：修复 `x.y.patch+1`，新功能 `x.minor+1`，不兼容变更 `major+1`。

## [0.3.4] - 2026-11-17

### 新增
- **UI 断言补齐 Playwright 常用能力**：原有 13 个断言偏少，`to_have_class` / `to_have_attribute` 这类高频断言只能自己 `inner_text()` 手写，绕开了自动等待重试。本轮按 P0 补齐 7 个正向断言：
  - `assert_attribute(locator, name, value=None)`：断言属性值，省略 `value` 时只断言属性存在（`href` / `disabled` / `data-*`）
  - `assert_class(locator, expected)` / `assert_class_contains(locator, expected)`：class 完全一致 / 包含指定类名
  - `assert_values(locator, expected)`：多选控件（`multiple select`）的选中值列表
  - `assert_editable` / `assert_empty` / `assert_attached` / `assert_focused`：可编辑 / 内容为空 / 已挂载 DOM / 获得焦点
  - `assert_id(locator, expected)`：id 断言
- **全部 UI 断言自动生成反向断言 `assert_not_xxx`**：此前除 `assert_not_checked` 外一个都没有，「文本不等于」「属性不是 xx」无法用带重试的断言表达。新增 `@negates` 标记 + `@with_negations` 类装饰器，在导入时按正向签名生成反向方法，调用 Playwright 的 `not_to_*`；同步/异步共用同一份生成逻辑
- **参数透传补齐**：`assert_text` / `assert_text_contains` 支持 `ignore_case` / `use_inner_text`，`assert_url` 支持 `ignore_case`；`assert_text_contains` 的参数名由 `substring` 改为 `expected`，与 Playwright 一致（现在也接受正则与列表）

### 变更
- `assert_text_contains(locator, substring)` 的第二个位置参数改名为 `expected`，且接受正则 / 列表；按位置传参的老代码不受影响，按关键字 `substring=` 调用的需要改名（框架内无此用法）
- 项目模板 `pages/asserts/asserts.py` 的自定义断言示例改为 `assert_order_no`：原示例 `assert_text_contains` 会覆盖内置同名断言，导致自定义版（无自动等待）静默取代内置版

### 测试
- `tests/test_assertion.py` 新增断言覆盖测试：同步/异步方法集合必须一致、每个正向断言都有反向断言、正反签名一致、`@negates` 里的原生断言名在当前 Playwright 版本上真实存在；另有反向分派测试验证真的调用 `not_to_*` 且关键字原样透传（`tests/test_assertion.py` 曾捕获过一个 `not_` 前缀漏写 `to_` 的实现错误）

## [0.3.3] - 2026-11-16

### 变更
- **`just-go init` 不再生成 `config.ini`**：模板里那份全是注释和空值，没有一行真正生效，只是把「可调项清单」摆给用户看，却与 `conftest.py` 里的 `config.run.*` 示例重复。常改的项（`slow_time` / `show_browser` / `browser_type` / `storage_state` / `browser_path` / 报告标题语言）都写在 `conftest.py` 里即时生效；`log_path` / `report_path` / `cache_path` / `allure_path` / `ffmpeg_path` 在框架导入时已算成常量、conftest 覆盖不生效，需要时在项目根自建 `config.ini` 只写要改的项
- 模板 `.gitignore` 增加 `config.ini`：自建的这份是机器相关配置（浏览器/工具绝对路径、产物目录名），不应提交

### 文档
- `docs/reference.md` 的配置章节改为「项目级 `config.ini`（可选）」：列出自建时需要写的项（只含 conftest 改不动的路径项），并说明为什么这些项不能写进 conftest
- 模板 `README.md` / `conftest.py` 注释同步：区分「conftest 里写即时生效」与「必须自建 config.ini」两类配置

## [0.3.2] - 2026-11-16

### 新增
- **接口客户端 `page.api`**：`SyncWebUI` / `AsyncWebUI` 挂 `APIRequest` / `AsyncAPIRequest`，让 GUI 用例在同一会话里造数据、取数据，不必再裸用 `page.request` 手拼 query、每次传 headers
  - 方法：`get` / `post` / `put` / `patch` / `delete` / `request`，透传 `params` / `json` / `data` / `files` / `headers` / `timeout`；`json=` 转 Playwright 的 `data`，`data=dict` 转 `form`，`files=`（路径 / bytes / `(文件名, 内容[, MIME])`）转 `multipart`，同传冲突抛 `ValueError`
  - 统一响应 `ApiResponse` / `AsyncApiResponse`：`status_code` / `ok` / `headers` / `url`、`body()` / `text` / `json()`、`assert_status(*expected)` / `assert_ok()`，不命中抛 `RequestError` 并带 url 与响应前 200 字
  - 相对路径按 `JUSTGO_TEST_BASE_URL`（`setup_env()` 写入）解析，缺基址直接抛 `ConfigError`，不再拼出错误 URL 静默失败
  - 默认不抛非 2xx（业务接口状态码不等于用例失败），`fail_on_status=True` 才在非 2xx 时抛；`retry_times` 映射到 Playwright 的 `max_retries`
  - 超时单位为秒，`timeout=0` 表示不超时（与 Playwright 语义一致）
  - **自动沿用登录态鉴权**：页面对象构造时即 `bind_auth(context)`，监听同源业务请求把 `Authorization` / `X-Access-Token` / `X-Token` 同步进请求头，token 型鉴权（cookie 为空）的项目不必再在 conftest 里抓 token 再注入；显式 `set_headers` / `set_token` 或构造时传 headers 后停止自动覆盖
  - `wait_auth(timeout)` 靠 `page.wait_for_timeout` 推动 Playwright 派发事件，等首屏业务请求带上 token（单纯 `sleep` 等不到），判据是「抓到过鉴权头」而不是 headers 非空；`refresh_api()` 在 page 换 context 后重建并先 `unbind_auth()` 摘掉旧监听；`ensure_api()` 只在 context 真的变了才重建（同 context 切标签不丢已抓到的 token）
  - 边界：不支持流式下载与请求级代理/证书（`context.request` 是 context 级），大文件下载仍走 `Request.download()`；纯 API 套件仍建议用 `Request`，走这条路径会拉起驱动进程

### 修复
- **`--env` 完全不生效**：插件在 `pytest_sessionstart` 才写 `JUSTGO_ENV`，而项目 `conftest.py` 顶部的 `setup_env()` 在导入时就执行了；且它用 `setdefault`，即使环境变量后来变了也不会覆盖。`just-go run demo --env prod` 实际一直请求 dev 地址。改为 `setup_env()` 先从命令行原样取 `--env`，插件在 `pytest_configure` 用解析后的值再调 `apply_env()` 刷新（用户自己 export 的 `JUSTGO_TEST_BASE_URL` 仍优先）
- **`just-go init` 骨架无法被收集**：模板 `cases/login/test_login_1.py` 里写了 `test_login_2`，而 `CaseControl` 要求方法名包含用例文件名，生成项目第一步 `pytest --collect-only` 就 `CaseError` 中断。第二条用例拆到 `test_login_2.py`，`tag/login.csv` 同步登记
- **API 骨架模块名不一致**：`init [api]` 生成 `apis/base_api.py`，但 `user_manager_api.py` 与文档都是 `from .base import BaseApi`，生成项目导入即 `ModuleNotFoundError`。统一为 `apis/base.py`
- **`create_new_instance()` 对模板页面对象 TypeError**：同步版把 `only_keep_one` 透传给子类构造函数，而模板 `BasePage` / `PageExport` 的 `__init__` 只接收 `page`。改为先构造实例再关闭多余 tab（与异步版一致）
- **`--tag` 畸形表达式死循环**：`apply_operator()` 在操作数不足时只 `return` 而不弹出运算符，调用方 `while` 条件不变，`--tag "L1 and )"` / `"L1 and and L1"` 会把整个进程挂死。新增 `_is_well_formed()` 先做结构校验，并让 `apply_operator` 兜底抛错
- **`AsyncAssert` 不认 `AsyncElement`**：`_to_locator` 只处理 `Element`，异步用例 `await page.assert_visible(async_element(...))` 报 `Unsupported type`。两种包装都还原成原生 Locator
- **`assert_url` / `assert_title` 不能传 `PageExport`**：包装对象被 `expect()` 判为 `Unsupported type`，新增 `_to_page()` 还原原生 Page
- **`sleep()` 截断小数**：`int(_time) * 1000` 让 `sleep(0.5)` 实际等待 0ms，改为 `int(float(_time) * 1000)`
- **`close_current_tab()` 只剩一页时拿到已关闭页**：`pages[-1]` 会指向刚关闭的页或空列表；改为先检查数量并提示
- **`page.api` 预绑定失败会中断页面对象构造**：同步 fixture 里构造异步页面对象时没有运行中的事件循环，Playwright 的 `context.on()` 抛 `RuntimeError`。预绑定只是「尽早抓到首屏 token」的优化，任何失败都降级为 `api` 属性懒创建并记 debug 日志，不再打断构造

### 变更（不兼容）
- **`--env` 现在真正生效**：此前该参数被忽略，所有环境一律使用 `dev` 地址；升级后 `--env test` / `--env prod` 会按 `setup_env()` 的映射取地址。若映射里对应环境为空字符串，请求会因基址为空而失败，请补齐地址或只使用 `dev`
- **`page.api` 的 `files=` 语义**：Playwright 的 `fetch` 没有 `files` 参数，文件上传统一转成 `multipart`（`FilePayload`）；请求参数校验失败（`TypeError`）也统一包成 `RequestError`

### 文档
- **README 重写**：按「为什么用 → 30 秒看懂 → 核心能力 → 5 分钟跑通 → 用例怎么写 → 能力详解」重排，特性按工程结构 / 写用例 / 跑用例 / 看结果分组；删掉重复的登录示例与页面类定义；修正 5 处与代码不符的示例（`page.context` → `page.page.context`、不存在的 `BASE_URLS`、tag CSV 嵌套路径、未定义的 `resp`、断言清单从 7 个补全到 22 个）
- 参考手册拆分到 `docs/reference.md`（命令、配置、目录结构、环境要求、FAQ），README 只留主干
- 补充 `LICENSE` 文件（MIT），修复 README 徽章 404
- 异步用例说明更正：模板只生成同步 `PageExport`，异步用例直接用原生 page；需要异步页面对象与断言时给出 `AsyncBasePage` / `AsyncAssert` 的接入方式与混用风险
- 模板生成的 `README.md` 与 API 模板的用例链接配置、tag CSV 路径说明同步更正（`setup_env(case_base_url=...)`、`tag/<模块>.csv`）
- README 新增「在 GUI 用例里调接口：`page.api`」小节（方法、响应对象、鉴权、超时语义、边界）
- 模板 `pages/base_page.py` docstring 补 `self.api` 用法示例，并提醒「接口造数据后页面不会自动刷新，要重新 `goto` / `reload`」；`switch_to_latest_tab` / `close_current_tab` 切换后自动 `ensure_api()`

### 测试
- 246 passed、ruff 通过（新增 75 条用例：41 条接口客户端用例 `tests/test_api.py`，覆盖 URL 拼接与缺基址、`json` / `form` / `str` / `files` 载荷构造、`timeout=0`、敏感头打码、`assert_status` / `assert_ok`、异常包装、`retry_times` 映射、同步/异步双套、`bind_auth` 自动鉴权、`wait_auth`、`unbind_auth` / `ensure_api`、`create_new_instance`、`sleep` 小数秒、`_init_api` 预绑定失败时降级不中断构造（同步/异步）；32 条缺陷回归用例覆盖 `--env` 解析与优先级、畸形 tag 表达式不挂死、`AsyncElement` / `PageExport` 断言还原、骨架 `init` 后可收集、`pytest_configure` 应用 `--env`）
- 端到端验证：本地 HTTP 服务 + 真实 Playwright `APIRequestContext`，`timeout=0` 正常、`files=` 产出 `multipart/form-data` 且文件名保留、`Authorization` 自动沿用、非鉴权头不再让 `wait_auth` 误报；`init [all]` 生成 20 个文件后可 `--collect-only` 收集 3 条用例
- 实际项目验证（`D:/ProjectCode/autolib_autotest`）：升级后登录 + `page.api` 取数用例 1 passed，接口 200 且 `code == 0`，`Authorization` 由 `bind_auth` 自动带入
- 未覆盖：异步 `_async_page_lifecycle` 无真实异步用例可跑，仅代码结构与单测层面检查；`image/finder.py` 两处改动无自动化测试（cv2 为可选依赖，CI 不安装）

## [0.3.1] - 2026-11-13

### 新增
- **locator 入参归一化**：`SyncWebUI` / `AsyncWebUI` 新增 `_as_locator()` / `_as_selector()`，接收 locator 的方法统一支持三种入参——选择器字符串、`element()` 声明的 `Element`、原生 `Locator`
  - `scroll_to` / `upload_file` / `get_attribute` / `switch_to_frame` / `drag_and_drop` 五个方法同步支持；`drag_and_drop` 改走 `Locator.drag_to`
  - `Element` 取 `.native`（绑定它自己的 page，切标签页后仍定位正确，且保留 `first` / `nth` / `filter` 的派生链）；原生 `Locator` 原样返回，不再二次 `page.locator()` 包装
  - `switch_to_frame` 取 `Element.selector`（`frame_locator` 只接受字符串），`Element` 无选择器表达式时抛 `ValueError` 并说明原因
- **模板 `BasePage` 同步**：`pages/base_page.py` 的 `wait_visible` / `get_text` / `is_visible`（同步、异步两套）支持传 `Element`，子类不必再自己写兼容层
- **`AsyncElement.all`**：异步侧补齐与 `Element.all` 对齐，返回 `list[AsyncElement]`（需 `await`）
- **`Record.take_record_file()`**：取出录屏文件并清空引用，供 attach 之后调用
- **`just-go init` 预建 `images/` 目录**：`IMAGE_PATH` 就是项目根，给模板图一个明确的存放位置

### 修复
- **运行时依赖漏声明**：`pyproject.toml` 补齐 `requests`、`faker`。缺声明时干净环境会在 `GenerateReport.set_report_env()` 的 `version("requests")` 抛 `PackageNotFoundError`（用例全过也会在收尾崩溃），`from just_go.http import Request` / `from just_go.data import mock` 直接 `ModuleNotFoundError`
- **`import just_go` 的破坏性副作用**：旧实现在 import 时无条件 `shutil.rmtree(TMP_REPORT_PATH)` 并创建四个产物目录，导致 IDE 索引、`just-go --help`、以及另一个进程正在跑测试时都会删除正在使用的报告目录，目录只读时还会让 import 失败。改为各目录在使用时创建，allure 结果清空移到 `pytest_configure`
- **用例失败时录屏不停**：`record.stop()` 原先写在 fixture 的 `yield` 之后，用例抛异常就被跳过，导致 ffmpeg 进程残留、mp4 不封口。改到 `finally`，成功/失败/中断都会停录屏并关闭浏览器资源
- **录屏文件挂错用例**：`Record.stop()` 不重置输出路径，Windows 上视频删不掉时下一条用例的 teardown 会重复 attach 上一条的视频；新增 `take_record_file()` 在 attach 后取走引用
- **用例失败被误记为 Playwright 会话异常**：旧实现的 `except` 包住了 `yield`，任何断言失败都记成「Playwright 同步浏览器会话异常（首次失败的真实原因）」+ 完整栈。拆成「启动阶段」与「运行阶段」，启动失败单独报错
- **`--tag` 子串匹配误判**：`L1` 会命中 `L10`，token 还会匹配场景等自由文本。ASCII 标签改为按完整标签精确比对，中文 token 保留包含匹配（`--tag 登录` 仍能命中「登录接口」）；标签值支持 `|` / `,` / `;` 分隔多标签
- **tag CSV 缺列导致整套件退出**：`v.strip()` 不设防 `None`，CSV 少一列即 `AttributeError` 并被转成 `pytest.exit`。改为空串兜底，单个文件异常只跳过该文件并告警
- **缺 tag 中断全量**：新增用例还没登记 tag 时会 `pytest.exit` 终止整个会话。改为跳过该用例并汇总告警
- **用例 ID 提取过宽**：任意尾段都被当作 ID（`test_foo_bar_baz` 得到 `baz`）。改为只接受纯数字尾段
- **每列值都注册成 pytest marker**：除用例ID/跳过原因外所有列都被 `addinivalue_line` 注册，CSV 加列会把中文长句塞进 pytest 配置。改为只注册 `用例级别`（`MARKER_COLUMNS` 白名单）
- **日志把普通值当文件路径截断**：任何含 `/` 或 `\` 的值都取 basename，`fill("2026/11/13")` 记成 `"13"`、`evaluate("a/b")` 只剩后半段。改为只在带盘符 / 以分隔符开头 / 带常见文件扩展名时才取文件名
- **`_unwrap_args` 不认 `AsyncElement`**：异步元素互传（`a.drag_to(b)`、`a.filter(has=b)`）会把包装对象直接交给 Playwright 报类型错误
- **`IMAGE_PATH` 与实际解析基准不一致**：`settings.IMAGE_PATH` 是项目根，但模板图解析只认 `Path.cwd()`，IDE/CI 里 cwd ≠ 项目根时找不到图。改为先按 `IMAGE_PATH` 解析，再退回 cwd
- **`_load_template` 抛裸 `OSError`**：模板状态读取失败不在框架异常体系内，改为 `TemplateNotFoundError`
- **非 Function item 崩溃**：`pytest_runtest_setup` / `pytest_runtest_makereport` 直接取 `item.obj.__doc__`，项目含 doctest 等 item 时 `AttributeError`；改为安全取并退回占位标题
- **注册表写坏即静默清空**：`save_registry` 非原子写，写一半崩溃后 `load_registry` 静默返回 `{}`，用户会以为注册记录凭空消失。改为 `mkstemp` + `os.replace` 原子替换，损坏时打印明确警告
- **`@log` 破坏绑定语义 / 日志泄露密码**：`staticmethod` / `classmethod` 被包装成普通函数，静态方法经实例调用时会把 `self` 当第一个参数；docstring 里的 `{{password}}` 会把真实密码写进日志。改为保持原绑定类型、敏感参数打码 `***`
- **`slow_time` 非整数配置崩溃**：配置写成 `0.5`（本意是秒）时 `int()` 直接 `ValueError` 且报错看不出是哪一项；改为 `int(float())` 并抛带原始值的 `ConfigError`
- **`retries=-1` 得到空错误**：循环一次都不执行，最终抛 `RequestError("请求错误: None")`；改为拒绝负数与非整数
- **源码树 `just-go version` 显示旧版本**：先查已安装元数据，本地改了版本号却装过旧 wheel 时会显示成旧版本，误判「改动没生效」；改为源码树优先读 `pyproject.toml`
- **teardown 异常时用例标签残留**：`set_case_label("")` 在 teardown 抛异常时不执行，改为 `try/finally`
- **xdist 并行录屏互相覆盖**：录屏是全局单例 + 整屏抓取，多 worker 会同时录制并互删文件；检测到 `--record=yes` 与并行执行时明确告警（未做 per-worker 隔离）
- **日志取文件名不跨平台**：`Element` 记动作日志时用 `os.path.basename()` 截取文件名，POSIX（GitHub Actions）上它不把反斜杠当分隔符，Windows 盘符路径 `D:\data\logo.png` 会整串留在日志里，导致 Linux CI 的 `test_set_input_files_shows_basename` 失败；改为按最后一个分隔符切分的 `_basename()`，反斜杠与正斜杠都对

### 变更（不兼容）
- **CLI 模块位置**：`cli.py` 移入 `just_go/cli.py`，`[project.scripts]` 入口改为 `just_go.cli:main`，删除 `py-modules = ["cli"]`。此前会往 site-packages 根放一个顶层 `cli` 模块，任何项目的 `import cli` 都会命中它。**旧安装需 `pip uninstall -y just-go` 后重新安装**，否则命令仍指向旧的顶层模块
- **`--tag` 匹配语义**：ASCII 标签由「子串包含」改为「完整标签匹配」，`--tag L1` 不再命中 `L10`
- **缺 tag 的用例**：从「`pytest.exit` 中断整个套件」改为「跳过该用例 + 结束时汇总告警」
- **marker 注册范围**：只有 `用例级别` 列会注册成 `pytest.mark.<级别>`，`用例名称` / `步骤` / `场景` 等自由文本列不再注册
- **产物目录清理时机**：从 `import just_go` 移到 `pytest_configure`（会话开始），只有真正跑测试时才清理上一轮结果

### 文档
- 精简 `_internal/errors.py` 与 `_internal/image/` 各模块 docstring，去掉与实现重复的说明
- `.gitignore` 忽略本地 `tools/` 目录
- `settings.FRAMEWORK_ROOT` 注释更正为「just_go 包目录」（与实现一致）

### 测试
- 171 passed、ruff 通过（新增 23 条回归用例：locator 归一化 7 条、`_basename` 跨平台、`_looks_like_path` / 非路径值不截断、`AsyncElement` 参数还原与 `all`、tag 边界（`L1` vs `L10`、多标签分隔）、tag CSV 缺列、用例 ID 严格、marker 白名单、`take_record_file`、`_safe_version`、`slow_time` 解析、`_case_title`、`retries` 非法值、`@log` 的 staticmethod/classmethod/脱敏、注册表原子写与损坏提示、`init` 建 `images/`）
- 验证 `import just_go` 不再创建/删除产物目录（预置 `cache/report` 文件在 import 后仍存在）
- 模拟安装布局（把 `just_go` 拷到临时目录后 import）：`_build_templates("all")` 的 19 个模板全部成功加载
- 实际项目验证：登录用例 1 passed（13.09s，仓库源码路径）
- 未覆盖：异步 `_async_page_lifecycle` 无真实异步用例可跑，仅代码结构与单测层面检查；`image/finder.py` 两处改动无自动化测试（cv2 为可选依赖，CI 不安装）

## [0.3.0] - 2026-11-12

### 新增
- **属性式元素声明**：`element(selector, 描述, sensitive)` / `async_element()` 声明页面元素，访问后直接调 Playwright 动作，自动记日志与 Allure 步骤；`Element` / `AsyncElement` 从 `just_go.web` 导出，`.native` 取原生 Locator，链式定位（`first` / `nth` / `filter` / `get_by_*`）保持包装
- **屏幕找图能力**：合入 `image_recognition` 到 `just_go/_internal/image/`（模板匹配、截图、鼠标动作），对外门面 `just_go.image`
  （`find_image` / `wait_image` / `grab` / `screen_size` / `IMAGE_PATH`）；断言新增 `assert_image` / `assert_not_image`
- **图像识别可选依赖**：`just-go[image]`（numpy / opencv-python-headless / pillow / mss），不装不影响框架导入与运行（门面按需惰性取实现）
- **项目级配置覆盖**：`<项目根>/config.ini` 叠加框架默认配置，只写要改的项；`just-go init` 生成该项目级模板
- **日志用例标识**：每条用例的日志行带 `[用例标识]` 前缀（loguru patcher + contextvars），未设置时格式与原来一致
- **图像异常体系**：`ImageRecognitionError` 为域根共 15 类并入 `just_go/_internal/errors.py`，`just_go/errors.py` 对外导出 13 个
- **CLI**：`just-go init` 在机器无 pipenv 时提示跳过虚拟环境创建，不再抛 `TypeError`

### 变更（不兼容）
- **模块拆分**：删除 `just_go/core.py`，拆为 `just_go/config.py`（`config` / `setup_env`）、`just_go/log.py`（`log` / `logger`）、`just_go/case.py`（`CaseControl`）；模板、文档与示例 import 全部同步迁移
- **PO 模板结构**：元素类（`xxx_page_ele.py`）不再继承 `BasePage`，只做 `element` 声明；页面类在 `__init__` 里绑定 `self.page`；断言独立到 `pages/asserts/asserts.py` 的 `Asserts`，`PageExport` 只继承 `BasePage`，通过 `__getattr__` 把 `assert_` 前缀转发给 `Asserts`，用例写法（`page.assert_visible(...)`）不变
- **`IMAGE_PATH` 语义**：直接取测试项目根 `ROOTDIR`，模板图目录由用户自行拼接；删除 `config.framework.image_path` 配置项，不带目录的 `find_image("btn")` 现在找 `<项目根>/btn.png`
- 模板文件统一去掉 `# coding=utf-8` 声明、清理 BOM，并补 `pages/asserts/` 的 package-data

### 修复
- **登录态复用从未生效**：`launch_persistent_context()` 不接受 `storage_state` 参数，改为 `launch()` + `browser.new_context()` 两段式；`_page_setup()` 拆为 `launch` / `context` 两组参数，去掉临时 `user_data_dir`
- **首次运行死锁**：`storage_state` 文件由登录用例自身产出，启动时校验存在会永久卡住首次运行；改为存在才加载、缺失跳过且仅提示一次
- **Allure「行为」空分组**：`epic` / `feature` / `story` 仅在 CSV 对应列有值时才添加，避免出现无 value 的空分组
- **`CaseControl` 误判**：兼容 `case_base` / `base_case` 两种基类文件名；只校验函数（`inspect.isfunction`），`settings` / `data` 等类属性不再被当成用例方法
- **录屏 ffmpeg 定位**：`FFMPEG_PATH` 按 `config.framework.ffmpeg_path` → PATH → `~/.just-go/ffmpeg` 多级解析，一次安装供所有项目与虚拟环境复用
- **运行时依赖声明**：`pyproject.toml` 补齐 `loguru`、`allure-python-commons`，避免干净环境安装后导入报 `ModuleNotFoundError`

### 测试
- 全量 140 用例通过、ruff 通过（新增 `tests/test_element.py` 及 image 相关用例）
- 实际项目验证：登录用例通过，`state.json` 复用生效（无登录动作、无缺失告警）
- 生成骨架编译与导入通过；wheel 内含 `templates/gui/pages/asserts/asserts.py`

## [0.2.0] - 2026-10-22

### 新增
- **异步支持**：协程用例可直接使用web异步方法
- **分类导入**：用户通过公开模块导入
- **内部实现隐藏**：代码全部移入 `just_go/_internal/`，外层同名文件仅做 re-export 壳
- **setup_env()**：`just_go.core` 提供 `setup_env(base_urls, case_base_url="")`，一行替代 conftest.py 里的多环境样板代码

### 重构
- **CLI 精简**：删除 pipenv 虚拟环境引导死代码（`_ensure_pipenv_runtime`/`_pipenv_install`/`_parse_pyproject_deps`/`_install_core`/`_install_all_py`/`_pipenv_venv_path`/`_is_venv`）
- `just-go install` 只安装系统级工具（playwright 浏览器/allure 报告工具/ffmpeg 录屏编码器），Python 依赖由项目 Pipfile 自动安装
- 删除 `cmd_run` 里的 PYTHONPATH 回退逻辑

### 修复
- 见代码

### 测试
- 全量 109 用例通过

## [0.1.9] - 2026-10-21

### 新增
- 项目独立虚拟环境创建与使用

### 修复
- 无

### 测试
- 全量 102 用例通过、ruff 通过

## [0.1.8] - 2026-10-21

### 新增
- Allure 报告默认**单文件 HTML**（`--single-file`）、**中文界面**（`--lang zh`）、**标题为被测项目名**
  （`--name`）；参数按 allure 版本自动启用：`>=2.24` 单文件，`>=2.30` 报告名/语言
- 默认 allure 版本升至 2.30.0（`--name`/`--lang` 自 2.24 起被移除、2.30 恢复），新装即具备完整报告能力
- `just-go version` / `just-go --version` 版本查询命令（无需 pipenv / 框架依赖即可执行，
  已安装包元数据优先，源码运行回退读取 pyproject.toml）
- `config.ini` 新增 `report_name` / `report_language`（缺省=被测项目名 / 中文）

### 修复
- 修复 allure 2.24-2.29 无 `--name`/`--lang` 选项时参数被误当成结果目录的兼容问题
  （按版本自动跳过，老版本仅加 `--single-file`）

### 测试
- 新增 `tests/test_tools.py` 6 用例（GenerateReport 版本探测与命令组装），全量 102 用例通过、ruff 通过

## [0.1.5] - 2026-10-20

### 新增
- 多浏览器支持：`config.run.browser_type`（chromium / firefox / webkit）
- 登录态复用：`config.run.storage_state` 加载已保存登录态，跨用例免重复登录
- 多环境切换：`--env dev/test/prod` 写入 `JUSTGO_ENV`，骨架 conftest 按环境加载被测地址
- 失败自动重试：骨架默认 `--reruns=1 --reruns-delay=1`，支持 `@pytest.mark.flaky` 单用例覆盖
- 通用页面基类：init 骨架 `pages/base_page.py` 由空白模板改为现成实现
  （fill/click/wait_visible/get_text/is_visible/select_option/press/多标签页）
- 数据驱动工具：`just_go.data` 加载 JSON/CSV 测试数据供 pytest 参数化
- 接口令牌注入：`Request.set_token(token, prefix, header_name)` 全局请求头注入
- 框架自身单元测试：`tests/`（parse_tag / settings / exceptions / assertion / plugin / data / request）
- CI 测试流水线：`.github/workflows/test.yml`（push/PR 自动 pytest + ruff）
- PyPI 元数据：license（MIT，PEP 639 表达式）、authors、keywords、classifiers

### 重构与修复
- `just_go/__init__.py` 改显式导入 + `__all__`，消除 star import 隐式依赖链
- `plugin.py` 全部名字改显式导入（修复 `Function` 等依赖隐式链的潜在 NameError）
- `browser_utils.py` 去重 playwright 导入、修正 `expect` re-export、补 `__all__`
- `controller.py` 修复 `not in` 写法；`settings.py` 移除未用导入
- 全项目通过 ruff 检查（配置见 pyproject.toml `[tool.ruff]`）
- README 补充「浏览器与登录态」「多环境切换」「失败重试」「数据驱动」「接口令牌」说明

## [0.1.4] - 2026-10-20

### 重构
- init 骨架模板抽离为 `just_go/templates/` 独立文件，随包发布（不再内联于 cli.py）
- README 补充「浏览器与登录态」「多环境切换」「失败重试」说明（与模板同步）

## [0.1.3] - 2026-10-20

### 新增
- PyPI 发布自动化：GitHub Actions + Trusted Publishing，打 `v*` tag 自动构建发布
- `pyproject.toml` 补充项目主页与仓库链接

## [0.1.2] - 未记录

（早期发布版本，本次整理前无变更记录）

## [0.1.0] - 首次发布

（早期发布版本，本次整理前无变更记录）
