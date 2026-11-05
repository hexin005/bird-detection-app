import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // 由 FastAPI 挂载在 /scene 下，构建产物用相对路径
  base: './',
  plugins: [vue()],
  server: {
    port: 5180,
    proxy: {
      // 开发时把 API / WebSocket 转发到后端
      '/api': { target: 'http://127.0.0.1:8008', ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
  },
})
