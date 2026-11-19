#!/usr/bin/env node
// `npm run test:web` (PLAN §5): node-check -> gen:contract --check -> vitest run ->
// [build lock] next build (fixture guard) -> first-load -> Playwright against out/.
// Arguments after `--` go to Playwright only.
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pwArgs = process.argv.slice(2);
const npx = process.platform === "win32" ? "npx.cmd" : "npx";

function run(label, cmd, args) {
  console.log(`\n=== test:web: ${label}`);
  const r = spawnSync(cmd, args, { cwd: webDir, stdio: "inherit", env: process.env });
  if (r.status !== 0) {
    console.error(`test:web: FAILED at "${label}" (exit ${r.status ?? r.signal})`);
    process.exit(r.status || 1);
  }
}

run("node-check", process.execPath, ["scripts/node-check.mjs"]);
run("gen:contract --check", process.execPath, ["scripts/gen-contract.mjs", "--check"]);
run("vitest", npx, ["vitest", "run"]);
// Build and e2e both use out/, so they run under one build lock.
run("build + first-load + playwright (build lock)", process.execPath, [
  "scripts/with-lock.mjs",
  "--lock",
  "build",
  "--",
  process.execPath,
  "scripts/build-and-e2e.mjs",
  ...pwArgs,
]);
console.log("\ntest:web: all steps passed");
