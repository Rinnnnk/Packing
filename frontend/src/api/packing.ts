import request from './request';
import type { JsonResult, OrderSummaryVo, ScanGuideVo, BoardScanDto } from '../types/packing';

export const packingApi = {
  /**
   * 导入工单文件 (.xlsx / .xls / .csv)
   */
  importOrder(file: File): Promise<JsonResult<OrderSummaryVo>> {
    const formData = new FormData();
    formData.append('file', file);
    return request.post('/api/packing/order/import/post', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  /**
   * 扫码枪条码校验与防呆落点指引
   */
  scanBoard(dto: BoardScanDto): Promise<JsonResult<ScanGuideVo>> {
    return request.post('/api/packing/board/scan/post', dto);
  },

  /**
   * 查询工单详细排版方案
   */
  getOrderPlan(orderId: string): Promise<JsonResult<OrderSummaryVo>> {
    return request.get('/api/packing/order/get', { params: { orderId } });
  },
};