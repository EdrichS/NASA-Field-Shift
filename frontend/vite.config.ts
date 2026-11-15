import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Fixed port: Auth0 callback URLs and backend CORS expect 5173.
    port: 5173,
    strictPort: true,
    // The Cloudflare Quick Tunnel serves this dev server on a random *.trycloudflare.com host.
    allowedHosts: ['.trycloudflare.com'],
    // The app calls /api/...; the dev server forwards it to FastAPI, so one tunnel (one origin)
    // serves both the app and the API and the browser never needs CORS.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
