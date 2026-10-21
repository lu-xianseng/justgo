# 更新日志

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
版本号递增规则：修复 `x.y.patch+1`，新功能 `x.minor+1`，不兼容变更 `major+1`。
发布到 PyPI 后同版本不可覆盖，发新版必须递增版本号。

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
