import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development Vite serves the UI and forwards API calls to Django.
const backend = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';
// Keep the browser's host, like Nginx does on the server: Django builds the Marketian sign-in
// and sign-out return addresses from it.
const toBackend = { target: backend, changeOrigin: false };

export default defineConfig({
  plugins: [react()],
  server: {
    host: process.env.VITE_HOST || '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': toBackend,
      '/admin': toBackend,
      '/accounts': toBackend,
      '/static': toBackend,
    },
  },
  build: { outDir: 'dist', sourcemap: false },
});
