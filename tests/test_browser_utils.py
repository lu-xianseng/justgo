# -*- coding: utf-8 -*-
"""WebUI 页面能力单元测试（mock Page 验证方法转发，不启动真实浏览器）"""
from unittest import mock

from just_go._internal.web import SyncWebUI


class FakePage:
    """模拟 playwright Page：全部方法为 mock，可断言调用"""

    def __init__(self):
        self.context = mock.Mock()
        self.context.pages = [self]
        self._loc = mock.Mock()
        self.locator = mock.Mock(return_value=self._loc)
        self.evaluate = mock.Mock()
        self.get_by_text = mock.Mock()
        self.get_by_text.return_value.first.wait_for = mock.Mock()
        self.route = mock.Mock()
        self.unroute = mock.Mock()
        self.drag_and_drop = mock.Mock()
        self.screenshot = mock.Mock()
        self.frame_locator = mock.Mock()
        self.wait_for_timeout = mock.Mock()


def make_webui():
    page = FakePage()
    return SyncWebUI(page), page


class TestScroll:
    def test_scroll_to_bottom(self):
        w, page = make_webui()
        w.scroll_to_bottom()
        page.evaluate.assert_called_once()
        assert page.evaluate.call_args[0][0].startswith("window.scrollTo")

    def test_scroll_to_locator(self):
        w, page = make_webui()
        w.scroll_to("#list")
        page.locator.assert_called_with("#list")
        page._loc.scroll_into_view_if_needed.assert_called_once()


class TestUpload:
    def test_upload_file(self):
        w, page = make_webui()
        w.upload_file("input[type=file]", r"C:\tmp\a.txt")
        page.locator.assert_called_with("input[type=file]")
        page._loc.set_input_files.assert_called_with(r"C:\tmp\a.txt")


class TestScreenshot:
    def test_screenshot_attaches_to_allure(self):
        w, page = make_webui()
        page.screenshot = mock.Mock(return_value=b"png-bytes")
        with mock.patch("just_go._internal.web.allure.attach") as attach:
            w.screenshot(name="step1")
        page.screenshot.assert_called_once()
        attach.assert_called_once()
        assert attach.call_args[0][0] == b"png-bytes"
        assert attach.call_args[1]["name"] == "step1"


class TestFrame:
    def test_switch_to_frame_returns_frame_locator(self):
        w, page = make_webui()
        fl = w.switch_to_frame("#iframe")
        assert fl is page.frame_locator.return_value
        page.frame_locator.assert_called_with("#iframe")

    def test_exit_frame_returns_page(self):
        w, page = make_webui()
        assert w.exit_frame() is page


class TestMisc:
    def test_wait_for_text(self):
        w, page = make_webui()
        w.wait_for_text("登录成功")
        page.get_by_text.assert_called_with("登录成功", exact=False)
        page.get_by_text.return_value.first.wait_for.assert_called_once()

    def test_get_attribute(self):
        w, page = make_webui()
        page._loc.get_attribute = mock.Mock(return_value="/detail/1")
        assert w.get_attribute("a.link", "href") == "/detail/1"
        page._loc.get_attribute.assert_called_with("href")

    def test_execute_js(self):
        w, page = make_webui()
        page.evaluate = mock.Mock(return_value=42)
        assert w.execute_js("1 + 1") == 42
        page.evaluate.assert_called_with("1 + 1", None)

    def test_mock_route_json(self):
        w, page = make_webui()
        w.mock_route("**/api/login", json={"code": 0})
        page.route.assert_called_once()
        assert page.route.call_args[0][0] == "**/api/login"

    def test_unroute(self):
        w, page = make_webui()
        w.unroute("**/api/login")
        page.unroute.assert_called_with("**/api/login")

    def test_drag_and_drop(self):
        w, page = make_webui()
        w.drag_and_drop("#src", "#dst")
        page.drag_and_drop.assert_called_with("#src", "#dst")
