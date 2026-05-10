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
    resolve: {
      // stats-gl ships a nested three@0.170 — without dedup, R3F's
      // useThree throws "Hooks can only be used within Canvas component"
      // and the scene renders to pure black. (PR #6 fix; do not remove.)
      dedupe: ["three", "@react-three/fiber", "@react-three/drei"],
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
