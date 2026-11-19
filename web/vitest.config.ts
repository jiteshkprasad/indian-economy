import path from "node:path";
import { defineConfig } from "vitest/config";

const r = (p: string) => path.resolve(import.meta.dirname, p);

// Unit tests (PLAN §5.2). Each unit owns tests/unit/<unit area>/**.
export default defineConfig({
  resolve: {
    alias: [
      { find: /^@\/(.*)$/, replacement: `${r("src")}/$1` },
      { find: /^@content\/(.*)$/, replacement: `${r("content")}/$1` },
      { find: /^@messages\/(.*)$/, replacement: `${r("messages")}/$1` },
      // `server-only` throws outside a React Server Components build; tests import server code directly.
      { find: /^server-only$/, replacement: r("tests/unit/platform/_server-only-stub.ts") },
    ],
  },
  test: {
    include: ["tests/unit/**/*.test.{ts,tsx}"],
    environment: "node",
    pool: "threads",
    testTimeout: 20000,
    reporters: ["default"],
  },
});
