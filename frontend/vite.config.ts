import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'

// Check if HTTPS certificates exist, if not use HTTP
let https = false
const certPath = path.resolve(__dirname, '../certs/certificate.crt')
const keyPath = path.resolve(__dirname, '../certs/private.key')

if (fs.existsSync(certPath) && fs.existsSync(keyPath)) {
  https = {
    cert: fs.readFileSync(certPath),
    key: fs.readFileSync(keyPath),
  }
}

export default defineConfig({
  plugins: [vue()],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  // #746: Dieser `server`-Block (inkl. Dev-Proxy) gilt AUSSCHLIESSLICH für den
  // lokalen Vite-Dev-Server (`vite dev`). In Produktion wird der statische
  // `dist/`-Build ausgeliefert/hinter nginx gestellt — dieser Proxy ist dort
  // nicht aktiv. `secure: false` (s.u.) ist daher rein localhost-only.
  server: {
    port: 5173,
    strictPort: false,
    https: https,
    proxy: {
      '/api': {
        // Ziel ist immer localhost (lokaler Backend-Dev-Server).
        target: 'https://localhost:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api'),
        // secure:false akzeptiert das selbstsignierte Dev-Zertifikat von
        // localhost:5000. NUR für die lokale Entwicklung — kein Produktionspfad.
        secure: false, // localhost-only: self-signed Dev-Cert zulassen
        timeout: 180000,         // 3 min (für Repo-Scan ~30s + Reserve)
        proxyTimeout: 180000,
      }
    }
  },

  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'terser',
    rollupOptions: {
      output: {
        // Funktions-Form statt Objekt-Form: kompatibel mit Rollup (vite 5) UND
        // dem Rolldown-Bundler (vite 8). Die Objekt-Form wirft unter vite 8
        // "manualChunks is not a function".
        manualChunks(id: string) {
          if (id.includes('/node_modules/vue/') || id.includes('/node_modules/@vue/')) return 'vue'
          if (id.includes('/node_modules/pinia') || id.includes('/node_modules/axios')) return 'vendors'
        }
      }
    }
  }
})
