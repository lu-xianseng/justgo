## 目录结构（GUI）

```
{name}/
├─ conftest.py            # 项目根配置：声明框架插件 + 注入被测地址（必改）
├─ pytest.ini             # pytest 配置：收集规则 / 默认录屏
├─ cases/                 # 测试用例（一个用例文件 = 一个模块/功能的一组用例）
│  ├─ base_case.py        # 用例基类：公共样板（打开页面/实例化页面对象）下沉到这里
│  └─ module/
│     └─ test_xxx.py      # 用例占位文件：按命名约定重命名并填充（见三步走）
├─ pages/                 # 页面对象（PO 核心：每个页面一个类，一个模块一个文件）
│  ├─ __init__.py         # 统一出口：所有页面对象在此导出，用例从 pages 导入
│  ├─ base_page.py        # 页面基类：通用元素操作（业务无关）
│  └─ module.py           # 模块页面占位文件：按模块封装业务操作
└─ tag/                   # 用例标记（可选：tag 机制启用后支持 --tag 筛选）
   └─ module.csv          # 一个模块一个 CSV，登记该模块下所有用例
```

## 核心思路：基类下沉公共逻辑，页面/用例只写业务

自动化开发大量代码是重复的（输入、点击、等待、打开页面、实例化对象……）。
本骨架用**两个基类**把这些业务无关的逻辑收拢，写页面和用例时只需要关注业务：

| 基类 | 位置 | 收拢什么 |
| --- | --- | --- |
| `BasePage` | pages/base_page.py | 继承框架 `WebUI`，自动获得：滚动/上传/截图/iframe/文本等待/属性/JS/接口 mock/拖拽/响应拦截；本文件只补充 Playwright 没有的便捷方法：wait_visible/get_text/is_visible/多标签页 |
| `BaseCase` | cases/base_case.py | 用例公共样板（实例化页面对象、打开页面 open_page），后续可加登录/数据准备等 |

## 怎么开发 GUI 用例（三步走）

### 1. 写页面对象（pages/<模块>.py）
继承 `BasePage`，通用操作直接用 Playwright 原生方法（`self.page.fill/click/press` 等）或框架能力，**只写业务**（定位器 + 业务操作组合）：

```python
from pages.base_page import BasePage

class HomePage(BasePage):
    # ① 元素定位器：集中维护，页面结构变了只改这里
    _search_input = 'input[placeholder*="搜索"]'

    # ② 业务操作：组合通用动作，只写业务步骤
    def search(self, keyword):
        self.page.fill(self._search_input, keyword)   # Playwright 原生
        self.page.press(self._search_input, "Enter")  # Playwright 原生

    # ③ 返回业务结果：供用例层断言
    def get_search_result(self):
        return self.get_text(self._search_result)  # BasePage 便捷方法
```

写完后在 `pages/__init__.py` 统一导出（新增页面也这样做）：

```python
from pages.base_page import BasePage
from pages.module import ModulePage

__all__ = ["BasePage", "ModulePage", "PageExport"]
```

### 2. 写用例（cases/）
继承 `BaseCase`，设置 `page_cls` 指定被测页面，**只写业务步骤 + 断言**：

```python
import allure
from cases.base_case import BaseCase
from pages import ModulePage

@allure.feature("模块")
class TestModule(BaseCase):
    page_cls = ModulePage  # 被测页面对象类

    def test_module_search_1001(self, page):
        """模块搜索功能验证"""
        module = self.open_page(page)  # 基类样板：实例化 ModulePage 并打开
        module.search("手机")          # 业务步骤
        assert "手机" in module.get_search_result(), "搜索结果应包含关键词"
```

约定：
- 用例函数名 `test_<模块>_<用例ID>`，用例ID（如 1001）与 tag CSV 中的 用例ID 对应；
- `page` 是框架提供的 fixture（Playwright 页面）：同步用例直接调用，
  异步用例 `async def test_xxx(page)` 用 `await page.xxx()`，两种写法都支持；
- 通用能力按需在 `BasePage`/`BaseCase` 扩展（如公共登录、表格操作），页面和用例保持只写业务。

### 3. 登记 tag（可选）
不需要筛选可以跳过。需要时在 `tag/<模块>/<模块名>.csv` 登记该用例（4 列）：

```
用例ID,用例级别,场景,跳过原因
1001,L1,模块搜索,
```

- 用例ID 与用例函数名 `test_<模块>_<用例ID>` 中的 ID 对应（框架按此匹配）；
- `跳过原因` 填写后该用例自动跳过；
- 登记后即可筛选：`just-go run <名称> --tag "L1 and 模块"`（支持 and/or/括号）；
- 不想用 tag：删掉 `tag/` 目录即可，用例直接全部执行。
