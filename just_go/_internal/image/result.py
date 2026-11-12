"""识别结果的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Match:
    """一次成功命中的结果。"""

    path: str          # 实际参与匹配的图片绝对路径
    score: float       # 相似度得分，0~1，1 表示完全一致
    x: int             # 命中区域左上角 x（相对搜索画面左上角）
    y: int             # 命中区域左上角 y
    width: int         # 命中区域宽（即模板宽）
    height: int        # 命中区域高（即模板高）

    @property
    def center(self) -> Tuple[int, int]:
        """命中区域中心点坐标，一般用于鼠标点击。"""
        return self.x + self.width // 2, self.y + self.height // 2

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def box(self) -> Tuple[int, int, int, int]:
        """(x, y, width, height)"""
        return self.x, self.y, self.width, self.height

    def to_tuple(self) -> Tuple[int, int, int, int]:
        return self.box

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "score": round(self.score, 4),
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "center_x": self.center[0],
            "center_y": self.center[1],
        }

    def __str__(self) -> str:
        cx, cy = self.center
        return (
            f"<Match {self.path} score={self.score:.4f} "
            f"box=({self.x},{self.y},{self.width},{self.height}) center=({cx},{cy})>"
        )


@dataclass
class FindResult:
    """find_by_image() 的返回值。

    未命中时对象仍然返回（可用于排查最优得分），但布尔值为 False，
    因此 ``if find_by_image(...):`` 可以直接当判断用。
    """

    found: bool
    match: Optional[Match] = None
    matches: Tuple[Match, ...] = ()     # return_all=True 时的全部命中
    attempts: int = 0                   # 实际尝试次数
    elapsed_ms: float = 0.0
    best_score: float = 0.0             # 所有尝试中的最高相似度
    best_path: Optional[str] = None      # 最高相似度对应的图片
    templates: Tuple[str, ...] = ()      # 参与匹配的图片列表
    source_size: Tuple[int, int] = (0, 0)  # 搜索画面尺寸 (宽, 高)
    origin: Optional[Tuple[int, int]] = None
    # ↑ 搜索画面左上角在屏幕坐标中的位置；None 表示画面来自图片/内存图像，
    #   此时 match 的 x/y 是相对该画面自身的坐标。

    def __bool__(self) -> bool:
        return self.found

    def __len__(self) -> int:
        """命中数量（return_all 时可能大于 1）。"""
        if self.matches:
            return len(self.matches)
        return 1 if self.match else 0

    def __str__(self) -> str:
        if self.found:
            head = f"命中 {self.match!s}"
            if self.matches:
                head = f"命中 {len(self.matches)} 处，最佳 {self.match!s}"
        else:
            head = (
                f"未命中，最高相似度 {self.best_score:.4f}"
                f"（{self.best_path}）"
            )
        return (
            f"<FindResult {head} attempts={self.attempts} "
            f"elapsed={self.elapsed_ms:.1f}ms source={self.source_size[0]}x{self.source_size[1]}>"
        )

    def __repr__(self) -> str:
        return self.__str__()

    def to_dict(self) -> dict:
        return {
            "found": self.found,
            "match": self.match.to_dict() if self.match else None,
            "matches": [m.to_dict() for m in self.matches],
            "attempts": self.attempts,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "best_score": round(self.best_score, 4),
            "best_path": self.best_path,
            "templates": list(self.templates),
            "source_size": list(self.source_size),
            "origin": list(self.origin) if self.origin else None,
        }
