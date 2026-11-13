# -*- coding: utf-8 -*-
"""element 元素封装单元测试：描述符 / 动作日志 / 脱敏 / 链式定位 / 参数还原"""
import pytest

from just_go._internal.asserts import _to_locator
from just_go._internal.element import Element
from just_go._internal.logger import logger
from just_go._internal.web import SyncWebUI
from just_go.web import AsyncElement, async_element, element


class FakeLocator:
    """最小可用的 Locator 替身：记录调用，支持链式"""

    def __init__(self, selector, calls):
        self.selector = selector
        self.calls = calls

    @property
    def first(self):
        return FakeLocator(f"{self.selector} >> first", self.calls)

    @property
    def last(self):
        return FakeLocator(f"{self.selector} >> last", self.calls)

    def nth(self, index):
        return FakeLocator(f"{self.selector} >> nth({index})", self.calls)

    def filter(self, **kwargs):
        return FakeLocator(f"{self.selector} >> filter", self.calls)

    def locator(self, child):
        return FakeLocator(f"{self.selector} >> {child}", self.calls)

    def get_by_role(self, role, **kwargs):
        return FakeLocator(f"{self.selector} >> role={role}", self.calls)

    def count(self):
        return 2

    def fill(self, value, **kwargs):
        self.calls.append(("fill", self.selector, value))

    def click(self, **kwargs):
        self.calls.append(("click", self.selector, None))

    def check(self, **kwargs):
        self.calls.append(("check", self.selector, None))

    def set_input_files(self, files, **kwargs):
        self.calls.append(("set_input_files", self.selector, files))

    def drag_to(self, target, **kwargs):
        self.calls.append(("drag_to", self.selector, target))

    def inner_text(self, **kwargs):
        return "文本内容"


class FakeContext:
    pages = []


class FakePage:
    def __init__(self):
        self.context = FakeContext()
        self.calls = []

    def locator(self, selector):
        return FakeLocator(selector, self.calls)


class DemoPage(SyncWebUI):
    """演示页面"""

    account = element("[name='username']", "账号输入框")
    password = element("[name='password']", "密码输入框", sensitive=True)
    token_input = element("#token", "令牌")  # 属性名命中敏感词，自动脱敏
    remark = element("#remark", "备注输入框")
    login_btn = element("button:has-text('登录')", "登录按钮")
    upload_input = element("input[type=file]", "上传控件")


@pytest.fixture
def log_messages():
    """捕获 loguru 日志正文"""
    messages = []
    sink_id = logger.add(lambda m: messages.append(m.record["message"]))
    yield messages
    logger.remove(sink_id)


@pytest.fixture
def demo_page():
    return DemoPage(FakePage())


class TestDescriptor:
    def test_get_returns_element(self, demo_page):
        assert isinstance(demo_page.account, Element)

    def test_class_access_returns_descriptor(self):
        # 类上访问拿描述符本身，不是 Element
        assert not isinstance(DemoPage.account, Element)

    def test_element_selector_and_desc(self, demo_page):
        el = demo_page.account
        assert el.selector == "[name='username']"
        assert el.desc == "账号输入框"

    def test_desc_defaults_to_attr_name(self):
        class NoDesc(SyncWebUI):
            """无描述页面"""

            phone = element("#phone")

        assert NoDesc(FakePage()).phone.desc == "phone"

    def test_inherited_by_subclass(self):
        class Child(DemoPage):
            """子页面"""

        assert isinstance(Child(FakePage()).account, Element)

    def test_async_element_type(self):
        class AsyncDemo(SyncWebUI):
            """异步演示页面"""

            account = async_element("#a", "账号")

        assert isinstance(AsyncDemo(FakePage()).account, AsyncElement)

    def test_async_element_has_action_methods(self):
        assert callable(AsyncElement.fill)
        assert callable(AsyncElement.click)


class TestActionLog:
    def test_fill_logs_value(self, demo_page, log_messages):
        demo_page.account.fill("admin")
        assert any("账号输入框" in m and '"admin"' in m for m in log_messages)

    def test_click_logs_action(self, demo_page, log_messages):
        demo_page.login_btn.click()
        assert any("登录按钮" in m and "点击" in m for m in log_messages)

    def test_page_name_from_docstring(self, demo_page, log_messages):
        demo_page.account.fill("admin")
        assert any(m.startswith("[演示页面]") for m in log_messages)

    def test_action_calls_real_locator(self, demo_page):
        demo_page.account.fill("admin")
        assert demo_page.page.calls == [("fill", "[name='username']", "admin")]

    def test_every_action_method_generated(self):
        from just_go._internal.element import _ACTION_LABELS

        for name in _ACTION_LABELS:
            assert callable(getattr(Element, name))
            assert callable(getattr(AsyncElement, name))


class TestSensitive:
    def test_explicit_sensitive(self, demo_page, log_messages):
        demo_page.password.fill("123456")
        assert any("***" in m for m in log_messages)
        assert not any("123456" in m for m in log_messages)

    def test_auto_sensitive_by_attr_name(self, demo_page, log_messages):
        demo_page.token_input.fill("abc123")
        assert any("***" in m for m in log_messages)
        assert not any("abc123" in m for m in log_messages)

    def test_normal_value_not_masked(self, demo_page, log_messages):
        demo_page.remark.fill("随便写")
        assert any("随便写" in m and "***" not in m for m in log_messages)


class TestChain:
    def test_first_returns_element(self, demo_page):
        el = demo_page.login_btn.first
        assert isinstance(el, Element)
        assert el.native.selector.endswith(">> first")

    def test_last_returns_element(self, demo_page):
        el = demo_page.login_btn.last
        assert isinstance(el, Element)
        assert el.native.selector.endswith(">> last")

    def test_nth_returns_element(self, demo_page):
        el = demo_page.account.nth(1)
        assert isinstance(el, Element)
        assert "nth(1)" in el.native.selector

    def test_child_locator_returns_element(self, demo_page):
        el = demo_page.account.locator("#child")
        assert isinstance(el, Element)
        assert "#child" in el.native.selector

    def test_get_by_role_returns_element(self, demo_page):
        el = demo_page.login_btn.get_by_role("button")
        assert isinstance(el, Element)
        assert "role=button" in el.native.selector

    def test_all_returns_element_list(self, demo_page):
        items = demo_page.account.all
        assert len(items) == 2
        assert all(isinstance(i, Element) for i in items)

    def test_chain_action_still_logs(self, demo_page, log_messages):
        demo_page.login_btn.first.click()
        assert any("登录按钮" in m and "点击" in m for m in log_messages)

    def test_every_child_method_generated(self):
        from just_go._internal.element import _CHILD_METHODS

        for name in _CHILD_METHODS:
            assert callable(getattr(Element, name))
            assert callable(getattr(AsyncElement, name))


class TestArgumentUnwrap:
    def test_drag_to_element_converted_to_locator(self, demo_page):
        demo_page.account.drag_to(demo_page.login_btn)
        calls = demo_page.page.calls
        assert calls[0][0] == "drag_to"
        assert isinstance(calls[0][2], FakeLocator)

    def test_set_input_files_shows_basename(self, demo_page, log_messages):
        demo_page.upload_input.set_input_files(r"D:\data\logo.png")
        assert any("logo.png" in m and "D:\\data" not in m for m in log_messages)

    def test_basename_handles_both_separators(self):
        """日志取文件名不能依赖 os.sep：POSIX 上 os.path.basename 不认反斜杠。

        CI 是 Linux，本机是 Windows，这条用例在两边都要通过。
        """
        from just_go._internal.element import _basename

        assert _basename(r"D:\data\logo.png") == "logo.png"
        assert _basename("/data/logo.png") == "logo.png"
        assert _basename("logo.png") == "logo.png"
        assert _basename(r"D:\data\a.png") == "a.png"

    def test_non_path_value_not_truncated(self, demo_page, log_messages):
        """日期这类含斜杠的普通值不能当成文件路径截成最后一段"""
        demo_page.remark.fill("2026/11/13")
        assert any("2026/11/13" in m for m in log_messages)
        assert not any(m.endswith('"13"') for m in log_messages)

    def test_looks_like_path(self):
        from just_go._internal.element import _looks_like_path

        assert _looks_like_path(r"D:\data\logo.png")
        assert _looks_like_path("/tmp/cases.csv")
        assert _looks_like_path("images/btn.png")
        assert not _looks_like_path("2026/11/13")
        assert not _looks_like_path("a/b")

    def test_unwrap_args_covers_async_element(self):
        """异步元素互传（drag_to/filter）也要还原成原生 Locator"""
        from just_go._internal.element import _unwrap_args

        class FakeOwner:
            class page:
                @staticmethod
                def locator(selector):
                    return FakeLocator(selector, [])

        target = AsyncElement(FakeOwner(), selector="#b")
        args, kwargs = _unwrap_args((target,), {"target": target})
        assert isinstance(args[0], FakeLocator)
        assert isinstance(kwargs["target"], FakeLocator)

    def test_async_element_has_all(self):
        """AsyncElement 与同步版对齐，提供 all"""
        import inspect as _inspect

        assert _inspect.iscoroutinefunction(AsyncElement.all)


class TestPassthrough:
    def test_unknown_member_passthrough(self, demo_page):
        assert demo_page.account.inner_text() == "文本内容"

    def test_native_property(self, demo_page):
        assert isinstance(demo_page.account.native, FakeLocator)

    def test_repr(self, demo_page):
        assert "账号输入框" in repr(demo_page.account)

    def test_private_attr_raises(self, demo_page):
        with pytest.raises(AttributeError):
            _ = demo_page.account._no_such_private


class TestAssertCompatible:
    def test_to_locator_unwraps_element(self, demo_page):
        assert isinstance(_to_locator(demo_page.account), FakeLocator)

    def test_to_locator_keeps_selector(self):
        assert _to_locator("#submit") == "#submit"
