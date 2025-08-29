import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import tsconfigPaths from 'vite-tsconfig-paths'

// https://vite.dev/config/
export default defineConfig({
  plugins: [tsconfigPaths(), tanstackRouter({ target: 'react', autoCodeSplitting: true }), tailwindcss(), react()],
  server: {
    host: true,
    port: 8008
  }
})
