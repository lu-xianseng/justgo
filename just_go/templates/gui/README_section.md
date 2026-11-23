## 目录结构（GUI）

```
{name}/
├─ conftest.py            # 项目根配置：声明框架插件 + 注入被测地址（必改）
├─ pytest.ini             # pytest 配置：收集规则 / 默认录屏 / 报告模式
├─ cases/                 # 测试用例
│  ├─ case_base.py        # 用例基类：公共样板（登录、数据准备）下沉到这里
│  └─ module/
│     └─ test_xxx.py      # 用例文件：按命名约定重命名并填充
├─ pages/                 # 页面对象
│  ├─ __init__.py         # 统一出口：PageExport = 通用能力 + 子页面 + 断言
│  ├─ base_page.py        # BasePage / AsyncBasePage + element 元素声明
│  ├─ asserts/
│  │  └─ asserts.py       # 断言集合：内置断言 + 你自定义的断言
│  └─ login_page/
│     ├─ login_page_ele.py  # 只写元素（不继承基类）
│     └─ login_page.py      # 继承元素类，只写业务动作组合
└─ tag/                   # 用例标记（可选：启用后支持 --tag 筛选）
   └─ module.csv          # 一个模块一个 CSV，登记该模块下所有用例
```

## 核心思路：元素与业务分离，动作日志自动化

每个页面拆成两个文件，各司其职：

| 文件 | 只写什么 |
| --- | --- |
| `xxx_page_ele.py` | 元素声明：定位表达式 + 中文描述 + 脱敏标记 |
| `xxx_page.py` | 业务动作组合：调用元素动作完成业务流程 |

元素类**不需要继承任何基类**：`element` 描述符只要求页面实例上有 `page` 属性，由页面类的 `__init__` 绑定。

`BasePage` 只被 `PageExport` 使用，它继承框架 `SyncWebUI`，自动获得滚动/上传/截图/iframe/文本等待/属性/JS/接口 mock/拖拽/响应拦截，另补充 wait_visible/get_text/is_visible/多标签页。

## 怎么开发 GUI 用例（三步走）

### 1. 写页面（pages/<模块>/）

元素文件用 `element(selector, 描述)` 声明，访问后直接调动作，**日志和 Allure 步骤自动记录**：

```python
# pages/login_page/login_page_ele.py
from just_go.web import element

class LoginPageEle:          # 不继承基类
    """登录页面"""

    account = element("[name='username']", "账号输入框")
    password = element("[name='password']", "密码输入框", sensitive=True)
    login_btn = element("button:has-text('登录')", "登录按钮")
```

业务文件继承元素类，只写业务动作组合；`__init__` 只做一件事——把 page 交给元素：

```python
# pages/login_page/login_page.py
from just_go.log import log

from .login_page_ele import LoginPageEle

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

运行日志：

```
INFO | - [登录页面对象] 账号输入框(account) 输入 "admin"
INFO | - [登录页面对象] 密码输入框(password) 输入 ***
INFO | - [登录页面对象] 登录按钮(login_btn) 点击
```

要点：

- 自动记日志的动作：`click` `fill` `press` `check` `select_option` `hover` `drag_to` `set_input_files` `wait_for` `screenshot` 等 28 个；`inner_text` `count` `get_attribute` `is_visible` 这类只读取值的方法直通原生 Locator，不记日志（IDE 补全和返回类型照样完整）
- 链式定位 `first` `last` `nth` `filter` `locator` `get_by_*` `visible` `normalize` `describe` 返回包装后的 Element，日志能力不丢（`visible` 是属性，写 `el.visible` 不是 `el.visible()`）
- iframe：`el.frame_locator("iframe")` / `el.content_frame` 返回 `FrameElement`，只能继续 `locator` / `get_by_*`，不能直接 `.click()`
- 要原生 Locator（如传给 playwright 的 `expect`）用 `.native`
- `sensitive=True` 时值显示 `***`；属性名/描述含 `password` `pwd` `token` `secret` `密码` `验证码` 也会自动脱敏
- 异步用例用 `async_element` 声明，动作需 `await`

新增页面后在 `pages/__init__.py` 注册：

```python
from just_go.log import log

from pages.asserts.asserts import Asserts
from pages.base_page import BasePage
from pages.login_page.login_page import LoginPage

@log
class PageExport(BasePage):
    """页面对象 + 断言统一出口"""

    def __init__(self, page):
        super().__init__(page)
        self.asserts = Asserts()
        self.login_page = LoginPage(self.page)

    def __getattr__(self, name):
        """assert_xxx 转发给 Asserts"""
        asserts = self.__dict__.get("asserts")
        if asserts is not None and name.startswith("assert_"):
            return getattr(asserts, name)
        raise AttributeError(f"{type(self).__name__} 没有属性 {name!r}")
```

### 断言放哪：独立的 `Asserts`

断言不挂在 `PageExport` 的继承链上，而是 `pages/asserts/asserts.py` 里的一个独立类，方便你随时加业务断言：

```python
# pages/asserts/asserts.py
from just_go.asserts import AssertCommon, SyncAssert

class Asserts(SyncAssert, AssertCommon):
    """项目断言集合：内置断言 + 自定义断言"""

    def assert_order_no(self, locator):
        """业务断言：订单号必须是 12 位数字"""
        actual = self.page.locator(locator).inner_text()
        assert re.fullmatch(r"\d{12}", actual.strip()), f"订单号格式不对：{actual!r}"
```

- 内置断言（`assert_visible` / `assert_text` / `assert_text_contains` / `assert_attribute` / `assert_class` 等 UI 断言，以及 `assert_equal` / `assert_in` / `assert_re_check_equal` / `assert_image` 等数据断言）继承 `AssertCommon`、`SyncAssert` 即全部可用；
- 每个 UI 断言都紧跟着配套的 `assert_not_xxx`（如 `assert_not_visible` / `assert_not_text_contains`），同样走 Playwright 的自动等待重试，**不要**自己取 `inner_text()` 再比较；它们是真实方法，IDE 里有补全、跳转与参数提示；
- 自定义断言按 `assert_` 前缀写进 `Asserts`，用例里直接 `page.assert_order_no(...)`；自定义时请避开内置名字，覆盖后将失去内置的重试与日志行为；
- 其他命名前缀不会被转发，改用 `page.asserts.xxx(...)` 调用；
- 异步用例把 `SyncAssert` 换成 `AsyncAssert`（方法集合完全一致，需 `await`）。

### 2. 写用例（cases/）

继承 `CaseBase`，只写业务步骤 + 断言：

```python
from cases.case_base import CaseBase
from pages import PageExport

class TestLogin(CaseBase):
    """登录模块用例"""

    def test_login_1(self, page: PageExport):
        """输入正确账号密码，登录系统"""
        page.login_page.account.fill("admin")
        page.login_page.password.fill("123456")
        page.login_page.login_btn.click()
        page.assert_visible(page.login_page.login_btn)
```

约定：

- 用例函数名 `test_<模块>_<用例ID>`，用例ID（如 1001）与 tag CSV 中的 用例ID 对应；
- `page` 是框架 fixture（已包装成 PageExport）：同步用例直接调，异步用例 `async def test_xxx(page)` 用 `await`；
- 断言可直接传 Element，也可传 selector 字符串。

### 3. 登记 tag（可选）

不需要筛选可以跳过。需要时在 `tag/<模块名>.csv` 登记该用例（4 列）：

```
用例ID,用例级别,场景,跳过原因
1001,L1,模块搜索,
```

- 用例ID 与用例函数名 `test_<模块>_<用例ID>` 中的 ID 对应（框架按此匹配）；
- `跳过原因` 填写后该用例自动跳过；
- 登记后即可筛选：`just-go run <名称> --tag "L1 and 模块"`（支持 and/or/括号）；
- 不想用 tag：删掉 `tag/` 目录即可，用例直接全部执行。
