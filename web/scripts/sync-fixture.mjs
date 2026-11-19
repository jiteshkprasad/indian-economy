#!/usr/bin/env node
// Copies the fixture (or a custom DATA_ROOT) to web/public/data-fixture/ for client
// fetches (PLAN §3.10). When the data root is `public`, removes public/data-fixture/
// so fixture files never ship in out/. The copy goes to a temp folder first and is
// renamed into place, so concurrent dev servers never see a half-written folder.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolveDataRoot } from "../src/data/root.mjs";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dest = path.join(webDir, "public", "data-fixture");
const root = resolveDataRoot(webDir);

if (root.kind === "public") {
  if (fs.existsSync(dest)) {
    fs.rmSync(dest, { recursive: true, force: true });
    console.log("sync-fixture: data root is public; removed public/data-fixture/");
  }
  process.exit(0);
}
if (!fs.existsSync(path.join(root.dir, "index.json"))) {
  console.error(`sync-fixture: no index.json in ${root.dir}; run \`uv run python -m pipeline export --fixture\` first`);
  process.exit(1);
}
const tmp = `${dest}.tmp-${process.pid}`;
fs.rmSync(tmp, { recursive: true, force: true });
fs.cpSync(root.dir, tmp, { recursive: true });
const old = `${dest}.old-${process.pid}`;
if (fs.existsSync(dest)) fs.renameSync(dest, old);
fs.renameSync(tmp, dest);
fs.rmSync(old, { recursive: true, force: true });
console.log(`sync-fixture: copied ${path.relative(webDir, root.dir) || root.dir} -> public/data-fixture/`);
