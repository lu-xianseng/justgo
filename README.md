# just-go

只需要专注业务编写的一个分离式 **Web 自动化测试框架**。

> 测试项目单独存放、互不影响。升级框架、迁移机器、接入 CI，都不需要改动已写好的测试代码。

[![PyPI Version](https://img.shields.io/pypi/v/just-go)](https://pypi.org/project/just-go/)
[![Python Versions](https://img.shields.io/pypi/pyversions/just-go)](https://pypi.org/project/just-go/)
[![License](https://img.shields.io/pypi/l/just-go)](https://github.com/lu-xianseng/justgo/blob/main/LICENSE)
[![CI](https://github.com/lu-xianseng/justgo/actions/workflows/test.yml/badge.svg)](https://github.com/lu-xianseng/justgo/actions/workflows/test.yml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue)]()

---

## 设计理念

测试工程普遍面临三个痛点：**框架代码与用例代码耦合**（升级困难）、**重复劳动**（登录、录屏、报告、重试都要自己搭）、**筛选与报告粗糙**（用例多了之后无法精确挑选、结果难以追溯）。just-go 从这三个问题出发：

```mermaid
flowchart LR
    subgraph 框架层["just-go"]
        CLI["CLI：init / add / run / install"]
        PLUGIN["pytest 插件：page fixture、tag 筛选、录屏、重试、多环境"]
        TOOLS["工具：allure 报告、ffmpeg 录屏、数据驱动、接口封装"]
    end

    subgraph 项目层["测试项目"]
        CONF["conftest.py 配置"]
        CASES["cases/ 用例"]
        PAGES["pages/ 页面对象"]
        TAG["tag/ 用例登记"]
    end

    CLI --> |"run <项目>"| PLUGIN
    PLUGIN --> CASES
    CASES --> PAGES
    TOOLS --> |"产出"| REPORTS["logs / reports / cache"]
    TAG -.-> |"按标签筛选"| CASES

    style 框架层 fill:#f0f4ff
    style 项目层 fill:#f0fff0
```

- **框架层**：安装后，随 PyPI 版本升级；
- **项目层**：`just-go init` 生成的标准骨架，测试代码与框架完全解耦；
- **产物层**：日志、Allure 报告、原始结果自动归置，也可重定向归档。

---

## 核心特性

| 特性 | 说明 |
| --- | --- |
| **框架分离** | 测试项目内不含框架源码，框架独立升级，项目之间互不影响 |
| **脚手架** | `just-go init` 生成 GUI / API / 全量骨架，基类下沉公共逻辑，用例只写业务 |
| **同步 / 异步** | `def` 与 `async def` 任意混用，框架自动路由，无需 pytest-asyncio |
| **浏览器兼容** | `config.run.browser_type` 切换 chromium / firefox / webkit，不改用例代码 |
| **登录态复用** | 登录一次保存 `storage_state`，跨用例免重复登录 |
| **多环境切换** | `--env dev/test/prod` 一键切换被测环境 |
| **自动重试** | 默认失败重试 1 次，`@pytest.mark.flaky` 单用例覆盖 |
| **tag 筛选** | 项目 `tag/` 目录 + CSV 登记，`--tag "L1 and smoke"` 表达式精确挑选 |
| **录屏** | 基于 ffmpeg 录屏（Windows `gdigrab` / Linux `x11grab`），失败用例自动附入报告 |
| **报告** | 开箱即用：HTML，含失败截图、录屏、日志、用例链接 |
| **数据驱动** | `just_go.data` 加载 JSON / CSV 数据，配合 `pytest.mark.parametrize` |
| **接口能力** | Request 提供上传/下载/自动重试/代理/Cookie 管理，模板 `BaseApi` 直接复用 |
| **文档日志** | `@log` 类装饰器：方法被调用时自动把 docstring 记为日志（支持 `{{参数}}` 占位符），页面对象封装操作一目了然 |
| **元素动作日志** | `element()` 声明元素后，`page.login_page.account.fill("admin")` 直接调动作即自动记日志 + Allure 步骤，敏感字段自动脱敏 |
| **接口令牌** | `Request.set_token()` 注入全局请求头，接口用例免重复写鉴权头 |
| **产物重定向** | 默认输出在项目根，CI / 只读目录场景用 `--output` 重定向 |

---

## 快速开始

### 1. 安装框架

```bash
pip install just-go
just-go install          # 安装运行工具：Chromium / allure / ffmpeg
```

> `install` 按需指定组件：`just-go install [playwright|allure|ffmpeg|all]`。
> Python 依赖（pytest/requests/allure 库等）由项目虚拟环境自动安装，不需要本命令处理。

### 2. 初始化测试项目

```bash
just-go init demo             # GUI 骨架：页面对象 + 页面用例（默认类型）
just-go init "demo[api]"      # API 骨架：接口封装 + 接口用例
just-go init "demo[all]"      # 两套都生成
```

生成**标准空白骨架**：目录结构、配置、开发指南齐全，业务代码按项目内 `README.md` 指引填充。

### 3. 配置被测地址

编辑测试项目 `conftest.py`（骨架已内置 `setup_env()` 调用，默认走 `dev`）：

```python
from just_go.config import setup_env

setup_env({
    "dev":  "http://192.168.1.10:8080",   # 必改：填入实际地址
    "test": "http://test.example.com",
    "prod": "https://www.example.com",
})
```

### 4. 注册并运行

```bash
just-go add demo D:\ProjectCode\demo   # 注册项目（名称自定）
just-go run demo                            # 执行全部用例
just-go run demo --env prod                 # 按环境切换被测地址
just-go run demo --tag "smoke and L1"       # 按 tag 表达式筛选
just-go run demo --collect-only             # 只收集用例，不执行
```

跑完打开项目根 `reports/<最新时间戳>/index.html` 查看报告，录屏、失败截图、日志都在里面。

报告默认为**单文件 HTML**（整个报告就是一个 `index.html`，方便归档/分享）、**中文界面**、**标题为被测项目名**（如 `reports/<时间戳>/index.html` 打开后标题显示 `AutoLib`）；如需自定义标题或语言，可在被测项目 `config.ini` 中配置 `report_name` / `report_language`（需 allure ≥ 2.30，框架安装默认即 2.30）。

---

## 用例编写

`page` 是框架提供的 fixture，conftest.py 自动包装成 `PageExport`（页面对象 + 断言统一出口）。
用例里直接调 `page.<模块>_page.<元素>.<动作>`：

```python
from cases.case_base import CaseBase
from pages import PageExport

class TestLogin(CaseBase):
    def test_login_1(self, page: PageExport):
        """输入正确账号密码，登录系统"""
        page.login_page.account.fill("admin")     # 元素动作（自动记日志）
        page.login_page.password.fill("123456")
        page.login_page.login_btn.click()
        page.assert_visible(page.login_page.login_btn)   # UI 断言，可直接传 Element
        page.assert_equal("ok", resp["status"])          # 数据断言
```

同步用例 `def test_xxx(page)`，异步用例 `async def test_xxx(page)`（方法需 await）。

内置断言（在 `pages/asserts/asserts.py` 的 `Asserts` 里，PageExport 通过 `__getattr__` 转发成 `page.assert_xxx`）：

| 断言 | 说明 |
| --- | --- |
| `assert_equal(expect, actual)` | 相等 |
| `assert_in(expect, actual)` | 包含 |
| `assert_re_check_equal(pattern, text)` | 正则匹配 |
| `assert_visible(locator)` | 元素可见 |
| `assert_text(locator, expected)` | 元素文本 |
| `assert_image("btn")` | 屏幕上有该图（需 `just-go[image]`） |
| `assert_not_image("tip")` | 屏幕上没有该图（需 `just-go[image]`） |

自定义异常体系（`from just_go.errors import JustGoError, RequestError, RecordError`）：

```python
try:
    ...
except JustGoError as e:   # 捕获所有框架自定义异常
    ...
```

## 页面对象（GUI）

页面按目录分层，**元素和业务动作分开写**：

```
pages/
├─ __init__.py                    # PageExport：通用能力 + 子页面 + 断言
├─ base_page.py                   # BasePage / AsyncBasePage + element 声明
├─ asserts/
│  └─ asserts.py                  # 断言集合：内置断言 + 自定义断言
└─ login_page/
   ├─ login_page_ele.py           # 只写元素（不继承基类）
   └─ login_page.py               # 继承元素类，只写业务动作组合
```

`base_page.py` 继承框架 `SyncWebUI` / `AsyncWebUI`，提供通用浏览器操作能力，只被 `PageExport` 使用；
元素类不继承它：`element` 描述符只要求页面实例上有 `page` 属性。

### 元素声明：`element(selector, 描述)`

```python
# pages/login_page/login_page_ele.py
from just_go.web import element

class LoginPageEle:          # 不需要继承任何基类
    """登录页面"""

    account = element("[name='username']", "账号输入框")
    password = element("[name='password']", "密码输入框", sensitive=True)
    login_btn = element("button:has-text('登录')", "登录按钮")
```

元素访问后直接调 Playwright 动作，**日志和 Allure 步骤自动记录**：

```
INFO | - [登录页面对象] 账号输入框(account) 输入 "admin"
INFO | - [登录页面对象] 密码输入框(password) 输入 ***
INFO | - [登录页面对象] 登录按钮(login_btn) 点击
```

- 自动记日志的动作：`click` `dblclick` `tap` `fill` `clear` `type` `press` `press_sequentially` `select_text` `check` `uncheck` `set_checked` `select_option` `hover` `focus` `blur` `set_input_files` `drop` `drag_to` `scroll_into_view_if_needed` `wait_for` `dispatch_event` `evaluate` `evaluate_all` `evaluate_handle` `screenshot` `highlight` `hide_highlight`
- 只读取值的方法（`inner_text` `count` `get_attribute` `is_visible` 等）直通原生 Locator，不记日志
- 链式定位 `first` `last` `nth` `filter` `locator` `get_by_*` 等返回包装后的 Element，日志能力不丢
- 要拿原生 Locator（比如传给 playwright 的 `expect`）用 `.native`

`sensitive=True` 时值在日志里显示 `***`；属性名或描述含 `password` `pwd` `token` `secret` `密码` `验证码` 等关键词也会自动脱敏。

### 业务动作组合

```python
# pages/login_page/login_page.py
from .login_page_ele import LoginPageEle

class LoginPage(LoginPageEle):
    """登录页面对象"""

    def __init__(self, page):
        self.page = page          # 元素描述符从这里取 page

    def login(self, account, password):
        """登录：输入 {{account}} 后提交"""
        self.account.fill(account)
        self.password.fill(password)
        self.login_btn.click()
```

`@log` 记业务级日志，Element 记元素级日志，两层互补。

### 用例

```python
def test_login_1(self, page: PageExport):
    """输入正确账号密码，登录系统"""
    page.login_page.account.fill("admin")
    page.login_page.password.fill("123456")
    page.login_page.login_btn.click()
    page.assert_visible(page.login_page.login_btn)   # 断言可直接传 Element
```

`PageExport` 只继承 `BasePage`，页面对象挂在 `self` 上；断言不继承，全部委托给独立的 `Asserts`：

```python
@log
class PageExport(BasePage):
    def __init__(self, page):
        super().__init__(page)
        self.asserts = Asserts()          # 断言独立成类，可自定义
        self.login_page = LoginPage(self.page)

    def __getattr__(self, name):
        asserts = self.__dict__.get("asserts")
        if asserts is not None and name.startswith("assert_"):
            return getattr(asserts, name)
        raise AttributeError(f"{type(self).__name__} 没有属性 {name!r}")
```

conftest.py 自动把 page fixture 包装成 PageExport。
新增页面：在 `pages/` 下建 `xxx_page/` 目录，元素写 `xxx_page_ele.py`（不继承基类）、
业务写 `xxx_page.py`（`__init__` 里 `self.page = page`），再到 `PageExport.__init__` 里
注册 `self.xxx_page = XxxPage(self.page)`。
自定义断言：往 `pages/asserts/asserts.py` 的 `Asserts` 里加 `assert_xxx` 方法，
`page.assert_xxx(...)` 自动生效；非 `assert_` 前缀用 `page.asserts.xxx(...)` 调用。

异步用例用 `async_element` 声明，动作方法需 `await`。

---

## 接口封装（API）

`init [api]` 生成的骨架：`apis/base_api.py` 继承框架 `Request`，
`apis/user_manager_api.py` 按模块封装接口（一个模块一个文件），`apis/__init__.py` 统一导出。

`BaseApi` 继承 `Request` 自动获得全部 HTTP 能力，只额外提供基址拼接：

| 能力 | 说明 |
| --- | --- |
| `get/post/put/delete`、`upload_file`、`download` | 继承自框架 `Request`（session 复用、默认超时、异常统一） |
| `set_token` / `set_cookie` / `get_cookies` / `set_proxy` | 继承自框架 `Request` |
| `retry_times` / `retry_delay` | 构造参数：接口失败自动重试（默认关闭，幂等接口建议开启） |
| `base_url` / `_url(path)` | 本类新增：`JUSTGO_TEST_BASE_URL` 基址 + 拼接完整接口地址 |

```python
from .base_api import BaseApi

class UserManagerApi(BaseApi):
    def login(self, username, password):
        """登录：POST /api/login"""
        resp = self.post(self._url("/api/login"), json={"username": username, "password": password})
        return resp.json()

user_manager_api = UserManagerApi()
```

用例直接调接口 + 断言（不需要 page fixture）：

```python
from apis import user_manager_api

def test_login_1():
    data = user_manager_api.login("admin", "123456")
    assert data["code"] == 0
```

---

## 高级能力

### 多浏览器

`config.run.browser_type` 支持 `chromium` / `firefox` / `webkit`（默认 chromium），在项目 conftest.py 顶部切换，**不用改任何用例**：

```python
from just_go.config import config
config.run.browser_type = "firefox"   # 或 webkit
```

### 登录态复用

解决"每个用例都要登录"：登录一次保存状态，后续用例直接复用。

```python
# 1. 登录用例中保存（执行一次即可）：
page.context.storage_state(path="state.json")

# 2. 项目 conftest.py 声明复用：
config.run.storage_state = "state.json"   # 相对路径基于测试项目根
```

之后每个用例启动浏览器都会自动加载登录态；重新登录只需删除 `state.json` 再跑一次保存步骤。

### 多环境切换

骨架 conftest.py 内置 `setup_env({...})`（dev / test / prod），运行时指定环境：

```bash
just-go run demo --env prod    # 或直接在项目根: pytest --env prod
```

未指定时默认 `dev`。环境标识写入 `JUSTGO_ENV`，conftest 按它选择被测地址；增删环境只改 `BASE_URLS` 字典。

### 失败自动重试

骨架默认失败用例自动重试 1 次（间隔 1 秒）。单个用例单独控制：

```python
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_unstable_1001(self, page):
    ...
```

全局关闭：把 `pytest.ini` 中的 `--reruns=1 --reruns-delay=1` 改为 `--reruns=0` 或删除。

### 数据驱动

把用例数据抽到 JSON / CSV 文件，配合 pytest 参数化：

```python
import pytest
from just_go.data import load_json_cases, load_csv_cases

@pytest.mark.parametrize("case", load_json_cases("login_cases.json"))
def test_login(case):
    data = login(case["username"], case["password"])
    assert data["code"] == 0
```

- JSON：顶层为数组，每项一组参数；
- CSV：首行为表头；
- 相对路径基于测试项目根解析。

### 接口令牌注入

登录拿到 token 后一键注入全局请求头，后续请求自动携带：

```python
from just_go.http import Request

api = Request()
api.set_token(token, prefix="Bearer ")          # Authorization: Bearer <token>
api.set_token(token, header_name="X-Token")     # 自定义请求头名
```

---

### 方法文档即日志（@log 类装饰器）

装饰在类上，该类（含父类）的公共方法**被调用时自动把方法文档记为日志**，对页面对象封装尤其有用——每个业务操作自动变成一条可读日志，Allure 报告里能看到完整操作轨迹。

```python
from just_go.log import log

@log
class LoginPage(LoginPageEle):
    """登录页面对象"""

    def __init__(self, page):
        self.page = page          # 元素描述符从这里取 page

    def login(self, account, password):
        """登录：输入 {{account}} 后提交"""
        self.account.fill(account)
        self.password.fill(password)
        self.login_btn.click()
```

调用 `page.login_page.login("admin", "123456")` 时自动记录 `登录：输入 admin 后提交`，随后每个元素动作再各记一条——业务级和元素级两层日志。

约定（装饰器强制）：
- 类及父类的公共方法**必须写 docstring**，缺失直接抛 `TypeError` 提醒补文档，保证所有操作都有日志可查；
- `_` 开头的内部方法不记录日志，也不强制要求 docstring；
- 文档中可用 `{{参数名}}` 占位实际调用值，让日志带上关键数据（搜索词、订单号等）。

## 桌面录屏（ffmpeg）

- **开启**：`pytest.ini` 中 `--record=yes`（骨架默认开启，删除该行即关闭）；临时开关 `just-go run demo --record=no`
- **方式**：ffmpeg 抓取整个桌面（Windows 用 `gdigrab`，Linux 用 `x11grab`），产出 mp4 附入 Allure 报告（仅失败用例保留附件，通过即删除）
- **依赖**：不需要系统预装 ffmpeg，也不占用项目虚拟环境（无需安装任何录屏相关 Python 包）

```bash
just-go install ffmpeg    # 从 PyPI 取出内置 ffmpeg 二进制，落到 ~/.just-go/ffmpeg
```

运行时解析顺序：`config.ini` 的 `ffmpeg_path` → PATH 上的 ffmpeg → `~/.just-go/ffmpeg`。
共享目录中的二进制**一次安装供所有项目与虚拟环境复用**，安装后立即生效，不需要重开终端。

---

## 图像识别（屏幕找图，可选）

用于 Playwright 覆盖不到的场景：桌面客户端找图点击、页面局部渲染的像素级校验。
底层是 OpenCV 模板匹配，返回真实屏幕坐标与相似度。

**安装**（可选依赖，不装也不影响框架本身的导入与运行）：

```bash
pipenv install "just-go[image]"
```

**模板图位置**：相对路径基于测试项目根解析，放哪由你决定 —— 文件在 `images/btn.png` 就写 `find_image("images/btn")`，在 `assets/img/btn.png` 就写 `find_image("assets/img/btn")`。也可以用 `search_dirs` 限定只在某个目录里找。

```python
from just_go.image import find_image, wait_image, grab, screen_size

# 找图：命中返回 FindResult，match.center 是真实屏幕坐标
r = find_image("images/login_btn", similarity=0.9)   # 后缀可省略；相对路径基于项目根
if r:
    print(r.match.center, r.match.score)

# 等待：轮询直到出现或超时，超时返回 found=False（不抛异常）
r = wait_image("success_tip", similarity=0.85, timeout=10)

# 只在某个屏幕区域找（明显更快），区域同样是屏幕坐标 (x, y, w, h)
r = find_image("btn", source=(0, 0, 800, 600))

# 自己取画面与屏幕尺寸（BGR ndarray，可交给 cv2 或其它库处理）
frame = grab()
print(screen_size())
```

要点：

- **坐标**：`Match.x/y/center` 已是真实屏幕坐标（多显示器时含虚拟桌面偏移，副屏在左侧会是负数）
- **相似度**：默认 `1.0`（同一机器、同一分辨率、静态界面）；截图有缩放或抗锯齿时用 `0.85 ~ 0.95`
- **`source`**：`None` 全屏 / `(x,y,w,h)` 屏幕区域 / 图片路径或 `PIL.Image`（离线比对，此时坐标是图内坐标）/ 无参可调用对象
- **DPI**：首次截屏自动把进程设为 Per-Monitor DPI 感知，避免 125%/150% 缩放下模板对不上
- **断言**：`page.assert_image("btn")` / `page.assert_not_image("tip")`。前者内部走 `wait_image` 轮询（默认等 3 秒），命中返回 `FindResult` 可继续取坐标，未命中抛 `AssertionError`（文案带尝试次数与最高相似度）；后者默认只检查一次（`timeout=0`），传 `timeout=3` 表示 3 秒内一直没出现才算通过。两者都是同步方法，async 用例里直接调用、不用 await
- **多匹配**：`find_image("btn", return_all=True)` 后取 `r.matches`

---

## tag 用例筛选（可选）

不使用 tag 也能跑：项目没有 `tag/` 目录时，全部用例直接执行。需要筛选时：

**1. 建目录与登记表**（`just-go init` 骨架自带空表）：

```
tag/
└─ module.csv            # 一个用例模块一个 CSV，与 cases/<模块>/ 对应
```

**2. 登记用例**（固定 4 列）：

```csv
用例ID,用例级别,场景,跳过原因
1001,L1,登录,
1002,L2,订单,接口未就绪
```

- `用例ID` 与用例函数名 `test_<模块>_<用例ID>` 中的 ID 对应（如 `test_login_1001` ↔ `1001`）；
- `跳过原因` 填写后该用例自动跳过；
- 登记后即可按表达式筛选：

```bash
just-go run demo --tag "L1 and smoke"          # 逻辑与
just-go run demo --tag "L1 or L2"              # 逻辑或
just-go run demo --tag "(L1 or L2) and smoke"  # 括号组合
```

---

## 运行产物

默认输出在测试项目根下（CI / 只读目录场景可用 `just-go run demo --output <目录>` 重定向，按 输出根/项目名 分子目录，多项目互不干扰）：

```
demo/
├─ logs/           # 运行日志（loguru，每次运行一个时间戳文件，10MB 滚动保留 7 天）
├─ reports/        # Allure HTML 报告（每次运行一个时间戳目录，不覆盖历史）
└─ cache/          # Allure 原始结果（report/）、临时录屏与截图（temp/）
```

---

## 配置参考

### 项目级 `config.ini`（`<项目根>/config.ini`，覆盖框架默认）

`just-go init` 生成的项目里带一份，只写要改的项，没写的沿用框架默认（模板里默认全部注释掉）：

```ini
[run]
show_browser = False
browser_type = chromium
```

上面这份表示无头运行、固定用 chromium，其余配置不变。可覆盖的项就是下面两张表里的项；改完需重启进程才生效。

### 框架级（`just_go/configs/config.ini`，装包后不用改）

| 配置项 | 说明 |
| --- | --- |
| `framework.browser_path` | 指定浏览器可执行文件路径（默认 Playwright 自带 Chromium） |
| `framework.allure_path` | allure 工具路径（留空自动查找：PATH → `~/.just-go/allure/*/bin`） |
| `framework.report_name` / `report_language` | 报告标题（缺省=被测项目名）/ 语言（缺省 zh），allure ≥ 2.30 生效 |
| `framework.log_path` / `report_path` / `cache_path` | 产物目录名（默认 logs / reports / cache） |
| `run.slow_time` | 操作慢速等待毫秒数（默认 500） |
| `run.show_browser` | `True` 显示浏览器窗口 / `False` 无头运行 |
| `run.browser_type` | 浏览器类型：`chromium` / `firefox` / `webkit` |
| `run.storage_state` | 登录态文件路径（留空不启用，相对路径基于测试项目根） |

### 项目级（conftest.py / 命令行）

| 配置项 | 位置 | 说明 |
| --- | --- | --- |
| `setup_env({...})` + `JUSTGO_TEST_BASE_URL` | 项目 `conftest.py` | 被测系统地址（**必改**），写入报告环境信息 |
| `JUSTGO_TEST_CASE_BASE_URL` | 项目 `conftest.py` | 测试管理平台（如禅道）用例链接前缀（可选） |
| `--env <名称>` | `just-go run` / `pytest` | 运行环境（dev/test/prod），配合 `BASE_URLS` 切换 |
| `--record` | 项目 `pytest.ini` | 录屏开关（默认 yes） |
| `--reruns` | 项目 `pytest.ini` | 失败重试（默认 1），`@pytest.mark.flaky` 可单用例覆盖 |
| `--output <目录>` | `just-go run` | 产物输出根目录重定向 |
| `config.run.*` | 项目 `conftest.py` | 运行时覆盖框架配置，仅对本次运行生效 |

---

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `just-go install [playwright\|allure\|ffmpeg\|all]` | 安装 / 检查运行工具（默认 all） |
| `just-go init <目录[类型]>` | 初始化测试项目骨架（gui / api / all，默认 gui） |
| `just-go add <名称> <路径>` | 注册测试项目 |
| `just-go list` | 列出已注册项目（含路径有效性标记） |
| `just-go remove <名称>` | 取消注册 |
| `just-go run <名称\|路径> [pytest参数]` | 执行测试项目，其余参数透传 pytest（`--tag` / `--record` / `--env` / `--collect-only` 等）；**自动使用被测项目独立虚拟环境**（无则回退框架环境，兼容旧项目） |
| `just-go shell <名称\|路径>` | 进入被测项目的 pipenv 虚拟环境（首次自动创建并安装依赖） |
| `just-go version`（或 `just-go --version`） | 显示框架版本号（无需任何依赖，可直接执行） |

---

## 环境要求

- Python 3.10+
- 平台：Windows / Linux（Linux 桌面录屏需 X11 环境）
- 浏览器：`just-go install playwright` 自动安装 Chromium
- Allure 报告需 Java：`just-go install allure` 检测缺失会自动尝试安装（Windows 用 winget 装 Temurin JDK，Linux 用 apt 装 OpenJDK 17），装不了会给出手动下载指引
- ffmpeg：录屏必需，`just-go install ffmpeg` 从 PyPI 取出内置二进制装到 `~/.just-go/ffmpeg`（不依赖 winget/apt，不写入项目虚拟环境，一次安装供所有项目共用），或手动下载 ffmpeg 放到该目录 / 加入 PATH

> **测试项目虚拟环境**：`just-go init` 生成骨架时自动创建项目级 pipenv 虚拟环境并安装依赖。
> GUI 项目自动包含 playwright，纯 API 项目不装 playwright。
> `just-go run` 自动检测并使用项目环境执行；项目额外依赖在环境内 `pipenv install <包名>`。

---

## 常见问题

**录屏没有产出 / 提示 ffmpeg 未安装？**
运行 `just-go install ffmpeg`，二进制装到 `~/.just-go/ffmpeg` 后立即被框架发现，不需要重开终端；所有项目的虚拟环境共用同一份，无需各自安装。

**Allure 报告没生成？**
`just-go install allure` 安装报告工具（需要 Java，检测缺失会自动装 Temurin JDK）。报告生成依赖 allure 工具；即使未装，Allure 原始结果仍保留在 `cache/report/`。

**浏览器起不来 / 提示 playwright 相关错误？**
运行 `just-go install playwright` 安装 Chromium；若配置了 `framework.browser_path`，确认该路径的浏览器可执行文件存在；无头模式看不到窗口属正常（`config.run.show_browser`）。

**用例收集数量为 0？**
`just-go init` 生成的是空白脚手架，填充前收集到 0 个用例属正常。确认用例函数名以 `test_` 开头、位于 `testpaths`（默认 `cases/`）目录下。

**用例被自动跳过？**
检查对应 `tag/<模块>/<模块名>.csv` 的「跳过原因」列是否已填写。

**`--tag` 筛选不生效？**
`--tag` 依赖 `tag/` 目录与登记数据：确认 CSV 已登记该用例（用例ID 与函数名中 ID 一致），表达式不区分大小写，支持 `and` / `or` / 括号组合。

**想直接用 pytest 而不是 just-go run？**
可以。项目根 `conftest.py` 已声明框架插件，在项目根直接敲 `pytest` 即可，效果相同。

**导入 just_go 报 `SoftwareNotInstallError`？**
说明项目虚拟环境未创建或依赖未装全：在项目目录执行 `pipenv install`，或重新 `just-go init` 生成项目（自动创建环境）。

---

## 贡献与许可

- 问题与建议：GitHub Issues（[issues](https://github.com/lu-xianseng/justgo/issues)）
- 版本发布：打tag 触发 GitHub Actions + Trusted Publishing 自动构建发布到 PyPI
- License：MIT
