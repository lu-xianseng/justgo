## 目录结构（API）

```
{name}/
├─ conftest.py            # 项目根配置：声明框架插件 + 注入被测地址（必改）
├─ pytest.ini             # pytest 配置：收集规则
├─ apis/                  # 接口封装（一个模块一个文件，把接口封装成方法）
│  ├─ __init__.py         # 统一出口：接口封装在此导出，用例从 apis 导入
│  ├─ base.py             # 接口基类：通用请求能力（get/post/put/delete、令牌注入，业务无关）
│  └─ module.py           # 模块接口占位文件：按模块封装接口方法
├─ cases/                 # 测试用例
│  ├─ base_case.py        # 用例基类（API 用例通常用不到，保留备用）
│  └─ api/
│     └─ test_xxx.py      # 用例占位文件：按命名约定重命名并填充
└─ tag/                   # 用例标记（可选：tag 机制启用后支持 --tag 筛选）
   └─ api.csv             # 一个模块一个 CSV，登记该模块下所有用例
```

## 核心思路：基类下沉公共逻辑，接口/用例只写业务

与 GUI 骨架对称：`apis/base.py` **直接继承框架的 Request**（HTTP 能力全部继承），
本类只额外提供基址拼接，具体接口封装只写业务方法。

| 基类 | 位置 | 收拢什么 |
| --- | --- | --- |
| `BaseApi` | apis/base.py | 继承框架 Request：get/post/put/delete/upload_file/download、set_token/set_cookie/get_cookies/set_proxy、自动重试；新增 base_url 基址 + _url(path) 拼接 |

## 怎么开发 API 用例（三步走）

### 1. 封装接口（apis/<模块>.py）
继承 `BaseApi`，通用请求能力直接用，**只写业务**（接口地址 + 参数 + 返回业务结果）：

```python
from .base import BaseApi

class UserApi(BaseApi):
    def login(self, username, password):
        """登录：POST /api/login"""
        resp = self.post(
            self._url("/api/login"),
            json={"username": username, "password": password},
        )
        return resp.json()

    def get_user_info(self, user_id):
        """获取用户信息：GET /api/user/{id}"""
        resp = self.get(self._url(f"/api/user/{user_id}"))
        return resp.json()

user_api = UserApi()
```

登录拿 token 后可注入全局请求头，后续请求自动携带：

```python
user_api.set_token(token, prefix="Bearer ")   # Authorization: Bearer <token>
```

写完后在 `apis/__init__.py` 统一导出（新增模块也这样做）：

```python
from .module import module_api

__all__ = ["module_api", "ApiExport"]
```

### 2. 写用例（cases/api/）
API 用例不需要 page fixture，直接调接口方法 + 断言：

```python
from apis import module_api

def test_login_1001():
    data = module_api.login("admin", "123456")
    assert data["code"] == 0
```

约定：用例函数名 `test_<模块>_<用例ID>`，用例ID 与 tag CSV 中的 用例ID 对应。

### 3. 登记 tag（可选）
和 GUI 一样，在 `tag/<模块>/<模块名>.csv` 登记该用例：

```
用例ID,用例级别,场景,跳过原因
1001,L1,登录接口,
```

- 用例ID 与用例函数名 `test_<模块>_<用例ID>` 中的 ID 对应（框架按此匹配）；
- 运行时可筛选：`just-go run <项目> --tag "L1 and 登录"`；
- 不想用 tag：删掉 `tag/` 目录即可，用例直接全部执行。
