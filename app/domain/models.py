# -*- coding: utf-8 -*-
"""
models.py - 领域实体数据模型
"""
from dataclasses import dataclass, field, asdict
from typing import List, Tuple


@dataclass
class Board:
    id: str
    room_id: str
    length: int
    width: int
    thickness: int = 18
    density_kg_m2: float = 23.0
    name: str = ""
    barcode: str = ""

    def __post_init__(self):
        if not self.barcode:
            self.barcode = self.id
        if self.length < self.width:
            self.length, self.width = self.width, self.length

    @property
    def area_m2(self) -> float:
        return (self.length * self.width) / 1e6

    @property
    def weight_kg(self) -> float:
        return self.area_m2 * self.density_kg_m2

    @property
    def weight_g(self) -> int:
        return int(round(self.weight_kg * 1000))


@dataclass
class PlacedBoard:
    board_id: str
    barcode: str
    room_id: str
    x: int
    y: int
    length: int
    width: int
    thickness: int
    layer: int
    is_rotated: bool
    weight_kg: float
    name: str = ""
    is_scanned: bool = False

    def to_dict(self):
        return asdict(self)


@dataclass
class Package:
    package_id: int
    room_id: str
    layers: int
    boards: List[PlacedBoard] = field(default_factory=list)
    is_oversized_single: bool = False  # 标记单板物理超重大件 (>50kg)

    @property
    def total_weight_kg(self) -> float:
        return sum(b.weight_kg for b in self.boards)

    @property
    def total_weight_g(self) -> int:
        return sum(int(round(b.weight_kg * 1000)) for b in self.boards)

    @property
    def bounding_box(self) -> Tuple[int, int, int]:
        if not self.boards:
            return 0, 0, 0
        max_x = max(b.x + b.length for b in self.boards)
        max_y = max(b.y + b.width for b in self.boards)
        max_h = sum(
            max((b.thickness for b in self.boards if b.layer == l_idx), default=18)
            for l_idx in range(self.layers)
        )
        return max_x, max_y, max_h

    @property
    def space_utilization(self) -> float:
        bx, by, bh = self.bounding_box
        if bx == 0 or by == 0 or bh == 0:
            return 0.0
        boards_vol = sum(b.length * b.width * b.thickness for b in self.boards)
        return boards_vol / (bx * by * bh)

    def to_dict(self):
        bx, by, bh = self.bounding_box
        return {
            "package_id": self.package_id,
            "room_id": self.room_id,
            "layers": self.layers,
            "is_oversized_single": self.is_oversized_single,
            "total_weight_kg": round(self.total_weight_kg, 2),
            "bounding_box": {"length": bx, "width": by, "height": bh},
            "space_utilization": round(self.space_utilization, 4),
            "boards_count": len(self.boards),
            "boards": [b.to_dict() for b in self.boards]
        }