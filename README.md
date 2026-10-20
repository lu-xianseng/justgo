# just-go

Web 自动化测试框架：**框架与测试代码分离，一条命令跑指定测试项目，自动产出 allure 报告（含录屏、失败截图、日志）。**

```bash
pip install just-go      # 1. 安装框架
just-go install          # 2. 安装运行依赖（浏览器/报告工具/ffmpeg）
just-go init SHOP-TEST   # 3. 生成测试项目骨架
just-go run SHOP-TEST    # 4. 执行测试项目
```

框架只装一次、全局复用；测试项目单独存放、各自独立。升级框架、换机器、接入 CI，都不影响已写好的测试代码。

---

## 核心特性

| 特性 | 说明 |
| --- | --- |
| **框架与测试代码分离** | 测试项目里没有任何框架源码；框架独立安装升级，项目之间互不影响 |
| **PO 模式脚手架** | `just-go init` 一键生成 GUI / API / 全量骨架，基类下沉公共逻辑，页面/用例只写业务 |
| **同步 / 异步用例混写** | `def` 与 `async def` 任意混用，框架自动路由，无需 pytest-asyncio |
| **桌面录屏（ffmpeg）** | 基于系统 ffmpeg（gdigrab）录制整个桌面，产出 mp4 自动附到报告；`just-go install ffmpeg` 一键安装 |
| **allure 报告开箱即用** | 自动生成 HTML 报告，附失败截图、录屏、用例日志；报告工具与 Java 由 `just-go install` 自动处理 |
| **tag 用例筛选** | 项目 `tag/` 目录 + CSV 登记用例，`--tag "L1 and smoke"` 表达式筛选，支持 and/or/括号 |
| **多浏览器支持** | `config.run.browser_type` 一键切换 chromium / firefox / webkit，无需改用例 |
| **登录态复用** | 登录一次保存 storage_state，跨用例复用，免重复登录 |
| **失败自动重试** | 默认失败重试 1 次（flaky 用例用 `@pytest.mark.flaky` 单独控制） |
| **产物可重定向** | 日志/报告/录屏默认输出在测试项目根，CI 场景用 `--output` 重定向归档 |
| **环境管理省心** | pipenv 虚拟环境自动引导；`just-go install core/playwright/allure/ffmpeg` 缺什么装什么 |

---

## 快速开始

### 1. 安装框架

```bash
pip install just-go
just-go install          # 全部运行依赖：核心库 / Chromium / allure / ffmpeg
```

> 首次执行会提示创建 pipenv 虚拟环境，按提示确认即可；后续命令自动复用。

### 2. 初始化测试项目

```bash
just-go init SHOP-TEST             # GUI 骨架（页面对象 + 页面用例），默认类型
just-go init "SHOP-API[api]"       # API 骨架（接口封装 + 接口用例）
just-go init "SHOP-ALL[all]"       # 两种都生成
```

生成的是**空白脚手架**：目录结构、配置、开发指南齐全，类名/方法名/业务逻辑由你按项目内 README 填充。

### 3. 配置被测地址

编辑测试项目的 `conftest.py`：

```python
os.environ.setdefault("JUSTGO_TEST_BASE_URL", "http://192.168.1.10:8080")  # 被测系统地址（必改）
```

### 4. 注册并运行

```bash
just-go add shop D:\ProjectCode\SHOP-TEST   # 注册项目（名字自己起）
just-go run shop                            # 执行全部用例
just-go run shop --tag "smoke and L1"       # 按 tag 筛选执行
just-go run shop --collect-only             # 只收集用例不执行
```

跑完打开项目根 `reports/` 下最新目录的 `index.html` 查看报告，录屏、失败截图、日志都在里面。

---

## 用例怎么写

`page` 是框架提供的 fixture（Playwright 页面），同步 / 异步两种写法可以混用：

```python
# 同步（默认）
def test_login(page):
    page.goto("https://example.com")
    page.fill("#user", "admin")
    assert "登录成功" in page.content()

# 异步：用例内用 await
async def test_login(page):
    await page.goto("https://example.com")
    await page.fill("#user", "admin")
    assert "登录成功" in await page.content()
```

内置断言（`from just_go import AssertCommon`）：

```python
common = AssertCommon()
common.assert_equal("ok", resp.get("status"))        # 相等
common.assert_in("手机", page_text)                  # 包含
common.assert_re_check_equal(r"\d{6}", page_text)    # 正则匹配
```

框架还提供自定义异常体系（基类 `JustGoError`），测试项目可统一捕获框架错误：

```python
from just_go import JustGoError, RequestError, RecordError

try:
    ...
except JustGoError as e:   # 捕获所有框架自定义异常
    ...
```

> 可选：用例基类声明 `metaclass=CaseControl` 可开启命名校验（用例方法名须包含用例文件名）。

---

## 录屏

- 开启：`pytest.ini` 中的 `--record=yes`（骨架默认开启，删掉该行即关闭）；
  临时开关：`just-go run shop --record=no`
- 方式：系统 ffmpeg 以 `gdigrab` 录制**整个桌面**，产出 mp4 自动附到 allure 报告
- 依赖：系统需已安装 ffmpeg 且加入 PATH

```bash
just-go install ffmpeg    # 自动安装（winget），装完需新开终端刷新 PATH
```

---

## 浏览器与登录态

**多浏览器**：`config.run.browser_type` 支持 `chromium` / `firefox` / `webkit`（默认 chromium），
不用改任何用例代码：

```python
# 测试项目 conftest.py 顶部
from just_go import config
config.run.browser_type = "firefox"   # 或 webkit
```

**登录态复用**：Web 用例最痛的"每个用例都要登录"问题——登录一次保存状态，后续用例直接复用：

```python
# 1. 登录用例里保存（通常在首个用例或一次性脚本执行一次）：
page.context.storage_state(path="state.json")

# 2. 项目 conftest.py 声明复用：
config.run.storage_state = "state.json"   # 相对路径基于测试项目根
```

之后每个用例启动浏览器都会自动加载该登录态。重新登录只需删掉 `state.json` 再跑一次保存步骤。

**失败自动重试**：骨架默认失败用例重试 1 次（间隔 1 秒）。个别用例想单独控制：

```python
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_unstable_1001(self, page):
    ...
```

想全局关闭：把 `pytest.ini` 里的 `--reruns=1 --reruns-delay=1` 两行删掉或改为 `--reruns=0`。

**多环境切换**：骨架 conftest.py 内置 `BASE_URLS`（dev/test/prod），运行时用 `--env` 一键切换：

```bash
just-go run shop --env prod    # 或 pytest --env prod
```

未指定时默认 `dev`。环境标识写入 `JUSTGO_ENV`，conftest 按它加载对应被测地址（增删环境只改 `BASE_URLS` 字典）。

**数据驱动**：把用例数据抽到 JSON/CSV 文件，配合 pytest 参数化：

```python
import pytest
from just_go.data import load_json_cases, load_csv_cases

@pytest.mark.parametrize("case", load_json_cases("login_cases.json"))
def test_login(case):
    data = login(case["username"], case["password"])
    assert data["code"] == 0
```

JSON 顶层为数组（每项一组参数），CSV 首行为表头；相对路径基于测试项目根解析。

**接口令牌注入**：登录拿到 token 后一键注入全局请求头，后续请求自动携带：

```python
from just_go import Request

api = Request()
api.set_token(token, prefix="Bearer ")           # Authorization: Bearer <token>
api.set_token(token, header_name="X-Token")      # 自定义请求头名
```

---

## tag 用例筛选（可选）

不用 tag 也能跑：项目没有 `tag/` 目录时，用例全部直接执行。需要筛选时：

**1. 建目录与 CSV**（`just-go init` 骨架自带空表）：

```
tag/
└─ module.csv            # 一个用例模块一个 CSV，与 cases/<模块>/ 对应
```

**2. 登记用例**（4 列）：

```csv
用例ID,用例级别,场景,跳过原因
1001,L1,登录,
1002,L2,订单,接口未就绪
```

- `用例ID` 与用例函数名 `test_<模块>_<用例ID>` 中的 ID 对应（如 `test_login_1001` ↔ `1001`）
- `跳过原因` 填写后该用例自动跳过
- 登记后即可筛选执行：

```bash
just-go run shop --tag "L1 and smoke"          # 逻辑与
just-go run shop --tag "L1 or L2"              # 逻辑或
just-go run shop --tag "(L1 or L2) and smoke"  # 括号组合
```

---

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `just-go install [core\|playwright\|allure\|ffmpeg\|all]` | 安装/检查运行依赖（默认 all） |
| `just-go init <目录[类型]>` | 初始化测试项目骨架（gui/api/all，默认 gui） |
| `just-go add <名称> <路径>` | 注册测试项目 |
| `just-go list` | 列出已注册项目（含路径有效性标记） |
| `just-go remove <名称>` | 取消注册 |
| `just-go run <名称\|路径> [pytest参数]` | 执行测试项目，其余参数透传给 pytest（`--tag`/`--record`/`--collect-only` 等） |

---

## 配置

### 框架级（`just_go/configs/config.ini`，一般不用改）

| 配置项 | 说明 |
| --- | --- |
| `framework.browser_path` | 指定浏览器可执行文件路径（默认用 Playwright 自带 Chromium） |
| `framework.allure_path` | allure 工具路径（留空自动查找 PATH 或 `~/.just-go/allure`） |
| `run.slow_time` | 操作慢速等待毫秒数（默认 500） |
| `run.show_browser` | `True` 显示浏览器窗口 / `False` 无头运行 |
| `run.browser_type` | 浏览器类型：`chromium` / `firefox` / `webkit`（默认 chromium） |
| `run.storage_state` | 登录态文件路径（留空不启用；相对路径基于测试项目根） |

### 项目级

| 配置项 | 位置 | 说明 |
| --- | --- | --- |
| `JUSTGO_TEST_BASE_URL` | 项目 `conftest.py` | 被测系统地址（**必改**），用于页面跳转基址 + 报告环境信息 |
| `JUSTGO_TEST_CASE_BASE_URL` | 项目 `conftest.py` | 测试管理平台（如禅道）用例链接前缀（可选） |
| `--record` | 项目 `pytest.ini` | 录屏开关（默认开） |
| `--reruns` | 项目 `pytest.ini` | 失败重试次数（默认 1），`@pytest.mark.flaky(reruns=3)` 可单用例覆盖 |
| `--env <名称>` | `just-go run` / `pytest` | 运行环境（dev/test/prod），写入 `JUSTGO_ENV`，配合骨架 conftest 的 `BASE_URLS` 切换被测地址 |
| `config.run.slow_time` 等 | 项目 `conftest.py` | 运行时覆盖框架配置，只对本次运行生效 |
| `--output <目录>` | `just-go run` | 产物输出根目录，按 输出根/项目名 分子目录，多项目互不干扰 |

---

## 运行产物

默认输出在测试项目根下：

```
SHOP-TEST/
├─ logs/           # 运行日志（loguru，每次运行一个时间戳文件，10MB 滚动）
├─ reports/        # allure HTML 报告（每次运行一个时间戳目录）
└─ cache/          # allure 原始结果（report/）、临时录屏与截图（temp/）
```

CI / 只读目录场景：`just-go run shop --output D:\产物目录`。

---

## 环境要求

- Python 3.10+
- 浏览器：`just-go install playwright` 自动安装 Chromium
- allure 报告需 Java：`just-go install allure` 检测缺失会自动尝试安装（winget 装 Temurin JDK），装不了会给出手动下载指引
- ffmpeg：录屏必需，`just-go install ffmpeg` 自动安装（winget），或手动下载加入 PATH

> 测试项目自身的 Python 依赖（如 redis、pymysql）由项目自行安装到运行环境，框架不代管。

---

## 常见问题

**录屏没有产出 / 提示 ffmpeg 未安装？**
运行 `just-go install ffmpeg` 自动安装（winget），装完**新开终端**刷新 PATH 再跑。

**allure 报告没生成？**
`just-go install allure` 安装报告工具（需要 Java，检测缺失会自动尝试装 Temurin JDK）。
报告生成依赖 allure 工具；即使未装，allure 原始结果仍保留在 `cache/report/`。

**浏览器起不来 / 提示 playwright 相关错误？**
运行 `just-go install playwright` 安装 Chromium；若配置了 `config.ini` 的 `browser_path`，
确认该路径的浏览器可执行文件存在；无头模式看不到窗口属正常（`config.run.show_browser`）。

**用例收集数量为 0？**
`just-go init` 生成的是空白脚手架，填充前收集到 0 个用例属正常。确认用例函数名以
`test_` 开头、位于 `testpaths`（默认 `cases/`）目录下。

**用例被自动跳过？**
检查对应 `tag/<模块>/<模块名>.csv` 的「跳过原因」列是否已填写。

**`--tag` 筛选不生效？**
`--tag` 依赖 `tag/` 目录与登记数据：确认 CSV 已登记该用例（用例ID 与函数名中 ID 一致），
表达式不区分大小写，支持 `and` / `or` / 括号组合。

**想直接用 pytest 而不是 just-go run？**
可以。项目根 `conftest.py` 已声明框架插件，在项目根直接敲 `pytest` 即可，效果相同。

**导入 just_go 报 `SoftwareNotInstallError`？**
说明依赖（如 playwright）未安装到当前环境：在框架环境内运行 `just-go install`，
或确认当前 Python 与框架运行环境一致（pipenv 环境会自动引导）。
