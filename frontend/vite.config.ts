import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev'de /api/* istekleri FastAPI'ye (8000) yönlenir; CORS ayarı gerekmez.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
