import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/deepseek/',
  plugins: [vue()],
  server: {
    port: 5178,
    proxy: {
      '/api': 'http://127.0.0.1:8000'
    }
  }
})
