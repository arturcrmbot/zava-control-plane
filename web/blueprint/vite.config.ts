/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // FastAPI runs on 3001 (matches web/portal and web/client convention).
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:3001";
  return {
    plugins: [react()],
    server: {
      port: 5175,
      proxy: {
        "/api": apiTarget,
      },
    },
    preview: {
      port: 5175,
      proxy: {
        "/api": apiTarget,
      },
    },
    test: {
      environment: "jsdom",
      globals: true,
      include: ["src/**/*.test.{ts,tsx}"],
      // Repo root has a tailwind/postcss config used by other web apps;
      // don't load it for the blueprint test runner.
      css: false,
    },
    css: {
      postcss: { plugins: [] },
    },
  };
});
