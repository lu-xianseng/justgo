"""屏幕取图后端。

优先使用 mss（快、支持多显示器），未安装则退回 Pillow 的 ImageGrab。
统一返回 numpy BGR 三通道数组（OpenCV 习惯顺序）。
"""

from __future__ import annotations

import ctypes
import os
import threading
from typing import Optional, Tuple

import numpy as np

from just_go._internal.errors import ScreenCaptureError
from just_go._internal.logger import logger

_dpi_ready = False
_dpi_lock = threading.Lock()

try:  # mss 为可选依赖
    import mss  # type: ignore

    _HAS_MSS = True
except Exception:  # pragma: no cover - 环境相关
    mss = None  # type: ignore
    _HAS_MSS = False

try:
    from PIL import ImageGrab

    _HAS_PIL_GRAB = True
except Exception:  # pragma: no cover
    ImageGrab = None  # type: ignore
    _HAS_PIL_GRAB = False

_tls = threading.local()


def enable_dpi_awareness() -> bool:
    """让进程按「物理像素」取屏，避免 125%/150% 缩放导致模板对不上。

    必须在创建任何 GUI 窗口前调用（模块内首次截屏会自动调用一次）。
    """
    global _dpi_ready
    with _dpi_lock:
        if _dpi_ready:
            return True
        if os.name != "nt":
            _dpi_ready = True
            return False
        try:  # Win10 1703+：Per-Monitor V2
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            _dpi_ready = True
            return True
        except Exception:
            pass
        try:  # Win8.1+：Per-Monitor
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            _dpi_ready = True
            return True
        except Exception:
            pass
        try:  # Vista+：System DPI Aware
            ctypes.windll.user32.SetProcessDPIAware()
            _dpi_ready = True
            return True
        except Exception:
            logger.trace("设置进程 DPI 感知失败，若系统缩放非 100% 可能匹配不准")
            return False


def _get_mss():
    inst = getattr(_tls, "mss", None)
    if inst is None:
        inst = mss.mss()  # type: ignore[union-attr]
        _tls.mss = inst
    return inst


def _normalize_region(region) -> Tuple[int, int, int, int]:
    if len(region) != 4:
        raise ValueError(f"region 必须是 (x, y, width, height)，收到：{region!r}")
    x, y, w, h = (int(v) for v in region)
    if w <= 0 or h <= 0:
        raise ValueError(f"region 宽高必须为正数，收到：{region!r}")
    return x, y, w, h


def _virtual_origin() -> Tuple[int, int]:
    """虚拟桌面左上角在屏幕坐标系中的位置（副屏在左侧时可能为负数）。"""
    if os.name == "nt":
        try:
            u = ctypes.windll.user32
            return int(u.GetSystemMetrics(76)), int(u.GetSystemMetrics(77))
        except Exception:
            return 0, 0
    return 0, 0


def grab(region: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
    """截取屏幕画面（只返回像素，不要坐标偏移）。"""
    return grab_with_origin(region)[0]


def grab_with_origin(
    region: Optional[Tuple[int, int, int, int]] = None,
) -> Tuple[np.ndarray, Tuple[int, int]]:
    """截屏，并返回这块画面在屏幕坐标系里的左上角 (left, top)。

    多显示器且副屏位于负坐标一侧时，整屏截图的数组原点并不等于屏幕 (0, 0)，
    匹配出的数组坐标必须加上这个偏移才是真实屏幕坐标。
    """
    enable_dpi_awareness()
    box = _normalize_region(region) if region is not None else None

    if _HAS_MSS:
        sct = _get_mss()
        if box is None:
            monitor = sct.monitors[0]
        else:
            x, y, w, h = box
            monitor = {"left": x, "top": y, "width": w, "height": h}
        shot = np.asarray(sct.grab(monitor))
        origin = (int(monitor.get("left", 0)), int(monitor.get("top", 0)))
        return np.ascontiguousarray(shot[:, :, :3]), origin  # BGRA -> BGR

    if _HAS_PIL_GRAB:
        if box is None:
            img = ImageGrab.grab(all_screens=True)
            origin = _virtual_origin()
        else:
            x, y, w, h = box
            img = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
            origin = (x, y)
        arr = np.asarray(img.convert("RGB"))
        return np.ascontiguousarray(arr[:, :, ::-1]), origin  # RGB -> BGR

    raise ScreenCaptureError("没有可用的截屏后端：请安装 mss（推荐）或 Pillow。")


def screen_size() -> Tuple[int, int]:
    """返回虚拟桌面尺寸 (宽, 高)；多显示器时是所有屏幕拼起来的整体。"""
    enable_dpi_awareness()
    if _HAS_MSS:
        mon = _get_mss().monitors[0]
        return int(mon["width"]), int(mon["height"])
    if _HAS_PIL_GRAB:
        img = ImageGrab.grab(all_screens=True)
        return img.size
    return 0, 0
