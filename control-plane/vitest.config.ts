import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  css: false,
  resolve: {
    alias: {
      "@shared": path.resolve(__dirname, "src/shared"),
      "@client": path.resolve(__dirname, "src/client")
    }
  },
  test: {
    environment: "node",
    exclude: ["**/node_modules/**", "**/dist/**", "tests/e2e/**"]
  }
});
