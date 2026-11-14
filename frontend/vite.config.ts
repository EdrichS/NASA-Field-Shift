import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Fixed port: Auth0 callback URLs and backend CORS expect 5173.
    port: 5173,
    strictPort: true,
  },
})
