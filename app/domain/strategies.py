# -*- coding: utf-8 -*-
"""
strategies.py - 3D 物理多层堆叠策略（外包络收敛、尺寸相似度惩罚、高层满层质检与稀疏层剥离）

【本版本修复记录】
1. [核心Bug修复] finalize_package: 稀疏层剔除时缺少 break，导致某层被剔除后，
   更上一层若恰好达标会被"跳层保留"，但该上层板材在放置时从未针对新的下层
   重新校验过支撑率，存在悬空风险。现修复为：一旦某层被剔除，其上所有层
   全部级联作废，保证保留下来的层永远是从 0 开始连续的。
2. [性能优化] can_fit_board / _try_fit_layer 中原先每次候选都用
   max(...) 全量扫描 self.placed_boards 求外包络 (cur_max_x/cur_max_y)
   及最长单板边 (longest_single_board)，为 O(n) 操作。现改为在 add_board
   时增量维护，取值降为 O(1)。此项为纯性能优化，不改变任何排样结果。
"""
from typing import List, Tuple, Optional
from app.domain.config import PackingConfig
from app.domain.models import Board, PlacedBoard, Package
from app.domain.geometry import MaxRectsLayerPacker


class True3DPackageBuilder:
    def __init__(self, target_layers: int, config: PackingConfig):
        self.target_layers = target_layers
        self.config = config
        self.layer_packers = [MaxRectsLayerPacker(config.max_length, config.max_width) for _ in range(target_layers)]
        self.placed_boards: List[PlacedBoard] = []
        self.boards_per_layer: List[List[PlacedBoard]] = [[] for _ in range(target_layers)]
        self.current_weight_g = 0

        # 增量维护的外包络状态（替代原先对 placed_boards 的全量 max() 扫描）
        self.cur_max_x = 0
        self.cur_max_y = 0
        self.longest_single_board = 0

    def can_fit_board(self, board: Board) -> Optional[Tuple[int, int, int, int, int, bool]]:
        if self.current_weight_g + board.weight_g > self.config.max_weight_g:
            return None

        # 大板独占保护：底层单板 >= 40kg，直接在 Layer 0 平铺，禁止加高层造成空气包裹
        if self.boards_per_layer[0]:
            layer0_max_single = max(b.weight_kg for b in self.boards_per_layer[0])
            if layer0_max_single >= self.config.heavy_board_solo_kg:
                return self._try_fit_layer(0, board)

        best_candidate = None
        min_cost = float('inf')

        # 优先填入当前板数较少的层，促成各层均匀堆叠
        layer_priority = sorted(range(self.target_layers), key=lambda l: (len(self.boards_per_layer[l]), l))

        for l_idx in layer_priority:
            if l_idx > 0 and len(self.boards_per_layer[l_idx - 1]) == 0:
                continue

            fit_res = self._try_fit_layer(l_idx, board)
            if fit_res is not None:
                _, bx, by, p_dx, p_dy, is_rot = fit_res

                # 计算放置后整个包装 2D 外包络的膨胀代价 (Expansion Cost)
                cur_max_x = self.cur_max_x
                cur_max_y = self.cur_max_y
                new_max_x = max(cur_max_x, bx + p_dx)
                new_max_y = max(cur_max_y, by + p_dy)
                expansion_area = (new_max_x * new_max_y) - (cur_max_x * cur_max_y) if cur_max_x > 0 else 0

                # 鼓励高层堆叠以实现多层包装
                layer_bonus = (l_idx + 1) * 30000
                total_cost = expansion_area * 2 - layer_bonus

                if total_cost < min_cost:
                    min_cost = total_cost
                    best_candidate = fit_res

        return best_candidate

    def _try_fit_layer(self, layer_idx: int, board: Board) -> Optional[Tuple[int, int, int, int, int, bool]]:
        packer = self.layer_packers[layer_idx]

        if self.placed_boards:
            cur_max_x = self.cur_max_x
            cur_max_y = self.cur_max_y
            longest_single_board = self.longest_single_board
        else:
            cur_max_x = 0
            cur_max_y = 0
            longest_single_board = max(board.length, board.width)

        candidates = []

        # 1. 原向尝试
        pos1 = packer.find_position_fixed(board.length, board.width)
        if pos1:
            bx, by, _, _ = pos1
            if bx + board.length <= self.config.max_length and by + board.width <= self.config.max_width:
                new_max_x = max(cur_max_x, bx + board.length)
                new_max_y = max(cur_max_y, by + board.width)
                expansion = (new_max_x * new_max_y) - (cur_max_x * cur_max_y) if cur_max_x > 0 else 0

                # 核心防空洞约束：防止小板接在长板后面无谓拉长整个包裹
                excess_length = max(0, (bx + board.length) - max(longest_single_board, board.length))
                length_stretch_penalty = excess_length * 20000

                candidates.append((expansion + length_stretch_penalty, bx, by, board.length, board.width, False))

        # 2. 旋转 90° 尝试
        pos2 = packer.find_position_fixed(board.width, board.length)
        if pos2:
            bx, by, _, _ = pos2
            if bx + board.width <= self.config.max_length and by + board.length <= self.config.max_width:
                new_max_x = max(cur_max_x, bx + board.width)
                new_max_y = max(cur_max_y, by + board.length)
                expansion = (new_max_x * new_max_y) - (cur_max_x * cur_max_y) if cur_max_x > 0 else 0

                excess_length = max(0, (bx + board.width) - max(longest_single_board, board.length))
                length_stretch_penalty = excess_length * 20000

                candidates.append((expansion + length_stretch_penalty, bx, by, board.width, board.length, True))

        if not candidates:
            return None

        candidates.sort(key=lambda c: c[0])
        for cost, bx, by, p_dx, p_dy, is_rot in candidates:
            if layer_idx > 0 and not self._check_support(layer_idx, bx, by, p_dx, p_dy):
                continue
            return layer_idx, bx, by, p_dx, p_dy, is_rot

        return None

    def _check_support(self, target_layer: int, x: int, y: int, dx: int, dy: int) -> bool:
        lower_boards = self.boards_per_layer[target_layer - 1]
        if not lower_boards:
            return False

        overlap_area = 0
        target_area = dx * dy
        for lb in lower_boards:
            ix1 = max(x, lb.x)
            iy1 = max(y, lb.y)
            ix2 = min(x + dx, lb.x + lb.length)
            iy2 = min(y + dy, lb.y + lb.width)
            if ix1 < ix2 and iy1 < iy2:
                overlap_area += (ix2 - ix1) * (iy2 - iy1)

        return (overlap_area / target_area) >= self.config.min_support_ratio

    def add_board(self, board: Board, fit_info: Tuple[int, int, int, int, int, bool]):
        l_idx, bx, by, p_dx, p_dy, is_rot = fit_info
        self.layer_packers[l_idx].place_rect(bx, by, p_dx, p_dy)
        pb = PlacedBoard(
            board_id=board.id,
            barcode=board.barcode,
            room_id=board.room_id,
            x=bx,
            y=by,
            length=p_dx,
            width=p_dy,
            thickness=board.thickness,
            layer=l_idx,
            is_rotated=is_rot,
            weight_kg=board.weight_kg,
            name=board.name
        )
        self.placed_boards.append(pb)
        self.boards_per_layer[l_idx].append(pb)
        self.current_weight_g += board.weight_g

        # 增量更新外包络状态，避免下次候选评估时全量重扫描
        self.cur_max_x = max(self.cur_max_x, bx + p_dx)
        self.cur_max_y = max(self.cur_max_y, by + p_dy)
        self.longest_single_board = max(self.longest_single_board, p_dx, p_dy)

    def finalize_package(self, pkg_id: int, room_id: str) -> Tuple[Optional[Package], List[str]]:
        """
        核心质检：剔除填充不足的稀疏层，杜绝 4 层包因空层产生的空间浪费。

        【修复说明】原实现中，某层因填充率不足被剔除（else 分支）后，循环并未终止，
        会继续检查更上一层——若更上一层恰好达标，会被单独保留，导致保留下来的层
        编号不连续（例如保留了第 0 层和第 2 层，剔除第 1 层）。重新编号压缩后，
        第 2 层的板材会被提升为"新的第 1 层"，直接叠放在第 0 层之上，但这些板材
        在实际放置时，_check_support 校验的是它们与"原第 1 层"的支撑关系，而不是
        与第 0 层的支撑关系——第 0 层与它们之间从未做过支撑校验，存在悬空风险。

        现修复为：层级堆叠必须连续，一旦某层被剔除，其上所有层全部级联作废。
        """
        if not self.placed_boards:
            return None, []

        cur_max_x = self.cur_max_x
        cur_max_y = self.cur_max_y
        pkg_footprint_area = cur_max_x * cur_max_y

        valid_layers = [0]
        rejected_board_ids = []

        for l_idx in range(1, self.target_layers):
            layer_boards = self.boards_per_layer[l_idx]
            if not layer_boards:
                break

            l_area = sum(b.length * b.width for b in layer_boards)
            layer_ok = pkg_footprint_area > 0 and (l_area / pkg_footprint_area) >= self.config.min_layer_fill_ratio

            if layer_ok:
                valid_layers.append(l_idx)
            else:
                # 该层不达标：本层及其上所有层全部级联作废，保证堆叠连续、支撑链完整
                for l2 in range(l_idx, self.target_layers):
                    rejected_board_ids.extend([b.board_id for b in self.boards_per_layer[l2]])
                break

        num_layers = len(valid_layers)

        # 严格消除空层：若目标 4 层但只满了 3 层，强制退回第 3 层板材，固化为紧凑的 2 层包
        if self.target_layers == 4 and num_layers == 3:
            rejected_board_ids.extend([b.board_id for b in self.boards_per_layer[valid_layers[2]]])
            valid_layers = valid_layers[:2]
            num_layers = 2

        kept_boards: List[PlacedBoard] = []
        for new_l_idx, old_l_idx in enumerate(valid_layers):
            for pb in self.boards_per_layer[old_l_idx]:
                pb.layer = new_l_idx
                kept_boards.append(pb)

        final_layers_spec = 4 if num_layers >= 4 else (2 if num_layers >= 2 else 1)

        pkg = Package(
            package_id=pkg_id,
            room_id=room_id,
            layers=final_layers_spec,
            boards=kept_boards
        )
        return pkg, rejected_board_ids