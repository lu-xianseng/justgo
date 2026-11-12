"""图像识别的高层接口：找图与等待。

底层模板匹配见 finder.py，这里补上框架侧的两件事：

- 模板图相对路径基于测试项目根解析（settings.IMAGE_PATH 就是项目根，目录名自己拼）
- 动作日志走框架 logger，自动带当前用例标识

断言与点击不在这里实现：断言交给 pytest 的 assert（``assert find_image(...)``），
输入与报告附件由调用方按需组合。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Sequence

from just_go._internal.logger import logger
from just_go._internal.settings import IMAGE_PATH

from .finder import find_by_image
from .result import FindResult

__all__ = ["find_image", "wait_image", "IMAGE_PATH"]


def _describe(images: Sequence[Any]) -> str:
    """把模板参数压成一句简短描述，用于日志。"""
    parts: list[str] = []
    for item in images:
        parts.append(Path(str(item)).name if isinstance(item, (str, os.PathLike)) else str(item))
    return " / ".join(parts) if parts else "?"


def _search_dirs(search_dirs: Optional[Sequence[Any]]) -> list:
    """模板相对路径的解析根：调用方显式指定优先，否则用测试项目根目录。"""
    return [IMAGE_PATH] if search_dirs is None else list(search_dirs)


def _poll(
    images: Sequence[Any],
    similarity: float,
    timeout: float,
    interval: float,
    **kwargs: Any,
) -> FindResult:
    """在 timeout 秒内反复找图（interval 为两轮之间的间隔，单位秒）。"""
    interval = max(0.0, float(interval))
    attempts = max(1, int(float(timeout) / interval) + 1) if interval > 0 else 1
    return find_by_image(
        *images,
        similarity=similarity,
        retries=attempts - 1,
        retry_interval=int(interval * 1000),
        **kwargs,
    )


def find_image(
    *images: Any,
    similarity: float = 1.0,
    retries: int = 0,
    retry_interval: int = 1000,
    grayscale: bool = True,
    source: Any = None,
    return_all: bool = False,
    required: bool = False,
    method: str = "ccoeff",
    search_dirs: Optional[Sequence[Any]] = None,
) -> FindResult:
    """在当前屏幕（或指定画面）里找图。

    模板相对路径基于测试项目根解析（settings.IMAGE_PATH = 项目根，
    例如传 "images/btn" 或 "assets/img/btn"）。

    参数：
        images          1 个或多个模板图路径。可写 find_image("a.png")、
                        find_image("a", "b")（自动补 .png/.jpg/.jpeg）、
                        find_image(["a.png", "b.png"])。多个之间是「或」语义：
                        命中的是第 1 张满足相似度的图，同轮多张命中时取分数最高的那张。
        similarity      相似度阈值，默认 1.0（100%）；也接受百分数写法（90 表示 90%）。
        retries         重试次数，默认 0（即只尝试 1 次）；每一轮都会重新取图。
        retry_interval  重试间隔（毫秒），默认 1000。
        grayscale       是否转灰度后匹配，默认 True。灰度更快、对颜色轻微差异更宽容。
        source          搜索画面，默认 None = 全屏（含多显示器）。也可传
                        (x, y, w, h) 屏幕区域（明显更快）、截图文件路径、
                        PIL.Image、numpy 图像、无参可调用对象（每轮尝试前调用一次）。
                        传图片或内存图像时，命中坐标是图内坐标，不再是屏幕坐标。
        return_all      True 时把该模板所有达标位置放进 FindResult.matches。
        required        True 时未命中抛 MatchNotFoundError，适合断言语义。
        method          匹配算法：ccoeff（默认，抗整体亮度偏移）、
                        corr（直接用像素相关，对纯色块更敏感）、
                        sqdiff（差值平方，内部已翻转为 1-score）。
        search_dirs     相对路径的搜索目录，默认 [IMAGE_PATH]。

    返回 FindResult。未命中也能用：bool(result) 为 False，
    可从 best_score / best_path 看到最接近的结果。
    """
    result = find_by_image(
        *images,
        similarity=similarity,
        retries=retries,
        retry_interval=retry_interval,
        grayscale=grayscale,
        source=source,
        return_all=return_all,
        required=required,
        method=method,
        search_dirs=_search_dirs(search_dirs),
    )
    label = _describe(images)
    if result.found:
        logger.info(
            f"图像命中: {label} 相似度 {result.match.score:.4f} 中心 {result.match.center}"
        )
    else:
        logger.info(f"图像未命中: {label} 最高相似度 {result.best_score:.4f}")
    return result


def wait_image(
    *images: Any,
    similarity: float = 1.0,
    timeout: float = 10,
    interval: float = 0.5,
    grayscale: bool = True,
    source: Any = None,
    method: str = "ccoeff",
    search_dirs: Optional[Sequence[Any]] = None,
) -> FindResult:
    """在 timeout 秒内反复找图，命中即返回；超时返回 found=False 的结果（不抛异常）。

    参数：
        images      同 find_image：1 个或多个模板图路径，可省略 .png/.jpg/.jpeg
                    后缀，多个之间是「或」语义。
        similarity  相似度阈值，默认 1.0（100%）；也接受百分数写法（90 表示 90%）。
        timeout     最长等待秒数，默认 10。实际尝试次数由 timeout / interval 推算，
                    至少 1 次。
        interval    两轮尝试之间的间隔秒数，默认 0.5；传 0 表示只尝试 1 次。
        grayscale   是否转灰度后匹配，默认 True。
        source      搜索画面，默认 None = 全屏（含多显示器）。也可传 (x, y, w, h)
                    屏幕区域、截图文件路径、PIL.Image、numpy 图像、无参可调用对象。
        method      匹配算法：ccoeff（默认）、corr、sqdiff。
        search_dirs 相对路径的搜索目录，默认 [IMAGE_PATH]。

    返回 FindResult；超时同样返回对象（found 为 False，attempts 是实际尝试次数，
    best_score 是等待期间的最高分）。要「超时就抛异常」用
    find_image(..., required=True) 或自己判断后 assert。
    """
    result = _poll(
        images,
        similarity,
        timeout,
        interval,
        grayscale=grayscale,
        source=source,
        method=method,
        search_dirs=_search_dirs(search_dirs),
    )
    label = _describe(images)
    if result.found:
        logger.info(f"图像可见: {label} 相似度 {result.match.score:.4f}")
    else:
        logger.info(f"图像等待超时: {label} 最高相似度 {result.best_score:.4f}")
    return result
