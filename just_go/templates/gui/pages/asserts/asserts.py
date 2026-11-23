#!/usr/bin/env python3
"""项目断言集合（pages/asserts/asserts.py）

断言独立成类，不从 PageExport 继承，好处是你可以随意往里加业务断言，
不用改动页面对象的继承链。

- 内置断言来自 AssertCommon（数据断言）与 SyncAssert（UI 断言），继承即全部可用；
  每个 UI 断言都紧跟着配套的 assert_not_xxx（如 assert_not_visible / assert_not_text_contains），
  是真实方法，IDE 可补全与跳转；
- 自定义断言按 assert_xxx 命名写成本类方法，PageExport 会自动转发：
      page.assert_visible(page.login_page.login_btn)   # 内置 UI 断言
      page.assert_xxx(...)                             # 你新增的断言
- 自定义时请避开内置名字：覆盖 assert_text_contains 之类会丢掉 Playwright 的
  自动等待重试与统一日志，改用一个业务含义的新名字（如 assert_order_no）；
- 想用别的命名前缀，直接经由 page.asserts 调用，如 page.asserts.check_xxx(...)
- 异步用例把 SyncAssert 换成 AsyncAssert，其余不变。
"""
from just_go.asserts import AssertCommon, SyncAssert


class Asserts(SyncAssert, AssertCommon):
    """项目断言集合：内置断言 + 自定义断言

    自定义断言就按下面这样写在本类里（按需替换成本项目的断言）：

    def assert_order_no(self, locator):
        '''订单号必须是 12 位数字'''
        actual = self.page.locator(locator).inner_text()
        assert re.fullmatch(r"\\d{12}", actual.strip()), f"订单号格式不对：{actual!r}"
    """
