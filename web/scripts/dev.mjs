#!/usr/bin/env node
// `npm run dev`: node check, fixture sync, then `next dev`. With a per-unit
// NEXT_DIST_DIR (e.g. .next-u3) Next is pointed at tsconfig.next-u3.json (gitignored,
// extends tsconfig.json), so dev runs do not rewrite the committed tsconfig.json.
// next-env.d.ts is still rewritten by Next; `npm run normalise` (also run by
// every build) restores it. Extra arguments go to `next dev`.
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
for (const s of ["node-check.mjs", "sync-fixture.mjs"]) {
  const r = spawnSync(process.execPath, [path.join(webDir, "scripts", s)], { stdio: "inherit", cwd: webDir });
  if (r.status !== 0) process.exit(r.status ?? 1);
}
const dist = process.env.NEXT_DIST_DIR;
if (dist) {
  const file = path.join(webDir, devTsconfigName(dist));
  if (!fs.existsSync(file)) fs.writeFileSync(file, JSON.stringify({ extends: "./tsconfig.json" }, null, 2) + "\n");
}
const bin = path.join(webDir, "node_modules", ".bin", process.platform === "win32" ? "next.cmd" : "next");
const child = spawn(bin, ["dev", ...process.argv.slice(2)], { stdio: "inherit", cwd: webDir, env: process.env });
child.on("exit", (code, sig) => process.exit(code ?? (sig ? 1 : 0)));
for (const s of ["SIGINT", "SIGTERM"]) process.on(s, () => child.kill(s));

export function devTsconfigName(distDir) {
  return `tsconfig.${path.basename(distDir).replace(/^\.+/, "")}.json`;
}
