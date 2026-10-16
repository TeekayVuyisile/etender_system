import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Bind to IPv4 explicitly; some browsers/tools can't reach Vite's default IPv6-only localhost.
    host: '127.0.0.1',
    // Forward /api/* requests to the FastAPI backend, so the frontend can call
    // fetch('/api/health') without hard-coding the backend's address.
    proxy: {
      // Trailing slash: only real API calls, not app pages that happen to start with /api.
      '/api/': backend,
      // Swagger UI and its schema, so the "API docs" link works in development.
      '/docs': backend,
      '/openapi.json': backend,
    },
  },
})
