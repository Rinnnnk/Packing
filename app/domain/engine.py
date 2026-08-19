# -*- coding: utf-8 -*-
"""
engine.py - 业务调度总控
优化特性：多维模数分桶排序策略池、多目标打分收敛、双向超界校验与早停剪枝
"""
import math
import time
from typing import List, Dict, Optional, Tuple
from app.domain.config import PackingConfig
from app.domain.models import Board, PlacedBoard, Package
from app.domain.strategies import True3DPackageBuilder


class FurniturePackingEngine:
    def __init__(self, config: Optional[PackingConfig] = None):
        self.config = config or PackingConfig()

    def pack_boards(self, boards: List[Board]) -> Dict:
        """主入口：按房间强隔离分流打包并输出完整统计摘要"""
        start_t = time.time()
        room_groups: Dict[str, List[Board]] = {}
        for b in boards:
            room_groups.setdefault(b.room_id, []).append(b)

        all_packages: List[Package] = []
        pkg_id_seq = 1

        for room_id, r_boards in sorted(room_groups.items()):
            room_pkgs, pkg_id_seq = self._pack_single_room(room_id, r_boards, pkg_id_seq)
            all_packages.extend(room_pkgs)

        elapsed_ms = (time.time() - start_t) * 1000.0

        layer_dist = {1: 0, 2: 0, 4: 0}
        total_util = 0.0
        for p in all_packages:
            layer_dist[p.layers] = layer_dist.get(p.layers, 0) + 1
            total_util += p.space_utilization

        avg_util = (total_util / len(all_packages)) if all_packages else 0.0

        return {
            "summary": {
                "total_rooms": len(room_groups),
                "total_boards": len(boards),
                "total_packages": len(all_packages),
                "total_weight_kg": round(sum(b.weight_kg for b in boards), 2),
                "avg_space_utilization": round(avg_util, 4),
                "packages_by_layer": layer_dist,
                "execution_time_ms": round(elapsed_ms, 2)
            },
            "packages": [p.to_dict() for p in all_packages]
        }

    def _pack_single_room(self, room_id: str, boards: List[Board], start_pkg_id: int) -> Tuple[List[Package], int]:
        """单房间核心打包逻辑"""
        packages: List[Package] = []
        pkg_id = start_pkg_id

        # 1. 物理设备极限校验与超重大板 (>50kg) 独立打包
        normal_boards: List[Board] = []
        for b in boards:
            fit_orig = (b.length <= self.config.max_length and b.width <= self.config.max_width)
            fit_rot = (b.width <= self.config.max_length and b.length <= self.config.max_width)
            if not (fit_orig or fit_rot):
                raise ValueError(
                    f"板件 [{b.id}-{b.name}] 尺寸 ({b.length}x{b.width}mm) 超过设备极限 ({self.config.max_length}x{self.config.max_width}mm)"
                )

            if b.weight_g > self.config.max_weight_g:
                is_rot = False
                dx, dy = b.length, b.width
                if not fit_orig and fit_rot:
                    dx, dy, is_rot = b.width, b.length, True

                pb = PlacedBoard(
                    board_id=b.id, barcode=b.barcode, room_id=room_id, x=0, y=0,
                    length=dx, width=dy, thickness=b.thickness, layer=0,
                    is_rotated=is_rot, weight_kg=b.weight_kg, name=b.name
                )
                packages.append(Package(package_id=pkg_id, room_id=room_id, layers=1, boards=[pb], is_oversized_single=True))
                pkg_id += 1
            else:
                normal_boards.append(b)

        if not normal_boards:
            return packages, pkg_id

        room_total_weight_kg = sum(b.weight_kg for b in normal_boards)
        theoretical_min_pkgs = math.ceil(room_total_weight_kg / self.config.max_package_weight_kg)

        best_set: Optional[List[Package]] = None
        best_score = float('inf')

        # 2. 多维启发式排序策略池 (解决长短混拼与尺寸失配)
        sort_strategies = [
            # 策略 1: 长度模数(200mm) + 宽度模数(100mm) + 面积 (模数优先)
            lambda b: (b.length // 200 * 200, b.width // 100 * 100, b.length * b.width),
            # 策略 2: 长宽比>=3.5 窄条与宽板分流聚类 + 长度优先
            lambda b: ((b.length / max(1, b.width) >= 3.5), b.length // 150 * 150, b.length * b.width),
            # 策略 3: 长度绝对优先 + 面积
            lambda b: (b.length, b.length * b.width),
            # 策略 4: 面积优先 + 长度
            lambda b: (b.length * b.width, b.length),
            # 策略 5: 单板重量优先 + 面积 (逼近 50kg 背包)
            lambda b: (b.weight_g, b.length * b.width),
            # 策略 6: 周长优先 + 面积
            lambda b: (b.length + b.width, b.length * b.width),
            # 策略 7: 细粒度模数 (100mm x 50mm)
            lambda b: (b.length // 100 * 100, b.width // 50 * 50, b.length * b.width),
        ]

        board_map = {b.id: b for b in normal_boards}

        for strat in sort_strategies:
            unplaced = sorted(normal_boards, key=strat, reverse=True)
            cur_pkgs: List[Package] = []
            cur_pkg_id = pkg_id

            while unplaced:
                # 尝试 4 层包 (若剩余板件 >= 4 且无单板大重件)
                if len(unplaced) >= 4 and unplaced[0].weight_kg < self.config.heavy_board_solo_kg:
                    builder4 = True3DPackageBuilder(4, self.config)
                    placed_b, rem_b = self._fill_builder(builder4, unplaced)
                    pkg, rejected_ids = builder4.finalize_package(cur_pkg_id, room_id)

                    if pkg and pkg.layers == 4:
                        cur_pkgs.append(pkg)
                        cur_pkg_id += 1
                        unplaced = rem_b + [board_map[bid] for bid in rejected_ids]
                        unplaced.sort(key=strat, reverse=True)
                        continue

                # 尝试 2 层包 (若剩余板件 >= 2)
                if len(unplaced) >= 2:
                    builder2 = True3DPackageBuilder(2, self.config)
                    placed_b, rem_b = self._fill_builder(builder2, unplaced)
                    pkg, rejected_ids = builder2.finalize_package(cur_pkg_id, room_id)

                    if pkg and (pkg.layers == 2 or len(rem_b) == 0):
                        cur_pkgs.append(pkg)
                        cur_pkg_id += 1
                        unplaced = rem_b + [board_map[bid] for bid in rejected_ids]
                        unplaced.sort(key=strat, reverse=True)
                        continue

                # 1 层残料收尾
                builder1 = True3DPackageBuilder(1, self.config)
                placed_b, rem_b = self._fill_builder(builder1, unplaced)
                pkg, _ = builder1.finalize_package(cur_pkg_id, room_id)
                if pkg:
                    cur_pkgs.append(pkg)
                    cur_pkg_id += 1
                unplaced = rem_b

            one_layer_count = sum(1 for p in cur_pkgs if p.layers == 1 and not p.is_oversized_single)
            avg_util = sum(p.space_utilization for p in cur_pkgs) / len(cur_pkgs) if cur_pkgs else 0
            
            # 多目标打分：总包数少 > 消除1层散包 > 提高空间利用率
            score = len(cur_pkgs) * 1000 + one_layer_count * 250 - avg_util * 600

            if score < best_score:
                best_score = score
                best_set = cur_pkgs

            # 达到理论极限且无散包时早停
            if len(cur_pkgs) == theoretical_min_pkgs and one_layer_count == 0 and avg_util >= 0.85:
                best_set = cur_pkgs
                break

        packages.extend(best_set or [])
        return packages, pkg_id + len(best_set or [])

    @staticmethod
    def _fill_builder(builder: True3DPackageBuilder, boards: List[Board]) -> Tuple[List[Board], List[Board]]:
        placed, rem = [], []
        for b in boards:
            fit = builder.can_fit_board(b)
            if fit is not None:
                builder.add_board(b, fit)
                placed.append(b)
            else:
                rem.append(b)
        return placed, rem