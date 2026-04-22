import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  css: false,
  resolve: {
    alias: {
      "@shared": path.resolve(__dirname, "web/shared"),
      "@client": path.resolve(__dirname, "web/client")
    }
  },
  test: {
    environment: "node",
    exclude: ["**/node_modules/**", "**/dist/**", "**/e2e/**"]
  }
});
