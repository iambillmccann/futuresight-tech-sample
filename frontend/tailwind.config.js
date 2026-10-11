const themed = (name) => `rgb(var(--color-${name}) / <alpha-value>)`
const scale = (name, shades) =>
  Object.fromEntries(shades.map((shade) => [shade, themed(`${name}-${shade}`)]))

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // Colors resolve to CSS variables in src/index.css, which switch with the
      // operating system's prefers-color-scheme setting.
      colors: {
        canvas: themed('canvas'),
        surface: themed('surface'),
        slate: scale('slate', [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]),
        amber: scale('amber', [50, 200, 700, 800]),
        rose: scale('rose', [50, 100, 200, 700]),
        emerald: scale('emerald', [700]),
        panel: '#f5f5f5',
        brand: {
          DEFAULT: themed('brand'),
          strong: themed('brand-strong'),
          soft: themed('brand-soft'),
          ink: themed('brand-ink'),
          contrast: themed('brand-contrast'),
        },
        accent: '#dfe7ff',
        success: '#1f9d67',
        warning: {
          DEFAULT: themed('warning'),
          soft: themed('warning-soft'),
          ink: themed('warning-ink'),
        },
        star: themed('star'),
        border: '#e5e7eb',
        ink: '#1f2937',
      },
      boxShadow: {
        soft: '0 1px 3px rgba(15, 23, 42, 0.08)',
      },
    },
  },
  plugins: [],
}
