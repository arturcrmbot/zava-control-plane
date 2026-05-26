import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // FastAPI runs on 3101 per repo .env.example (NOT 8000 as the plan template suggested).
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:3101";
  // BASE_PATH (set at build time) controls the public path of emitted assets.
  // Cloud container deploys serve this SPA at /portal/, so the image build
  // sets BASE_PATH=/portal/. Local dev / preview leaves it unset → "/".
  const base = process.env.BASE_PATH || "/";
  return {
    base,
    plugins: [react()],
    server: {
      port: 5274,
      proxy: {
        "/api": apiTarget,
      },
    },
    preview: {
      port: 5274,
      proxy: {
        "/api": apiTarget,
      },
    },
  };
});
