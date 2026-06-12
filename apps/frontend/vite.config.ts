import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  define: {
    // In production, API_BASE defaults to '' (same-origin via Nginx/CDN rewrite).
    // Override with VITE_API_BASE env var if backend is on a different domain.
    __API_BASE__: JSON.stringify(process.env.VITE_API_BASE ?? ''),
  },
})
