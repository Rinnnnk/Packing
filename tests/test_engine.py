# -*- coding: utf-8 -*-
"""
test.py - 全场景测试套件 (支持真实工厂 Excel 订单与蒙特卡洛高压随机测试)
"""
import os
import random
import time
import pandas as pd
from typing import List
from app.domain.config import PackingConfig
from app.domain.models import Board
from app.domain.engine import FurniturePackingEngine
from app.domain.validator import ProductionValidator


def load_real_excel_data(file_path: str) -> List[Board]:
    """从工厂真实 Excel 订单表格中加载板材清单"""
    df = pd.read_excel(file_path)
    boards = []
    for _, row in df.iterrows():
        b = Board(
            id=str(row['板件条码']),
            room_id=str(row['房间']),
            length=int(round(row['成品长度'])),
            width=int(round(row['成品宽度'])),
            thickness=int(row['厚度']),
            density_kg_m2=23.0,
            name=str(row['板件名称']),
            barcode=str(row['板件条码'])
        )
        boards.append(b)
    return boards


class RandomOrderGenerator:
    PRESETS = {
        "衣柜侧板": (1800, 2750, 450, 600),
        "顶底板":   (1200, 2400, 450, 600),
        "中立隔板": (1500, 2400, 400, 550),
        "标准层板": (400, 1000, 300, 550),
        "抽屉底板": (300, 550, 300, 500),
        "抽屉面板": (300, 600, 120, 250),
        "封边收口": (1800, 2600, 60, 150),
        "通顶大门": (2400, 2780, 800, 1200),
    }

    @classmethod
    def generate_random_room(cls, room_id: str, board_count: int) -> List[Board]:
        boards = []
        for i in range(board_count):
            preset_name, (min_l, max_l, min_w, max_w) = random.choice(list(cls.PRESETS.items()))
            length = random.randint(min_l, max_l)
            width = random.randint(min_w, max_w)
            thickness = random.choice([18, 18, 18, 9, 25])
            density = 23.0 if thickness == 18 else (12.0 if thickness == 9 else 30.0)

            board = Board(
                id=f"{room_id}_B{i+1:02d}",
                room_id=room_id,
                length=length,
                width=width,
                thickness=thickness,
                density_kg_m2=density,
                name=f"{preset_name}_{i+1}"
            )
            boards.append(board)
        return boards

    @classmethod
    def generate_multi_room_batch(cls, room_count: int = 4) -> List[Board]:
        all_boards = []
        room_names = ["主卧", "次卧", "客餐厅", "书房", "儿童房", "玄关", "阳台柜", "厨房"]
        selected_rooms = random.sample(room_names, min(room_count, len(room_names)))

        for r_name in selected_rooms:
            count = random.randint(8, 25)
            room_boards = cls.generate_random_room(r_name, count)
            all_boards.extend(room_boards)

        return all_boards


def test_excel_order():
    excel_files = [f for f in os.listdir(".") if f.endswith(".xlsx") and not f.startswith("~$")]
    print("=" * 70)
    if not excel_files:
        print("  [测试 1] 真实工厂 Excel 订单实测")
        print("  [提示] 当前 Packing 目录下未找到 .xlsx 文件，已跳过真实数据测试。")
        print("  [操作] 请将 Excel 表格放置于项目根目录下后重新运行。")
        print("=" * 70)
        return

    excel_path = excel_files[0]
    print(f"  [测试 1] 真实工厂 Excel 订单实测: {excel_path}")
    print("=" * 70)

    boards = load_real_excel_data(excel_path)
    config = PackingConfig()
    engine = FurniturePackingEngine(config)

    result = engine.pack_boards(boards)
    ProductionValidator.validate(boards, result, config)

    summary = result["summary"]
    print(f"\n[打包概要]")
    print(f"  * 房间数: {summary['total_rooms']} | 总板数: {summary['total_boards']} 块")
    print(f"  * 总包装数: {summary['total_packages']} 包 | 总重量: {summary['total_weight_kg']} kg")
    print(f"  * 平均空间利用率: {summary['avg_space_utilization'] * 100:.2f}%")
    print(f"  * 算法耗时: {summary['execution_time_ms']} ms")
    print(f"  * 规格分布: 4层={summary['packages_by_layer'][4]}包, 2层={summary['packages_by_layer'][2]}包, 1层={summary['packages_by_layer'][1]}包")

    print("\n[各包装详情]")
    for p in result["packages"]:
        bb = p["bounding_box"]
        oversized_tag = " [超重大板]" if p.get("is_oversized_single") else ""
        print(f"  * 包装 #{p['package_id']:02d} [{p['room_id']}] 规格: {p['layers']}层{oversized_tag} | "
              f"重量: {p['total_weight_kg']:.2f}kg/50kg | 外包: {bb['length']}x{bb['width']}x{bb['height']}mm | "
              f"板数: {p['boards_count']} | 利用率: {p['space_utilization']*100:.1f}%")

    print("\n" + "-" * 50)
    print("  >>> 工厂真实数据规则校验: 100% PASS！")
    print("-" * 50)


def test_monte_carlo(rounds: int = 50):
    print("\n" + "=" * 70)
    print(f"  [测试 2] 蒙特卡洛高压随机测试 (连续 {rounds} 轮完全随机生产工况)")
    print("=" * 70)

    config = PackingConfig()
    engine = FurniturePackingEngine(config)

    total_boards = 0
    total_pkgs = 0
    total_time = 0.0
    util_list = []

    for r in range(1, rounds + 1):
        batch = RandomOrderGenerator.generate_multi_room_batch(room_count=random.randint(2, 6))
        t0 = time.time()
        res = engine.pack_boards(batch)
        t_el = (time.time() - t0) * 1000.0

        ProductionValidator.validate(batch, res, config)

        total_boards += len(batch)
        total_pkgs += res["summary"]["total_packages"]
        total_time += t_el
        util_list.append(res["summary"]["avg_space_utilization"])

        if r % 10 == 0 or r == rounds:
            print(f"  -> 完成 {r:02d}/{rounds} 轮 | 本轮板数: {len(batch):02d} | 耗时: {t_el:.2f}ms | 规则校验: 100% PASS")

    avg_util = sum(util_list) / len(util_list)
    print("\n[蒙特卡洛压力测试总结报告]")
    print(f"  * 成功通过轮数: {rounds}/{rounds} 轮 (0 缺陷, 0 碰撞, 0 跨房间混装)")
    print(f"  * 累计检验板材: {total_boards} 块")
    print(f"  * 累计生成包装: {total_pkgs} 个")
    print(f"  * 平均单订单耗时: {total_time / rounds:.2f} ms")
    print(f"  * 综合平均空间利用率: {avg_util * 100:.2f}%")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_excel_order()
    test_monte_carlo(50)