<template>
  <div class="relative w-full h-full flex flex-col bg-industrial-900 rounded-xl overflow-hidden shadow-2xl border border-industrial-800">
    <!-- 顶部排样控制器 -->
    <div class="flex items-center justify-between px-5 py-3 bg-industrial-850 border-b border-industrial-800 text-sm">
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

    <!-- 画布渲染区域 -->
    <div ref="containerRef" class="flex-1 relative flex items-center justify-center p-6 bg-industrial-950/80">
      <canvas ref="canvasRef" class="rounded-lg border border-industrial-800 shadow-2xl bg-industrial-950"></canvas>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import type { PackageVo, PlacedBoardVo } from '../types/packing';

const props = defineProps<{
  pkg: PackageVo | null;
  highlightBarcode: string | null;
}>();

const activeLayer = ref(0);
const containerRef = ref<HTMLDivElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);

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

  const bbox = props.pkg.bounding_box;
  const padding = 50;
  const availW = container.clientWidth - padding * 2;
  const availH = container.clientHeight - padding * 2;

  // 坐标高保真等比缩放 (毫米 -> 屏幕像素)
  const scale = Math.min(availW / bbox.length, availH / bbox.width);
  const drawW = bbox.length * scale;
  const drawH = bbox.width * scale;

  canvas.width = container.clientWidth;
  canvas.height = container.clientHeight;
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const startX = (canvas.width - drawW) / 2;
  const startY = (canvas.height - drawH) / 2;

  // 1. 绘制包围盒虚线外框 (Bounding Box)
  ctx.strokeStyle = '#4b5563';
  ctx.lineWidth = 1.5;
  ctx.setLineDash([8, 6]);
  ctx.strokeRect(startX, startY, drawW, drawH);
  ctx.setLineDash([]);

  // 2. 若不在底层，渲染下层板件半透明虚影 (供工人核对实体支撑)
  if (activeLayer.value > 0) {
    const lowerBoards = props.pkg.boards.filter((b: PlacedBoardVo) => b.layer === activeLayer.value - 1);
    ctx.fillStyle = 'rgba(55, 65, 81, 0.35)';
    ctx.strokeStyle = 'rgba(75, 85, 99, 0.5)';
    ctx.lineWidth = 1;

    for (const lb of lowerBoards) {
      const bx = startX + lb.x * scale;
      const by = startY + lb.y * scale;
      const bw = lb.length * scale;
      const bh = lb.width * scale;
      ctx.fillRect(bx, by, bw, bh);
      ctx.strokeRect(bx, by, bw, bh);
    }
  }

  // 3. 绘制当前操作层的实体板材
  const currentBoards = props.pkg.boards.filter((b: PlacedBoardVo) => b.layer === activeLayer.value);

  for (const b of currentBoards) {
    const bx = startX + b.x * scale;
    const by = startY + b.y * scale;
    const bw = b.length * scale;
    const bh = b.width * scale;
    const isTarget = props.highlightBarcode && (b.barcode === props.highlightBarcode || b.board_id === props.highlightBarcode);

    if (isTarget) {
      // 当前扫码命中：荧光绿高亮
      ctx.fillStyle = 'rgba(16, 185, 129, 0.85)';
      ctx.strokeStyle = '#34d399';
      ctx.lineWidth = 3;
    } else if (b.is_scanned) {
      // 历史已扫码入箱：深绿微光
      ctx.fillStyle = 'rgba(5, 150, 105, 0.45)';
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = 1.5;
    } else {
      // 待扫码就位：工业深灰蓝
      ctx.fillStyle = 'rgba(31, 41, 55, 0.85)';
      ctx.strokeStyle = '#6b7280';
      ctx.lineWidth = 1.5;
    }

    ctx.fillRect(bx, by, bw, bh);
    ctx.strokeRect(bx, by, bw, bh);

    // 绘制板材名称与规格文本
    ctx.fillStyle = isTarget ? '#ffffff' : (b.is_scanned ? '#a7f3d0' : '#e2e8f0');
    ctx.font = `600 ${Math.max(11, Math.min(13, bw / 12))}px Inter, system-ui`;
    ctx.fillText(`${b.name}`, bx + 8, by + 20);

    ctx.fillStyle = isTarget ? '#ffffff' : '#94a3b8';
    ctx.font = '10px monospace';
    ctx.fillText(`${b.length}×${b.width}×${b.thickness}mm`, bx + 8, by + 34);

    // 旋转标识
    if (b.is_rotated) {
      ctx.fillStyle = '#fbbf24';
      ctx.fillText('↻ 旋转90°', bx + bw - 60, by + 20);
    }
  }
};

watch([() => props.pkg, () => props.highlightBarcode, activeLayer], renderCanvas, { deep: true });
onMounted(() => {
  window.addEventListener('resize', renderCanvas);
  renderCanvas();
});
onUnmounted(() => window.removeEventListener('resize', renderCanvas));
</script>