# -*- coding: utf-8 -*-
"""
config.py - 打包配置与工程参数

【本版本变更记录】
1. [优化新增] min_acceptable_util：单包最低可接受空间利用率阈值。
   用于 engine.py 评分函数中的"低利用率惩罚项"，抑制"为了少出一个包而
   放任个别包裹利用率过低（内部大量空气层）"的极端方案。
"""
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class PackingConfig:
    max_length: int = 2800              # 最大长度 (mm)
    max_width: int = 1220               # 最大宽度 (mm)
    max_package_weight_kg: float = 50.0 # 最大单包重量 (kg)
    allowed_layers: Tuple[int, ...] = (1, 2, 4) # 允许的包装规格层数
    default_thickness: int = 18         # 默认板厚 (mm)
    default_density: float = 23.0       # 默认密度 (kg/m²)
    min_support_ratio: float = 0.5      # 下层实体最小支撑率 (防悬空)
    min_layer_fill_ratio: float = 0.40  # 上层相对包围盒的最小填充率 (防空洞)
    heavy_board_solo_kg: float = 40.0   # 底层单板达此重量时直接锁为单层包 (防空气层)
    min_acceptable_util: float = 0.70   # 单包最低可接受空间利用率 (低于此值触发评分惩罚)

    @property
    def max_weight_g(self) -> int:
        return int(round(self.max_package_weight_kg * 1000))