# -*- coding: utf-8 -*-
"""
engine.py - 业务调度总控（房间隔离、长宽比与尺寸聚类分流、多策略择优）

【本版本变更记录】
1. [健壮性修复-历史] 超重大板双朝向校验，避免异常尺寸数据裸奔到断言层崩溃。
2. [优化新增] 评分函数增加"低利用率惩罚项"：原评分只用 avg_util（平均利用率）
   衡量方案好坏，会放任个别包裹利用率极低（内部大量空气层）而不被惩罚，只要
   总包数和平均值好看即可。现改为额外跟踪 min_util（本方案中利用率最低的包），
   低于 config.min_acceptable_util 时按差值线性施加重罚，促使 6 种排序策略
   在竞争时更倾向于避免出现"利用率洼地"包裹，而不是仅优化总数和平均值。
3. [优化新增] summary 中新增 low_utilization_packages 诊断字段，列出最终方案
   中利用率低于阈值的包装编号，便于后续 FastAPI 接口层/前端向仓库人员标记提醒。
"""
import time
from typing import List, Dict, Optional, Tuple
from app.domain.config import PackingConfig
from app.domain.models import Board, PlacedBoard, Package
from app.domain.strategies import True3DPackageBuilder


class BoardOversizeError(ValueError):
    """板材物理尺寸超出设备极限（两种朝向均无法容纳），需人工介入处理。"""
    pass


class FurniturePackingEngine:
    def __init__(self, config: Optional[PackingConfig] = None):
        self.config = config or PackingConfig()

    def pack_boards(self, boards: List[Board]) -> Dict:
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
        low_util_packages: List[int] = []
        for p in all_packages:
            layer_dist[p.layers] = layer_dist.get(p.layers, 0) + 1
            total_util += p.space_utilization
            # 超重独立大板本身没有拼装意义，利用率天然偏低，不纳入低利用率告警
            if not p.is_oversized_single and p.space_utilization < self.config.min_acceptable_util:
                low_util_packages.append(p.package_id)

        avg_util = (total_util / len(all_packages)) if all_packages else 0.0

        return {
            "summary": {
                "total_rooms": len(room_groups),
                "total_boards": len(boards),
                "total_packages": len(all_packages),
                "total_weight_kg": round(sum(b.weight_kg for b in boards), 2),
                "avg_space_utilization": round(avg_util, 4),
                "packages_by_layer": layer_dist,
                "execution_time_ms": round(elapsed_ms, 2),
                "low_utilization_packages": low_util_packages
            },
            "packages": [p.to_dict() for p in all_packages]
        }

    def _pack_single_room(self, room_id: str, boards: List[Board], start_pkg_id: int) -> Tuple[List[Package], int]:
        packages: List[Package] = []
        pkg_id = start_pkg_id

        # 1. 超重单板 (>50kg) 独立打包并打上专用标识
        normal_boards: List[Board] = []
        for b in boards:
            if b.weight_g > self.config.max_weight_g:
                dx, dy, is_rot = self._resolve_oversized_orientation(b)
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

        # 2. 多策略多维排序试探最佳装箱 (长宽比分桶 + 模数聚类 + 面积与重量)
        best_set: Optional[List[Package]] = None
        best_score = float('inf')

        sort_strategies = [
            lambda b: (b.length, b.length * b.width),
            lambda b: (b.length * b.width, b.length),
            lambda b: (b.weight_g, b.length * b.width),
            lambda b: (b.length + b.width, b.length * b.width),
            lambda b: (b.length // 100 * 100, b.width // 50 * 50, b.length * b.width),
            lambda b: (b.length // 200 * 200, b.length * b.width),
        ]

        board_map = {b.id: b for b in normal_boards}

        for strat in sort_strategies:
            unplaced = sorted(normal_boards, key=strat, reverse=True)
            cur_pkgs: List[Package] = []
            cur_pkg_id = pkg_id

            while unplaced:
                # 尝试构建 4 层包 (若剩余板材 >= 4 块 且非单板大重件)
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

                # 尝试构建 2 层包 (若剩余板材 >= 2 块)
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

            # 低利用率惩罚项：找出本方案中利用率最差的包，低于阈值则按差值重罚，
            # 抑制"为少出一个包而放任个别包裹内部大量空气层"的极端方案
            min_util = min((p.space_utilization for p in cur_pkgs), default=1.0)
            low_util_penalty = max(0.0, self.config.min_acceptable_util - min_util) * 2000

            score = len(cur_pkgs) * 1000 + one_layer_count * 150 - avg_util * 400 + low_util_penalty

            if score < best_score:
                best_score = score
                best_set = cur_pkgs

        packages.extend(best_set or [])
        return packages, pkg_id + len(best_set or [])

    def _resolve_oversized_orientation(self, b: Board) -> Tuple[int, int, bool]:
        """
        判定超重单板 (>50kg) 应以哪种朝向摆放进包装外形极限 (max_length x max_width)。
        注意：models.Board.__post_init__ 已保证 b.length >= b.width。

        - 原朝向：占用 (length, width)，要求 length<=max_length 且 width<=max_width
        - 旋转90°：占用 (width, length)，要求 width<=max_length 且 length<=max_width

        两种朝向均无法容纳时，说明该板材物理尺寸超出设备极限，主动抛出业务异常，
        避免带着非法数据继续跑完整个装箱流程、最终在 validator 断言层崩溃。
        """
        fits_normal = b.length <= self.config.max_length and b.width <= self.config.max_width
        fits_rotated = b.width <= self.config.max_length and b.length <= self.config.max_width

        if fits_normal:
            return b.length, b.width, False
        if fits_rotated:
            return b.width, b.length, True

        raise BoardOversizeError(
            f"板材 [{b.barcode}]（{b.name}）尺寸 {b.length}x{b.width}mm 超出设备最大处理规格 "
            f"{self.config.max_length}x{self.config.max_width}mm，两种朝向均无法容纳，"
            f"请人工确认该板材是否可分体加工或需特殊运输方案。"
        )

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