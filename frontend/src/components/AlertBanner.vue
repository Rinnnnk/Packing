<template>
  <transition
    enter-active-class="transform ease-out duration-300 transition"
    enter-from-class="translate-y-[-20px] opacity-0"
    enter-to-class="translate-y-0 opacity-100"
    leave-active-class="transition ease-in duration-200"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="visible"
      :class="[
        'p-4 rounded-xl border flex items-center justify-between shadow-2xl transition-all',
        type === 'ERROR'
          ? 'bg-rose-950/95 border-rose-600 text-rose-100 animate-pulse'
          : 'bg-emerald-950/95 border-emerald-500 text-emerald-100'
      ]"
    >
      <div class="flex items-center space-x-3">
        <span class="text-2xl">{{ type === 'ERROR' ? '🚨' : '✅' }}</span>
        <div>
          <h4 class="font-bold text-sm leading-tight">{{ title }}</h4>
          <p class="text-xs opacity-90 mt-0.5">{{ message }}</p>
        </div>
      </div>

      <button
        @click="$emit('close')"
        class="px-3 py-1 rounded-lg bg-black/30 hover:bg-black/50 text-xs font-semibold transition-colors"
      >
        知道了
      </button>
    </div>
  </transition>
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