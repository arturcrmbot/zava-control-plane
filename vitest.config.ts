import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  css: false,
  resolve: {
    alias: {
      "@shared": path.resolve(__dirname, "web/shared"),
      "@client": path.resolve(__dirname, "web/client")
    },
    // Workspace packages (e.g. web/blueprint) ship their own node_modules with
    // their own react copy. Without dedupe, a hook compiled from web/blueprint
    // would load that copy while @testing-library/react loads the root copy,
    // producing the classic "Cannot read properties of null (reading 'useState')"
    // error from two React instances.
    dedupe: ["react", "react-dom"]
  },
  test: {
    environment: "node",
    setupFiles: [path.resolve(__dirname, "vitest.setup.ts")],
    exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**"]
  }
});
