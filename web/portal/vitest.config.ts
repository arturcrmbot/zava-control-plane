import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

const repoRoot = path.resolve(__dirname, "..", "..");
const portalNodeModules = path.resolve(__dirname, "node_modules");

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      { find: "@portal", replacement: path.resolve(__dirname, "src") },
      // Vite's import-analysis plugin only walks up the directory tree from
      // the file being transformed; tests live in <repo>/tests/web/portal but
      // their dependencies are installed in web/portal/node_modules. Map the
      // bare specifiers explicitly so resolution succeeds for both .js and
      // .mjs entry points.
      { find: /^msw$/, replacement: path.join(portalNodeModules, "msw/lib/core/index.mjs") },
      { find: /^msw\/node$/, replacement: path.join(portalNodeModules, "msw/lib/node/index.mjs") },
      { find: /^@testing-library\/react$/, replacement: path.join(portalNodeModules, "@testing-library/react/dist/index.js") },
      { find: /^@testing-library\/jest-dom\/vitest$/, replacement: path.join(portalNodeModules, "@testing-library/jest-dom/dist/vitest.mjs") },
      { find: /^@testing-library\/jest-dom$/, replacement: path.join(portalNodeModules, "@testing-library/jest-dom/dist/index.mjs") },
      { find: /^@testing-library\/dom$/, replacement: path.join(portalNodeModules, "@testing-library/dom/dist/index.js") },
      { find: /^react$/, replacement: path.join(portalNodeModules, "react/index.js") },
      { find: /^react\/jsx-runtime$/, replacement: path.join(portalNodeModules, "react/jsx-runtime.js") },
      { find: /^react\/jsx-dev-runtime$/, replacement: path.join(portalNodeModules, "react/jsx-dev-runtime.js") },
      { find: /^react-dom$/, replacement: path.join(portalNodeModules, "react-dom/index.js") },
      { find: /^react-dom\/client$/, replacement: path.join(portalNodeModules, "react-dom/client.js") },
      // Don't alias vitest itself — vitest must self-resolve so the running
      // process and the imported types come from the same module instance.
    ],
  },
  server: {
    fs: { allow: [repoRoot] },
  },
  test: {
    dir: repoRoot,
    environment: "jsdom",
    globals: true,
    setupFiles: [path.resolve(__dirname, "src/test-setup.ts")],
    include: ["tests/web/portal/**/*.test.{ts,tsx}"],
    deps: {
      moduleDirectories: ["node_modules", portalNodeModules],
    },
  },
});
