# -*- coding: utf-8 -*-
from fastapi import APIRouter, UploadFile, File
from app.common.result import JsonResult
from app.dto.packing_dto import BoardScanDto
from app.vo.packing_vo import OrderSummaryVo, ScanGuideVo
from app.services.packing_service import PackingService, PackingPlanCache

router = APIRouter(prefix="/api/packing", tags=["智能板材装箱打包接口"])
service = PackingService()


@router.post("/order/import/post", response_model=JsonResult[OrderSummaryVo], summary="导入工厂Excel生成打包排版方案")
async def order_import_post(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        return JsonResult.error("仅支持上传 Excel 格式文件 (.xlsx / .xls)")
    try:
        content = await file.read()
        res_vo = service.import_excel_and_pack(content, file.filename)
        return JsonResult.success(data=res_vo, message="工单解析与打包规划完成")
    except Exception as e:
        return JsonResult.error(message=f"打包排版计算失败: {str(e)}", code=400)


@router.get("/order/get", response_model=JsonResult[dict], summary="查询指定订单的排版方案明细")
def order_get(orderId: str):
    plan = PackingPlanCache.get(orderId)
    if not plan:
        return JsonResult.error("指定工单不存在", code=404)
    return JsonResult.success(data=plan)


@router.post("/board/scan/post", response_model=JsonResult[ScanGuideVo], summary="扫码枪条码校验与防呆落点指引")
def board_scan_post(dto: BoardScanDto):
    success, guide_vo, msg = service.process_scan(dto)
    if success:
        return JsonResult.success(data=guide_vo, message=msg)
    else:
        return JsonResult(code=400, message=msg, data=guide_vo)