import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // FastAPI runs on 3001 per repo .env.example (NOT 8000 as the plan template suggested).
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:3001";
  return {
    plugins: [react()],
    server: {
      port: 5174,
      proxy: {
        "/api": apiTarget,
      },
    },
    preview: {
      port: 5174,
      proxy: {
        "/api": apiTarget,
      },
    },
  };
});
