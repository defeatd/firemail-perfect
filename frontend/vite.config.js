import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 从环境变量读取端口，默认为3000
const port = process.env.VITE_PORT ? parseInt(process.env.VITE_PORT) : 3000

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    cors: true,
    port,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://127.0.0.1:8765',
        ws: true
      }
    }
  }
})
