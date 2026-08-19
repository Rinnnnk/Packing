/**
 * 标准统一后端响应格式 (JsonResult<T>)
 */
export interface JsonResult<T = any> {
  code: number;
  message: string;
  data: T;
  timestamp: number;
}

/**
 * 板件排样落点数据
 */
export interface PlacedBoardVo {
  board_id: string;
  barcode: string;
  room_id: string;
  x: number;
  y: number;
  length: number;
  width: number;
  thickness: number;
  layer: number;
  is_rotated: boolean;
  weight_kg: number;
  name: string;
  is_scanned: boolean;
}

/**
 * 包装箱明细数据
 */
export interface PackageVo {
  package_id: number;
  room_id: string;
  layers: 1 | 2 | 4;
  is_oversized_single: boolean;
  total_weight_kg: number;
  bounding_box: {
    length: number;
    width: number;
    height: number;
  };
  space_utilization: number;
  boards_count: number;
  boards: PlacedBoardVo[];
  status?: '0' | '1' | '2'; // 0-待装, 1-装配中, 2-已封箱
}

/**
 * 工单概览返回对象 (OrderSummaryVo)
 */
export interface OrderSummaryVo {
  order_id: string;
  total_rooms: number;
  total_boards: number;
  total_packages: number;
  total_weight_kg: number;
  avg_space_utilization: number;
  execution_time_ms: number;
  packages_by_layer: { [key: number]: number };
  packages: PackageVo[];
}

/**
 * 扫码请求入参 (BoardScanDto)
 */
export interface BoardScanDto {
  order_id: string;
  barcode: string;
  current_package_id: number | null;
}

/**
 * 扫码防呆状态机返回 (ScanGuideVo)
 */
export interface ScanGuideVo {
  match_status: 'SUCCESS' | 'INTERCEPT_CROSS_PKG' | 'INTERCEPT_FLOATING';
  alert_message: string;
  package_id: number;
  room_id: string;
  layer_idx: number;
  x: number;
  y: number;
  length: number;
  width: number;
  is_rotated: boolean;
  board_name: string;
  package_finished: boolean;
}