import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  appType: 'spa',
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@api': path.resolve(__dirname, './src/api'),
      '@components': path.resolve(__dirname, './src/components'),
      '@hooks': path.resolve(__dirname, './src/hooks'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@services': path.resolve(__dirname, './src/services'),
      '@store': path.resolve(__dirname, './src/store'),
      '@styles': path.resolve(__dirname, './src/styles'),
      '@types': path.resolve(__dirname, './src/types'),
      '@utils': path.resolve(__dirname, './src/utils'),
    },
  },
  server: {
    port: 3000,
    host: true,
    strictPort: true,
    proxy: {
      '/api/v1/users': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/comments': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/works': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/cases': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/credits': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/recommendations': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/search': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/ws': {
        target: 'http://localhost:9080',
        changeOrigin: true,
        ws: true,
      },
      '/api/v1/scripts': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/storyboard': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/characters': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/scenes': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/assets': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/render': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
      '/api/v1/videos': {
        target: 'http://localhost:9080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          ui: ['antd', '@ant-design/icons'],
          state: ['@reduxjs/toolkit', 'react-redux', 'zustand'],
          utils: ['axios', 'dayjs', 'lodash-es'],
        },
      },
    },
  },
})