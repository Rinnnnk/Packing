# -*- coding: utf-8 -*-
"""
validator.py - 生产级零容忍规则断言校验器

【本版本修复记录】
1. [安全兜底新增] 原校验体系完全信任 builder 内部状态，未独立复核"上层板材相对
   下层的支撑率"这一核心物理约束。虽然 strategies.py 已修复了导致悬空的根因
   （finalize_package 的跳层 bug），但为了防止未来任何算法改动再次引入类似问题，
   这里补充一道独立的支撑率复验规则（规则 5），直接基于最终输出的包装结构
   重新计算每一层板材与其正下方一层的几何重叠面积占比，确保 >=1 层的每一块
   板材都获得了 config.min_support_ratio 以上的实体支撑，否则直接判定为 Bug。
"""
from typing import List, Dict
from app.domain.config import PackingConfig
from app.domain.models import Board


class ProductionValidator:
    @staticmethod
    def validate(input_boards: List[Board], result: Dict, config: PackingConfig):
        packages = result["packages"]

        # 1. 板材守恒性校验 (不重不漏)
        input_ids = {b.id for b in input_boards}
        placed_ids = set()
        for p in packages:
            for b in p["boards"]:
                bid = b["board_id"]
                if bid in placed_ids:
                    raise AssertionError(f"[Bug] 板材 [{bid}] 被重复分配！")
                placed_ids.add(bid)

        missing_ids = input_ids - placed_ids
        extra_ids = placed_ids - input_ids
        if missing_ids:
            raise AssertionError(f"[Bug] 板材遗漏: {missing_ids}")
        if extra_ids:
            raise AssertionError(f"[Bug] 未知板材: {extra_ids}")

        # 2. 房间物理隔离与载重
        for p in packages:
            for b in p["boards"]:
                if b["room_id"] != p["room_id"]:
                    raise AssertionError(f"[Bug] 包装 #{p['package_id']} 出现跨房间混装！")

            # 载重校验
            if p["boards_count"] > 1:
                if p["total_weight_kg"] > config.max_package_weight_kg + 0.005:
                    raise AssertionError(f"[Bug] 包装 #{p['package_id']} 超重: {p['total_weight_kg']:.2f}kg > 50kg！")
            elif p["boards_count"] == 1:
                single_b = p["boards"][0]
                if single_b["weight_kg"] > config.max_package_weight_kg and p["layers"] != 1:
                    raise AssertionError(f"[Bug] 超重大板必须为 1 层包装！")

        # 3. 几何重叠与越界校验
        for p in packages:
            bx = p["bounding_box"]["length"]
            by = p["bounding_box"]["width"]
            if bx > config.max_length or by > config.max_width:
                raise AssertionError(f"[Bug] 包装 #{p['package_id']} 尺寸越界: {bx}x{by}mm！")

            for l_idx in range(p["layers"]):
                lbs = [b for b in p["boards"] if b["layer"] == l_idx]
                for i in range(len(lbs)):
                    for j in range(i + 1, len(lbs)):
                        b1, b2 = lbs[i], lbs[j]
                        overlap = not (
                            b1["x"] + b1["length"] <= b2["x"] or
                            b2["x"] + b2["length"] <= b1["x"] or
                            b1["y"] + b1["width"] <= b2["y"] or
                            b2["y"] + b2["width"] <= b1["y"]
                        )
                        if overlap:
                            raise AssertionError(f"[Bug] 包装 #{p['package_id']} 第 {l_idx+1} 层发生几何碰撞！")

        # 4. 层数规格校验
        for p in packages:
            if p["layers"] not in config.allowed_layers:
                raise AssertionError(f"[Bug] 包装 #{p['package_id']} 层数 {p['layers']} 非法！")

        # 5. 上层支撑率复验（防悬空最后一道防线）
        for p in packages:
            if p["layers"] <= 1:
                continue

            layers_map: Dict[int, list] = {}
            for b in p["boards"]:
                layers_map.setdefault(b["layer"], []).append(b)

            for l_idx in range(1, p["layers"]):
                upper_boards = layers_map.get(l_idx, [])
                if not upper_boards:
                    continue  # 该层无板材，视为未使用层，不涉及悬空问题

                lower_boards = layers_map.get(l_idx - 1, [])
                if not lower_boards:
                    raise AssertionError(
                        f"[Bug] 包装 #{p['package_id']} 第 {l_idx + 1} 层存在板材，"
                        f"但第 {l_idx} 层为空，出现整层悬空！"
                    )

                for ub in upper_boards:
                    overlap_area = 0
                    for lb in lower_boards:
                        ix1 = max(ub["x"], lb["x"])
                        iy1 = max(ub["y"], lb["y"])
                        ix2 = min(ub["x"] + ub["length"], lb["x"] + lb["length"])
                        iy2 = min(ub["y"] + ub["width"], lb["y"] + lb["width"])
                        if ix1 < ix2 and iy1 < iy2:
                            overlap_area += (ix2 - ix1) * (iy2 - iy1)

                    target_area = ub["length"] * ub["width"]
                    support_ratio = (overlap_area / target_area) if target_area > 0 else 0.0

                    if support_ratio < config.min_support_ratio - 1e-6:
                        raise AssertionError(
                            f"[Bug] 包装 #{p['package_id']} 板材 [{ub['board_id']}]（第 {l_idx + 1} 层）"
                            f"实际支撑率 {support_ratio * 100:.1f}% 低于最低要求 "
                            f"{config.min_support_ratio * 100:.0f}%，存在悬空风险！"
                        )