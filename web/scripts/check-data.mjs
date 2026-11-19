#!/usr/bin/env node
// Guard run before `next build` (PLAN §3.10):
//  - the data root must have index.json whose files all exist with the listed sha256;
//  - a fixture data root fails the build unless ALLOW_FIXTURE=1, and then every
//    line of output says "E2E ON FIXTURE DATA" (Checkpoint C may not cite such runs).
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolveDataRoot } from "../src/data/root.mjs";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export function checkData(env = process.env) {
  const root = resolveDataRoot(webDir, env);
  const indexPath = path.join(root.dir, "index.json");
  if (!fs.existsSync(indexPath)) {
    return { ok: false, msg: `check-data: no index.json in ${root.dir} (DATA_ROOT=${env.DATA_ROOT ?? "<default>"}). Run \`uv run python -m pipeline export\` (or \`--fixture\`).` };
  }
  let idx;
  try {
    idx = JSON.parse(fs.readFileSync(indexPath, "utf8"));
  } catch (e) {
    return { ok: false, msg: `check-data: ${indexPath} is not valid JSON: ${e.message}` };
  }
  const isFixture = idx.fixture === true || root.kind !== "public";
  if (isFixture && env.ALLOW_FIXTURE !== "1") {
    return {
      ok: false,
      msg: `check-data: the data root is fixture data (${root.dir}). A production build on fixture data is not allowed. Set ALLOW_FIXTURE=1 only for e2e runs before the real export exists.`,
    };
  }
  if (root.kind === "public" && idx.fixture === true) {
    return { ok: false, msg: "check-data: web/public/data/index.json says fixture: true; only the real export may write web/public/data/." };
  }
  const vdir = path.join(root.dir, idx.data_version);
  const bad = [];
  for (const [rel, meta] of Object.entries(idx.files ?? {})) {
    const p = path.join(vdir, rel);
    if (!fs.existsSync(p)) {
      bad.push(`missing ${rel}`);
      continue;
    }
    const buf = fs.readFileSync(p);
    const sha = crypto.createHash("sha256").update(buf).digest("hex");
    if (sha !== meta.sha256) bad.push(`sha256 mismatch ${rel}`);
    else if (buf.length !== meta.bytes) bad.push(`size mismatch ${rel}`);
  }
  if (bad.length) return { ok: false, msg: `check-data: ${vdir} does not match index.json:\n  ${bad.join("\n  ")}` };
  return { ok: true, fixture: isFixture, root, idx };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const r = checkData();
  if (!r.ok) {
    console.error(r.msg);
    process.exit(1);
  }
  if (r.fixture) {
    console.warn("*".repeat(64));
    console.warn("E2E ON FIXTURE DATA: this build uses generated fixture data (ALLOW_FIXTURE=1).");
    console.warn("Checkpoint C may not cite it.");
    console.warn("*".repeat(64));
  } else {
    console.log(`check-data: OK, ${r.idx.data_version} (${Object.keys(r.idx.files).length} files verified)`);
  }
}
