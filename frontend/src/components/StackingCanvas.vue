<template>
  <div class="relative w-full h-full flex flex-col bg-industrial-900 rounded-xl overflow-hidden shadow-2xl border border-industrial-800">
    <!-- 顶部排样控制器 -->
    <div class="flex items-center justify-between px-5 py-3 bg-industrial-850 border-b border-industrial-800 text-sm flex-shrink-0">
      <div class="flex items-center space-x-3">
        <span class="text-slate-400">当前排样俯视图:</span>
        <span class="font-bold text-white text-base font-mono">
          包装 #{{ String(pkg?.package_id || 0).padStart(2, '0') }}
        </span>
        <span class="px-2.5 py-0.5 rounded text-xs bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
          {{ pkg?.room_id }}
        </span>
        <span class="text-xs text-slate-400 font-mono">
          外包尺寸: {{ pkg?.bounding_box.length }} × {{ pkg?.bounding_box.width }} × {{ pkg?.bounding_box.height }} mm
        </span>
      </div>

      <!-- 层级切换选项卡 -->
      <div class="flex items-center space-x-1.5 bg-industrial-950 p-1 rounded-lg border border-industrial-800">
        <button
          v-for="l in (pkg?.layers || 1)"
          :key="l - 1"
          @click="activeLayer = l - 1"
          :class="[
            'px-3.5 py-1 rounded text-xs font-semibold transition-all',
            activeLayer === l - 1
              ? 'bg-emerald-500 text-industrial-950 shadow-md shadow-emerald-500/20 font-bold'
              : 'text-slate-400 hover:text-slate-200'
          ]"
        >
          第 {{ l }} 层
        </button>
      </div>
    </div>

    <!-- 画布渲染区域 (Flex 自动完美居中，彻底杜绝向下位移) -->
    <div ref="containerRef" class="flex-1 w-full h-full min-h-0 overflow-hidden relative flex items-center justify-center p-6 bg-industrial-950/90">
      <canvas ref="canvasRef" class="rounded-lg shadow-2xl bg-industrial-950"></canvas>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue';
import type { PackageVo, PlacedBoardVo } from '../types/packing';

const props = defineProps<{
  pkg: PackageVo | null;
  highlightBarcode: string | null;
}>();

const activeLayer = ref(0);
const containerRef = ref<HTMLDivElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);
let resizeObserver: ResizeObserver | null = null;

// 当扫码匹配到特定板材时，自动切换到该板所在的层
watch(() => props.highlightBarcode, (code: string | null) => {
  if (!code || !props.pkg) return;
  const target = props.pkg.boards.find((b: PlacedBoardVo) => b.barcode === code || b.board_id === code);
  if (target) {
    activeLayer.value = target.layer;
  }
});

// 监听包装箱切换，重置到第 0 层
watch(() => props.pkg?.package_id, () => {
  activeLayer.value = 0;
});

const renderCanvas = () => {
  const canvas = canvasRef.value;
  const container = containerRef.value;
  if (!canvas || !container || !props.pkg) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const rect = container.getBoundingClientRect();
  const padding = 40;
  const availW = Math.max(10, rect.width - padding * 2);
  const availH = Math.max(10, rect.height - padding * 2);

  const bbox = props.pkg.bounding_box;
  if (!bbox || bbox.length <= 0 || bbox.width <= 0) return;

  // 1. 计算等比缩放因子
  const scale = Math.min(availW / bbox.length, availH / bbox.width);
  const drawW = Math.max(10, Math.floor(bbox.length * scale));
  const drawH = Math.max(10, Math.floor(bbox.width * scale));

  // 2. 适配高清屏分辨率 (解决模糊并锁定物理像素)
  const dpr = window.devicePixelRatio || 1;
  canvas.width = drawW * dpr;
  canvas.height = drawH * dpr;
  canvas.style.width = `${drawW}px`;
  canvas.style.height = `${drawH}px`;

  // 重置变换矩阵并应用高清缩放
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, drawW, drawH);

  // 3. 绘制外包围盒虚线底框 (以 0,0 为原点)
  ctx.strokeStyle = '#4b5563';
  ctx.lineWidth = 1.5;
  ctx.setLineDash([6, 6]);
  ctx.strokeRect(0.5, 0.5, drawW - 1, drawH - 1);
  ctx.setLineDash([]);

  // 4. 若不在底层，绘制下一层的半透明实体虚影 (用于现场对齐支撑率检查)
  if (activeLayer.value > 0) {
    const lowerBoards = props.pkg.boards.filter((b: PlacedBoardVo) => b.layer === activeLayer.value - 1);
    ctx.fillStyle = 'rgba(55, 65, 81, 0.35)';
    ctx.strokeStyle = 'rgba(75, 85, 99, 0.5)';
    ctx.lineWidth = 1;

    for (const lb of lowerBoards) {
      const bx = lb.x * scale;
      const by = lb.y * scale;
      const bw = lb.length * scale;
      const bh = lb.width * scale;
      ctx.fillRect(bx, by, bw, bh);
      ctx.strokeRect(bx, by, bw, bh);
    }
  }

  // 5. 绘制当前操作层的实体板件
  const currentBoards = props.pkg.boards.filter((b: PlacedBoardVo) => b.layer === activeLayer.value);

  for (const b of currentBoards) {
    const bx = b.x * scale;
    const by = b.y * scale;
    const bw = b.length * scale;
    const bh = b.width * scale;
    const isTarget = props.highlightBarcode && (b.barcode === props.highlightBarcode || b.board_id === props.highlightBarcode);

    if (isTarget) {
      ctx.fillStyle = 'rgba(16, 185, 129, 0.9)'; // 扫码命中：高亮鲜绿
      ctx.strokeStyle = '#34d399';
      ctx.lineWidth = 2.5;
    } else if (b.is_scanned) {
      ctx.fillStyle = 'rgba(5, 150, 105, 0.5)'; // 已入箱：就位绿
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 1.5;
    } else {
      ctx.fillStyle = 'rgba(30, 41, 59, 0.85)'; // 待装：工业深灰
      ctx.strokeStyle = '#64748b';
      ctx.lineWidth = 1.5;
    }

    ctx.fillRect(bx, by, bw, bh);
    ctx.strokeRect(bx, by, bw, bh);

    // 绘制板材名称与规格文本 (自动截断防止溢出)
    ctx.save();
    ctx.beginPath();
    ctx.rect(bx, by, bw, bh);
    ctx.clip();

    ctx.fillStyle = isTarget ? '#ffffff' : (b.is_scanned ? '#a7f3d0' : '#e2e8f0');
    const fontSize = Math.max(10, Math.min(13, Math.floor(bh / 3)));
    ctx.font = `600 ${fontSize}px Inter, system-ui, sans-serif`;
    ctx.fillText(`${b.name}`, bx + 8, by + fontSize + 6);

    ctx.fillStyle = isTarget ? '#ffffff' : '#94a3b8';
    ctx.font = `${Math.max(9, fontSize - 2)}px monospace`;
    ctx.fillText(`${b.length}×${b.width}×${b.thickness}mm`, bx + 8, by + fontSize * 2 + 10);

    if (b.is_rotated) {
      ctx.fillStyle = '#fbbf24';
      ctx.fillText('↻ 旋转90°', bx + bw - 65, by + fontSize + 6);
    }
    ctx.restore();
  }
};

watch([() => props.pkg, () => props.highlightBarcode, activeLayer], () => {
  nextTick(renderCanvas);
}, { deep: true });

onMounted(() => {
  nextTick(() => {
    renderCanvas();
    if (containerRef.value) {
      resizeObserver = new ResizeObserver(() => renderCanvas());
      resizeObserver.observe(containerRef.value);
    }
  });
});

onUnmounted(() => {
  if (resizeObserver) {
    resizeObserver.disconnect();
  }
});
</script>