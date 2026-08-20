# -*- coding: utf-8 -*-
"""
strategies.py - 3D 物理多层堆叠策略
核心特性：
- P1 (硬性物理红线): 50kg载重、2800x1220边界、同层几何防相交、跨层>=50%面积支撑
- P2 (结构刚度与规格): 底层整板托底(大板优先)/紧凑底座、高层投影硬约束(不超底盘)、边界膨胀截断
- P3 (紧凑排布代价函数): 严格低层优先填满(同层能放坚决同层放)、同层模数对齐、内部空腔填补奖励
- P4 (末端自适应兜底): 稀疏层级联熔断、4退2规格收敛
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
        
        # 增量边界与基底轮廓 (O(1) 维护)
        self.cur_max_x = 0
        self.cur_max_y = 0
        self.layer0_max_x = 0
        self.layer0_max_y = 0
        self.longest_single_board = 0

    def can_fit_board(self, board: Board) -> Optional[Tuple[int, int, int, int, int, bool]]:
        """
        探测板件最佳放入层与落点坐标
        返回 (layer_idx, x, y, dx, dy, is_rotated)，若无法合法放入则返回 None
        """
        # =====================================================================
        # P1: 重量绝对红线校验
        # =====================================================================
        if self.current_weight_g + board.weight_g > self.config.max_weight_g:
            return None

        # =====================================================================
        # P2: 超重大板独占保护 (单板 >= 40kg 锁定在 Layer 0 平铺，禁止加高层)
        # =====================================================================
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

        # =====================================================================
        # P2: 底层结构刚度与托底母板规则
        # 若底层首件为大板 (长度 >= 1500mm 或面积 >= 0.5m²)，锁定整块母板托底，禁止底层继续并排散料；
        # 若底层为中小散件，允许拼接 2~3 块构建紧凑复合底座
        # =====================================================================
        if self.target_layers > 1 and self.boards_per_layer[0]:
            l0_first = self.boards_per_layer[0][0]
            is_large_anchor = (l0_first.length >= 1500 or (l0_first.length * l0_first.width) >= 500000)
            if is_large_anchor or len(self.boards_per_layer[0]) >= 3 or self.layer0_max_y >= 750:
                allowed_layers = list(range(1, self.target_layers))
            else:
                allowed_layers = list(range(self.target_layers))
        else:
            allowed_layers = list(range(self.target_layers))

        best_candidate = None
        min_cost = float('inf')

        # =====================================================================
        # P3: 遍历候选层（严格由低到高 0 -> 1 -> 2 -> 3，同层能放坚决同层放）
        # =====================================================================
        layer_priority = sorted(allowed_layers, key=lambda l: (
            l,  # 优先低层
            -len(self.boards_per_layer[l])  # 优先已有板件的层
        ))

        for l_idx in layer_priority:
            # 物理依赖：下层为空时禁止跨层放置
            if l_idx > 0 and len(self.boards_per_layer[l_idx - 1]) == 0:
                continue

            fit_res = self._try_fit_layer(l_idx, board)
            if fit_res is not None:
                cost, bx, by, p_dx, p_dy, is_rot = fit_res

                new_max_x = max(self.cur_max_x, bx + p_dx)
                new_max_y = max(self.cur_max_y, by + p_dy)
                new_area = new_max_x * new_max_y

                # -------------------------------------------------------------
                # P2: 边界膨胀截断 (Expansion Cutoff)
                # 包裹趋于饱满 (>=35kg) 时，禁止因塞入碎料导致整体包围盒面积膨胀 >15%
                # -------------------------------------------------------------
                if cur_weight_kg >= 35.0 and cur_area > 0:
                    area_expansion_ratio = (new_area - cur_area) / cur_area
                    if area_expansion_ratio > 0.15 and board.area_m2 / max(1e-5, (new_area - cur_area) / 1e6) < 0.70:
                        continue

                # -------------------------------------------------------------
                # P2: 高层依附硬约束 (高层绝对不能超出底层母板轮廓)
                # -------------------------------------------------------------
                if l_idx > 0 and self.layer0_max_x > 0 and self.layer0_max_y > 0:
                    if (bx + p_dx) > self.layer0_max_x * 1.02 or (by + p_dy) > self.layer0_max_y * 1.02:
                        continue

                # -------------------------------------------------------------
                # P2: 散件 1 层包抗弯约束 (禁止无限摊平为薄片)
                # -------------------------------------------------------------
                if self.target_layers == 1 and cur_area > 1000000:
                    if board.length < 1500 and (new_max_x > 1500 or new_max_y > 900):
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
            # P1: 设备物理极值过滤
            if test_len > self.config.max_length or test_wid > self.config.max_width:
                continue

            # 遍历当前层全部可用自由矩形 (Free Rectangles)，确保 100% 发现同层并排空位
            for free in packer.free_rects:
                if free.w >= test_len and free.h >= test_wid:
                    bx, by = free.x, free.y
                    if (bx + test_len) > self.config.max_length or (by + test_wid) > self.config.max_width:
                        continue

                    # P2: 高层超出底层轮廓硬过滤
                    if layer_idx > 0 and self.layer0_max_x > 0 and self.layer0_max_y > 0:
                        if (bx + test_len) > self.layer0_max_x * 1.02 or (by + test_wid) > self.layer0_max_y * 1.02:
                            continue

                    # =========================================================
                    # P3: 紧凑度与代价评分 (Cost Function)
                    # =========================================================
                    new_max_x = max(self.cur_max_x, bx + test_len)
                    new_max_y = max(self.cur_max_y, by + test_wid)
                    old_area = self.cur_max_x * self.cur_max_y
                    new_area = new_max_x * new_max_y
                    expansion_area = (new_area - old_area) if old_area > 0 else (new_max_x * new_max_y)

                    excess_len = max(0, (bx + test_len) - cur_max_board_len)
                    length_stretch_penalty = excess_len * 25000

                    # 低层填补极低代价，高层递增代价 (促成同层并排，杜绝同一层能放下却分层放)
                    layer_cost = layer_idx * 40000

                    # 内部空腔填补奖励（利用已有面积不额外扩张外廓给予高额奖励）
                    internal_fit_bonus = 50000 if (old_area > 0 and expansion_area == 0) else 0

                    short_side = min(free.w - test_len, free.h - test_wid)
                    strip_penalty = 20000 if (min(board.length, board.width) <= 120 and test_len < test_wid) else 0

                    cost = (
                        expansion_area * 1.5
                        + length_stretch_penalty
                        + strip_penalty
                        + layer_cost
                        + short_side * 5
                        - internal_fit_bonus
                    )

                    candidates.append((cost, bx, by, test_len, test_wid, is_rot))

        if not candidates:
            return None

        # 代价由低到高排序
        candidates.sort(key=lambda c: c[0])

        for cost, bx, by, pdx, pdy, is_rot in candidates:
            # =================================================================
            # P1: 跨层物理防悬空校验 (上层实体必须获得下层 >= 50% 面积支撑)
            # =================================================================
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
        """在指定层和坐标上落板并更新物理状态"""
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

        if l_idx == 0:
            self.layer0_max_x = max(self.layer0_max_x, bx + p_dx)
            self.layer0_max_y = max(self.layer0_max_y, by + p_dy)

        self.cur_max_x = max(self.cur_max_x, bx + p_dx)
        self.cur_max_y = max(self.cur_max_y, by + p_dy)
        self.longest_single_board = max(self.longest_single_board, board.length, board.width)

    def finalize_package(self, pkg_id: int, room_id: str) -> Tuple[Optional[Package], List[str]]:
        """
        P4: 规格最终收敛与熔断剥离
        剔除稀疏层、级联剥离断层，将 3 层强制收敛为 2 层规格，确保只输出 4/2/1 标准包装
        """
        if not self.placed_boards:
            return None, []

        pkg_footprint_area = self.cur_max_x * self.cur_max_y
        valid_layers = [0]
        rejected_board_ids: List[str] = []

        # 逐层向上校验，遇断层或稀疏层立即级联熔断
        for l_idx in range(1, self.target_layers):
            layer_boards = self.boards_per_layer[l_idx]
            if not layer_boards:
                break
            l_area = sum(b.length * b.width for b in layer_boards)
            if pkg_footprint_area > 0 and (l_area / pkg_footprint_area) >= self.config.min_layer_fill_ratio:
                valid_layers.append(l_idx)
            else:
                for l_fail in range(l_idx, self.target_layers):
                    rejected_board_ids.extend([b.board_id for b in self.boards_per_layer[l_fail]])
                break

        num_layers = len(valid_layers)

        # 4层退回2层规格收敛
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