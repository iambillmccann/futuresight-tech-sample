/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        panel: '#f5f5f5',
        brand: '#5b4ad9',
        accent: '#dfe7ff',
        success: '#1f9d67',
        warning: '#f7d57a',
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
