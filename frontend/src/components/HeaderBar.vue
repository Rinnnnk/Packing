<template>
  <header class="h-16 bg-[#14161f]/80 backdrop-blur-2xl border-b border-white/[0.08] shadow-glass-sm flex items-center justify-between px-6 z-20 select-none">
    <!-- 系统 Logo & 工单关键指标 -->
    <div class="flex items-center space-x-4">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-apple-blue to-indigo-500 flex items-center justify-center shadow-md shadow-apple-blue/20 ring-1 ring-white/20">
        <span class="font-black text-white text-lg font-mono">P</span>
      </div>
      <div>
        <div class="flex items-center space-x-2">
          <h1 class="text-sm font-bold text-apple-ink tracking-tight">智能板材装箱打包作业台</h1>
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-apple-blue/15 text-apple-blue border border-apple-blue/30">
            PROD v1.0
          </span>
        </div>
        <p class="text-[11px] text-apple-secondary font-mono">工业 4.0 智能分拣与物理防呆系统</p>
      </div>

      <!-- 工单状态胶囊 -->
      <div v-if="orderSummary" class="flex items-center space-x-3 pl-4 ml-2 border-l border-white/[0.08]">
        <div class="flex items-center space-x-2 px-3 py-1 rounded-full bg-white/[0.06] border border-white/[0.08] text-xs font-mono font-bold text-apple-ink shadow-inner">
          <span class="w-2 h-2 rounded-full bg-apple-green animate-pulse"></span>
          <span class="text-apple-green">{{ orderSummary.order_id }}</span>
        </div>
        <div class="flex items-center space-x-3 text-xs text-apple-secondary font-mono">
          <span>共 <strong class="text-apple-ink font-semibold">{{ orderSummary.total_boards }}</strong> 块</span>
          <span class="text-white/15">/</span>
          <span><strong class="text-apple-ink font-semibold">{{ orderSummary.total_weight_kg.toFixed(1) }}</strong> kg</span>
          <span class="text-white/15">/</span>
          <span>利用率 <strong class="text-apple-green font-bold text-[13px]">{{ (orderSummary.avg_space_utilization * 100).toFixed(1) }}%</strong></span>
        </div>
      </div>
    </div>

    <!-- 硬件状态与导入按钮 -->
    <div class="flex items-center space-x-3.5">
      <!-- 扫码枪雷达状态指示 -->
      <div class="flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-white/[0.06] border border-white/[0.08] shadow-glass-sm text-xs">
        <span class="relative flex h-2 w-2">
          <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-apple-green"></span>
        </span>
        <span class="text-apple-ink font-medium tracking-tight text-[11px]">USB HID 扫码枪就绪</span>
      </div>

      <!-- 导入工单按钮 -->
      <input type="file" ref="fileInputRef" accept=".xlsx,.xls,.csv" class="hidden" @change="onFileSelected" />
      <button
        @click="fileInputRef?.click()"
        :disabled="isLoading"
        class="px-4 py-2 bg-apple-blue hover:bg-blue-600 active:scale-[0.98] disabled:opacity-50 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-apple-blue/25 flex items-center space-x-2 ring-1 ring-white/20"
      >
        <span v-if="isLoading" class="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
        <span>{{ isLoading ? '正在排样计算...' : '导入工单文件' }}</span>
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import type { OrderSummaryVo } from '../types/packing';

defineProps<{
  orderSummary: OrderSummaryVo | null;
  isLoading: boolean;
}>();

const emit = defineEmits<{
  (e: 'fileSelected', file: File): void;
}>();

const fileInputRef = ref<HTMLInputElement | null>(null);

const onFileSelected = (e: Event) => {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (file) {
    emit('fileSelected', file);
    if (fileInputRef.value) fileInputRef.value.value = '';
  }
};
</script>