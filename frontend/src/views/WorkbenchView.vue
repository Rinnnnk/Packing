<template>
  <div class="h-screen w-screen flex flex-col bg-industrial-950 overflow-hidden">
    <!-- 顶部状态栏 -->
    <HeaderBar
      :order-summary="orderSummary"
      :is-loading="isLoading"
      @file-selected="handleOrderImport"
    />

    <!-- 主工作区 -->
    <main class="flex-1 flex overflow-hidden p-4 gap-4">
      <!-- 左侧包装箱队列卡片 -->
      <PackageList
        :packages="orderSummary?.packages || []"
        :selected-package-id="selectedPackageId"
        @select-package="handlePackageSelect"
      />

      <!-- 中央画布与防呆警报 -->
      <section class="flex-1 flex flex-col gap-3 min-w-0">
        <!-- 防呆拦截警报横幅 -->
        <AlertBanner
          :visible="alertState.visible"
          :type="alertState.type"
          :title="alertState.title"
          :message="alertState.message"
          @close="alertState.visible = false"
        />

        <!-- 2D 排样画布 -->
        <div class="flex-1 min-h-0">
          <StackingCanvas
            :pkg="currentPackage"
            :highlight-barcode="highlightBarcode"
          />
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import HeaderBar from '../components/HeaderBar.vue';
import PackageList from '../components/PackageList.vue';
import StackingCanvas from '../components/StackingCanvas.vue';
import AlertBanner from '../components/AlertBanner.vue';
import { packingApi } from '../api/packing';
import { useBarcodeScanner } from '../composables/useBarcodeScanner';
import { useAudioAlert } from '../composables/useAudioAlert';
import type { OrderSummaryVo, PackageVo, PlacedBoardVo } from '../types/packing';

const isLoading = ref(false);
const orderSummary = ref<OrderSummaryVo | null>(null);
const selectedPackageId = ref<number | null>(null);
const highlightBarcode = ref<string | null>(null);

const { playAlert } = useAudioAlert();

const alertState = ref({
  visible: false,
  type: 'SUCCESS' as 'SUCCESS' | 'ERROR',
  title: '',
  message: '',
});

const currentPackage = computed<PackageVo | null>(() => {
  if (!orderSummary.value || selectedPackageId.value === null) return null;
  return orderSummary.value.packages.find((p: PackageVo) => p.package_id === selectedPackageId.value) || null;
});

// 处理包装箱选择
const handlePackageSelect = (pkgId: number) => {
  selectedPackageId.value = pkgId;
  highlightBarcode.value = null;
};

// 导入工单文件
const handleOrderImport = async (file: File) => {
  isLoading.value = true;
  try {
    const res = await packingApi.importOrder(file);
    if (res.code === 200) {
      orderSummary.value = res.data;
      selectedPackageId.value = res.data.packages[0]?.package_id || 1;
      highlightBarcode.value = null;
      playAlert('SUCCESS');
      alertState.value = {
        visible: true,
        type: 'SUCCESS',
        title: '工单导入与排样成功',
        message: `生成 ${res.data.total_packages} 个包装箱，平均空间利用率: ${(res.data.avg_space_utilization * 100).toFixed(1)}%`,
      };
    } else {
      playAlert('ERROR');
      alertState.value = {
        visible: true,
        type: 'ERROR',
        title: '工单解析失败',
        message: res.message,
      };
    }
  } catch (err: any) {
    playAlert('ERROR');
    alertState.value = {
      visible: true,
      type: 'ERROR',
      title: '系统通讯异常',
      message: err.message,
    };
  } finally {
    isLoading.value = false;
  }
};

// 全局扫码枪事件监听
useBarcodeScanner(async (barcode: string) => {
  if (!orderSummary.value) {
    playAlert('ERROR');
    alertState.value = {
      visible: true,
      type: 'ERROR',
      title: '扫码未就绪',
      message: '请先上传工单 Excel/CSV 文件生成打包方案！',
    };
    return;
  }

  const res = await packingApi.scanBoard({
    order_id: orderSummary.value.order_id,
    barcode: barcode,
    current_package_id: selectedPackageId.value,
  });

  if (res.code === 200 && res.data) {
    highlightBarcode.value = barcode;
    selectedPackageId.value = res.data.package_id;

    // 更新前端板材与包装箱状态
    const pkg = orderSummary.value.packages.find((p: PackageVo) => p.package_id === res.data.package_id);
    if (pkg) {
      const b = pkg.boards.find((x: PlacedBoardVo) => x.barcode === barcode || x.board_id === barcode);
      if (b) b.is_scanned = true;
      if (res.data.package_finished) {
        pkg.status = '2';
        playAlert('FINISHED');
      } else {
        pkg.status = '1';
        playAlert('SUCCESS');
      }
    }

    alertState.value = {
      visible: true,
      type: 'SUCCESS',
      title: '扫码就位指引',
      message: res.data.alert_message,
    };
  } else {
    playAlert('ERROR');
    alertState.value = {
      visible: true,
      type: 'ERROR',
      title: '防呆状态机拦截',
      message: res.message || '扫码校验未通过',
    };
  }
});
</script>