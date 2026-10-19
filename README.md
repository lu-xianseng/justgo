# lets-go

Web 自动化测试框架。框架和测试代码分开放：lets-go 装的是框架，测试项目是另一个目录，用命令指定项目来跑测试。

## 安装

```bash
pip install lets-go
```

也可以下载 wheel 文件本地安装：

```bash
pip install lets_go-0.1.0-py3-none-any.whl
```

装完在命令行里就有 `lets-go` 命令了。

## 安装运行依赖

框架运行需要一些依赖，用 `lets-go install` 装：

```bash
lets-go install          # 全部装好（推荐）
```

也可以分开装：

```bash
lets-go install core        # 框架核心依赖（pytest、playwright 等）
lets-go install playwright  # 浏览器 chromium（跑测试必须）
lets-go install allure      # 报告工具，用于生成 HTML 报告
lets-go install ffmpeg      # 桌面录屏用，可选
```

几个说明：

- 报告工具 allure 不随框架打包，装的时候会下载到用户目录 `~/.lets-go/allure/`。生成 HTML 报告需要 Java，没装的话命令会自动尝试安装（用 winget 装 Temurin JDK），装不了会给手动下载地址。不装 allure 也能跑用例、出原始结果，只是不出 HTML 报告。
- 录屏默认用 Playwright 自带的，不需要装 ffmpeg。只有你想切回桌面录屏时才需要 ffmpeg。
- 测试项目自己用的 Python 包（比如 redis、pymysql），装到运行 lets-go 的那个 Python 里就行。开发版（源码目录里跑）用 `pipenv install 包名`，安装版直接 `pip install 包名`。

## 新建测试项目

```bash
lets-go init SHOP-TEST
```

会在当前目录下生成一个 `SHOP-TEST` 项目（想放别处就写绝对路径，比如 `lets-go init D:\ProjectCode\SHOP-TEST`，项目名取目录名）。目录已存在且不为空时会拒绝。

生成的是空骨架：`cases/module/`、`pages/module_page/`、`tag/module.csv`、`conftest.py`、`pytest.ini` 和一份开发指南。文件里只留了说明注释，页面类、用例函数这些都要自己填。先看项目里那份 `README.md`，按里面的步骤写页面对象和用例。

写用例之前，先打开 `conftest.py`，把 `LETSGO_TEST_BASE_URL` 改成被测系统的实际地址。

## 注册项目

```bash
lets-go add shop D:\ProjectCode\SHOP-TEST   # 注册，名字自己起
lets-go list                                 # 看已注册的项目
lets-go remove shop                          # 取消注册
```

注册不是必须的，不注册也能直接按路径跑。

## 跑测试

```bash
lets-go run shop                                # 按注册名跑
lets-go run D:\ProjectCode\SHOP-TEST            # 按路径跑
lets-go run shop --collect-only                 # 只收集用例，不执行
lets-go run shop --tag "smoke and L1"           # 按标记筛选
```

其他 pytest 参数也能往后加，直接透传给 pytest。

## 测试报告、日志、录屏在哪

默认输出在**测试项目根目录**下：

```
SHOP-TEST/
├─ logs/           # 运行日志
├─ reports/        # allure HTML 报告（带时间戳的目录）
└─ cache/
   ├─ report/      # allure 原始结果，录屏、截图也在里面
   └─ temp/        # 录屏等临时文件
```

不想输出到项目目录（比如 CI 归档、项目目录只读），可以重定向：

```bash
lets-go run shop --output D:\lets-go-output
```

产物会放到 `D:\lets-go-output\shop\` 下面（输出根目录 + 项目名）。也可以用环境变量 `LETSGO_OUTPUT_ROOT`，效果一样。

报告用浏览器打开 `reports` 里最新时间戳目录下的 `index.html`。

## 配置

**被测系统地址**：改测试项目 `conftest.py` 里的 `LETSGO_TEST_BASE_URL`。有测试管理平台的话，可以再配 `LETSGO_TEST_CASE_BASE_URL` 让报告里带上用例链接。

**框架配置**：在框架的 `configs/config.ini` 里，只放框架自己的项（浏览器路径、慢速等待、录屏方式这些）。想改某个值，直接在测试项目 `conftest.py` 里赋值，只对这次运行生效，优先级更高：

```python
from lets_go import config

config.run.slow_time = 1000          # 操作间隔毫秒
config.run.show_browser = False      # 无头模式
```

## 用例写法

同步、异步都行，一个项目里可以混着写。

同步（默认）：

```python
def test_login(page):
    page.goto("https://example.com")
    page.fill("#user", "admin")
```

异步，用 `await`，不需要装 pytest-asyncio：

```python
async def test_login(page):
    await page.goto("https://example.com")
    await page.fill("#user", "admin")
```

`page` 是框架给的 fixture，用例直接拿。失败自动截图、录屏对两种写法都生效。

## tag 筛选（可选）

项目根放一个 `tag/` 目录，里面一个模块一个 CSV，登记用例。没有这个目录就不启用筛选，用例全部执行。

```
tag/module.csv:
脚本ID,用例ID,用例级别,场景,跳过原因,废弃,其它
1001,1001,L1,模块搜索,,,
```

跑的时候用 `--tag` 筛选。不想用了，把 `tag/` 目录删掉就行。

## 录屏

默认开着，用 Playwright 内置录屏，跑完自动把 webm 附到报告里。不想录屏，把 `pytest.ini` 里的 `--record=yes` 删掉。想用桌面录屏（需要 ffmpeg），改框架配置：

```ini
[run]
record_backend = ffmpeg
```
