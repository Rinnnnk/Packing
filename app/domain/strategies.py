# -*- coding: utf-8 -*-
"""
strategies.py - 3D 物理多层堆叠策略
优化特性：基准层轮廓锚定、同层长度模数惩罚、边界膨胀截断、防悬空与级联熔断
"""
from typing import List, Tuple, Optional
from app.domain.config import PackingConfig
from app.domain.models import Board, PlacedBoard, Package
from app.domain.geometry import MaxRectsLayerPacker


class True3DPackageBuilder:
    def __init__(self, target_layers: int, config: PackingConfig):
        self.target_layers = target_layers
        self.config = config
        self.layer_packers = [
            MaxRectsLayerPacker(config.max_length, config.max_width) 
            for _ in range(target_layers)
        ]
        self.placed_boards: List[PlacedBoard] = []
        self.boards_per_layer: List[List[PlacedBoard]] = [[] for _ in range(target_layers)]
        self.current_weight_g = 0
        
        # 增量外包络与基准层轮廓状态 (O(1) 更新)
        self.cur_max_x = 0
        self.cur_max_y = 0
        self.layer0_max_x = 0
        self.layer0_max_y = 0
        self.longest_single_board = 0

    def can_fit_board(self, board: Board) -> Optional[Tuple[int, int, int, int, int, bool]]:
        """探测板件最佳放入层与坐标落点，返回 (layer_idx, x, y, dx, dy, is_rotated)"""
        if self.current_weight_g + board.weight_g > self.config.max_weight_g:
            return None

        # 大板独占保护：底层单板 >= 40kg 直接锁定在 Layer 0 平铺，禁止加高
        if self.boards_per_layer[0]:
            layer0_max_single = max(b.weight_kg for b in self.boards_per_layer[0])
            if layer0_max_single >= self.config.heavy_board_solo_kg:
                fit_res = self._try_fit_layer(0, board)
                if fit_res is not None:
                    _, bx, by, p_dx, p_dy, is_rot = fit_res
                    return (0, bx, by, p_dx, p_dy, is_rot)
                return None

        cur_weight_kg = self.current_weight_g / 1000.0
        cur_area = self.cur_max_x * self.cur_max_y

        best_candidate = None
        min_cost = float('inf')

        # 优先填入面积较小、板数较少的层以平衡各层饱满度
        layer_priority = sorted(range(self.target_layers), key=lambda l: (
            sum(b.length * b.width for b in self.boards_per_layer[l]),
            len(self.boards_per_layer[l]),
            l
        ))

        for l_idx in layer_priority:
            # 物理规则：下层为空时禁止放置上层
            if l_idx > 0 and len(self.boards_per_layer[l_idx - 1]) == 0:
                continue

            fit_res = self._try_fit_layer(l_idx, board)
            if fit_res is not None:
                cost, bx, by, p_dx, p_dy, is_rot = fit_res

                new_max_x = max(self.cur_max_x, bx + p_dx)
                new_max_y = max(self.cur_max_y, by + p_dy)
                new_area = new_max_x * new_max_y

                # 拦截规则 1：当包裹已较重 (>=35kg)，拒绝因塞入零散小板件而大幅度膨胀整包轮廓
                if cur_weight_kg >= 35.0 and cur_area > 0:
                    area_expansion_ratio = (new_area - cur_area) / cur_area
                    if area_expansion_ratio > 0.15 and board.area_m2 / max(1e-5, (new_area - cur_area) / 1e6) < 0.70:
                        continue

                # 拦截规则 2：高层绝不能将整包尺寸撑大超过底层轮廓的 12%
                if l_idx > 0 and self.layer0_max_x > 0 and self.layer0_max_y > 0:
                    l0_area = self.layer0_max_x * self.layer0_max_y
                    if new_area > l0_area * 1.12:
                        continue

                if cost < min_cost:
                    min_cost = cost
                    best_candidate = (l_idx, bx, by, p_dx, p_dy, is_rot)

        return best_candidate

    def _try_fit_layer(self, layer_idx: int, board: Board) -> Optional[Tuple[float, int, int, int, int, bool]]:
        packer = self.layer_packers[layer_idx]
        cur_max_board_len = max(self.longest_single_board, board.length)
        candidates = []

        # 尝试方向：原向(False) 与 旋转90度(True)
        orientations = [(board.length, board.width, False), (board.width, board.length, True)]

        for test_len, test_wid, is_rot in orientations:
            if test_len > self.config.max_length or test_wid > self.config.max_width:
                continue

            pos = packer.find_position_fixed(test_len, test_wid)
            if not pos:
                continue

            # 4元组解构 (x, y, best_short, best_long)
            bx, by, _, _ = pos
            if (bx + test_len) > self.config.max_length or (by + test_wid) > self.config.max_width:
                continue

            # 1. 2D 外包络扩张代价计算
            new_max_x = max(self.cur_max_x, bx + test_len)
            new_max_y = max(self.cur_max_y, by + test_wid)
            old_area = self.cur_max_x * self.cur_max_y
            new_area = new_max_x * new_max_y
            expansion_area = (new_area - old_area) if old_area > 0 else (new_max_x * new_max_y)

            # 2. 单板过度拉伸惩罚
            excess_len = max(0, (bx + test_len) - cur_max_board_len)
            length_stretch_penalty = excess_len * 25000

            # 3. 基准层轮廓锚定惩罚（解决跨层包围盒虚胖）
            contour_penalty = 0
            if layer_idx > 0 and (self.layer0_max_x > 0 or self.layer0_max_y > 0):
                overflow_x = max(0, (bx + test_len) - self.layer0_max_x)
                overflow_y = max(0, (by + test_wid) - self.layer0_max_y)
                contour_penalty = (overflow_x * 35000) + (overflow_y * 45000)

            # 4. 同层长度模数失配惩罚（解决长短板混拼导致的大空洞）
            length_disparity_penalty = 0
            layer_boards = self.boards_per_layer[layer_idx]
            if layer_boards:
                layer_max_len = max(b.length for b in layer_boards)
                if layer_max_len > 1800 and test_len < (layer_max_len * 0.6):
                    length_disparity_penalty = (layer_max_len - test_len) * 15000

            # 5. 细长条（宽度 <= 120mm）横向突兀放置惩罚
            strip_penalty = 0
            if min(board.length, board.width) <= 120 and test_len < test_wid:
                strip_penalty = 20000

            total_cost = (
                expansion_area * 1.5
                + length_stretch_penalty
                + contour_penalty
                + length_disparity_penalty
                + strip_penalty
                + (layer_idx * 15000)
            )

            candidates.append((total_cost, bx, by, test_len, test_wid, is_rot))

        if not candidates:
            return None

        candidates.sort(key=lambda c: c[0])

        for cost, bx, by, pdx, pdy, is_rot in candidates:
            # 物理防悬空：上层实体必须获得下层 >= 50% 面积支撑
            if layer_idx > 0 and not self._check_support(layer_idx, bx, by, pdx, pdy):
                continue
            return cost, bx, by, pdx, pdy, is_rot

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

        return (overlap_area / target_area) >= (self.config.min_support_ratio - 1e-5)

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

        # 增量更新边界
        self.cur_max_x = max(self.cur_max_x, bx + p_dx)
        self.cur_max_y = max(self.cur_max_y, by + p_dy)
        self.longest_single_board = max(self.longest_single_board, board.length, board.width)

        if l_idx == 0:
            self.layer0_max_x = max(self.layer0_max_x, bx + p_dx)
            self.layer0_max_y = max(self.layer0_max_y, by + p_dy)

    def finalize_package(self, pkg_id: int, room_id: str) -> Tuple[Optional[Package], List[str]]:
        """剔除填充不足的稀疏层，级联剥离断层，杜绝悬空板与4层虚高"""
        if not self.placed_boards:
            return None, []

        pkg_footprint_area = self.cur_max_x * self.cur_max_y
        valid_layers = [0]
        rejected_board_ids: List[str] = []

        # 逐层向上校验，遇断层或稀疏层立即熔断
        for l_idx in range(1, self.target_layers):
            layer_boards = self.boards_per_layer[l_idx]
            if not layer_boards:
                break
            l_area = sum(b.length * b.width for b in layer_boards)
            if pkg_footprint_area > 0 and (l_area / pkg_footprint_area) >= self.config.min_layer_fill_ratio:
                valid_layers.append(l_idx)
            else:
                # 触发级联丢弃自当前层及以上的所有板材
                for l_fail in range(l_idx, self.target_layers):
                    rejected_board_ids.extend([b.board_id for b in self.boards_per_layer[l_fail]])
                break

        num_layers = len(valid_layers)

        # 规格收敛：若目标4层但仅保留3层，剥离第3层退回标准2层
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