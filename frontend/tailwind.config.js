/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        industrial: {
          950: '#0b0f19',
          900: '#111827',
          850: '#161f33',
          800: '#1f2937',
          700: '#374151',
          600: '#4b5563',
        },
      },
    },
  },
  plugins: [],
}