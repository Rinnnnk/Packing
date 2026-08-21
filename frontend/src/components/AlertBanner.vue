<template>
  <div class="fixed top-20 right-8 z-50 flex flex-col space-y-2 pointer-events-none">
    <transition
      enter-active-class="transform ease-spring-out duration-300 transition"
      enter-from-class="translate-y-[-16px] opacity-0 scale-95"
      enter-to-class="translate-y-0 opacity-100 scale-100"
      leave-active-class="ease-in duration-200 transition"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="visible"
        :class="[
          'pointer-events-auto w-96 p-4 rounded-2xl border backdrop-blur-2xl shadow-glass-lg flex items-start space-x-3.5',
          type === 'ERROR'
            ? 'bg-[#22161a]/90 border-rose-500/30 text-rose-100'
            : 'bg-[#14231b]/90 border-emerald-500/30 text-emerald-100'
        ]"
      >
        <div :class="['w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5', type === 'ERROR' ? 'bg-rose-500/20 text-apple-red' : 'bg-emerald-500/20 text-apple-green']">
          <span class="text-sm font-bold">{{ type === 'ERROR' ? '✕' : '✓' }}</span>
        </div>
        <div class="flex-1 min-w-0">
          <h4 class="font-bold text-xs leading-tight tracking-wide text-apple-ink">{{ title }}</h4>
          <p class="text-xs text-apple-secondary mt-1 leading-relaxed break-words">{{ message }}</p>
        </div>
        <button
          @click="$emit('close')"
          class="flex-shrink-0 text-apple-secondary hover:text-white text-xs px-2.5 py-1 rounded-lg bg-white/[0.08] hover:bg-white/[0.15] transition-colors font-medium"
        >
          知道了
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean;
  type: 'SUCCESS' | 'ERROR';
  title: string;
  message: string;
}>();

defineEmits<{
  (e: 'close'): void;
}>();
</script>