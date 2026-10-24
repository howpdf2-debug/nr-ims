import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // The UI calls /nrims-api/v1/... (see src/lib/api.ts); in dev the same mapping nginx does in production.
      '/nrims-api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        rewrite: (path: string) => path.replace(/^\/nrims-api/, '/api'),
      },
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes('node_modules')) return undefined
          if (/[\\/](react|react-dom|react-router|react-router-dom)[\\/]/.test(id)) return 'vendor-react'
          if (/[\\/](echarts|echarts-for-react|zrender)[\\/]/.test(id)) return 'vendor-charts'
          if (id.includes('reactflow')) return 'vendor-flow'
          if (id.includes('@tanstack')) return 'vendor-query'
          return undefined
        },
      },
    },
  },
})