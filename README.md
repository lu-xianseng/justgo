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
├── tools/allure/       # allure 报告工具
├── lets-go.bat         # Windows 命令入口
├── pyproject.toml      # 可 pip/pipenv 安装（安装后获得 lets-go 命令）
└── Pipfile             # pipenv 依赖清单
```

## 安装



```
# 方式一：pipenv（推荐，与原项目一致）
cd D:\ProjectCode\lets-go
pipenv install
playwright install

# 方式二：pip 安装（获得全局 lets-go 命令）
pip install -e D:\ProjectCode\lets-go

# 方式三：不安装，直接用启动脚本（把 lets-go 目录加入 PATH）
set PATH=D:\ProjectCode\lets-go;%PATH%
```

### 依赖安装命令

框架提供 `lets-go install` 一键安装/检查运行依赖（发布下载后首选）：

```
# 一键安装全部依赖（推荐）
lets-go install

# 或分组件安装
lets-go install core         # 框架核心 Python 依赖（pytest/allure-pytest/playwright 等）
lets-go install legacy       # 旧测试项目历史依赖（jsonpath/redis/selenium/pycryptodome，测试代码直接使用）
lets-go install playwright   # Playwright 浏览器 chromium + 录制编码器 ffmpeg（webm 录屏必需）
lets-go install allure       # 检查报告工具：Java + allure CLI（生成 HTML 报告）
lets-go install ffmpeg       # 系统 ffmpeg（仅桌面录屏后端 record_backend=ffmpeg 需要，可选）
```

说明：

- `core` 依赖清单以 `pyproject.toml` 的 `[project] dependencies` 为唯一来源，`legacy` 来自
  `[project.optional-dependencies] legacy`；
- 浏览器与框架 playwright 库版本自动匹配，无需手动对齐；
- 不装 allure/ffmpeg 不影响用例执行与 allure 原始结果（录屏 webm 照常产出），仅影响
  HTML 报告生成与桌面录屏。

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

### 录屏

默认使用 **Playwright 内置录屏**（`record_backend = playwright`）：零额外依赖、无需安装
ffmpeg，用例执行时录制页面并产出 webm，自动以附件插入 allure 报告。切换回 ffmpeg 桌面录屏
（需安装 ffmpeg）时，修改 `lets_go/configs/config.ini`：

```ini
[run]
record_backend = ffmpeg
```

## 测试项目需要满足的约定



* 根目录下有一个 conftest.py，至少声明 `pytest_plugins = ["lets_go.plugin"]`（框架插件兜底）；

* 测试代码中 `from lets_go import ...` 引用框架（原 `from src import ...` 已统一改写）；

* tag CSV 位于用例目录对应位置（沿用原有 `cases -> tag` 映射规则）；

* 应用级 fixture、环境配置（config）留在测试项目内，属于测试项目自身；

* 被测系统地址 / 禅道用例地址等**测试项目相关配置**不在框架 config 中，由测试项目通过环境变量注入：
  `LETSGO_TEST_BASE_URL`（allure 报告环境信息）、`LETSGO_TEST_CASE_BASE_URL`（allure 用例链接），
  未配置时框架自动跳过对应项。