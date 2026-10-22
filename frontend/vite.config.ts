import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  worker: { format: 'es' }, // MapLibre starts its worker as a module worker
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
