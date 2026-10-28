/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// El navegador solo habla con FastAPI (proxy /api → 127.0.0.1:8000). Nunca toca SQLite.
// KOVA_API_URL y KOVA_WEB_PORT permiten usar otros puertos (p. ej. si 8000 o 5173 ya están ocupados).
const API = process.env.KOVA_API_URL ?? "http://127.0.0.1:8000";
const PUERTO = Number(process.env.KOVA_WEB_PORT ?? 5173);
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: PUERTO,
    strictPort: true,
    proxy: { "/api": { target: API, changeOrigin: false } },
  },
  preview: { host: "127.0.0.1", port: 4173, proxy: { "/api": API } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
