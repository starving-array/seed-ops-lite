import { existsSync, readFileSync } from 'fs'
import { resolve } from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const landingPath = resolve(__dirname, 'public/index-landing.html')

export default defineConfig(({ mode }) => ({
  base: mode === 'production' ? '/app/' : '/',
  plugins: [
    react(),
    {
      name: 'landing-page',
      configureServer(server) {
        return () => {
          server.middlewares.use((req, res, next) => {
            const url = req.url ?? ''
            if (url.startsWith('/app')) {
              req.url = '/index.html'
              return next()
            }
            if (url === '/' || url === '' || url === '/index.html') {
              if (existsSync(landingPath)) {
                res.statusCode = 200
                res.setHeader('Content-Type', 'text/html')
                res.end(readFileSync(landingPath, 'utf-8'))
                return
              }
            }
            next()
          })
        }
      },
    },
  ],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        landing: landingPath,
      },
    },
  },
}))
