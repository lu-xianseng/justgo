# 更新日志

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
版本号递增规则：修复 `x.y.patch+1`，新功能 `x.minor+1`，不兼容变更 `major+1`。

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
