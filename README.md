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
│   └── configs/config.ini   # 框架配置（浏览器、目录、allure 路径）
├── tools/allure/       # allure 报告工具
├── lets-go.bat         # Windows 命令入口
├── pyproject.toml      # 可 pip/pipenv 安装（安装后获得 lets-go 命令）
└── Pipfile             # pipenv 依赖清单
```

## 安装

```bash
# 方式一：pipenv（推荐，与原项目一致）
cd D:\ProjectCode\lets-go
pipenv install
playwright install

# 方式二：pip 安装（获得全局 lets-go 命令）
pip install -e D:\ProjectCode\lets-go

# 方式三：不安装，直接用启动脚本（把 lets-go 目录加入 PATH）
set PATH=D:\ProjectCode\lets-go;%PATH%
```

## 使用

### 注册测试项目

```bash
lets-go add office_automation D:\ProjectCode\web_auto_test
lets-go list
lets-go remove office_automation
```

### 执行测试

```bash
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

测试项目的运行产物（logs / reports / cache）输出在**测试项目根目录**下，与拆分前行为一致。

## 测试项目需要满足的约定

- 根目录下有一个 conftest.py，至少声明 `pytest_plugins = ["lets_go.plugin"]`（框架插件兜底）；
- 测试代码中 `from lets_go import ...` 引用框架（原 `from src import ...` 已统一改写）；
- tag CSV 位于用例目录对应位置（沿用原有 `cases -> tag` 映射规则）；
- 应用级 fixture、环境配置（config）留在测试项目内，属于测试项目自身。
