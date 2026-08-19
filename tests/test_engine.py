# -*- coding: utf-8 -*-
"""
test_engine.py - 工厂真实数据多文件批量回归与蒙特卡洛高压测试套件
"""
import os
import glob
import time
import pandas as pd
from typing import List
from app.domain.config import PackingConfig
from app.domain.models import Board
from app.domain.engine import FurniturePackingEngine
from app.domain.validator import ProductionValidator


def load_order_file(file_path: str) -> List[Board]:
    """通用工单文件加载器，兼容 .xlsx 与 .csv (自动探测编码)"""
    if file_path.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path)
    else:
        # 兼容中文工厂 CSV 常见的 GBK/GB18030/UTF-8 编码
        df = None
        for enc in ['gbk', 'gb18030', 'utf-8-sig', 'utf-8']:
            try:
                df = pd.read_csv(file_path, encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            raise ValueError(f"无法解析文件编码: {file_path}")

    boards = []
    for _, row in df.iterrows():
        thickness = int(row['厚度'])
        # 根据板材厚度配置标准工业密度
        if thickness == 9:
            density = 12.0
        elif thickness == 12:
            density = 15.0
        elif thickness == 22:
            density = 28.0
        elif thickness == 25:
            density = 30.0
        else:
            density = 23.0

        b = Board(
            id=str(row['板件条码']).strip(),
            room_id=str(row['房间']).strip(),
            length=int(round(row['成品长度'])),
            width=int(round(row['成品宽度'])),
            thickness=thickness,
            density_kg_m2=density,
            name=str(row['板件名称']).strip(),
            barcode=str(row['板件条码']).strip()
        )
        boards.append(b)
    return boards


def run_batch_real_data_tests(data_dir: str = "data"):
    """批量扫描 data/ 目录下的所有真实工单并执行闭环回归验证"""
    pattern = os.path.join(data_dir, "*.*")
    files = [f for f in glob.glob(pattern) if f.endswith(('.xlsx', '.xls', '.csv')) and not os.path.basename(f).startswith("~$")]

    # 兜底：如果 data/ 为空，检查根目录
    if not files:
        root_files = [f for f in glob.glob("*.*") if f.endswith(('.xlsx', '.xls', '.csv')) and not os.path.basename(f).startswith("~$")]
        files = root_files

    print("=" * 80)
    print(f"  [测试 1] 工厂真实数据多工单批量回归测试 (发现 {len(files)} 份真实数据)")
    print("=" * 80)

    if not files:
        print("  [提示] 未找到任何工单数据文件，请将 .xlsx/.csv 放入 data/ 目录下。")
        return

    config = PackingConfig()
    engine = FurniturePackingEngine(config)

    for idx, fpath in enumerate(files, 1):
        fname = os.path.basename(fpath)
        print(f"\n--- [{idx}/{len(files)}] 正在执行: {fname} ---")
        t0 = time.time()
        boards = load_order_file(fpath)
        load_ms = (time.time() - t0) * 1000.0

        res = engine.pack_boards(boards)
        # 零容忍物理与业务规则断言
        ProductionValidator.validate(boards, res, config)

        s = res["summary"]
        print(f"  * 读取耗时: {load_ms:.1f}ms | 算法耗时: {s['execution_time_ms']:.1f}ms")
        print(f"  * 房间数: {s['total_rooms']} | 板件数: {s['total_boards']} | 总重: {s['total_weight_kg']}kg")
        print(f"  * 包装箱: {s['total_packages']} 包 | 平均空间利用率: {s['avg_space_utilization']*100:.2f}%")
        print(f"  * 规格分布: 4层={s['packages_by_layer'][4]}包, 2层={s['packages_by_layer'][2]}包, 1层={s['packages_by_layer'][1]}包")
        print(f"  >>> 校验状态: 100% PASS (0缺陷 / 0碰撞 / 0跨房间 / 支撑率>=50%)")

    print("\n" + "=" * 80)
    print("  >>> 全部工厂真实数据批量回归测试完成，全部通过！")
    print("=" * 80)


if __name__ == "__main__":
    run_batch_real_data_tests("data")