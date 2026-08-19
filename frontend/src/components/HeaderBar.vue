<template>
  <header class="h-16 bg-industrial-900 border-b border-industrial-800 flex items-center justify-between px-6 z-20 shadow-md">
    <!-- 系统 Logo & 工单编号 -->
    <div class="flex items-center space-x-4">
      <div class="w-9 h-9 rounded-lg bg-emerald-500 flex items-center justify-center font-black text-industrial-950 text-xl shadow-lg shadow-emerald-500/20">
        P
      </div>
      <div>
        <h1 class="text-base font-bold text-slate-100 leading-tight">智能板材装箱打包作业台</h1>
        <p class="text-xs text-slate-400">工业 4.0 智能分拣与防呆系统</p>
      </div>
      <div v-if="orderSummary" class="flex items-center space-x-2 pl-4 border-l border-industrial-700">
        <span class="px-2.5 py-0.5 rounded-full text-xs font-mono bg-industrial-800 text-emerald-400 border border-industrial-700">
          {{ orderSummary.order_id }}
        </span>
        <span class="text-xs text-slate-400">
          共 {{ orderSummary.total_boards }} 块 | {{ orderSummary.total_weight_kg }} kg | 利用率 {{ (orderSummary.avg_space_utilization * 100).toFixed(1) }}%
        </span>
      </div>
    </div>

    <!-- 硬件状态与工单导入 -->
    <div class="flex items-center space-x-5">
      <div class="flex items-center space-x-2 px-3 py-1 rounded-lg bg-industrial-850 border border-industrial-800 text-xs">
        <span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
        <span class="text-slate-300 font-medium">HID 扫码枪就绪</span>
      </div>

      <input
        type="file"
        ref="fileInputRef"
        accept=".xlsx,.xls,.csv"
        class="hidden"
        @change="onFileSelected"
      />
      <button
        @click="fileInputRef?.click()"
        :disabled="isLoading"
        class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 text-white rounded-lg text-sm font-semibold transition-all shadow-lg shadow-indigo-600/30 flex items-center space-x-2"
      >
        <span v-if="isLoading" class="animate-spin text-xs">⏳</span>
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
    // 重置 input 以允许重复上传同名文件
    if (fileInputRef.value) fileInputRef.value.value = '';
  }
};
</script>