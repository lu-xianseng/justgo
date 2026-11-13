"""模板匹配
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image as PILImage

from just_go._internal.errors import MatchNotFoundError, TemplateNotFoundError
from just_go._internal.logger import logger
from just_go._internal.settings import IMAGE_PATH

from . import capture
from .result import FindResult, Match

__all__ = ["find_by_image", "clear_cache", "MATCH_METHODS", "IMAGE_EXTS"]

#: 自动补全的图片后缀（按顺序尝试）
IMAGE_EXTS: Tuple[str, ...] = (".png", ".jpg", ".jpeg")

#: 可用的匹配算法，均使用归一化形式，得分落在 0~1
MATCH_METHODS: dict[str, int] = {
    "ccoeff": cv2.TM_CCOEFF_NORMED,   # 默认：抗整体亮度偏移，最常用
    "corr": cv2.TM_CCORR_NORMED,      # 直接用像素相关，对纯色块更敏感
    "sqdiff": cv2.TM_SQDIFF_NORMED,   # 差值平方，越接近 0 越像（内部已翻转为 1-score）
}

_LOWER_IS_BETTER = {cv2.TM_SQDIFF_NORMED}
# OpenCV 归一化得分的浮点误差：完全相同的图 TM_CCOEFF_NORMED 也只给 0.9999987，
# 因此比较阈值时留 0.1% 容差，否则 similarity=1（100%）永远不可能命中。
_SCORE_TOL = 1e-3

# 模板图片缓存：{(绝对路径, mtime_ns, size): BGR ndarray}
_template_cache: dict[Tuple[str, int, int], np.ndarray] = {}
_cache_lock = threading.RLock()


class _Template:
    """一个已解析的模板图片。"""

    __slots__ = ("path", "bgr", "gray")

    def __init__(self, path: str, bgr: np.ndarray):
        self.path = path
        self.bgr = bgr
        self.gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr

    @property
    def size(self) -> Tuple[int, int]:
        """(宽, 高)"""
        h, w = self.bgr.shape[:2]
        return w, h


# ---------------------------------------------------------------- 路径与图片


def _load_image_bgr(path: Path, what: str = "可用的图片文件") -> np.ndarray:
    """读取图片为 BGR 三通道数组。

    用 np.fromfile + cv2.imdecode 而不是 cv2.imread，以免 Windows 上中文路径读不到。
    """
    try:
        buf = np.fromfile(str(path), dtype=np.uint8)
    except OSError as exc:
        raise TemplateNotFoundError(str(path), what=what) from exc
    if buf.size == 0:
        raise TemplateNotFoundError(str(path), what=what)
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise TemplateNotFoundError(
            str(path), [f"{path}（文件存在但无法解码，可能不是有效图片）"], what=what
        )
    return _to_bgr(img)


def _to_bgr(img: np.ndarray) -> np.ndarray:
    """把各种通道布局归一化成连续内存的 BGR 三通道。"""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.ndim == 3:
        c = img.shape[2]
        if c == 1:
            return cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR)
        if c == 2:  # 灰度 + alpha
            return cv2.cvtColor(img[:, :, 0], cv2.COLOR_GRAY2BGR)
        if c == 4:  # 丢掉 alpha，只取 BGR
            return np.ascontiguousarray(img[:, :, :3])
        if c == 3:
            return np.ascontiguousarray(img)
    raise ValueError(f"无法识别的图片通道数：{img.shape}")


def _candidate_paths(root: Path) -> list[Path]:
    """按「原样 → 补全 .png/.jpg/.jpeg」的顺序给出候选路径。"""
    cands: list[Path] = [root]
    suffix = root.suffix.lower()
    if suffix in IMAGE_EXTS:
        cands.extend(root.with_suffix(ext) for ext in IMAGE_EXTS)
    else:
        cands.extend(root.with_name(root.name + ext) for ext in IMAGE_EXTS)
    uniq: list[Path] = []
    for c in cands:
        if c not in uniq:
            uniq.append(c)
    return uniq


def _resolve_image_path(
    raw: Any, search_dirs: Sequence[Any] | None = None, what: str = "可用的图片文件"
) -> str:
    """把传入的图片路径解析成真实存在的文件路径（后缀可省略）。"""
    p = Path(os.path.expandvars(os.path.expanduser(str(raw))))
    if p.is_absolute():
        bases: list[Optional[Path]] = [None]
    else:
        # 相对路径优先按 IMAGE_PATH（= 测试项目根）解析，与“模板图路径基于项目根”的
        # 约定一致；旧实现只认 Path.cwd()，IDE/CI 里 cwd ≠ 项目根时找不到模板图。
        bases = [Path(IMAGE_PATH)]
        cwd = Path.cwd()
        if cwd != Path(IMAGE_PATH):
            bases.append(cwd)
        if search_dirs:
            bases.extend(Path(os.path.expanduser(str(d))) for d in search_dirs)

    searched: list[str] = []
    for base in bases:
        root = p if base is None else base / p
        for cand in _candidate_paths(root):
            searched.append(str(cand))
            if cand.is_file():
                return str(cand.resolve())
    raise TemplateNotFoundError(str(raw), searched, what=what)


def _collect_image_paths(images: Sequence[Any], search_dirs: Sequence[Any] | None) -> list[str]:
    """把 find_by_image 收到的参数规整成一个去重后的路径列表。"""
    flat: list[Any] = []
    for item in images:
        if isinstance(item, (str, os.PathLike)):
            flat.append(item)
        elif isinstance(item, (list, tuple, set, frozenset)):
            flat.extend(item)
        elif isinstance(item, PILImage.Image):
            raise TypeError("图片路径参数不支持直接传 PIL.Image，请改传文件路径或使用 source 参数")
        elif isinstance(item, np.ndarray):
            raise TypeError("图片路径参数不支持直接传 ndarray，请改传文件路径或使用 source 参数")
        else:
            raise TypeError(f"不支持的图片参数类型：{type(item)!r}（{item!r}）")

    if not flat:
        raise ValueError("find_by_image() 至少需要传入 1 个图片路径")

    paths: list[str] = []
    for raw in flat:
        resolved = _resolve_image_path(raw, search_dirs, what="可用的模板图片")
        if resolved not in paths:
            paths.append(resolved)
    return paths


def _load_template(path: str) -> _Template:
    """带缓存地加载模板（文件被替换后会按 mtime/size 自动失效）。"""
    try:
        st = os.stat(path)
    except OSError as exc:
        # 模板在解析后被删除/占用：归入框架的 TemplateNotFoundError 体系，
        # 而不是把裸 OSError 抛给调用方
        raise TemplateNotFoundError(
            path, [f"{path}（状态读取失败：{exc}）"], what="可用的模板图片"
        ) from exc
    key = (path, st.st_mtime_ns, st.st_size)
    with _cache_lock:
        cached = _template_cache.get(key)
    if cached is None:
        cached = _load_image_bgr(Path(path))
        with _cache_lock:
            _template_cache[key] = cached
    return _Template(path, cached)


def clear_cache() -> None:
    """清空模板图片缓存（一般不需要手动调用）。"""
    with _cache_lock:
        _template_cache.clear()


# ---------------------------------------------------------------- 搜索画面


def _as_frame(value: Any) -> np.ndarray:
    """把 source 支持的各种形态统一成 BGR ndarray。"""
    if isinstance(value, np.ndarray):
        if value.dtype != np.uint8:
            logger.warning("source 图像 dtype={}，已转换为 uint8", value.dtype)
            value = np.clip(value, 0, 255).astype(np.uint8)
        return _to_bgr(value)
    if isinstance(value, PILImage.Image):
        return np.ascontiguousarray(np.asarray(value.convert("RGB"))[:, :, ::-1])
    if isinstance(value, (str, os.PathLike)):
        what = "可用的 source 画面图片"
        return _load_image_bgr(
            Path(_resolve_image_path(value, [IMAGE_PATH], what=what)), what=what
        )
    raise TypeError(f"source 不支持的类型：{type(value)!r}")


def _resolve_frame(source: Any) -> Tuple[np.ndarray, Optional[Tuple[int, int]]]:
    """取得本次要搜索的画面，以及该画面左上角在屏幕坐标里的位置。

    返回 origin=None 表示画面不是来自屏幕（图片文件 / 内存图像 / 自定义取图），
    此时命中的坐标是相对该画面自身的坐标。
    """
    if source is None:
        return capture.grab_with_origin()
    if isinstance(source, (tuple, list)) and len(source) == 4:
        x, y, w, h = (int(v) for v in source)
        return capture.grab_with_origin((x, y, w, h))
    if callable(source):
        produced = source()
        if produced is None:
            raise TypeError("source 可调用对象返回了 None")
        return _as_frame(produced), None
    return _as_frame(source), None


# ---------------------------------------------------------------- 匹配计算


def _normalize_similarity(value: Any) -> float:
    """允许传 0~1 的小数，也允许传 0~100 的百分数（90 视作 90%）。"""
    try:
        s = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"similarity 必须是数字，收到：{value!r}") from exc
    if 1.0 < s <= 100.0:
        s /= 100.0
    elif s > 100.0:
        raise ValueError(f"similarity 超出范围（0~1 或 0~100），收到：{value!r}")
    return max(0.0, min(1.0, s))


def _score_map(haystack: np.ndarray, template: np.ndarray, method_flag: int) -> np.ndarray:
    """返回统一语义的得分矩阵：越大越像，范围 0~1。"""
    res = cv2.matchTemplate(haystack, template, method_flag)
    if method_flag in _LOWER_IS_BETTER:
        res = 1.0 - res
    return res


def _best_of(res: np.ndarray) -> Tuple[float, Tuple[int, int]]:
    # 注意 cv2.minMaxLoc 的返回顺序：(minVal, maxVal, minLoc, maxLoc)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    score = float(min(1.0, max(0.0, max_val)))
    if 1.0 - score < _SCORE_TOL:  # 浮点噪声归一到 1.0，便于展示与判断
        score = 1.0
    return score, (int(max_loc[0]), int(max_loc[1]))


def _collect_matches(
    res: np.ndarray,
    path: str,
    size: Tuple[int, int],
    threshold: float,
    offset: Tuple[int, int] = (0, 0),
) -> Tuple[Match, ...]:
    """从得分矩阵里取出所有达标位置，并做简单的重叠去重（NMS）。"""
    tw, th = size
    ox, oy = offset
    ys, xs = np.where(res >= threshold - _SCORE_TOL)
    if len(xs) == 0:
        return ()
    scores = res[ys, xs]
    order = np.argsort(-scores)
    picked: list[Match] = []
    for idx in order:
        x, y, score = int(xs[idx]) + ox, int(ys[idx]) + oy, float(scores[idx])
        for m in picked:
            if abs(x - m.x) < tw and abs(y - m.y) < th:
                break  # 与已选位置重叠，丢弃
        else:
            picked.append(
                Match(path=path, score=min(1.0, max(0.0, score)), x=x, y=y, width=tw, height=th)
            )
    return tuple(picked)


# ---------------------------------------------------------------- 对外接口


def find_by_image(
    *images: Any,
    similarity: float = 1.0,
    retries: int = 0,
    retry_interval: int = 1000,
    grayscale: bool = True,
    source: Any = None,
    return_all: bool = False,
    required: bool = False,
    method: str = "ccoeff",
    search_dirs: Sequence[Any] | None = None,
) -> FindResult:
    """在当前屏幕（或指定画面）中查找目标图片，返回命中位置。

    :param images: 1 个或多个图片路径。可以写成 ``find_by_image("a.png")``、
        ``find_by_image("a", "b.jpg")``（"a" 会自动补 .png/.jpg/.jpeg）或
        ``find_by_image(["a.png", "b.png"])``。多个图片之间是「或」语义：
        命中的是第 1 张满足相似度的图；同一次尝试里若多张都命中，取分数最高的那张。
    :param similarity: 相似度阈值，默认 1.0 即 100%。也接受百分数写法（90 表示 90%）。
    :param retries: 重试次数，默认 0（即只尝试 1 次）；每一轮都会重新取图。
    :param retry_interval: 重试间隔（毫秒），默认 1000。
    :param grayscale: 是否转灰度后匹配，默认 True。灰度更快、对颜色轻微差异更宽容。
    :param source: 搜索画面来源，默认 None = 全屏（含多显示器）。
        也可传：截图文件路径 / PIL.Image / numpy 图像 / (x, y, w, h) 屏幕区域 /
        无参可调用对象（每轮尝试前都会调用一次，便于自定义取图）。
    :param return_all: True 时把该模板所有达标位置放进 ``matches``。
    :param required: True 时未命中直接抛 ``MatchNotFoundError``，适合断言语义。
    :param method: 匹配算法，``ccoeff``（默认）/``corr``/``sqdiff``。
    :param search_dirs: 相对路径的额外搜索目录（默认从当前工作目录找）。

    :return: ``FindResult``，未命中也可用（``bool(result)`` 为 False，
        并从 ``best_score``/``best_path`` 看到最接近的结果）。
    """
    tpl_paths = _collect_image_paths(images, search_dirs)
    threshold = _normalize_similarity(similarity)

    method_key = str(method).lower()
    if method_key not in MATCH_METHODS:
        raise ValueError(
            f"method 不支持：{method!r}，可选：{sorted(MATCH_METHODS)}"
        )
    method_flag = MATCH_METHODS[method_key]

    attempts_total = max(0, int(retries)) + 1
    interval = max(0.0, float(retry_interval)) / 1000.0

    started = time.perf_counter()
    best_score = 0.0
    best_path: Optional[str] = None
    source_size = (0, 0)
    match: Optional[Match] = None
    matches: Tuple[Match, ...] = ()
    attempt = 0
    origin: Optional[Tuple[int, int]] = None

    for attempt in range(1, attempts_total + 1):
        frame, origin = _resolve_frame(source)
        if frame.size == 0:
            raise ValueError("搜索画面为空（宽或高为 0），请检查 source/region")
        fh, fw = frame.shape[:2]
        source_size = (fw, fh)
        haystack = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if grayscale else frame

        hit: Optional[Tuple[float, _Template, Tuple[int, int], np.ndarray]] = None

        for path in tpl_paths:
            tpl = _load_template(path)
            needle = tpl.gray if grayscale else tpl.bgr
            th, tw = needle.shape[:2]

            if th > fh or tw > fw:
                logger.trace(
                    "模板 {} 尺寸 {}x{} 大于搜索画面 {}x{}，跳过本轮",
                    path, tw, th, fw, fh,
                )
                continue

            res = _score_map(haystack, needle, method_flag)
            score, loc = _best_of(res)

            if best_path is None or score > best_score:
                best_score, best_path = score, path

            if score >= threshold - _SCORE_TOL:
                # 同轮多张命中时，只保留分数最高的那张
                if hit is None or score > hit[0]:
                    hit = (score, tpl, loc, res)

        if hit is not None:
            score, tpl, loc, res = hit
            tw, th = tpl.size
            ox, oy = origin if origin else (0, 0)
            match = Match(
                path=tpl.path, score=score, x=loc[0] + ox, y=loc[1] + oy, width=tw, height=th
            )
            if return_all:
                matches = _collect_matches(res, tpl.path, (tw, th), threshold, (ox, oy))
                if not matches:
                    matches = (match,)
            logger.trace("命中 {}（attempt={}）", match, attempt)
            break

        logger.trace(
            "第 {}/{} 次未命中，最高相似度 {:.4f}（{}），阈值 {:.4f}",
            attempt, attempts_total, best_score, best_path, threshold,
        )
        if attempt < attempts_total and interval > 0:
            time.sleep(interval)

    elapsed_ms = (time.perf_counter() - started) * 1000.0

    result = FindResult(
        found=match is not None,
        match=match,
        matches=matches,
        attempts=attempt,
        elapsed_ms=elapsed_ms,
        best_score=best_score,
        best_path=best_path,
        templates=tuple(tpl_paths),
        source_size=source_size,
        origin=origin,
    )

    if not result.found and required:
        raise MatchNotFoundError(
            f"未找到目标图片，已尝试 {attempt} 次、共 {len(tpl_paths)} 张模板，"
            f"最高相似度 {best_score:.4f}（{best_path}），阈值 {threshold:.4f}，"
            f"搜索画面 {source_size[0]}x{source_size[1]}"
        )
    return result
