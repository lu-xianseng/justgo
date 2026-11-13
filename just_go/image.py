"""图像识别：屏幕找图与等待（可选依赖）。

安装：
    pipenv install "just-go[image]"

对外函数（完整参数说明见 help(find_image) / help(wait_image)）：

    find_image(*images, similarity=1.0, retries=0, retry_interval=1000,
               grayscale=True, source=None, return_all=False, required=False,
               method="ccoeff", search_dirs=None) -> FindResult
    wait_image(*images, similarity=1.0, timeout=10, interval=0.5,
               grayscale=True, source=None, method="ccoeff",
               search_dirs=None) -> FindResult
    grab(region=None) -> numpy.ndarray          # 当前屏幕画面，BGR 三通道
    screen_size() -> (width, height)

用法：
    from just_go.image import find_image, wait_image, grab, screen_size

    r = find_image("images/login_btn")          # 后缀可省略；相对路径基于项目根
    if r:                                       # FindResult 可直接当布尔用
        x, y = r.match.center                   # 真实屏幕坐标（已含多显示器偏移）
        print(r.match.score)                    # 相似度 0~1

    r = wait_image("success_tip", timeout=10)   # 轮询直到出现
    if not r:
        print(r.best_score, r.best_path)        # 最接近的一次，便于排查

    assert find_image("status_bar", required=True)   # 找不到时抛 MatchNotFoundError

返回对象（未命中同样有值，不会返回 None）：
    FindResult.found / match / matches / attempts / best_score / best_path / origin
    Match.x / y / center / width / height / score

关键参数：
    source  None=全屏；也可传 (x, y, w, h) 屏幕区域、截图文件路径、PIL.Image、
            numpy 图像、无参可调用对象。传图片或内存图像时命中坐标是图内坐标。
    method  ccoeff（默认，抗整体亮度偏移）/ corr（纯色块更敏感）/ sqdiff（差值平方）
    similarity  1.0 表示 100%，也接受百分数写法（90 表示 90%）


未安装可选依赖时 import just_go.image 不会失败，
只有真正取用其中符号时才抛带安装指引的 SoftwareNotInstallError。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from just_go._internal.errors import SoftwareNotInstallError
from just_go._internal.settings import IMAGE_PATH  # 不依赖 opencv，未装可选依赖时也能读

if TYPE_CHECKING:  # 仅用于 IDE 补全与静态检查
    from just_go._internal.image import (  # noqa: F401
        find_image,
        grab,
        screen_size,
        wait_image,
    )

__all__ = [
    "find_image",
    "wait_image",
    "grab",
    "screen_size",
    "IMAGE_PATH",
]

_INSTALL_HINT = 'pipenv install "just-go[image]"'


def __getattr__(name: str) -> Any:
    """惰性取实现模块的符号，缺依赖时给出带安装命令的框架异常。"""
    if name not in __all__:
        raise AttributeError(f"module 'just_go.image' has no attribute {name!r}")
    try:
        from just_go._internal import image as _impl
    except ImportError as exc:
        raise SoftwareNotInstallError(
            "图像识别依赖（numpy / opencv-python-headless）", _INSTALL_HINT
        ) from exc
    return getattr(_impl, name)
