<template>
  <aside class="w-80 flex flex-col bg-[#14161f]/75 backdrop-blur-2xl rounded-2xl border border-white/[0.08] shadow-glass-md overflow-hidden">
    <!-- 头部概要 -->
    <div class="p-3.5 border-b border-white/[0.06] flex justify-between items-center bg-white/[0.02]">
      <div class="flex items-center space-x-2">
        <span class="font-bold text-xs text-apple-ink tracking-tight">包装箱清单</span>
        <span class="px-2 py-0.5 rounded-full text-[11px] bg-white/[0.08] text-apple-ink font-mono font-bold">
          {{ packages?.length || 0 }} 包
        </span>
      </div>
      <span class="text-[11px] text-apple-tertiary font-mono">上限 50kg/包</span>
    </div>

    <!-- 卡片滑动队列 -->
    <div class="flex-1 overflow-y-auto p-2.5 space-y-2">
      <div
        v-for="pkg in packages"
        :key="pkg.package_id"
        @click="emit('selectPackage', pkg.package_id)"
        :class="[
          'p-3.5 rounded-xl border transition-all duration-200 cursor-pointer relative overflow-hidden',
          selectedPackageId === pkg.package_id
            ? 'bg-[#202533] border-apple-blue shadow-active-card'
            : 'bg-[#181b24]/50 border-white/[0.05] hover:bg-[#1e222e]/80 hover:border-white/[0.08] shadow-glass-sm'
        ]"
      >
        <!-- 激活指示光条 -->
        <div
          v-if="selectedPackageId === pkg.package_id"
          class="absolute left-0 top-2 bottom-2 w-1 bg-apple-blue rounded-r"
        ></div>

        <!-- 头部：箱号、房间、状态徽标 -->
        <div class="flex justify-between items-start mb-2.5 pl-1.5">
          <div class="flex items-center space-x-2">
            <span class="font-black text-sm text-apple-ink font-mono">
              #{{ String(pkg.package_id).padStart(2, '0') }}
            </span>
            <span class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-white/[0.06] text-apple-secondary border border-white/[0.06]">
              {{ pkg.room_id }}
            </span>
            <span v-if="pkg.is_oversized_single" class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
              超重大件
            </span>
          </div>

          <span
            :class="[
              'text-[10px] px-2 py-0.5 rounded-full font-bold border transition-colors font-mono',
              pkg.status === '2'
                ? 'bg-emerald-500/15 text-apple-green border-emerald-500/30'
                : (pkg.status === '1' ? 'bg-amber-500/15 text-apple-amber border-amber-500/30' : 'bg-white/[0.06] text-apple-secondary border-white/[0.06]')
            ]"
          >
            {{ pkg.status === '2' ? '已满箱' : (pkg.status === '1' ? '装配中' : '待装') }}
          </span>
        </div>

        <!-- 规格信息与重量进度条 -->
        <div class="space-y-1.5 pl-1.5">
          <div class="flex justify-between text-[11px] text-apple-secondary font-mono">
            <span>{{ pkg.layers }}层规格 · {{ pkg.boards_count || pkg.boards.length }} 块</span>
            <span :class="pkg.total_weight_kg > 49.5 ? 'text-apple-amber font-bold' : 'text-apple-ink font-medium'">
              {{ pkg.total_weight_kg.toFixed(1) }} / 50.0 kg
            </span>
          </div>

          <!-- 精致深色发光进度条 -->
          <div class="w-full h-1.5 bg-black/40 rounded-full overflow-hidden p-[0.5px]">
            <div
              :class="[
                'h-full transition-all duration-300 rounded-full',
                pkg.total_weight_kg > 49.5 ? 'bg-gradient-to-r from-amber-500 to-apple-amber' : 'bg-gradient-to-r from-emerald-500 to-apple-green'
              ]"
              :style="{ width: `${Math.min(100, (pkg.total_weight_kg / 50) * 100)}%` }"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import type { PackageVo } from '../types/packing';

defineProps<{
  packages: PackageVo[] | undefined;
  selectedPackageId: number | null;
}>();

const emit = defineEmits<{
  (e: 'selectPackage', packageId: number): void;
}>();
</script>