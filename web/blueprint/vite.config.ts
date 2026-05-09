/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // FastAPI runs on 3001 (matches web/portal and web/client convention).
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:3001";
  return {
    plugins: [react()],
    // stats-gl ships a nested three@0.170 which collides with our
    // top-level three@0.184. The duplicate confuses
    // @react-three/postprocessing's useThree call (different module
    // → different store) → R3F throws "Hooks can only be used within
    // the Canvas component" and the WebGL context is lost. Force every
    // import of three to resolve to the top-level copy.
    resolve: {
      dedupe: ["three", "@react-three/fiber", "@react-three/drei"],
    },
    optimizeDeps: {
      // Pre-bundle in a single bundle so dev mode + preview share one
      // instance.
      include: ["three", "@react-three/fiber", "@react-three/drei", "@react-three/postprocessing"],
    },
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
