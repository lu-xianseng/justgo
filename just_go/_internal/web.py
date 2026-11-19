#!/usr/bin/env python3
# coding=utf-8
# @Time     :2025/2/26 17:50
# @Author   :luye
"""Web UI 页面对象基类：同步 / 异步两套。

- SyncWebUI：配合 def test_xxx(page) 同步用例
- AsyncWebUI：配合 async def test_xxx(page) 异步用例，所有方法需 await

接收 locator 参数的方法统一支持三种入参：
    选择器字符串、Element / AsyncElement（element() 声明的元素）、原生 Locator

接口请求走 self.api（复用浏览器 context 的 cookie 与登录态）：
    page.api.get("/admin-api/xxx", params={"pageNo": 1})
"""
import functools
from typing import Any, Callable, TypeVar

try:
    import allure
    from playwright.async_api import Page as AsyncPage
    from playwright.async_api import Response as AsyncResponse
    from playwright.sync_api import Page, Response
except ImportError as e:
    from just_go._internal.errors import SoftwareNotInstallError

    missing = "allure" if e.name == "allure" else "playwright"
    raise SoftwareNotInstallError(missing) from e
from just_go._internal.api import APIRequest, AsyncAPIRequest
from just_go._internal.element import AsyncElement, Element
from just_go._internal.logger import logger

F = TypeVar("F", bound=Callable[..., Any])

__all__ = ["SyncWebUI", "AsyncWebUI"]


# ======================================================================
# 同步版（对应 playwright.sync_api）
# ======================================================================
class SyncWebUI:
    """同步页面对象基类，配合 def test_xxx(page) 使用。"""

    def __init__(self, page: Page, only_keep_one: bool = False):
        self.page: Page = page
        self.__api = None
        self._init_api()
        pages = self.page.context.pages
        if only_keep_one:
            for p in pages:
                if id(p) != id(self.page):
                    p.close()

    def _init_api(self):
        """尽早创建接口客户端并绑定鉴权监听。

        复用登录态时首屏的业务请求就带着 token；等到用例第一次访问 page.api
        才绑定，这些请求已经发完，token 抓不到，接口就会 401。

        这只是优化：任何原因绑不上都必须降级为 `api` property 懒创建，不能
        打断页面对象的构造。已知会失败的场景——异步页面对象在同步 fixture
        里构造时没有运行中的事件循环，`context.on()` 会抛 RuntimeError。
        """
        try:
            api = APIRequest(self.page.context.request)
            api.bind_auth(self.page.context, page=self.page)
        except Exception as exc:  # noqa: BLE001  预绑定失败不应影响用例执行
            logger.debug(f"page.api 预绑定鉴权监听失败，改为按需创建：{exc}")
            self.__api = None
            return
        self.__api = api

    # ------------------------------------------------------------------
    # 接口客户端
    # ------------------------------------------------------------------
    @property
    def api(self):
        """接口客户端：复用当前 page 所属 context 的 cookie 与登录态。

        懒创建，构造页面对象时不强依赖 context.request（假 page 也能构造）；
        创建后缓存复用——**不能靠比较 context 对象身份来判断是否重建**，
        Playwright 每次访问 page.context.request 都可能给出新的包装对象，
        判断会一直成立，导致每次访问都新建实例、set_headers 的配置全部丢失。
        page 被换到别的 context 后，调 refresh_api() 显式重建。

        需要自定义基址 / 全局头时可以直接替换：page.api = APIRequest(..., base_url=...)
        """
        if self.__api is None:
            self.__api = APIRequest(self.page.context.request)
            # 自动沿用页面业务请求里的鉴权头：token 型鉴权的项目（cookie 为空）
            # 不必再在 conftest 里手工抓 token 再注入
            self.__api.bind_auth(self.page.context)
        return self.__api

    @api.setter
    def api(self, value):
        self.__api = value

    def refresh_api(self):
        """重建接口客户端（page 被换到另一个 context 后调用，保留自定义配置请自行迁移）"""
        if self.__api is not None:
            # 旧实例的 request 监听还挂在原 context 上，不注销会一直累积
            self.__api.unbind_auth()
        self.__api = APIRequest(self.page.context.request)
        self.__api.bind_auth(self.page.context)
        return self.__api

    def ensure_api(self):
        """page 换了 context 才重建接口客户端；同一个 context 内切标签不动它。

        切标签（switch_to_latest_tab）通常仍在同一 context，盲目 refresh_api
        会把已经抓到的鉴权头丢掉，紧接着调接口就会 401。
        """
        if self.__api is not None:
            bound = getattr(self.__api, "_auth_context", None)
            if bound is self.page.context:
                return self.__api
        return self.refresh_api()

    # ------------------------------------------------------------------
    # locator 入参归一化（子类可复用）
    # ------------------------------------------------------------------
    def _as_locator(self, target):
        """选择器字符串 / Element / Locator → 原生 Locator。

        Element 取 .native（已绑定它自己的 page，切换标签页后仍定位正确）；
        字符串按选择器处理；其余对象（Locator）原样返回。
        """
        if isinstance(target, Element):
            return target.native
        if isinstance(target, str):
            return self.page.locator(target)
        return target

    def _as_selector(self, target):
        """Element → 选择器字符串（frame_locator 这类只收字符串的 API 用）

        没有选择器表达式的 Element（手工构造缺 selector）直接报错，
        比把 None 交给 frame_locator 更好定位。
        """
        if not isinstance(target, Element):
            return target
        if not target.selector:
            raise ValueError(
                "该 Element 没有选择器表达式，frame_locator 只接受选择器字符串，"
                "请直接传 iframe 的选择器"
            )
        return target.selector

    @classmethod
    def intercept_response(cls, api) -> Callable[[F], Callable[..., Response]]:
        """装饰器：拦截匹配 api 的响应，返回 Response 对象。"""

        def decorator(func) -> Callable[..., Response]:
            @functools.wraps(func)
            def wrapper(*args, **kwargs) -> Response:
                def response_handler(response: Response):
                    if api in response.url:
                        obj._justgo_response = response

                obj = args[0]
                obj._justgo_response = None
                obj.page.on("response", response_handler)
                try:
                    func(*args, **kwargs)
                    obj.page.wait_for_load_state("domcontentloaded")
                finally:
                    obj.page.remove_listener("response", response_handler)
                    result = obj._justgo_response
                    obj._justgo_response = None
                return result

            return wrapper

        return decorator

    def create_new_instance(self, page=None, close_other_tabs=True):
        """创建新页面实例（通常用于新弹出的 tab）。Returns: (instance, page_obj)

        不能把 only_keep_one 透传给子类构造函数：模板 BasePage / PageExport 的
        __init__ 只接收 page，多传参数会直接 TypeError。关闭多余 tab 在实例建好
        之后做，与异步版保持一致。
        """
        new_page = page if page else self.page.context.pages[-1]
        instance = self.__class__(new_page)
        if close_other_tabs:
            for p in new_page.context.pages:
                if id(p) != id(new_page):
                    p.close()
        return instance, new_page

    def all_tabs(self):
        """返回所有页面 tab 对象列表"""
        return self.page.context.pages

    def sleep(self, _time):
        """等待 {{_time}} 秒"""
        # logger.info(f"等待{_time}秒")
        self.page.wait_for_timeout(int(float(_time) * 1000))

    def scroll_to_bottom(self):
        """滚动到页面底部"""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    def scroll_to(self, locator):
        """滚动使元素进入视口。locator 可传 element(...) 声明的 Element"""
        self._as_locator(locator).scroll_into_view_if_needed()

    def upload_file(self, locator, path):
        """上传文件（单文件 str 或多文件 list[str]）。locator 可传 Element"""
        self._as_locator(locator).set_input_files(path)

    def screenshot(self, name="screenshot", full_page=False):
        """截图并附加到 allure 报告"""
        png = self.page.screenshot(full_page=full_page)
        allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)

    def switch_to_frame(self, locator):
        """进入 iframe，返回 FrameLocator。Element 取其选择器表达式"""
        return self.page.frame_locator(self._as_selector(locator))

    def exit_frame(self):
        """退出 iframe，回到主文档"""
        return self.page

    def wait_for_text(self, text, timeout=10_000):
        """等待文本出现（元素可见）"""
        self.page.get_by_text(text, exact=False).first.wait_for(
            state="visible", timeout=timeout
        )

    def get_attribute(self, locator, name):
        """获取元素属性值。locator 可传 Element"""
        return self._as_locator(locator).get_attribute(name)

    def execute_js(self, script, arg=None):
        """执行 JavaScript，返回结果"""
        return self.page.evaluate(script, arg)

    def mock_route(self, pattern, json=None, body=None, status=200, content_type="application/json"):
        """拦截并模拟接口响应"""
        def handler(route):
            if json is not None:
                route.fulfill(status=status, json=json, content_type=content_type)
            else:
                route.fulfill(status=status, body=body or "", content_type=content_type)

        self.page.route(pattern, handler)

    def unroute(self, pattern):
        """移除 mock_route 设置的接口拦截"""
        self.page.unroute(pattern)

    def drag_and_drop(self, source, target):
        """拖拽：source 元素拖到 target 元素（两者都可传 Element）"""
        self._as_locator(source).drag_to(self._as_locator(target))


# ======================================================================
# 异步版（对应 playwright.async_api）
# ======================================================================
class AsyncWebUI:
    """异步页面对象基类，配合 async def test_xxx(page) 使用。所有方法需 await。"""

    def __init__(self, page: AsyncPage):
        """构造函数只保存 page 引用（__init__ 不能是 async）。
        若需关闭多余 tab，请在构造后调用 await close_other_tabs()。"""
        self.page: AsyncPage = page
        self.__api = None
        self._init_api()

    def _init_api(self):
        """尽早创建异步接口客户端并绑定鉴权监听（理由同同步版）。

        同步 fixture 里构造异步页面对象时没有运行中的事件循环，`context.on()`
        会抛 RuntimeError，这里必须降级为懒创建而不是打断构造。
        """
        try:
            api = AsyncAPIRequest(self.page.context.request)
            api.bind_auth(self.page.context, page=self.page)
        except Exception as exc:  # noqa: BLE001  预绑定失败不应影响用例执行
            logger.debug(f"page.api 预绑定鉴权监听失败，改为按需创建：{exc}")
            self.__api = None
            return
        self.__api = api

    # ------------------------------------------------------------------
    # 接口客户端
    # ------------------------------------------------------------------
    @property
    def api(self):
        """接口客户端（异步）：复用当前 page 所属 context 的 cookie 与登录态。

        懒创建并缓存；理由同同步版——不要用 context 对象身份判断重建。
        所有请求方法都要 await。
        """
        if self.__api is None:
            self.__api = AsyncAPIRequest(self.page.context.request)
            self.__api.bind_auth(self.page.context)
        return self.__api

    @api.setter
    def api(self, value):
        self.__api = value

    def refresh_api(self):
        """重建异步接口客户端（page 被换到另一个 context 后调用）"""
        if self.__api is not None:
            self.__api.unbind_auth()
        self.__api = AsyncAPIRequest(self.page.context.request)
        self.__api.bind_auth(self.page.context)
        return self.__api

    def ensure_api(self):
        """page 换了 context 才重建异步接口客户端（理由同同步版）"""
        if self.__api is not None:
            bound = getattr(self.__api, "_auth_context", None)
            if bound is self.page.context:
                return self.__api
        return self.refresh_api()

    # ------------------------------------------------------------------
    # locator 入参归一化（子类可复用）
    # ------------------------------------------------------------------
    def _as_locator(self, target):
        """选择器字符串 / AsyncElement / 异步 Locator → 异步 Locator"""
        if isinstance(target, (Element, AsyncElement)):
            return target.native
        if isinstance(target, str):
            return self.page.locator(target)
        return target

    def _as_selector(self, target):
        """Element / AsyncElement → 选择器字符串（frame_locator 只收字符串）"""
        if not isinstance(target, (Element, AsyncElement)):
            return target
        if not target.selector:
            raise ValueError(
                "该 Element 没有选择器表达式，frame_locator 只接受选择器字符串，"
                "请直接传 iframe 的选择器"
            )
        return target.selector

    async def close_other_tabs(self):
        """关闭除当前页外的其他标签页"""
        for p in self.page.context.pages:
            if id(p) != id(self.page):
                await p.close()

    @classmethod
    def intercept_response(cls, api):
        """装饰器：拦截匹配 api 的响应（异步版）。"""

        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                def response_handler(response: AsyncResponse):
                    if api in response.url:
                        obj._justgo_response = response

                obj = args[0]
                obj._justgo_response = None
                self_page = obj.page
                self_page.on("response", response_handler)
                try:
                    await func(*args, **kwargs)
                    await self_page.wait_for_load_state("domcontentloaded")
                finally:
                    self_page.remove_listener("response", response_handler)
                    result = obj._justgo_response
                    obj._justgo_response = None
                return result

            return wrapper

        return decorator

    async def create_new_instance(self, page=None, close_other_tabs=True):
        """创建新页面实例。Returns: (AsyncWebUI 子类实例, AsyncPage)"""
        new_page = page if page else self.page.context.pages[-1]
        instance = self.__class__(new_page)
        if close_other_tabs:
            await instance.close_other_tabs()
        return instance, new_page

    def all_tabs(self):
        """返回所有页面 tab 对象列表（属性访问，同步）"""
        return self.page.context.pages

    async def sleep(self, _time):
        """等待 {{_time}} 秒"""
        # logger.info(f"等待{_time}秒")
        await self.page.wait_for_timeout(int(float(_time) * 1000))

    async def scroll_to_bottom(self):
        """滚动到页面底部"""
        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    async def scroll_to(self, locator):
        """滚动使元素进入视口。locator 可传 async_element(...) 声明的 AsyncElement"""
        await self._as_locator(locator).scroll_into_view_if_needed()

    async def upload_file(self, locator, path):
        """上传文件。locator 可传 AsyncElement"""
        await self._as_locator(locator).set_input_files(path)

    async def screenshot(self, name="screenshot", full_page=False):
        """截图并附加到 allure 报告"""
        png = await self.page.screenshot(full_page=full_page)
        allure.attach(png, name=name, attachment_type=allure.attachment_type.PNG)

    def switch_to_frame(self, locator):
        """进入 iframe，返回 AsyncFrameLocator，后续操作需 await"""
        return self.page.frame_locator(self._as_selector(locator))

    def exit_frame(self):
        """退出 iframe，回到主文档"""
        return self.page

    async def wait_for_text(self, text, timeout=10_000):
        """等待文本出现（元素可见）"""
        await self.page.get_by_text(text, exact=False).first.wait_for(
            state="visible", timeout=timeout
        )

    async def get_attribute(self, locator, name):
        """获取元素属性值。locator 可传 AsyncElement"""
        return await self._as_locator(locator).get_attribute(name)

    async def execute_js(self, script, arg=None):
        """执行 JavaScript，返回结果"""
        return await self.page.evaluate(script, arg)

    async def mock_route(self, pattern, json=None, body=None, status=200, content_type="application/json"):
        """拦截并模拟接口响应"""
        async def handler(route):
            if json is not None:
                await route.fulfill(status=status, json=json, content_type=content_type)
            else:
                await route.fulfill(status=status, body=body or "", content_type=content_type)

        await self.page.route(pattern, handler)

    async def unroute(self, pattern):
        """移除 mock_route 设置的接口拦截"""
        await self.page.unroute(pattern)

    async def drag_and_drop(self, source, target):
        """拖拽：source 元素拖到 target 元素（两者都可传 AsyncElement）"""
        await self._as_locator(source).drag_to(self._as_locator(target))
