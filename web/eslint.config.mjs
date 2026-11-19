import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    "node_modules/**",
    ".next/**",
    ".next*/**",
    "out/**",
    "public/**",
    "fixtures/**",
    "coverage/**",
    "test-results/**",
    "playwright-report/**",
    ".lighthouseci/**",
    "next-env.d.ts",
    "src/data/contract.gen.ts",
  ]),
  {
    rules: {
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_", destructuredArrayIgnorePattern: "^_" }],
    },
  },
]);
