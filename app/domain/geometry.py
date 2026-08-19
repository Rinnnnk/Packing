# -*- coding: utf-8 -*-
"""
geometry.py - 二维最大矩形空间排样核心 (MaxRects BSSF)
"""
from typing import List, Tuple, Optional


class Rect:
    __slots__ = ['x', 'y', 'w', 'h']

    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w = w
        self.h = h


class MaxRectsLayerPacker:
    """二维最大矩形排样器"""

    def __init__(self, width: int, height: int):
        self.bin_w = width
        self.bin_h = height
        self.free_rects: List[Rect] = [Rect(0, 0, width, height)]

    def find_position_fixed(self, w: int, h: int) -> Optional[Tuple[int, int, int, int]]:
        """在固定尺寸 (w, h) 下寻找最佳位置 (Best Short Side Fit)"""
        best_x = 0
        best_y = 0
        best_short = float('inf')
        best_long = float('inf')
        found = False

        for free in self.free_rects:
            if free.w >= w and free.h >= h:
                short_side = min(free.w - w, free.h - h)
                long_side = max(free.w - w, free.h - h)
                if short_side < best_short or (short_side == best_short and long_side < best_long):
                    best_x = free.x
                    best_y = free.y
                    best_short = short_side
                    best_long = long_side
                    found = True

        if not found:
            return None
        return best_x, best_y, best_short, best_long

    def place_rect(self, x: int, y: int, w: int, h: int):
        placed = Rect(x, y, w, h)
        new_free = []
        for free in self.free_rects:
            if not self._is_intersect(free, placed):
                new_free.append(free)
                continue
            if free.x < placed.x + placed.w and free.x + free.w > placed.x:
                if placed.y > free.y and placed.y < free.y + free.h:
                    new_free.append(Rect(free.x, free.y, free.w, placed.y - free.y))
                if placed.y + placed.h < free.y + free.h:
                    new_free.append(Rect(free.x, placed.y + placed.h, free.w, free.y + free.h - (placed.y + placed.h)))
            if free.y < placed.y + placed.h and free.y + free.h > placed.y:
                if placed.x > free.x and placed.x < free.x + free.w:
                    new_free.append(Rect(free.x, free.y, placed.x - free.x, free.h))
                if placed.x + placed.w < free.x + free.w:
                    new_free.append(Rect(placed.x + placed.w, free.y, free.x + free.w - (placed.x + placed.w), free.h))

        self.free_rects = self._prune(new_free)

    @staticmethod
    def _is_intersect(r1: Rect, r2: Rect) -> bool:
        return not (r1.x >= r2.x + r2.w or r1.x + r1.w <= r2.x or
                    r1.y >= r2.y + r2.h or r1.y + r1.h <= r2.y)

    @staticmethod
    def _prune(rects: List[Rect]) -> List[Rect]:
        pruned = []
        for i, r1 in enumerate(rects):
            is_contained = False
            for j, r2 in enumerate(rects):
                if i != j and r2.x <= r1.x and r2.y <= r1.y and \
                   r2.x + r2.w >= r1.x + r1.w and r2.y + r2.h >= r1.y + r1.h:
                    is_contained = True
                    break
            if not is_contained:
                pruned.append(r1)
        return pruned