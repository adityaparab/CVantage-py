import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: [
        "src/**/*.test.{ts,tsx}",
        "src/test/**",
        "src/**/*.d.ts",
        "src/main.tsx",
        "src/app/router.tsx",
        "src/components/ui/Showcase.tsx",
      ],
      thresholds: {
        // Global floor (ratchets up as features land).
        statements: 65,
        branches: 60,
        functions: 55,
        lines: 65,
        // Core infrastructure per the AC (≥80% on lib / api / components-ui).
        "src/api/**": { lines: 80 },
        "src/components/ui/**": { lines: 80 },
        "src/lib/**": { lines: 80 },
      },
    },
  },
});
