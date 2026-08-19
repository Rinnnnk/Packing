# -*- coding: utf-8 -*-
from typing import Optional
from pydantic import BaseModel, Field


class BoardScanDto(BaseModel):
    order_id: str = Field(..., description="订单编号")
    barcode: str = Field(..., description="扫码枪识别的板件唯一条码")
    current_package_id: Optional[int] = Field(None, description="当前前端聚焦操作的包装箱序号")


class PackageStatusUpdateDto(BaseModel):
    order_id: str = Field(..., description="订单编号")
    package_id: int = Field(..., description="包装箱序号")
    status: str = Field(..., description="包装状态: 0-待装, 1-装配中, 2-已封箱")