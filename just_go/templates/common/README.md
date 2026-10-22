# {name} 自动化测试项目

基于 just-go 框架的测试项目骨架（类型：{mode_label}）。

> **骨架说明**：本命令生成的是**空白脚手架**——目录结构、配置、开发指南都在，
> 但所有代码文件的类名、方法名、业务逻辑留空，由你按本指南自行填充。
> 填充后即可运行；未填充时 `pytest --collect-only` 收集到 0 个用例属正常现象。

> 说明：框架约定标记目录名为 `tag`（单数），位于项目根；项目没有 `tag/` 目录时
> 不启用 tag 机制，用例不校验、不筛选，全部直接执行。

{sections}

## 运行

```bash
# 首次：注册项目（把 <名称> 换成你的项目名）
just-go add <名称> .

# 进入本项目独立的 pipenv 虚拟环境（首次自动创建并安装依赖）
just-go shell <名称>

# 执行全部用例（自动使用本项目独立虚拟环境执行）
just-go run <名称>

# 只收集不执行（快速验证骨架）
just-go run <名称> --collect-only

# 带 tag 筛选
just-go run <名称> --tag "smoke and L1"
```

或进入项目环境后直接在项目根敲 pytest（conftest 已声明框架插件）：

```bash
just-go shell <名称>     # 进入项目虚拟环境
pytest
```

## 配置

| 配置项 | 位置 | 说明 |
| --- | --- | --- |
| 被测系统地址 | conftest.py 的 setup_env() | 必改，填入 dev/test/prod 环境地址 |
| 用例链接前缀 | conftest.py 的 JUSTGO_TEST_CASE_BASE_URL | 可选 |
| 录屏开关 | pytest.ini 的 --record | 默认开；删掉该行即关闭 |
| 录屏方式 | 框架内置 | 统一使用系统 ffmpeg 桌面录屏（Windows gdigrab / Linux x11grab），产出 mp4 附到报告；需已安装 ffmpeg（`just-go install ffmpeg`） |
| 失败重试 | pytest.ini 的 --reruns | 默认失败重试 1 次；单用例可用 `@pytest.mark.flaky(reruns=3)` 覆盖，改 0 即关闭 |
| 浏览器类型 | conftest.py 里 config.run.browser_type | chromium/firefox/webkit，默认 chromium |
| 登录态复用 | conftest.py 里 config.run.storage_state | 登录用例保存 state 文件后跨用例复用，免重复登录 |
| 慢速/是否显示浏览器 | conftest.py 里 config.run.xxx | 运行时覆盖，优先级高于框架配置文件 |

## 运行产物

默认输出到项目根下：`logs/`（日志）、`reports/`（allure HTML 报告）、
`cache/`（allure 原始结果 report/、临时录屏与截图 temp/）。
可重定向：`just-go run <名称> --output D:\产物目录`。

## 依赖与虚拟环境

- **本项目拥有独立的 pipenv 虚拟环境**（`just-go init` 时自动创建并安装依赖）。
  GUI 项目自动包含 playwright，纯 API 项目不装 playwright。
- `just-go run` 自动检测并使用项目环境执行，各测试项目之间依赖互不影响。
- 进入项目环境：`just-go shell <名称>`。
- 系统级工具（Chromium / allure / ffmpeg）：`just-go install` 按需安装。
- 测试项目额外的 Python 依赖（如 redis、pymysql）：在项目环境内 `pipenv install <包名>`。
