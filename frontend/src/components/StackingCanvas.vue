<template>
  <div class="relative w-full h-full flex flex-col bg-[#14161f]/75 backdrop-blur-2xl rounded-2xl overflow-hidden border border-white/[0.08] shadow-glass-md">
    <!-- 顶部状态栏 -->
    <div class="flex items-center justify-between px-6 py-3 bg-white/[0.02] border-b border-white/[0.06] text-xs flex-shrink-0">
      <div class="flex items-center space-x-3">
        <span class="text-apple-secondary font-medium">排样俯视图:</span>
        <span class="font-black text-apple-ink text-sm font-mono">
          包装 #{{ String(pkg?.package_id || 0).padStart(2, '0') }}
        </span>
        <span class="px-2.5 py-0.5 rounded-md text-[11px] bg-apple-blue/15 text-apple-blue border border-apple-blue/30 font-bold font-mono">
          {{ pkg?.room_id }}
        </span>
        <span class="text-[11px] text-apple-secondary font-mono">
          外包尺寸: {{ pkg?.bounding_box.length }} × {{ pkg?.bounding_box.width }} × {{ pkg?.bounding_box.height }} mm
        </span>
      </div>

      <!-- iOS 胶囊分层切换器 -->
      <div class="flex items-center bg-black/40 p-1 rounded-xl border border-white/[0.06]">
        <button
          v-for="l in (pkg?.layers || 1)"
          :key="l - 1"
          @click="activeLayer = l - 1"
          :class="[
            'px-4 py-1 rounded-lg text-xs font-semibold transition-all duration-200',
            activeLayer === l - 1
              ? 'bg-apple-blue text-white shadow-md shadow-apple-blue/30 font-bold'
              : 'text-apple-secondary hover:text-apple-ink'
          ]"
        >
          第 {{ l }} 层
        </button>
      </div>
    </div>

    <!-- 2D 画布视口区域 -->
    <div
      ref="containerRef"
      class="flex-1 w-full h-full min-h-0 overflow-hidden relative flex items-center justify-center p-8 bg-[#0b0c10] [background-image:radial-gradient(#252936_1.5px,transparent_1.5px)] [background-size:18px_18px]"
    >
      <canvas ref="canvasRef" class="shadow-glass-lg bg-[#151720] ring-1 ring-white/[0.08]"></canvas>
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

watch(() => props.highlightBarcode, (code) => {
  if (!code || !props.pkg) return;
  const target = props.pkg.boards.find(b => b.barcode === code || b.board_id === code);
  if (target) activeLayer.value = target.layer;
});

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
  const padding = 48;
  const availW = Math.max(10, rect.width - padding * 2);
  const availH = Math.max(10, rect.height - padding * 2);

  const bbox = props.pkg.bounding_box;
  if (!bbox || bbox.length <= 0 || bbox.width <= 0) return;

  const scale = Math.min(availW / bbox.length, availH / bbox.width);
  const drawW = Math.max(10, Math.floor(bbox.length * scale));
  const drawH = Math.max(10, Math.floor(bbox.width * scale));

  const dpr = window.devicePixelRatio || 1;
  canvas.width = drawW * dpr;
  canvas.height = drawH * dpr;
  canvas.style.width = `${drawW}px`;
  canvas.style.height = `${drawH}px`;

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, drawW, drawH);

  // 1. 绘制包围盒外虚线框（直角）
  ctx.strokeStyle = '#3e4454';
  ctx.lineWidth = 1.5;
  ctx.setLineDash([6, 6]);
  ctx.strokeRect(0.5, 0.5, drawW - 1, drawH - 1);
  ctx.setLineDash([]);

  // 2. 下层实体半透明虚影（Blueprint 深蓝灰直角）
  if (activeLayer.value > 0) {
    const lowerBoards = props.pkg.boards.filter(b => b.layer === activeLayer.value - 1);
    ctx.fillStyle = 'rgba(10, 132, 255, 0.12)';
    ctx.strokeStyle = 'rgba(10, 132, 255, 0.35)';
    ctx.lineWidth = 1;

    for (const lb of lowerBoards) {
      const bx = lb.x * scale;
      const by = lb.y * scale;
      const bw = lb.length * scale;
      const bh = lb.width * scale;
      ctx.fillRect(bx, by, bw, bh);
      ctx.strokeRect(bx + 0.5, by + 0.5, bw - 1, bh - 1);
    }
  }

  // 3. 绘制当前操作层板件（标准 90 度直角）
  const currentBoards = props.pkg.boards.filter(b => b.layer === activeLayer.value);

  for (const b of currentBoards) {
    const bx = b.x * scale;
    const by = b.y * scale;
    const bw = b.length * scale;
    const bh = b.width * scale;
    const isTarget = props.highlightBarcode && (b.barcode === props.highlightBarcode || b.board_id === props.highlightBarcode);

    if (isTarget) {
      ctx.fillStyle = 'rgba(48, 209, 88, 0.32)';
      ctx.strokeStyle = '#30d158';
      ctx.lineWidth = 2.5;
    } else if (b.is_scanned) {
      ctx.fillStyle = 'rgba(48, 209, 88, 0.16)';
      ctx.strokeStyle = '#30d158';
      ctx.lineWidth = 1.5;
    } else {
      ctx.fillStyle = '#232733';
      ctx.strokeStyle = '#4a5166';
      ctx.lineWidth = 1.5;
    }

    // 绘制直角矩形
    ctx.beginPath();
    ctx.rect(bx + 0.5, by + 0.5, bw - 1, bh - 1);
    ctx.fill();
    ctx.stroke();

    // 智能排版引擎：长窄件纵向自适应旋转 + 宽大板件横排
    ctx.save();
    ctx.beginPath();
    ctx.rect(bx + 1, by + 1, bw - 2, bh - 2);
    ctx.clip();

    const isVerticalStrip = (bw < 60 && bh >= 70);

    if (isVerticalStrip) {
      ctx.translate(bx + bw / 2, by + bh / 2);
      ctx.rotate(Math.PI / 2);

      const vWid = bw;
      const fontSize = Math.max(9, Math.min(11, Math.floor(vWid / 2.2)));

      ctx.fillStyle = isTarget ? '#ffffff' : (b.is_scanned ? '#a7f3d0' : '#f5f5f7');
      ctx.font = `600 ${fontSize}px -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'bottom';
      ctx.fillText(b.name, 0, -1);

      ctx.fillStyle = isTarget ? '#a7f3d0' : (b.is_scanned ? '#30d158' : '#98989d');
      ctx.font = `${Math.max(8, fontSize - 2)}px monospace`;
      ctx.textBaseline = 'top';
      ctx.fillText(`${b.length}×${b.width}mm`, 0, 1);
    } else {
      const fontSize = Math.max(9, Math.min(12, Math.floor(bh / 3.2)));
      ctx.fillStyle = isTarget ? '#ffffff' : (b.is_scanned ? '#a7f3d0' : '#f5f5f7');
      ctx.font = `600 ${fontSize}px -apple-system, BlinkMacSystemFont, "SF Pro Text", Inter, sans-serif`;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'alphabetic';

      let displayName = b.name;
      const maxTextWidth = bw - 16;
      if (ctx.measureText(displayName).width > maxTextWidth) {
        while (displayName.length > 4 && ctx.measureText(displayName + '…').width > maxTextWidth) {
          displayName = displayName.slice(0, -1);
        }
        displayName += '…';
      }

      ctx.fillText(displayName, bx + 8, by + fontSize + 6);

      ctx.fillStyle = isTarget ? '#a7f3d0' : (b.is_scanned ? '#30d158' : '#98989d');
      ctx.font = `${Math.max(8, fontSize - 2)}px monospace`;
      ctx.fillText(`${b.length}×${b.width}×${b.thickness}mm`, bx + 8, by + fontSize * 2 + 9);

      if (b.is_rotated) {
        ctx.fillStyle = '#ff9f0a';
        ctx.font = `${Math.max(8, fontSize - 2)}px sans-serif`;
        ctx.fillText('↻90°', bx + bw - 35, by + fontSize + 6);
      }
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
  if (resizeObserver) resizeObserver.disconnect();
});
</script>