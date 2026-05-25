import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const frontendPort = Number(process.env.FRONTEND_PORT || 5173);

export default defineConfig({
  plugins: [react()],
  server: {
    port: frontendPort,
    strictPort: true,
    proxy: {
      '/api': {
        target: process.env.CHATBOT_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ingestion-api': {
        target: process.env.INGESTION_API_URL || 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ingestion-api/, '/api'),
      },
      '/health': {
        target: process.env.CHATBOT_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
