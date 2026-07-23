import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:3101";
  return {
    plugins: [react()],
    server: {
      port: 5273,
      watch: {
        ignored: ["**/.travel-proof-runtime/**"],
      },
      proxy: {
        "/api": apiTarget,
        "/internal": apiTarget,
      }
    },
    preview: {
      port: 5273,
      proxy: {
        "/api": apiTarget,
        "/internal": apiTarget,
      }
    },
    resolve: {
      alias: {
        "@shared": path.resolve(__dirname, "web/shared"),
        "@client": path.resolve(__dirname, "web/client")
      }
    }
  };
});
