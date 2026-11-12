#!/usr/bin/env python3
"""项目断言集合（pages/asserts/asserts.py）

断言独立成类，不从 PageExport 继承，好处是你可以随意往里加业务断言，
不用改动页面对象的继承链。

- 内置断言来自 AssertCommon（数据断言）与 SyncAssert（UI 断言），继承即全部可用；
- 自定义断言按 assert_xxx 命名写成本类方法，PageExport 会自动转发：
      page.assert_visible(page.login_page.login_btn)   # 内置 UI 断言
      page.assert_xxx(...)                             # 你新增的断言
- 想用别的命名前缀，直接经由 page.asserts 调用，如 page.asserts.check_xxx(...)
- 异步用例把 SyncAssert 换成 AsyncAssert，其余不变。
"""
from just_go.asserts import AssertCommon, SyncAssert


class Asserts(SyncAssert, AssertCommon):
    """项目断言集合：内置断言 + 自定义断言

    自定义断言就按下面这样写在本类里（按需替换成本项目的断言）：

    def assert_text_contains(self, locator, expected):
        actual = self.page.locator(locator).inner_text()
        assert expected in actual, f"元素文本不含 {expected!r}：{actual!r}"
    """
