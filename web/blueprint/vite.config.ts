import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  // FastAPI runs on 3101 (matches web/portal and web/client convention).
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:3101";
  // BASE_PATH controls the public path of built assets. GitHub Pages project
  // sites serve at `/<repo>/`, so the deploy workflow sets
  // BASE_PATH=/zava-control-plane/ before `vite build`. Local dev, `vite
  // preview`, and the Azure Container Apps build all leave BASE_PATH unset
  // and serve from `/`. Trailing slash is required by Vite. Read from
  // process.env directly — loadEnv only sees .env* files, not shell vars.
  const base = process.env.BASE_PATH || "/";
  // Derive demoUrl: shell env takes priority over .env files.
  const demoUrl = process.env.VITE_DEMO_URL || env.VITE_DEMO_URL;
  // When building at a path prefix (e.g. GitHub Pages) the blueprint will be
  // served from a different origin than the ACA backend, so an explicit URL is
  // required. Fail fast to prevent a broken asset being deployed.
  if (base !== "/" && !demoUrl) {
    throw new Error(
      "VITE_DEMO_URL is required when building the blueprint below a path prefix " +
        `(BASE_PATH=${base}). Set it to the ACA replay URL or '/' for same-origin.`,
    );
  }
  return {
    base,
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
