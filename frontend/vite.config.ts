/// <reference types="vitest/config" />
import { createHash } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

// Legt beim Bauen dist/sw.js aus sw.template.js an. Die Version ist ein Hash über alle
// gebauten Dateien und den Ordner public: ändert sich etwas, gibt es einen neuen Service
// Worker, und die App bietet "Neu laden" an.
function serviceWorker(): Plugin {
  return {
    name: 'fintrack-service-worker',
    apply: 'build',
    generateBundle(_, bundle) {
      const hash = createHash('sha256');
      for (const name of Object.keys(bundle).sort()) hash.update(name);
      for (const name of readdirSync('public').sort()) hash.update(name).update(readFileSync(`public/${name}`));
      const template = readFileSync('sw.template.js', 'utf8');
      hash.update(template);
      this.emitFile({ type: 'asset', fileName: 'sw.js', source: template.replace("'__VERSION__'", `'${hash.digest('hex').slice(0, 12)}'`) });
    },
  };
}

// Das Frontend läuft unter /app (Flask leitet / dorthin weiter).
// Im Dev-Server leitet Vite /api an Flask weiter. Der Host-Header bleibt dabei unverändert,
// damit Origin und Host übereinstimmen und der Cross-Site-Schutz von Flask nicht anschlägt.
export default defineConfig({
  base: '/app/',
  plugins: [react(), serviceWorker()],
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
    // Bibliotheken in eine eigene Datei: sie ändert sich bei einem normalen Deploy nicht und
    // bleibt im Browser-Cache, neu geladen wird nur der eigene Code
    rolldownOptions: {
      output: {
        codeSplitting: { groups: [{ name: 'vendor', test: /node_modules[\\/](react|react-dom|react-router|scheduler|@tanstack)[\\/]/ }] },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
  },
});
