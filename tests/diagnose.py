# -*- coding: utf-8 -*-
"""
tests/diagnose.py - 全局工单算法性能与异常包自动化诊断工具
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


def load_file(file_path: str) -> List[Board]:
    if file_path.endswith(('.xlsx', '.xls')):
        df = pd.read_excel(file_path)
    else:
        df = None
        for enc in ['gbk', 'gb18030', 'utf-8-sig', 'utf-8']:
            try:
                df = pd.read_csv(file_path, encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            raise ValueError(f"无法解析文件: {file_path}")

    boards = []
    for _, row in df.iterrows():
        thickness = int(row['厚度'])
        density = 12.0 if thickness <= 9 else (15.0 if thickness <= 12 else (23.0 if thickness <= 18 else (28.0 if thickness <= 22 else 30.0)))
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


def run_full_diagnostics(data_dir: str = "data", output_file: str = "diagnose_report.md"):
    files = sorted(glob.glob(os.path.join(data_dir, "*.*")))
    files = [f for f in files if f.endswith(('.xlsx', '.xls', '.csv')) and not os.path.basename(f).startswith("~$")]

    if not files:
        files = sorted(glob.glob("*.*"))
        files = [f for f in files if f.endswith(('.xlsx', '.xls', '.csv')) and not os.path.basename(f).startswith("~$")]

    config = PackingConfig()
    engine = FurniturePackingEngine(config)

    report = ["# 智能板材打包算法全局诊断与缺陷分析报告\n"]

    for fpath in files:
        fname = os.path.basename(fpath)
        boards = load_file(fpath)
        t0 = time.time()
        res = engine.pack_boards(boards)
        t_el = (time.time() - t0) * 1000.0

        ProductionValidator.validate(boards, res, config)
        s = res["summary"]
        pkgs = res["packages"]

        # 筛选异常包
        low_util_pkgs = [p for p in pkgs if p['space_utilization'] < 0.65]
        one_layer_pkgs = [p for p in pkgs if p['layers'] == 1 and not p.get('is_oversized_single')]

        report.append(f"## 📁 工单: `{fname}`")
        report.append(f"- **基本数据**: 板件数 `{s['total_boards']}` | 房间数 `{s['total_rooms']}` | 总重 `{s['total_weight_kg']}kg` | 算法耗时 `{t_el:.1f}ms`")
        report.append(f"- **打包指标**: 总包数 `{s['total_packages']}` (4层:{s['packages_by_layer'][4]} / 2层:{s['packages_by_layer'][2]} / 1层:{s['packages_by_layer'][1]}) | 平均利用率 `{s['avg_space_utilization']*100:.2f}%`")
        report.append(f"- **待优化项**: 低利用率包(<65%) `{len(low_util_pkgs)}` 个 | 1层散料包 `{len(one_layer_pkgs)}` 个\n")

        if low_util_pkgs:
            report.append("### 🔴 低空间利用率包装明细 (前 5 例):")
            for p in low_util_pkgs[:5]:
                bb = p['bounding_box']
                report.append(f"#### 📦 包装 #{p['package_id']:02d} [{p['room_id']}] · {p['layers']}层 · 重 {p['total_weight_kg']:.2f}kg · 外包 {bb['length']}x{bb['width']}x{bb['height']}mm · 利用率 **{p['space_utilization']*100:.1f}%**")
                report.append("| 层级 | 坐标 (X, Y) | 尺寸 (长x宽x厚) | 旋转 | 板件名称 |")
                report.append("|:---|:---|:---|:---:|:---|")
                for b in p['boards']:
                    rot_str = "是" if b['is_rotated'] else "否"
                    report.append(f"| L{b['layer']+1} | ({b['x']}, {b['y']}) | {b['length']}x{b['width']}x{b['thickness']}mm | {rot_str} | {b['name']} |")
                report.append("")
        report.append("---\n")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"\n>>> 诊断报告已生成: {output_file}")


if __name__ == "__main__":
    run_full_diagnostics()