import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:3001";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": apiTarget,
        "/internal": apiTarget,
      }
    },
    preview: {
      port: 5173,
      proxy: {
        "/api": apiTarget,
        "/internal": apiTarget,
      }
    },
    resolve: {
      alias: {
        "@shared": path.resolve(__dirname, "src/shared"),
        "@client": path.resolve(__dirname, "src/client")
      }
    }
  };
});
