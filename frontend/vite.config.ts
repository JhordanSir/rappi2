import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// Backend FastAPI corre por defecto en :8000. En dev se proxyea /api -> backend
// para evitar problemas de CORS. En produccion se usa VITE_API_URL o /api relativo.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          "react-vendor": ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
          maps: ["leaflet", "react-leaflet"],
          query: ["@tanstack/react-query", "axios"],
        },
      },
    },
  },
});
