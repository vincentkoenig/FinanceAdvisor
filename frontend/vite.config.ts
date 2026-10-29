/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Das neue Frontend läuft während des Umbaus unter /app, die alten Seiten bleiben unter /.
// Im Dev-Server leitet Vite /api an Flask weiter. Der Host-Header bleibt dabei unverändert,
// damit Origin und Host übereinstimmen und der Cross-Site-Schutz von Flask nicht anschlägt.
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  server: {
    port: 5280,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5000', changeOrigin: false },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
  },
});
