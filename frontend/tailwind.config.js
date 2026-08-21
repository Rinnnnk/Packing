/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        apple: {
          bg: '#0d0f14',                  // macOS 深度舞台底色
          surface: 'rgba(22, 24, 31, 0.75)', // 液态深色玻璃面板
          'surface-hover': 'rgba(32, 35, 46, 0.85)',
          'surface-active': '#222733',
          border: 'rgba(255, 255, 255, 0.08)',
          'border-light': 'rgba(255, 255, 255, 0.14)',
          ink: '#f5f5f7',                 // 视网膜纯白文字
          secondary: '#98989d',           // Apple 次级说明文字
          tertiary: '#636366',            // 占位/微弱提示
          blue: '#0a84ff',                // iOS Dark 官方系统蓝
          green: '#30d158',               // iOS Dark 官方系统绿
          amber: '#ff9f0a',               // iOS Dark 官方系统橙
          red: '#ff453a',                 // iOS Dark 官方系统红
        },
        obsidian: { 950: '#0d0f14' },
        industrial: { 950: '#0d0f14' }
      },
      boxShadow: {
        'glass-sm': '0 2px 8px -1px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.06), inset 0 1px 0 rgba(255, 255, 255, 0.1)',
        'glass-md': '0 8px 30px -4px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.12)',
        'glass-lg': '0 20px 50px -10px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(255, 255, 255, 0.1), inset 0 1px 1px rgba(255, 255, 255, 0.15)',
        'active-card': '0 12px 30px -4px rgba(10, 132, 255, 0.25), 0 0 0 1.5px #0a84ff, inset 0 1px 1px rgba(255, 255, 255, 0.2)',
      },
      transitionTimingFunction: {
        'spring-out': 'cubic-bezier(0.16, 1, 0.3, 1)',
      }
    },
  },
  plugins: [],
}