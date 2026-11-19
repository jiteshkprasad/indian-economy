#!/usr/bin/env node
// First-load JS budget for /en/ (PLAN §4.13): parses out/en/index.html, sums the
// gzipped size (zlib level 9) of every referenced /_next/static/**.js chunk and
// fails above the budget. 1 KB = 1,000 bytes here, the stricter reading.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(webDir, "out");
const BUDGET = Number(process.env.FIRST_LOAD_BUDGET_KB ?? 200) * 1000;
const page = process.argv[2] ?? "en/index.html";

export function referencedChunks(html) {
  const urls = new Set();
  // <script src> and <link href> to chunks; `noModule` scripts (legacy polyfills) are
  // never loaded by browsers that support modules, so they are not first-load JS.
  const re = /<(?:script|link)\b([^>]*?)(?:src|href)="(\/_next\/static\/[^"?#]+\.js)(?:\?[^"]*)?"([^>]*)>/gi;
  let m;
  while ((m = re.exec(html))) {
    if (/\bnomodule\b/i.test(m[1] + m[3])) continue;
    urls.add(m[2]);
  }
  // Chunks the inline RSC payload asks the client to load before hydration.
  const re2 = /\\"(\/_next\/static\/chunks\/[^"\\]+\.js)\\"/g; // escaped quotes: inside the payload string
  while ((m = re2.exec(html))) urls.add(m[1]);
  return [...urls].sort();
}

export function noModuleChunks(html) {
  const out = [];
  const re = /<script\b([^>]*?)src="(\/_next\/static\/[^"?#]+\.js)"([^>]*)>/gi;
  let m;
  while ((m = re.exec(html))) if (/\bnomodule\b/i.test(m[1] + m[3])) out.push(m[2]);
  return out;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const file = path.join(outDir, page);
  if (!fs.existsSync(file)) {
    console.error(`first-load: ${path.relative(webDir, file)} not found; run the build first`);
    process.exit(1);
  }
  const html = fs.readFileSync(file, "utf8");
  const chunks = referencedChunks(html);
  let total = 0;
  const rows = [];
  for (const u of chunks) {
    const p = path.join(outDir, u);
    if (!fs.existsSync(p)) {
      console.error(`first-load: referenced chunk missing: ${u}`);
      process.exit(1);
    }
    const gz = zlib.gzipSync(fs.readFileSync(p), { level: 9 }).length;
    total += gz;
    rows.push([gz, u]);
  }
  rows.sort((a, b) => b[0] - a[0]);
  for (const [gz, u] of rows) console.log(`${(gz / 1000).toFixed(1).padStart(8)} KB  ${u}`);
  for (const u of noModuleChunks(html)) if (!chunks.includes(u)) console.log(`   (not counted: noModule polyfills ${u})`);
  console.log(`first-load: ${page}: ${chunks.length} chunks, ${(total / 1000).toFixed(1)} KB gzipped (budget ${BUDGET / 1000} KB)`);
  if (total > BUDGET) {
    console.error("first-load: OVER BUDGET");
    process.exit(1);
  }
}
