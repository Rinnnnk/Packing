# -*- coding: utf-8 -*-
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class OrderSummaryVo(BaseModel):
    order_id: str = Field(..., description="订单编号")
    total_rooms: int = Field(..., description="房间数")
    total_boards: int = Field(..., description="板件总数")
    total_packages: int = Field(..., description="总包装箱数")
    total_weight_kg: float = Field(..., description="订单总重量 (kg)")
    avg_space_utilization: float = Field(..., description="平均空间利用率")
    execution_time_ms: float = Field(..., description="算法执行耗时 (ms)")
    packages_by_layer: Dict[int, int] = Field(..., description="各层数规格包装分布")
    packages: List[Dict[str, Any]] = Field(..., description="打包排版结果明细")


class ScanGuideVo(BaseModel):
    match_status: str = Field(..., description="状态: SUCCESS(放行), INTERCEPT_CROSS_PKG(错箱), INTERCEPT_FLOATING(防悬空)")
    alert_message: str = Field(..., description="声光与界面提示语")
    package_id: int = Field(..., description="目标包装箱ID")
    room_id: str = Field(..., description="所属房间")
    layer_idx: int = Field(..., description="所在目标层 (0/1/2/3)")
    x: int = Field(..., description="落点X坐标 (mm)")
    y: int = Field(..., description="落点Y坐标 (mm)")
    length: int = Field(..., description="落点长度 (mm)")
    width: int = Field(..., description="落点宽度 (mm)")
    is_rotated: bool = Field(..., description="是否旋转90度")
    board_name: str = Field(..., description="板件名称")
    package_finished: bool = Field(default=False, description="当前包装箱是否已全部装满")