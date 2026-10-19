# lets-go

Web 自动化测试框架（独立版）。框架与测试代码分离：**lets-go 只装框架，测试项目单独存放**，

通过命令指定测试项目执行自动化测试。

## 目录结构



```
lets-go/
├── lets_go/            # 框架包（原 web_auto_test 的 src，已独立并改名）
│   ├── cli.py          # lets-go 命令行入口
│   ├── plugin.py       # pytest 插件（原项目根 conftest.py 逻辑）
│   ├── settings.py     # 配置与路径定位（运行时指向测试项目根）
│   ├── browser_utils.py / request_utils.py / assertion.py / controller.py
│   ├── logger.py / tag_manage.py / parse_tag.py / tools.py
│   ├── mock.py / mock_data.py / exceptions.py
│   └── configs/config.ini   # 框架配置（仅浏览器、目录、allure 路径等框架项）
├── lets-go.bat         # Windows 命令入口
├── pyproject.toml      # 可 pip/pipenv 安装（安装后获得 lets-go 命令）
└── Pipfile             # pipenv 依赖清单
```

> allure 报告工具**不随框架打包**（外部工具、版本独立演进）：由
> `lets-go install allure` 下载安装到用户目录 `~/.lets-go/allure/`，框架自动发现。

## 安装

### 环境管理（pipenv 自动引导）

lets-go 使用 **pipenv 管理虚拟环境**，无需手动建 venv：

- 首次运行 `lets-go install`：自动检测 pipenv（缺失则自动 `pip install pipenv`）→
  创建/复用 pipenv 虚拟环境 → 安装依赖；
- `lets-go run` / `lets-go list` 等命令：自动通过 `pipenv run` 进入虚拟环境执行，
  测试与框架的依赖始终在同一环境；
- 若你已在某个虚拟环境中运行（如自己创建的 venv），不会重复引导；
- 想跳过 pipenv 管理（如 CI 已自行准备环境）：设置环境变量 `LETSGO_SKIP_PIPENV=1`。

### 依赖安装命令

框架提供 `lets-go install` 一键安装/检查运行依赖（发布下载后首选）：

```
# 一键安装全部依赖（推荐）
lets-go install

# 或分组件安装
lets-go install core         # 框架核心 Python 依赖（pytest/allure-pytest/playwright 等）
lets-go install playwright   # Playwright 浏览器 chromium + 录制编码器 ffmpeg（webm 录屏必需）
lets-go install allure       # 下载安装 allure 报告工具到 ~/.lets-go/allure（生成 HTML 报告；可指定版本，见下）
lets-go install ffmpeg       # 系统 ffmpeg（仅桌面录屏后端 record_backend=ffmpeg 需要，可选）
```

说明：

- Python 依赖统一由 pipenv 安装到虚拟环境：`lets-go install`（全部）按 `Pipfile` 全量安装；
  `install core` 按 `pyproject.toml` 的依赖清单安装（清单与 Pipfile 一致）；
- 框架只管理自身依赖，**测试项目自己的第三方包由项目自行安装**
  （`cd <框架目录>` 后 `pipenv install <包>`，装进同一共享环境）；
- 浏览器与框架 playwright 库版本自动匹配，无需手动对齐；
- **allure 工具与框架解耦**：不随框架打包，由 `lets-go install allure` 下载到用户目录
  `~/.lets-go/allure/`（默认锁定版本 2.24.1，可指定版本 `lets-go install allure 2.30.0` 随时升级/降级）；
  Java 仅生成 HTML 报告时需要（原始结果产出不需要）——命令检测到缺失时会**尝试 winget
  自动安装 Temurin JDK**（无 winget 时给出手动下载指引）。框架按以下优先级定位 allure：
  ① config.ini `allure_path` 填写的路径（绝对路径直接用，相对路径基于框架根解析）
  ② 留空时自动查找：PATH 上的 `allure` 命令，其次 `~/.lets-go/allure/*/bin`（多版本取最新）；
- 不装 allure 不影响用例执行与 allure 原始结果（录屏 webm 照常产出），仅跳过 HTML 报告生成
  （运行结束会提示 `lets-go install allure`）；不装 ffmpeg 仅影响桌面录屏后端。

## 使用

### 注册测试项目



```
lets-go add office_automation D:\ProjectCode\web_auto_test
lets-go list
lets-go remove office_automation
```

### 执行测试



```
# 按注册名称执行
lets-go run office_automation

# 按路径直接执行（未注册也可）
lets-go run D:\ProjectCode\web_auto_test

# 带 tag 筛选（沿用原 --tag 表达式，支持 and/or）
lets-go run office_automation --tag "smoke and L1"

# 只收集用例不执行（快速验证）
lets-go run office_automation --collect-only
```

其他 pytest 参数均可透传，通过 `pytest -h` 查看。

### 执行机制

`lets-go run` 会：



1. 解析目标为已注册名称或直接路径，得到测试项目根目录；

2. 设置环境变量 `LETSGO_PROJECT_ROOT` 指向测试项目根，框架据此定位 tag CSV、日志与报告目录；

3. 注入 `PYTHONPATH`（含框架根），未安装 lets-go 也可运行；

4. 以测试项目根为工作目录调用 `pytest -p lets_go.plugin`，其余参数透传。

测试项目的运行产物（logs /reports/cache）默认输出在**测试项目根目录**下，与拆分前行为一致。

### 产物输出目录（可选重定向）

发布 / CI / 只读项目目录场景下，可将产物输出到指定目录：

```bat
:: 命令行参数：按 输出根\项目名 分子目录（多项目互不串扰）
lets-go run office_automation --output D:\lets-go-output

:: 或环境变量（适合 CI 统一归档）：效果同上
set LETSGO_OUTPUT_ROOT=D:\lets-go-output
lets-go run office_automation
```

产物落盘位置：

| 产物 | 默认（项目根） | 指定输出根时 |
| --- | --- | --- |
| 运行日志 | `<项目根>\logs\` | `<输出根>\<项目名>\logs\` |
| allure HTML 报告 | `<项目根>\reports\` | `<输出根>\<项目名>\reports\` |
| allure 原始结果（含录屏 webm、截图） | `<项目根>\cache\report\` | `<输出根>\<项目名>\cache\report\` |
| 录屏 / 临时文件 | `<项目根>\cache\temp\` | `<输出根>\<项目名>\cache\temp\` |

项目名取注册名；按路径执行时取项目根目录名。tag CSV 等测试项目资源始终在项目根定位，不受输出重定向影响。

### 框架配置（两种方式）

框架配置集中在 `lets_go/configs/config.ini`（仅浏览器路径、目录、allure 路径、录屏后端等框架项；
**测试项目相关配置不在此处**）。使用中有两种修改方式：

**方式一：直接改 config.ini（持久生效）**

```ini
[run]
slow_time = 1000
show_browser = False
```

**方式二：测试项目运行时覆盖（推荐，尤其安装版）**

在测试项目 `conftest.py` 顶部导入并赋值，优先级高于 config.ini，仅本次运行生效：

```python
from lets_go import config

config.run.slow_time = 1000          # 慢速操作等待毫秒数
config.run.show_browser = False      # 无头模式
config.framework.browser_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
```

支持任意配置项：`config.framework.*` / `config.run.*` 均可读可写；未赋值项仍读 config.ini。
安装版（wheel）改不了 site-packages 里的配置文件时，用方式二即可。

### 录屏

默认使用 **Playwright 内置录屏**（`record_backend = playwright`）：零额外依赖、无需安装
ffmpeg，用例执行时录制页面并产出 webm，自动以附件插入 allure 报告。切换回 ffmpeg 桌面录屏
（需安装 ffmpeg）时，修改 `lets_go/configs/config.ini`：

```ini
[run]
record_backend = ffmpeg
```

## 测试项目组织方式（可自由选择，非强制）

框架对测试项目**不强制任何组织结构**——下列模式源自参考项目 web_auto_test，
你的项目可以完全照搬、部分采用或自行设计：

**最小要求（仅一条）**：测试项目根目录下有一个 conftest.py，声明
`pytest_plugins = ["lets_go.plugin"]`（让框架插件生效，`lets-go run` 本身也会注入插件，
此条是为了支持直接敲 pytest 的场景）。

**可选模式（参考 web_auto_test）**：

* 测试代码中 `from lets_go import ...` 引用框架（原 `from src import ...` 已统一改写）；
* **tag 筛选机制（可选）**：项目根放 `tag/` 目录 + CSV 标记文件（沿用 `cases -> tag`
  映射规则），`--tag` 表达式筛选即可用；项目没有 `tag/` 目录时，用例不校验、不筛选，
  直接全部执行；
* 应用级 fixture、环境配置（config）留在测试项目内，属于测试项目自身；
* 被测系统地址 / 禅道用例地址等**测试项目相关配置**不在框架 config 中，由测试项目通过环境变量注入：
  `LETSGO_TEST_BASE_URL`（allure 报告环境信息）、`LETSGO_TEST_CASE_BASE_URL`（allure 用例链接），
  未配置时框架自动跳过对应项。

## 用例写法：同步 / 异步（协程）两种都支持

框架的 `page` fixture 会按用例写法自动选择 Playwright 驱动，同一项目可混用：

* **同步（默认，原有方式）**：`def test_xxx(page)`，page 为 `playwright.sync_api` 页面，
  直接调用 `page.goto(...)` 等：

  ```python
  def test_login(page):
      page.goto("https://example.com")
      page.fill("#user", "admin")
  ```

* **异步（协程方式）**：`async def test_xxx(page)`，page 为 `playwright.async_api` 页面，
  用 `await page.xxx()` 调用。**无需安装 pytest-asyncio**，框架插件自动在事件循环中执行：

  ```python
  async def test_login(page):
      await page.goto("https://example.com")
      await page.fill("#user", "admin")
      assert "登录成功" in await page.content()
  ```

注意事项：

* 异步用例内所有 Playwright 方法都要 `await`（goto/fill/click/content/screenshot 等）；
* 失败自动截图、录屏（webm 附件）对同步、异步两种写法均生效；
* 不请求 `page` 的纯异步用例（如纯接口测试）同样支持，框架会自动创建临时事件循环执行。

**测试项目自己的 Python 依赖**（如 redis、pymysql 等）由项目自行安装到共享环境：
`cd <框架目录>` 后执行 `pipenv install <包>`，测试代码即可直接 import。