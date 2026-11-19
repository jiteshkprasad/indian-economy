#!/usr/bin/env node
// `next dev` with a per-unit NEXT_DIST_DIR rewrites tsconfig.json (adds
// ".next-uX/types/**" to `include`) and next-env.d.ts (imports
// "./.next-uX/dev/types/…"). This puts both back in their canonical, committed
// form. Run before builds (build:nolock does) and before committing.
//   node scripts/next-files.mjs          fix
//   node scripts/next-files.mjs --check  exit 1 if either file is not canonical
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TSCONFIG = path.join(webDir, "tsconfig.json");
const NEXT_ENV = path.join(webDir, "next-env.d.ts");

export const CANONICAL_NEXT_ENV = `/// <reference types="next" />
/// <reference types="next/image-types/global" />

// NOTE: This file should not be edited
// see https://nextjs.org/docs/app/api-reference/config/typescript for more information.
`;

export function canonicalTsconfig(text) {
  const cfg = JSON.parse(text);
  // keep what `next build` itself adds (.next/types, .next/dev/types) so builds do not
  // rewrite the file again; drop the per-unit dev dist dirs (.next-uN/…).
  const keep = (p) => !/^\.next/.test(p) || /^\.next\//.test(p);
  cfg.include = (cfg.include ?? []).filter(keep);
  for (const p of [".next/types/**/*.ts", ".next/dev/types/**/*.ts"]) if (!cfg.include.includes(p)) cfg.include.push(p);
  return JSON.stringify(cfg, null, 2) + "\n";
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const check = process.argv.includes("--check");
  const ts = fs.readFileSync(TSCONFIG, "utf8");
  const env = fs.existsSync(NEXT_ENV) ? fs.readFileSync(NEXT_ENV, "utf8") : "";
  const wantTs = canonicalTsconfig(ts);
  const bad = [];
  if (ts !== wantTs) bad.push("tsconfig.json");
  if (env !== CANONICAL_NEXT_ENV) bad.push("next-env.d.ts");
  if (check) {
    if (bad.length) {
      console.error(`next-files: not canonical: ${bad.join(", ")} (run \`node scripts/next-files.mjs\`)`);
      process.exit(1);
    }
    console.log("next-files: canonical");
  } else {
    if (ts !== wantTs) fs.writeFileSync(TSCONFIG, wantTs);
    if (env !== CANONICAL_NEXT_ENV) fs.writeFileSync(NEXT_ENV, CANONICAL_NEXT_ENV);
    console.log(bad.length ? `next-files: normalised ${bad.join(", ")}` : "next-files: canonical");
  }
}
