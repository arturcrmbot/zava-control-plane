import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // FastAPI runs on 3101 (matches web/portal and web/client convention).
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:3101";
  return {
    plugins: [react()],
    server: {
      port: 5275,
      proxy: {
        "/api": apiTarget,
      },
    },
    preview: {
      port: 5275,
      proxy: {
        "/api": apiTarget,
      },
    },
    resolve: {
      alias: {
        "@shared": path.resolve(__dirname, "../shared"),
      },
      // stats-gl ships a nested three@0.170 — without dedup, R3F's
      // useThree throws "Hooks can only be used within Canvas component"
      // and the scene renders to pure black. (PR #6 fix; do not remove.)
      // react / react-dom dedupe added in v1.1: when vitest is invoked from
      // this directory directly (rather than the repo root), workspace
      // packages would otherwise pick up two React copies and components
      // using hooks throw "Cannot read properties of null (reading 'useState')".
      dedupe: ["three", "@react-three/fiber", "@react-three/drei", "react", "react-dom"],
    },
    optimizeDeps: {
      include: [
        "three",
        "@react-three/fiber",
        "@react-three/drei",
        "@react-three/postprocessing",
        "d3-force",
      ],
    },
  };
});
