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
  // Pre-bundle the heavy dependencies so the first page load never re-optimizes
  // (a re-optimization briefly loads two copies of React).
  optimizeDeps: {
    include: [
      'react',
      'react-dom/client',
      'motion/react',
      'three',
      '@react-three/fiber',
      '@react-three/drei',
      '@tanstack/react-query',
      'lucide-react',
      'clsx',
    ],
  },
  build: {
    chunkSizeWarningLimit: 1500,
  },
})
