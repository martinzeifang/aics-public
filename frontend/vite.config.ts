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

  server: {
    port: 5173,
    strictPort: false,
    https: https,
    proxy: {
      '/api': {
        target: 'https://localhost:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api'),
        secure: false, // Allow self-signed certificates
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
        manualChunks: {
          'vue': ['vue'],
          'vendors': ['pinia', 'axios']
        }
      }
    }
  }
})
