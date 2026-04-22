import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/client/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        severity: {
          critical: "#dc2626",
          high: "#f97316",
          medium: "#eab308"
        }
      }
    }
  }
} satisfies Config;
