# letsgo

Web 自动化测试框架：**框架与测试代码分离，一条命令指定测试项目执行自动化测试，自动产出报告。**

```bash
pip install letsgo
lets-go install        # 安装运行依赖（浏览器、报告工具等）
lets-go init SHOP-TEST # 生成测试项目骨架
lets-go run SHOP-TEST  # 执行测试项目
```

框架只装一次，测试项目单独存放、各自独立。升级框架、换机器、发布到 CI，都不影响测试代码本身。

## 它解决什么问题

传统的 Web 自动化测试，框架代码和测试用例通常混在同一个项目里：换一个被测系统就要复制一份框架，框架升级要逐个项目改，别人接手还得先读懂整套源码。

letsgo 把这两层拆开：

```
┌────────────────────┐        ┌────────────────────┐
│  letsgo（框架）     │  run   │  测试项目（业务代码） │
│  安装一次，全局复用  │ ──────▶│  pages / cases /    │
│  pytest/报告/录屏/  │        │  apis / tag         │
│  tag 筛选/配置      │        │  只写被测系统相关    │
└────────────────────┘        └────────────────────┘
```

框架负责跑测试、出报告、管环境；测试项目只负责写被测系统（页面对象、接口封装、用例）。

## 主要优点

| 优点 | 说明 |
| --- | --- |
| **框架与测试代码分离** | 框架独立安装、独立升级；测试项目里没有任何框架源码，换项目、换人维护成本低 |
| **PO 模式脚手架** | `lets-go init` 一键生成项目骨架，支持 GUI / API / 两者全要；基类下沉公共逻辑，写页面和用例时只关注业务 |
| **同步 / 异步用例都支持** | `def` 或 `async def` 混着写都可以，无需安装 pytest-asyncio，框架自动路由 |
| **内置轻量录屏** | 默认用 Playwright 内置录制（零额外依赖），跑完自动把 webm 附到报告；不想装 ffmpeg 也能录屏 |
| **allure 报告开箱即用** | 自动生成 HTML 报告，附失败截图、录屏；报告工具和 Java 由 `lets-go install` 自动安装 |
| **tag 用例筛选** | 项目 `tag/` 目录 + CSV 登记用例，`--tag` 表达式筛选（支持 and/or），按级别/场景挑着跑 |
| **产物输出可重定向** | 日志、报告、录屏默认输出在测试项目根；CI 归档时用 `--output` 重定向到指定目录 |
| **环境管理省心** | pipenv 虚拟环境自动引导；`lets-go install core/playwright/allure/ffmpeg` 按需安装，缺什么装什么 |
| **配置都在项目里** | 被测地址、录屏后端、慢速等待都在测试项目配置，不动框架本身 |

## 快速开始

### 1. 安装框架

```bash
pip install letsgo
```

装完先装运行依赖（浏览器、报告工具）：

```bash
lets-go install          # 全部依赖
```

### 2. 初始化测试项目

```bash
lets-go init SHOP-TEST                     # GUI 骨架（页面对象 + 页面用例）
lets-go init "SHOP-API[api]"               # API 骨架（接口封装 + 接口用例）
lets-go init "SHOP-ALL[all]"               # 两种都生成
```

会在当前目录生成一个空白脚手架：目录结构、配置文件、开发指南都在，类名、方法名、业务逻辑由你按项目内 README 的步骤填充。

### 3. 配置被测地址

打开测试项目的 `conftest.py`，把 `LETSGO_TEST_BASE_URL` 改成被测系统实际地址。

### 4. 注册并运行

```bash
lets-go add shop D:\ProjectCode\SHOP-TEST   # 注册，名字自己起
lets-go run shop                            # 执行全部用例
lets-go run shop --tag "smoke and L1"       # 按 tag 筛选
lets-go run shop --collect-only             # 只收集用例，不执行
```

跑完打开 `reports/` 下最新目录里的 `index.html` 看报告，录屏、失败截图都在里面。

## 用例怎么写

同步（默认）：

```python
def test_login(page):
    page.goto("https://example.com")
    page.fill("#user", "admin")
    assert "登录成功" in page.content()
```

异步，用 `await`：

```python
async def test_login(page):
    await page.goto("https://example.com")
    await page.fill("#user", "admin")
    assert "登录成功" in await page.content()
```

`page` 是框架提供的 fixture，两种写法在一个项目里可以混用。

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `lets-go install [core\|playwright\|allure\|ffmpeg\|all]` | 安装/检查运行依赖 |
| `lets-go init <目录[类型]>` | 初始化测试项目骨架（gui/api/all，默认 gui） |
| `lets-go add <名称> <路径>` | 注册测试项目 |
| `lets-go list` | 列出已注册项目 |
| `lets-go remove <名称>` | 取消注册 |
| `lets-go run <名称\|路径> [pytest参数]` | 执行测试项目，其余参数透传给 pytest |

## 配置

| 配置项 | 位置 | 说明 |
| --- | --- | --- |
| 被测系统地址 | 项目 `conftest.py` 的 `LETSGO_TEST_BASE_URL` | 必改 |
| 用例链接前缀 | 项目 `conftest.py` 的 `LETSGO_TEST_CASE_BASE_URL` | 可选，报告带用例链接 |
| 录屏后端 | 项目 `pytest.ini` 的 `record_backend` | `playwright`（内置，默认）或 `ffmpeg`（桌面录屏） |
| 慢速 / 无头模式 | 项目 `conftest.py` 里 `config.run.slow_time` 等 | 运行时覆盖，只对本次运行生效 |
| 产物输出目录 | `lets-go run <项目> --output <目录>` | 重定向日志/报告/录屏，适合 CI 归档 |

测试项目自身的 Python 依赖（如 redis、pymysql）直接装到运行 letsgo 的 Python 里即可。

## 测试项目组织

`lets-go init` 生成的标准结构（GUI）：

```
SHOP-TEST/
├─ conftest.py            # 注入被测地址、声明框架插件
├─ pytest.ini             # pytest 配置、录屏开关
├─ cases/                 # 用例（含 base_case 用例基类）
├─ pages/                 # 页面对象（含 base_page 页面基类）
└─ tag/                   # 用例标记（可选）
```

框架对测试项目**不强制结构**：只要项目根有 `conftest.py` 声明框架插件就能跑。`init` 生成的结构是推荐起点，你完全可以根据自己的项目调整。

## 运行产物

默认输出在测试项目根下：

```
SHOP-TEST/
├─ logs/           # 运行日志
├─ reports/        # allure HTML 报告
└─ cache/          # allure 原始结果、录屏、截图
```

CI 或只读目录场景，用 `--output` 重定向到指定目录（按 输出根/项目名 分子目录，多项目互不干扰）。

## 环境要求

- Python 3.10+
- 浏览器由 `lets-go install playwright` 自动安装
- allure 报告需要 Java，`lets-go install allure` 检测到缺失会自动尝试安装（winget 装 Temurin JDK），装不了会给出手动下载指引
- ffmpeg 仅在使用 `record_backend = ffmpeg` 桌面录屏时需要，可选
