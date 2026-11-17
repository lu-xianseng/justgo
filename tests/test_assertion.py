# -*- coding: utf-8 -*-
"""AssertCommon 断言单元测试"""
import pytest

from just_go._internal.asserts import AssertCommon


class TestAssertCommon:
    def setup_method(self):
        self.assertor = AssertCommon()

    def test_equal_ok(self):
        self.assertor.assert_equal(1, 1)

    def test_equal_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_equal(1, 2)

    def test_not_equal_ok(self):
        self.assertor.assert_not_equal(1, 2)

    def test_not_equal_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_not_equal(1, 1)

    def test_in_ok(self):
        self.assertor.assert_in("abc", "xxabcxx")

    def test_in_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_in("zzz", "abc")

    def test_not_in_ok(self):
        self.assertor.assert_not_in("zzz", "abc")

    def test_true_ok(self):
        self.assertor.assert_true(1 == 1)

    def test_false_ok(self):
        self.assertor.assert_false(1 == 2)

    def test_re_check_equal_ok(self):
        self.assertor.assert_re_check_equal(r"\d{4}", "订单号 1234")

    def test_re_check_equal_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_re_check_equal(r"\d{4}", "无数字")

    def test_re_check_not_equal_ok(self):
        self.assertor.assert_re_check_not_equal(r"\d{4}", "无数字")

    def test_re_check_not_equal_fail(self):
        with pytest.raises(AssertionError):
            self.assertor.assert_re_check_not_equal(r"\d{4}", "订单号 1234")


class TestLocatorConversion:
    """断言可直接传 element() / async_element() 声明的元素"""

    @staticmethod
    def _owner():
        class FakePage:
            @staticmethod
            def locator(selector):
                return f"native:{selector}"

        class Owner:
            page = FakePage()

        return Owner()

    def test_to_locator_unwraps_async_element(self):
        """异步用例用 async_element 声明元素后，await page.assert_visible(el) 不能报类型错误"""
        from just_go._internal.asserts import _to_locator
        from just_go._internal.element import AsyncElement

        element = AsyncElement(self._owner(), selector="#a", desc="按钮")
        assert _to_locator(element) == "native:#a"

    def test_to_locator_unwraps_sync_element(self):
        from just_go._internal.asserts import _to_locator
        from just_go._internal.element import Element

        element = Element(self._owner(), selector="#b", desc="按钮")
        assert _to_locator(element) == "native:#b"

    def test_to_page_unwraps_page_export(self):
        """expect() 只认原生 Page，传 PageExport 会被判为 Unsupported type"""
        from just_go._internal.asserts import _to_page
        from just_go._internal.web import SyncWebUI

        class FakeContext:
            pages = []
            request = object()

            def on(self, event, handler):
                pass

        class FakePage:
            context = FakeContext()

            def wait_for_timeout(self, ms):
                pass

        class PageExport(SyncWebUI):
            def __init__(self, page):
                super().__init__(page)

        raw = FakePage()
        assert _to_page(PageExport(raw)) is raw
        assert _to_page(raw) is raw


class TestAssertionCoverage:
    """UI 断言集合：同步/异步一致，且每个正向断言都有可用的反向断言"""

    POSITIVE = (
        "assert_visible",
        "assert_hidden",
        "assert_attached",
        "assert_empty",
        "assert_count",
        "assert_text",
        "assert_text_contains",
        "assert_value",
        "assert_values",
        "assert_checked",
        "assert_enabled",
        "assert_disabled",
        "assert_editable",
        "assert_focused",
        "assert_attribute",
        "assert_id",
        "assert_class",
        "assert_class_contains",
        "assert_url",
        "assert_title",
    )

    def test_sync_and_async_expose_same_methods(self):
        """两套断言类必须一一对齐，避免只补了同步版"""
        from just_go.asserts import AsyncAssert, SyncAssert

        sync_ui = {n for n in vars(SyncAssert) if n.startswith("assert_")}
        async_ui = {n for n in vars(AsyncAssert) if n.startswith("assert_")}
        assert sync_ui == async_ui
        assert set(self.POSITIVE) <= sync_ui

    def test_every_positive_has_negation(self):
        """每个正向断言都要有配套 assert_not_xxx"""
        from just_go.asserts import SyncAssert

        for name in self.POSITIVE:
            neg = "assert_not_" + name[len("assert_"):]
            assert hasattr(SyncAssert, neg), f"缺少 {neg}"

    def test_negation_signature_matches_positive(self):
        """反向断言入参与正向一致，用例不必记两套参数"""
        import inspect

        from just_go.asserts import SyncAssert

        for name in self.POSITIVE:
            if name in ("assert_visible", "assert_hidden", "assert_attached", "assert_empty",
                        "assert_checked", "assert_enabled", "assert_disabled",
                        "assert_editable", "assert_focused"):
                continue  # 纯状态断言正向本身没有额外参数
            pos = inspect.signature(getattr(SyncAssert, name))
            neg = inspect.signature(getattr(SyncAssert, "assert_not_" + name[len("assert_"):]))
            assert list(pos.parameters) == list(neg.parameters), name

    def test_native_names_exist_in_playwright(self):
        """@negates 里写的断言名必须在当前 Playwright 版本上真实存在"""
        import inspect

        from playwright.sync_api import LocatorAssertions, PageAssertions

        from just_go.asserts import SyncAssert

        for name, func in vars(SyncAssert).items():
            native = getattr(func, "__negate_native__", None)
            if not native:
                continue
            group = (
                PageAssertions
                if list(inspect.signature(func).parameters)[1] == "page"
                else LocatorAssertions
            )
            assert hasattr(group, "to_" + native), f"{name}: to_{native} 不存在"
            assert hasattr(group, "not_to_" + native), f"{name}: not_to_{native} 不存在"


class TestNegationDispatch:
    """反向断言必须调用 Playwright 的 not_to_xxx，并原样透传参数"""

    @staticmethod
    def _record(monkeypatch, module_attr, async_mode=False):
        calls = []

        class Recorder:
            def __init__(self):
                self._name = None

            def __getattr__(self, name):
                def call(*args, **kwargs):
                    calls.append((name, args, kwargs))
                    if async_mode:
                        async def done():
                            return None

                        return done()
                    return None

                return call

        if async_mode:
            def fake_expect(target):
                calls.append(("expect", target))
                return Recorder()
        else:
            def fake_expect(target):
                calls.append(("expect", target))
                return Recorder()

        monkeypatch.setattr(f"just_go._internal.asserts.{module_attr}", fake_expect)
        return calls

    def test_not_have_text_called(self, monkeypatch):
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_text("#a", "错误提示")
        assert ("not_to_have_text", ("错误提示",), {}) in calls

    def test_ignore_case_forwarded(self, monkeypatch):
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_text_contains("#a", "提示", ignore_case=True)
        assert ("not_to_contain_text", ("提示",), {"ignore_case": True}) in calls

    def test_positive_ignore_case_forwarded(self, monkeypatch):
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_text("#a", "提示", ignore_case=True)
        name, args, kw = next(c for c in calls if c[0].startswith("to_"))
        assert name == "to_have_text" and args == ("提示",) and kw["ignore_case"] is True

    def test_attribute_value_forwarded(self, monkeypatch):
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_attribute("#a", "href", "/home")
        # 第一个断言参数按位置传，其余按关键字透传（Playwright 的 native 参数名一致）
        assert ("not_to_have_attribute", ("href",), {"value": "/home"}) in calls

    def test_attribute_keyword_call(self, monkeypatch):
        """用例按关键字调用（name= / value=）同样生效"""
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_attribute(locator="#a", name="disabled", value="true")
        assert ("not_to_have_attribute", ("disabled",), {"value": "true"}) in calls

    def test_page_keyword_call(self, monkeypatch):
        """page 断言按关键字传 page= 也必须还原成原生 Page"""
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_url(page="#p", expected="/login")
        assert ("not_to_have_url", ("/login",), {}) in calls

    def test_async_negation_awaits_native(self, monkeypatch):
        import asyncio

        from just_go.asserts import AsyncAssert

        calls = self._record(monkeypatch, "async_expect", async_mode=True)
        asyncio.run(AsyncAssert().assert_not_class("#a", "active"))
        assert ("not_to_have_class", ("active",), {}) in calls

    def test_explicit_timeout_forwarded(self, monkeypatch):
        """显式 timeout 必须透传，不能被吞掉；未传时用 Playwright 默认"""
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_text("#a", "错误", timeout=1000)
        assert ("not_to_have_text", ("错误",), {"timeout": 1000}) in calls

        calls.clear()
        SyncAssert().assert_not_text("#a", "错误")
        assert calls[-1][2] == {}, "未传 timeout 时不应传 timeout=None"
