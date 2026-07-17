/// <reference types="vitest/config" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [react(), tailwindcss()],

  // Options Vite adaptées à Tauri (appliquées en `tauri dev` / `tauri build`).
  clearScreen: false, // 1. ne pas masquer les erreurs Rust
  server: {
    port: 1420, // 2. Tauri attend un port fixe
    strictPort: true,
    host: host || false,
    hmr: host ? { protocol: "ws", host, port: 1421 } : undefined,
    watch: {
      ignored: ["**/src-tauri/**"], // 3. ne pas surveiller src-tauri
    },
  },

  // Vitest — garde-fous d'hygiène (Quality.md : forks bornés, isolation, timeouts).
  test: {
    environment: "node",
    globals: true,
    pool: "forks",
    poolOptions: { forks: { maxForks: 2 } },
    isolate: true,
    maxConcurrency: 5,
    testTimeout: 10000,
    hookTimeout: 10000,
  },
}));
