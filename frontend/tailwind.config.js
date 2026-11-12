/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: '#172554',
        indigo: {
          50: '#EEF2FF',
          100: '#E0E7FF',
          500: '#6366F1',
          600: '#4F46E5',
          700: '#4338CA',
        },
        teal: {
          50: '#F0FDFA',
          500: '#14B8A6',
          600: '#0D9488',
          700: '#0F766E',
        },
        app: {
          bg: 'rgb(var(--bg-app) / <alpha-value>)',
          sidebar: 'rgb(var(--bg-sidebar) / <alpha-value>)',
          surface: 'rgb(var(--bg-surface) / <alpha-value>)',
          muted: 'rgb(var(--bg-surface-muted) / <alpha-value>)',
          border: 'rgb(var(--border-subtle) / <alpha-value>)',
          'border-strong': 'rgb(var(--border-strong) / <alpha-value>)',
          text: 'rgb(var(--text-primary) / <alpha-value>)',
          'text-secondary': 'rgb(var(--text-secondary) / <alpha-value>)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        heading: ['Manrope', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        subtle: '0 1px 2px 0 rgb(15 23 42 / 0.04)',
        card: '0 1px 3px 0 rgb(15 23 42 / 0.06), 0 1px 2px -1px rgb(15 23 42 / 0.04)',
      },
    },
  },
  plugins: [],
}

