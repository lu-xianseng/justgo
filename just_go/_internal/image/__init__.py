"""图像识别（屏幕找图）：模板匹配 + 取图。
"""

from just_go._internal.settings import IMAGE_PATH

from .actions import find_image, wait_image
from .capture import grab, screen_size

__all__ = ["find_image", "wait_image", "grab", "screen_size", "IMAGE_PATH"]
