/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 主色调 — 微软蓝偏深，专业克制
        primary: {
          50: '#f0f7ff',
          100: '#d6eaff',
          200: '#add5ff',
          300: '#7abaff',
          400: '#4799eb',
          500: '#0066cc',
          600: '#0052a3',
          700: '#003d7a',
          800: '#002952',
          900: '#001429',
        },
        // 表面/背景色
        surface: {
          50: '#ffffff',
          100: '#fafafa',
          200: '#f5f5f7',
          300: '#f2f2f7',
          400: '#e8e8ed',
          500: '#e5e5ea',
          600: '#d2d2d7',
          700: '#aeaeb2',
          800: '#86868b',
          900: '#1d1d1f',
        },
        // 功能色
        success: {
          50: '#eaf9f0',
          100: '#c8f0d5',
          200: '#a3e6ba',
          300: '#7ddb9f',
          400: '#58d184',
          500: '#34c759',
          600: '#28a745',
          700: '#1e7e34',
          800: '#145523',
          900: '#0a2c11',
        },
        warning: {
          50: '#fff4e5',
          100: '#ffe3bf',
          200: '#ffd199',
          300: '#ffbf73',
          400: '#ffad4d',
          500: '#ff9500',
          600: '#cc7700',
          700: '#995900',
          800: '#663b00',
          900: '#331e00',
        },
        error: {
          50: '#ffebea',
          100: '#ffc7c4',
          200: '#ffa39e',
          300: '#ff7f78',
          400: '#ff5b52',
          500: '#ff3b30',
          600: '#cc2f26',
          700: '#99231d',
          800: '#661813',
          900: '#330c0a',
        },
        info: {
          50: '#e5f2ff',
          100: '#bfdeff',
          200: '#99c9ff',
          300: '#73b5ff',
          400: '#4da0ff',
          500: '#007aff',
          600: '#0062cc',
          700: '#004999',
          800: '#003166',
          900: '#001833',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['Fira Code', 'monospace'],
      },
      borderRadius: {
        'xl': '1rem',
        '2xl': '1.5rem',
      },
      boxShadow: {
        'subtle': '0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06)',
        'card': '0 2px 8px rgba(0, 0, 0, 0.04), 0 4px 16px rgba(0, 0, 0, 0.04)',
        'elevated': '0 4px 16px rgba(0, 0, 0, 0.06), 0 8px 32px rgba(0, 0, 0, 0.06)',
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'slide-down': 'slideDown 0.3s ease-out',
        'spin-slow': 'spin 3s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        slideDown: {
          '0%': { transform: 'translateY(-20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
  corePlugins: {
    preflight: false, // 禁用预加载样式，避免与Ant Design冲突
  },
}
