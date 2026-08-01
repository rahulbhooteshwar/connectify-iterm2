import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The build lands in ../static, which FastAPI mounts at /static and PyInstaller
// bundles into the binary - so the server, installer and release workflow all
// stay exactly as they are. base makes every asset URL resolve under /static/
// even though the page itself is served from /.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/static/',
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  // `tasks.py ui-dev` serves the app from Vite and talks to a backend started
  // with `tasks.py ui`, so the API has to be reachable under the same origin
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:7860',
    },
  },
})
