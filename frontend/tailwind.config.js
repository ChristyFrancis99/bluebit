/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'sans-serif'],
        display: ['Syne', 'sans-serif'],
        mono: ['DM Mono', 'monospace'],
      },
      colors: {
        navy: { DEFAULT: '#0a0f1e', 2: '#0f1729', 3: '#162040', 4: '#1e2d54' },
        cyan: { DEFAULT: '#00d4ff', dim: '#0099cc' },
      },
    },
  },
  plugins: [],
}
