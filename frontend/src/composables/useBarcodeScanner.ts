import { onMounted, onUnmounted, ref } from 'vue';

/**
 * USB HID 扫码枪全局键盘事件拦截
 * 扫码枪特征：按键触发间隔极短 (通常 <= 30ms)，以 Enter 结束
 */
export function useBarcodeScanner(onScan: (barcode: string) => void) {
  let charBuffer = '';
  let lastKeyTimestamp = 0;
  const isGunActive = ref(false);

  const handleKeyDown = (e: KeyboardEvent) => {
    // 忽略所有无字符含义的控制键
    if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock', 'Tab', 'Escape'].includes(e.key)) {
      return;
    }

    const currentTimestamp = performance.now();
    const interval = currentTimestamp - lastKeyTimestamp;
    lastKeyTimestamp = currentTimestamp;

    if (e.key === 'Enter') {
      if (charBuffer.length >= 3) {
        onScan(charBuffer.trim());
      }
      charBuffer = '';
      isGunActive.value = false;
      return;
    }

    // 扫码枪判定阈值：按键间隔 <= 35ms
    if (interval <= 35 || charBuffer.length === 0) {
      charBuffer += e.key;
      isGunActive.value = true;
    } else {
      // 人工手动输入按键，重置缓冲区
      charBuffer = e.key;
      isGunActive.value = false;
    }
  };

  onMounted(() => window.addEventListener('keydown', handleKeyDown));
  onUnmounted(() => window.removeEventListener('keydown', handleKeyDown));

  return { isGunActive };
}