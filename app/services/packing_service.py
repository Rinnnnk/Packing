# -*- coding: utf-8 -*-
"""
packing_service.py - 打包业务调度、文件解析与扫码防呆状态机
"""
import io
import uuid
import pandas as pd
from typing import List, Dict, Optional, Tuple
from app.domain.config import PackingConfig
from app.domain.models import Board
from app.domain.engine import FurniturePackingEngine
from app.domain.validator import ProductionValidator
from app.dto.packing_dto import BoardScanDto
from app.vo.packing_vo import OrderSummaryVo, ScanGuideVo


class PackingPlanCache:
    """生产级方案内存缓存（可平滑切换 Redis）"""
    _cache: Dict[str, Dict] = {}

    @classmethod
    def save(cls, order_id: str, plan_data: Dict):
        cls._cache[order_id] = plan_data

    @classmethod
    def get(cls, order_id: str) -> Optional[Dict]:
        return cls._cache.get(order_id)


class PackingService:
    def __init__(self):
        self.config = PackingConfig()
        self.engine = FurniturePackingEngine(self.config)

    def import_file_and_pack(self, file_content: bytes, filename: str) -> OrderSummaryVo:
        """
        全兼容工单文件解析（支持 .xlsx / .xls / .csv 及 GBK/UTF-8 编码）
        """
        filename_lower = filename.lower()
        if filename_lower.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file_content))
        elif filename_lower.endswith('.csv'):
            df = None
            # 自动探测并适配国内工厂常用的多种编码
            for enc in ['gbk', 'gb18030', 'utf-8-sig', 'utf-8']:
                try:
                    df = pd.read_csv(io.BytesIO(file_content), encoding=enc)
                    break
                except Exception:
                    continue
            if df is None:
                raise ValueError("CSV 文件编码无法识别，请确保为 GBK 或 UTF-8 编码")
        else:
            raise ValueError("不支持的文件格式，仅支持上传 .xlsx, .xls, .csv 文件")

        required_cols = {'房间', '成品长度', '成品宽度', '厚度', '板件名称', '板件条码'}
        if not required_cols.issubset(set(df.columns)):
            missing = required_cols - set(df.columns)
            raise ValueError(f"工单表格缺少必要列，缺少: {missing}")

        boards: List[Board] = []
        for _, row in df.iterrows():
            thickness = int(row['厚度'])
            # 动态适配 9mm / 12mm / 18mm / 22mm / 25mm 工业密度
            if thickness <= 9:
                density = 12.0
            elif thickness <= 12:
                density = 15.0
            elif thickness <= 18:
                density = 23.0
            elif thickness <= 22:
                density = 28.0
            else:
                density = 30.0

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

        # 触发 3D 核心排样计算
        pack_res = self.engine.pack_boards(boards)

        # 零容忍物理规则断言
        ProductionValidator.validate(boards, pack_res, self.config)

        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

        # 初始化扫码就位态
        for p in pack_res["packages"]:
            p["status"] = "0"
            for b in p["boards"]:
                b["is_scanned"] = False

        PackingPlanCache.save(order_id, pack_res)
        summary = pack_res["summary"]

        return OrderSummaryVo(
            order_id=order_id,
            total_rooms=summary["total_rooms"],
            total_boards=summary["total_boards"],
            total_packages=summary["total_packages"],
            total_weight_kg=summary["total_weight_kg"],
            avg_space_utilization=summary["avg_space_utilization"],
            execution_time_ms=summary["execution_time_ms"],
            packages_by_layer=summary["packages_by_layer"],
            packages=pack_res["packages"]
        )

    def process_scan(self, dto: BoardScanDto) -> Tuple[bool, Optional[ScanGuideVo], str]:
        plan = PackingPlanCache.get(dto.order_id)
        if not plan:
            return False, None, f"未找到订单 [{dto.order_id}] 的有效排版数据"

        target_pkg = None
        target_board = None

        for p in plan["packages"]:
            for b in p["boards"]:
                if b["barcode"] == dto.barcode or b["board_id"] == dto.barcode:
                    target_pkg = p
                    target_board = b
                    break
            if target_board:
                break

        if not target_board:
            return False, None, f"条码 [{dto.barcode}] 不属于当前工单的任何包装箱！"

        pkg_id = target_pkg["package_id"]

        # 防呆规则 1: 错箱拦截
        if dto.current_package_id is not None and dto.current_package_id != pkg_id:
            vo = ScanGuideVo(
                match_status="INTERCEPT_CROSS_PKG",
                alert_message=f"【错箱警报】该板件属于包装 #{pkg_id:02d} [{target_pkg['room_id']}]，请勿放入当前 #{dto.current_package_id:02d} 箱！",
                package_id=pkg_id,
                room_id=target_pkg["room_id"],
                layer_idx=target_board["layer"],
                x=target_board["x"],
                y=target_board["y"],
                length=target_board["length"],
                width=target_board["width"],
                is_rotated=target_board["is_rotated"],
                board_name=target_board["name"]
            )
            return False, vo, vo.alert_message

        # 防呆规则 2: 防悬空装载拦截（底层未放满禁止放上层）
        target_layer = target_board["layer"]
        if target_layer > 0:
            lower_boards = [b for b in target_pkg["boards"] if b["layer"] == target_layer - 1]
            unscanned_lower = [b["name"] for b in lower_boards if not b["is_scanned"]]
            if unscanned_lower:
                vo = ScanGuideVo(
                    match_status="INTERCEPT_FLOATING",
                    alert_message=f"【防悬空拦截】请先放平第 {target_layer} 层基础板件！(尚有 {len(unscanned_lower)} 块未放入)",
                    package_id=pkg_id,
                    room_id=target_pkg["room_id"],
                    layer_idx=target_board["layer"],
                    x=target_board["x"],
                    y=target_board["y"],
                    length=target_board["length"],
                    width=target_board["width"],
                    is_rotated=target_board["is_rotated"],
                    board_name=target_board["name"]
                )
                return False, vo, vo.alert_message

        # 校验通过，标记板材入箱就位
        target_board["is_scanned"] = True
        target_pkg["status"] = "1"

        all_pkg_scanned = all(b["is_scanned"] for b in target_pkg["boards"])
        if all_pkg_scanned:
            target_pkg["status"] = "2"

        vo = ScanGuideVo(
            match_status="SUCCESS",
            alert_message=f"请放入包装 #{pkg_id:02d} 第 {target_layer + 1} 层 (落点坐标 X:{target_board['x']}, Y:{target_board['y']})",
            package_id=pkg_id,
            room_id=target_pkg["room_id"],
            layer_idx=target_board["layer"],
            x=target_board["x"],
            y=target_board["y"],
            length=target_board["length"],
            width=target_board["width"],
            is_rotated=target_board["is_rotated"],
            board_name=target_board["name"],
            package_finished=all_pkg_scanned
        )
        return True, vo, "扫码校验通过"