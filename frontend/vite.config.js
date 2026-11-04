import { defineConfig } from 'vite';

// Development proxy: the browser calls this Vite server, not the remote API.
// Production uses the Nginx proxy defined in the Dockerfile.
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api/admin/summary': {
        target: process.env.DEV_API_ORIGIN || 'https://host.pasinduudana.me',
        changeOrigin: true,
        secure: true,
      },
      '/health': {
        target: process.env.DEV_API_ORIGIN || 'https://host.pasinduudana.me',
        changeOrigin: true,
        secure: true,
      },
    },
  },
});
