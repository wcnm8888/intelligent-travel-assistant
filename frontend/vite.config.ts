import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: mode === "uat" ? 15173 : 5173,
    strictPort: true,
    proxy: {
      "/api":
        mode === "uat" ? "http://127.0.0.1:18008" : "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
    css: true,
  },
}));
