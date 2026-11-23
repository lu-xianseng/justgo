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

    def test_sync_and_async_expose_same_methods(self):
        """两套断言类必须一一对齐，避免只补了同步版"""
        from just_go.asserts import AsyncAssert, SyncAssert

        sync_ui = {n for n in vars(SyncAssert) if n.startswith("assert_")}
        async_ui = {n for n in vars(AsyncAssert) if n.startswith("assert_")}
        assert sync_ui == async_ui

    def test_every_positive_has_negation(self):
        """每个正向断言都要有配套 assert_not_xxx"""
        for cls in self._classes():
            for name in self._positive_names(cls):
                neg = "assert_not_" + name[len("assert_"):]
                assert neg in vars(cls), f"{cls.__name__} 缺少 {neg}"

    def test_every_negation_has_positive(self):
        """反向断言不能孤立存在（除 assert_not_image 是数据断言，手写在 AssertCommon）"""
        for cls in self._classes():
            for name in vars(cls):
                if not name.startswith("assert_not_"):
                    continue
                pos = "assert_" + name[len("assert_not_"):]
                assert pos in vars(cls), f"{cls.__name__}.{name} 没有对应的 {pos}"

    def test_negation_signature_matches_positive(self):
        """反向断言入参与正向一致，用例不必记两套参数"""
        import inspect

        for cls in self._classes():
            for name in self._positive_names(cls):
                neg = "assert_not_" + name[len("assert_"):]
                pos_params = list(inspect.signature(getattr(cls, name)).parameters)
                neg_params = list(inspect.signature(getattr(cls, neg)).parameters)
                assert pos_params == neg_params, f"{cls.__name__}.{neg}: {pos_params} != {neg_params}"

    def test_negation_calls_matching_native_method(self):
        """反向断言调用的 not_to_xxx 必须与正向调用的 to_xxx 同名。

        两边都是手写的，复制粘贴最容易写成「反向断言调 not_to_be_visible，正向却是
        to_be_hidden」这类正反不配对。这里从方法体里静态解析原生方法名做交叉校验。
        """
        import inspect
        import re

        for cls in self._classes():
            for name in self._positive_names(cls):
                matching = re.findall(r"\.(to_\w+)\s*\(", inspect.getsource(getattr(cls, name)))
                assert matching, f"{cls.__name__}.{name} 没有调用任何 to_xxx 断言"
                neg = "assert_not_" + name[len("assert_"):]
                body = inspect.getsource(getattr(cls, neg))
                called = re.findall(r"\.(not_to_\w+)\s*\(", body)
                assert called == ["not_" + matching[0]], (
                    f"{cls.__name__}.{neg} 应调用 not_{matching[0]}（与正向一致），实际 {called}"
                )
                # 反向断言不能顺手调用正向方法（否则结果相反）
                assert not re.search(r"\.to_\w+\s*\(", body), f"{cls.__name__}.{neg} 误用了正向断言"

    def test_native_assertions_callable_in_playwright(self):
        """方法体里写的 to_xxx / not_to_xxx 必须在当前 Playwright 版本上真实存在"""
        import inspect
        import re

        from playwright.sync_api import LocatorAssertions, PageAssertions

        for cls in self._classes():
            for name in self._positive_names(cls):
                func = getattr(cls, name)
                matching = re.findall(r"\.(to_\w+)\s*\(", inspect.getsource(func))
                assert len(matching) == 1, f"{cls.__name__}.{name} 应只调用一个 to_xxx：{matching}"
                native = matching[0][len("to_"):]
                group = (
                    PageAssertions
                    if list(inspect.signature(func).parameters)[1] == "page"
                    else LocatorAssertions
                )
                assert hasattr(group, "to_" + native), f"{name}: to_{native} 不存在"
                assert hasattr(group, "not_to_" + native), f"{name}: not_to_{native} 不存在"

    @staticmethod
    def _classes():
        from just_go.asserts import AsyncAssert, SyncAssert

        return (SyncAssert, AsyncAssert)

    @staticmethod
    def _positive_names(cls):
        return [
            n for n in vars(cls)
            if n.startswith("assert_") and not n.startswith("assert_not_")
        ]


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

        def fake_expect(target):
            calls.append(("expect", target))
            return Recorder()

        monkeypatch.setattr(f"just_go._internal.asserts.{module_attr}", fake_expect)
        return calls

    @staticmethod
    def _native(calls):
        """本次调用里的原生断言方法（用例自己会传 locator，它走 expect(target) 不参与比对）"""
        return next(c for c in calls if c[0] != "expect")

    def test_not_have_text_called(self, monkeypatch):
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_text("#a", "错误提示")
        name, args, _ = self._native(calls)
        assert name == "not_to_have_text" and args == ("错误提示",)

    def test_ignore_case_forwarded(self, monkeypatch):
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_text_contains("#a", "提示", ignore_case=True)
        assert calls[-1][0] == "not_to_contain_text"
        assert calls[-1][2]["ignore_case"] is True

    def test_positive_ignore_case_forwarded(self, monkeypatch):
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_text("#a", "提示", ignore_case=True)
        name, args, kw = self._native(calls)
        assert name == "to_have_text" and args == ("提示",)
        assert kw["ignore_case"] is True

    def test_attribute_value_forwarded(self, monkeypatch):
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_attribute("#a", "href", "/home")
        name, args, _ = self._native(calls)
        assert name == "not_to_have_attribute" and args == ("href", "/home")

    def test_attribute_keyword_call(self, monkeypatch):
        """用例按关键字调用（name= / value=）同样生效"""
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_attribute(locator="#a", name="disabled", value="true")
        name, args, _ = self._native(calls)
        assert name == "not_to_have_attribute" and args == ("disabled", "true")

    def test_page_keyword_call(self, monkeypatch):
        """page 断言按关键字传 page= 也必须还原成原生 Page"""
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_url(page="#p", expected="/login")
        assert calls[0] == ("expect", "#p")
        name, args, _ = self._native(calls)
        assert name == "not_to_have_url" and args == ("/login",)

    def test_async_negation_awaits_native(self, monkeypatch):
        import asyncio

        from just_go.asserts import AsyncAssert

        calls = self._record(monkeypatch, "async_expect", async_mode=True)
        asyncio.run(AsyncAssert().assert_not_class("#a", "active"))
        name, args, _ = self._native(calls)
        assert name == "not_to_have_class" and args == ("active",)

    def test_explicit_timeout_forwarded(self, monkeypatch):
        """显式 timeout 必须透传；未传时用 Playwright 默认（timeout=None 与不传等价）"""
        from just_go.asserts import SyncAssert

        calls = self._record(monkeypatch, "sync_expect")
        SyncAssert().assert_not_text("#a", "错误", timeout=1000)
        assert calls[-1][2]["timeout"] == 1000

        calls.clear()
        SyncAssert().assert_not_text("#a", "错误")
        assert calls[-1][2]["timeout"] is None


class TestNegationIsStatic:
    """反向断言必须是源码里真实存在的方法：IDE 靠静态解析做补全与跳转"""

    @staticmethod
    def _positive_names(cls):
        return [
            n for n in vars(cls)
            if n.startswith("assert_") and not n.startswith("assert_not_")
        ]

    def test_negation_has_real_source(self):
        """动态生成的方法（setattr）在 inspect.getsource 里只会指向生成器那段代码，
        IDE 也无法补全/跳转。这里要求每个 assert_not_xxx 的源码就是它自己的 def 行。"""
        import inspect

        from just_go.asserts import AsyncAssert, SyncAssert

        for cls in (SyncAssert, AsyncAssert):
            for name in self._positive_names(cls):
                neg = "assert_not_" + name[len("assert_"):]
                func = getattr(cls, neg)
                first_line = inspect.getsource(func).lstrip().splitlines()[0].lstrip()
                assert first_line.startswith("def " + neg) or first_line.startswith("async def " + neg), (
                    f"{cls.__name__}.{neg} 不是独立定义的方法，IDE 无法跳转：{first_line!r}"
                )


class TestNegationLogging:
    """反向断言的日志风格要与正向一致：中文动作 + 用户传进来的对象"""

    @staticmethod
    def _messages():
        from just_go._internal.logger import logger

        messages = []
        sink_id = logger.add(lambda m: messages.append(m.record["message"]))
        return messages, sink_id

    def test_negation_logs_like_positive(self, monkeypatch):
        from just_go._internal.logger import logger
        from just_go.asserts import SyncAssert

        class Recorder:
            def __getattr__(self, name):
                return lambda *a, **kw: None

        monkeypatch.setattr("just_go._internal.asserts.sync_expect", lambda t: Recorder())
        messages, sink_id = self._messages()
        try:
            SyncAssert().assert_visible("#a")
            SyncAssert().assert_not_visible("#a")
        finally:
            logger.remove(sink_id)

        assert messages == ["元素可见: #a", "元素不可见: #a"], messages

    def test_negation_log_uses_element_repr(self, monkeypatch):
        """传 Element 时日志与正向一样打印 <Element 描述(...)>，而不是转换后的原生 Locator repr"""
        from just_go._internal.element import Element
        from just_go._internal.logger import logger
        from just_go.asserts import SyncAssert

        class Recorder:
            def __getattr__(self, name):
                return lambda *a, **kw: None

        class FakePage:
            @staticmethod
            def locator(selector):
                return selector

        class Owner:
            page = FakePage()

        monkeypatch.setattr("just_go._internal.asserts.sync_expect", lambda t: Recorder())
        el = Element(Owner(), selector="#a", desc="登录按钮")
        messages, sink_id = self._messages()
        try:
            SyncAssert().assert_not_visible(el)
        finally:
            logger.remove(sink_id)

        assert messages == ["元素不可见: <Element 登录按钮(#a)>"], messages
