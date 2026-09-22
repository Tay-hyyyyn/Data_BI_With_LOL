import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    css: false,
    globals: false,
    // The one full-router integration test (real fetch + react-query + msw) is slower than a
    // unit test on a cold module cache; the default 5s can be tight on a loaded machine.
    testTimeout: 15_000,
  },
});
