// Shared by src/data/server.ts and scripts/*.mjs: which data root the build uses (PLAN §3.10, §4.4).
//   DATA_ROOT=public   -> web/public/data/        (client base /data)
//   DATA_ROOT=fixtures -> web/fixtures/data/      (client base /data-fixture, copied by sync-fixture)
//   DATA_ROOT=<absolute path> -> that folder      (tests only; client base /data-fixture)
// Default: public once web/public/data/index.json exists, fixtures before.
import fs from "node:fs";
import path from "node:path";

export function resolveDataRoot(webDir, env = process.env) {
  const raw = (env.DATA_ROOT ?? "").trim();
  const publicDir = path.join(webDir, "public", "data");
  const fixturesDir = path.join(webDir, "fixtures", "data");
  let kind;
  let dir;
  if (raw === "") {
    kind = fs.existsSync(path.join(publicDir, "index.json")) ? "public" : "fixtures";
  } else if (raw === "public" || raw === "fixtures") {
    kind = raw;
  } else if (path.isAbsolute(raw)) {
    kind = "custom";
    dir = raw;
  } else {
    throw new Error(`DATA_ROOT must be "public", "fixtures" or an absolute path; got "${raw}"`);
  }
  if (kind === "public") dir = publicDir;
  if (kind === "fixtures") dir = fixturesDir;
  const base = kind === "public" ? "/data" : "/data-fixture";
  return { kind, dir, base, explicit: raw !== "" };
}
