#!/usr/bin/env node
// Runs inside the build lock (called by test-web.mjs): check-data, sync-fixture,
// next build, first-load, then Playwright with the given arguments.
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const npx = process.platform === "win32" ? "npx.cmd" : "npx";
const steps = [
  ["next-files", process.execPath, ["scripts/next-files.mjs"]],
  ["check-data", process.execPath, ["scripts/check-data.mjs"]],
  ["sync-fixture", process.execPath, ["scripts/sync-fixture.mjs"]],
  ["next build", npx, ["next", "build"]],
  // next build rewrites next-env.d.ts to import .next/types; restore the committed form
  ["next-files (after build)", process.execPath, ["scripts/next-files.mjs"]],
  ["first-load", process.execPath, ["scripts/first-load.mjs"]],
  ["playwright", npx, ["playwright", "test", ...process.argv.slice(2)]],
];
for (const [label, cmd, args] of steps) {
  console.log(`\n=== ${label}`);
  const r = spawnSync(cmd, args, { cwd: webDir, stdio: "inherit", env: process.env });
  if (r.status !== 0) {
    console.error(`FAILED at "${label}" (exit ${r.status ?? r.signal})`);
    process.exit(r.status || 1);
  }
}
