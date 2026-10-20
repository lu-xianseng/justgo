# 更新日志

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。
版本号递增规则：修复 `x.y.patch+1`，新功能 `x.minor+1`，不兼容变更 `major+1`。
发布到 PyPI 后同版本不可覆盖，发新版必须递增版本号。

## [0.1.5] - 未发布

> 说明：`0.1.4` 版本号曾提交但未发布，其改动全部并入本版本。

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
- init 骨架模板抽离为 `just_go/templates/` 独立文件，随包发布（不再内联于 cli.py）
- `just_go/__init__.py` 改显式导入 + `__all__`，消除 star import 隐式依赖链
- `plugin.py` 全部名字改显式导入（修复 `Function` 等依赖隐式链的潜在 NameError）
- `browser_utils.py` 去重 playwright 导入、修正 `expect` re-export、补 `__all__`
- `controller.py` 修复 `not in` 写法；`settings.py` 移除未用导入
- 全项目通过 ruff 检查（配置见 pyproject.toml `[tool.ruff]`）
- README 补充「浏览器与登录态」「多环境切换」「失败重试」「数据驱动」「接口令牌」说明

## [0.1.3] - 2026-10-20

### 新增
- PyPI 发布自动化：GitHub Actions + Trusted Publishing，打 `v*` tag 自动构建发布
- `pyproject.toml` 补充项目主页与仓库链接

## [0.1.2] - 未记录

（早期发布版本，本次整理前无变更记录）

## [0.1.0] - 首次发布

（早期发布版本，本次整理前无变更记录）
