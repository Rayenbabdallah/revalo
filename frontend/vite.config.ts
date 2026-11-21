import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const api = process.env.REVALO_API_URL ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': { target: api, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
  build: {
    chunkSizeWarningLimit: 1500,
  },
})
