import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

function readPortSettings() {
  const defaults = { webPort: 5173, backendPort: 8080 }
  const settingsPath = path.resolve(__dirname, '..', 'data', 'settings.json')

  if (!fs.existsSync(settingsPath)) {
    return defaults
  }

  try {
    const payload = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'))
    const webPort = Number.isInteger(payload?.web_port) && payload.web_port >= 1 && payload.web_port <= 65535
      ? payload.web_port
      : defaults.webPort
    const backendPort = Number.isInteger(payload?.backend_port) && payload.backend_port >= 1 && payload.backend_port <= 65535
      ? payload.backend_port
      : defaults.backendPort
    return { webPort, backendPort }
  } catch {
    return defaults
  }
}

const ports = readPortSettings()

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: ports.webPort,
    proxy: {
      '/api': `http://127.0.0.1:${ports.backendPort}`
    }
  }
})
