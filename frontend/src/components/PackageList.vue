<template>
  <aside class="w-80 flex flex-col bg-industrial-900/90 rounded-xl border border-industrial-800 overflow-hidden shadow-xl">
    <!-- 顶栏概要 -->
    <div class="p-3.5 border-b border-industrial-800 flex justify-between items-center bg-industrial-850/50">
      <div class="flex items-center space-x-2">
        <span class="font-bold text-sm text-slate-200">包装箱清单</span>
        <span class="px-2 py-0.5 rounded-full text-xs bg-industrial-700 text-slate-300 font-mono">
          {{ packages.length }} 包
        </span>
      </div>
      <span class="text-xs text-slate-400">上限 50kg/包</span>
    </div>

    <!-- 包装箱卡片滑动列表 -->
    <div class="flex-1 overflow-y-auto p-3 space-y-2.5">
      <div
        v-for="pkg in packages"
        :key="pkg.package_id"
        @click="$emit('selectPackage', pkg.package_id)"
        :class="[
          'p-3.5 rounded-xl border cursor-pointer transition-all duration-200 relative overflow-hidden',
          selectedPackageId === pkg.package_id
            ? 'bg-industrial-800/90 border-emerald-500 shadow-lg shadow-emerald-500/10 ring-1 ring-emerald-500/50'
            : 'bg-industrial-850/60 border-industrial-800 hover:border-industrial-700'
        ]"
      >
        <!-- 头部：箱号、房间、状态 -->
        <div class="flex justify-between items-start mb-2.5">
          <div class="flex items-center space-x-2">
            <span class="font-black text-base text-white font-mono">
              #{{ String(pkg.package_id).padStart(2, '0') }}
            </span>
            <span class="px-2 py-0.5 rounded text-xs bg-industrial-800 text-slate-300 border border-industrial-700">
              {{ pkg.room_id }}
            </span>
            <span v-if="pkg.is_oversized_single" class="px-1.5 py-0.5 rounded text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/30">
              超重大件
            </span>
          </div>

          <!-- 状态徽标 -->
          <span
            :class="[
              'text-xs px-2 py-0.5 rounded-full font-semibold border',
              pkg.status === '2'
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                : (pkg.status === '1' ? 'bg-amber-500/20 text-amber-300 border-amber-500/40' : 'bg-industrial-800 text-slate-400 border-industrial-700')
            ]"
          >
            {{ pkg.status === '2' ? '已满箱' : (pkg.status === '1' ? '装配中' : '待装') }}
          </span>
        </div>

        <!-- 规格信息与重量进度条 -->
        <div class="space-y-1.5">
          <div class="flex justify-between text-xs text-slate-400">
            <span>{{ pkg.layers }}层规格 · {{ pkg.boards.length }} 块板件</span>
            <span :class="pkg.total_weight_kg > 49.5 ? 'text-amber-400 font-bold font-mono' : 'font-mono'">
              {{ pkg.total_weight_kg.toFixed(2) }} / 50kg
            </span>
          </div>

          <div class="w-full h-1.5 bg-industrial-950 rounded-full overflow-hidden border border-industrial-800">
            <div
              :class="[
                'h-full transition-all duration-300 rounded-full',
                pkg.total_weight_kg > 49.5 ? 'bg-amber-500' : 'bg-emerald-500'
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
  packages: PackageVo[];
  selectedPackageId: number | null;
}>();

defineEmits<{
  (e: 'selectPackage', packageId: number): void;
}>();
</script>