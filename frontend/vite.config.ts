import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const injectedApiPort = process.env.VITE_PROXY_API_PORT;
  const defaultApiPort = mode === "uat" ? 18008 : 8000;
  const apiPort =
    injectedApiPort !== undefined && /^\d{1,5}$/.test(injectedApiPort)
      ? Number(injectedApiPort)
      : defaultApiPort;

  return {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: mode === "uat" ? 15173 : 5173,
      strictPort: true,
      proxy: {
        "/api": `http://127.0.0.1:${apiPort}`,
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/setup.ts"],
      restoreMocks: true,
      css: true,
      testTimeout: 10_000,
    },
  };
});
