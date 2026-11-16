# 参考手册

配置项、命令行参数、目录结构、环境要求与常见问题。面向用法与排错，快速上手先看
[README](../README.md)。

---

## 命令一览

| 命令 | 作用 |
| --- | --- |
| `just-go install [playwright\|allure\|ffmpeg\|all]` | 安装 / 检查运行工具（默认 all） |
| `just-go init <目录[类型]>` | 初始化测试项目骨架，类型 `gui` / `api` / `all`（默认 gui），如 `just-go init "demo[all]"` |
| `just-go add <名称> <路径>` | 注册测试项目 |
| `just-go list` | 列出已注册项目（含路径有效性标记） |
| `just-go remove <名称>` | 取消注册 |
| `just-go run <名称\|路径> [pytest参数]` | 执行测试项目，其余参数透传 pytest |
| `just-go shell <名称\|路径>` | 进入被测项目的 pipenv 虚拟环境（无则自动创建） |
| `just-go version` / `just-go --version` | 显示框架版本号 |

### `just-go run`

| 参数 | 说明 |
| --- | --- |
| `--output <目录>` | 产物输出根目录，按 `输出根/项目名` 分子目录；默认输出在项目根 |
| `--env <名称>` | 运行环境（dev/test/prod），配合 `setup_env()` 切换被测地址 |
| `--tag <表达式>` | 按 tag 表达式筛选，支持 `and` / `or` / 括号 |
| `--record=yes\|no` | 录屏开关（也可写在项目 `pytest.ini`） |
| `--report-single-mode=yes\|no` | `yes` 单文件 HTML（默认）/ `no` 目录模式 |
| `--reruns=<n>` / `--reruns-delay=<s>` | 失败重试次数与间隔 |
| `--collect-only` | 只收集不执行 |

`run` 会用被测项目的独立 pipenv 虚拟环境执行（项目根有 `Pipfile` 且环境已创建时），
否则回退到当前 Python 环境。设置 `JUSTGO_SKIP_PROJECT_VENV=1` 可强制用当前环境。

### `just-go install`

| 组件 | 安装内容 | 失败时的处理 |
| --- | --- | --- |
| `playwright` | Chromium | 打印退出码，可稍后重试 |
| `allure` | allure 2.30.0 到 `~/.just-go/allure/<版本>/` | 缺 Java 时 Windows 用 winget 装 Temurin JDK、Linux 用 apt 装 OpenJDK 17；装不了给出手动指引 |
| `ffmpeg` | 从 PyPI 的 imageio-ffmpeg wheel 取出二进制到 `~/.just-go/ffmpeg/` | 打印手动下载地址与目标路径 |

`just-go install allure 2.29.0` 可指定 allure 版本；`ffmpeg` 同理可指定 imageio-ffmpeg 版本。

---

## 配置项

### 项目级 `config.ini`（`<项目根>/config.ini`，可选）

`just-go init` **不会**生成这个文件——绝大多数项目用不上它。需要改下面这几项时再自建，
只写要改的项，没写的沿用框架默认：

```ini
[framework]
;机器相关的绝对路径（默认用 Playwright 自带浏览器 / 自动查找 allure、ffmpeg）
;browser_path =
;allure_path =
;ffmpeg_path =
;产物目录名（默认 logs / reports / cache）
;log_path = logs
;report_path = reports
;cache_path = cache
;报告标题（缺省 = 被测项目名）/ 语言（缺省 zh）
;report_name =
;report_language = zh
```

**为什么这些项不能写在 conftest.py 里**：`log_path` / `report_path` / `cache_path` /
`allure_path` / `ffmpeg_path` 在 `just_go._internal.settings` **导入时**就被拼成模块级常量
（`LOG_PATH`、`REPORT_PATH`、`ALLURE_PATH` 等），而项目 `conftest.py` 顶部导入框架时这些
常量已经算完；之后在 conftest 里赋值 `config.framework.report_path = ...` 只改缓存，常量
不会重算。只有 `run.*` 与 `framework.browser_path` / `report_name` / `report_language` 是
用到时才读，因此在 conftest 里赋值有效。

`config.ini` 里的路径都是**机器相关**的，团队里各不相同，因此这个文件适合不提交：
自建后可加进 `.gitignore`，每台机器放一份自己的。

### 框架默认（`just_go/configs/config.ini`，装包后不用改）

| 配置项 | 说明 |
| --- | --- |
| `framework.browser_path` | 浏览器可执行文件路径（默认 Playwright 自带） |
| `framework.allure_path` | allure 路径；留空自动查找 PATH → `~/.just-go/allure/*/bin` |
| `framework.ffmpeg_path` | ffmpeg 路径；留空自动查找 PATH → `~/.just-go/ffmpeg` |
| `framework.report_name` / `report_language` | 报告标题（缺省=被测项目名）/ 语言（缺省 `zh`） |
| `framework.log_path` / `report_path` / `cache_path` | 产物目录名（默认 `logs` / `reports` / `cache`） |
| `run.slow_time` | 操作慢速等待毫秒数（默认 500） |
| `run.show_browser` | `True` 显示窗口 / `False` 无头 |
| `run.browser_type` | `chromium` / `firefox` / `webkit` |
| `run.storage_state` | 登录态文件路径，留空不启用 |

改 `config.ini` 后需重启进程才生效。

### 项目 `conftest.py` 与命令行

| 配置 | 位置 | 说明 |
| --- | --- | --- |
| `setup_env({...})` | 项目 `conftest.py` | 多环境地址映射（**必改**），写入 `JUSTGO_TEST_BASE_URL` 与报告环境信息 |
| `setup_env(..., case_base_url=...)` | 项目 `conftest.py` | 测试管理平台用例链接前缀（可选） |
| `config.run.*` | 项目 `conftest.py` | 运行时覆盖配置，只对本次运行生效 |
| `--env <名称>` | 命令行 | 选择 `setup_env()` 中的环境 |
| `JUSTGO_TEST_BASE_URL` | 环境变量 | 被测地址；显式设置时优先级高于 `--env` |
| `JUSTGO_TEST_CASE_BASE_URL` | 环境变量 | 用例链接前缀，等同 `case_base_url` 参数 |
| `JUSTGO_PROJECT_ROOT` / `JUSTGO_PROJECT_NAME` | 环境变量 | 由 `just-go run` 自动注入，产物与模板图以此为基准 |
| `JUSTGO_OUTPUT_ROOT` | 环境变量 | 等同 `--output` |
| `JUSTGO_SKIP_PROJECT_VENV` | 环境变量 | 设为任意非空值则跳过项目虚拟环境 |

---

## 生成的目录结构

### GUI 骨架（`just-go init demo`）

```
demo/
├─ conftest.py              # 声明框架插件 + 注入被测地址 + page fixture 包装
├─ pytest.ini               # 收集规则 / 录屏 / 重试 / 报告模式
├─ Pipfile                  # 项目依赖（just-go、pytest 等）
├─ cases/                   # 用例，按模块分子目录
│  ├─ case_base.py          # 用例基类（开启命名校验）
│  └─ login/
│     ├─ test_login_1.py
│     └─ test_login_2.py
├─ pages/                   # 页面对象
│  ├─ __init__.py           # PageExport：页面 + 断言统一出口
│  ├─ base_page.py          # BasePage / AsyncBasePage
│  ├─ asserts/asserts.py    # 断言集合（内置 + 自定义）
│  └─ login_page/
│     ├─ login_page_ele.py  # 只写元素
│     └─ login_page.py      # 只写业务动作
├─ images/                  # 屏幕找图的模板图（IMAGE_PATH 就是项目根）
└─ tag/login.csv            # 用例登记（可选）
```

### API 骨架（`just-go init "demo[api]"`）

```
demo/
├─ conftest.py
├─ pytest.ini / Pipfile
├─ apis/
│  ├─ __init__.py           # 统一导出
│  ├─ base.py               # BaseApi，继承框架 Request
│  └─ user_manager_api.py   # 按模块封装接口
├─ cases/
│  ├─ case_base.py
│  └─ api/test_login_1.py
└─ tag/api.csv
```

`[all]` 同时生成两套。

---

## 环境要求

- **Python** 3.10+
- **平台** Windows / Linux（Linux 桌面录屏需 X11 环境）
- **浏览器** `just-go install playwright` 自动装 Chromium，也可在 `config.framework.browser_path` 指向本机 Chrome / Edge
- **Allure 报告** 需要 Java：`just-go install allure` 会自动尝试安装 JDK
- **ffmpeg** 录屏需要：`just-go install ffmpeg` 一次安装，所有项目共用
- **图像识别** 可选依赖：`pipenv install "just-go[image]"`（numpy / opencv-python-headless / pillow / mss）

### 依赖分工

- 框架本体（`just-go`）声明了 playwright / pytest 生态之外的运行依赖：loguru、allure-python-commons、requests、faker
- 测试项目依赖由项目 `Pipfile` 决定：`just-go init` 自动生成并安装
- 系统级工具（浏览器、allure、ffmpeg）由 `just-go install` 管理，与虚拟环境解耦

---

## 常见问题

**录屏没有产出 / 提示 ffmpeg 未安装？**
`just-go install ffmpeg`。装到 `~/.just-go/ffmpeg` 后立即被识别，无需重开终端，所有项目共用。

**Allure 报告没生成？**
`just-go install allure`（需要 Java）。即使未装，Allure 原始结果仍保留在 `cache/report/`，装好后可手动生成。

**浏览器起不来 / Playwright 报错？**
`just-go install playwright`；若配了 `framework.browser_path`，确认该路径存在。
报 `Playwright Sync API inside the asyncio loop` 时，检查是否有插件或 `sitecustomize` 提前起了事件循环，
框架会在日志里打印检测到的 loop 与活动任务。

**用例收集数量为 0？**
`just-go init` 生成的是空白骨架，填充前 0 条属正常。确认用例函数以 `test_` 开头、位于 `cases/` 下。

**用例被自动跳过？**
两个原因：`tag/<模块>.csv` 的 `跳过原因` 列填了内容；或已启用 tag 但该用例没有登记记录（日志会告警）。

**`--tag` 筛选不生效？**
确认 `tag/` 目录存在且 CSV 路径与用例目录对应（`cases/login_manage/` → `tag/login_manage.csv`），
用例ID 与函数名中数字一致。表达式支持 `and` / `or` / 括号，不区分大小写。

**`--env prod` 报"被测地址为空"？**
`setup_env()` 里该环境的值为空字符串。填上地址，或只使用已配置的环境。

**`--tag` 表达式写错会怎样？**
畸形表达式（括号不配对、`L1 and and L2`）会被判为不匹配并跳过全部用例，不会挂住进程。

**用例名报 `CaseError`？**
框架要求方法名包含用例文件名（`test_login_2346.py` 里只能有 `test_login_2346`）。
一个文件放一条用例，多写就复制新文件。

**想直接用 pytest 而不是 `just-go run`？**
可以。项目根 `conftest.py` 已声明 `pytest_plugins = ["just_go._internal.plugin"]`，直接 `pytest` 效果相同。

**导入 just_go 报 `SoftwareNotInstallError`？**
项目虚拟环境未创建或依赖不全：在项目目录执行 `pipenv install`，或重新 `just-go init`。

**能同时跑 GUI 和 API 用例吗？**
可以。`init "demo[all]"` 生成同一项目下的两套；API 用例不请求 `page` fixture，不会启动浏览器。
