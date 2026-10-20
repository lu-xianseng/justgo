## 目录结构（API）

```
{name}/
├─ conftest.py            # 项目根配置：声明框架插件 + 注入被测地址（必改）
├─ pytest.ini             # pytest 配置：收集规则
├─ apis/                  # 接口封装（一个模块一个文件，把接口封装成方法）
│  ├─ __init__.py         # 统一出口：接口封装在此导出，用例从 apis 导入
│  └─ module/
│     └─ api.py           # 接口占位文件：按模块封装接口方法
├─ cases/                 # 测试用例
│  ├─ base_case.py        # 用例基类（API 用例通常用不到，保留备用）
│  └─ api/
│     └─ test_xxx.py      # 用例占位文件：按命名约定重命名并填充
└─ tag/                   # 用例标记（可选：tag 机制启用后支持 --tag 筛选）
   └─ api.csv             # 一个模块目录一个 CSV，登记该目录下所有用例
```

## 怎么开发 API 用例

### 1. 封装接口（apis/）
把被测系统的接口按模块封装成方法，一个接口一个方法，返回业务结果给用例断言：

```python
import os
import requests  # 需要先安装：pip install requests

BASE = os.environ.get("JUSTGO_TEST_BASE_URL", "")

def login(username, password):
    resp = requests.post(f"{BASE}/api/login", json={"username": username, "password": password})
    return resp.json()
```

写完后在 `apis/__init__.py` 统一导出（新增模块也这样做）。

### 2. 写用例（cases/api/）
API 用例不需要 page fixture，直接调接口方法 + 断言：

```python
from apis.module import api as module_api

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
