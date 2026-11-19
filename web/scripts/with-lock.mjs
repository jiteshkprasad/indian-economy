#!/usr/bin/env node
// Run a command while holding a named lock (PLAN §4.15).
//   node scripts/with-lock.mjs --lock <name> -- <command> [args...]
// The lock is an atomic `mkdir web/.locks/<name>` with a pid file inside. A lock
// is stale only when its pid is dead, so a slow build is never stolen. Waits
// (polling every 2 s, printing who holds it) until the lock is free.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const argv = process.argv.slice(2);
const li = argv.indexOf("--lock");
const dd = argv.indexOf("--");
if (li < 0 || dd < 0 || dd < li + 2 || dd === argv.length - 1) {
  console.error("usage: node scripts/with-lock.mjs --lock <name> -- <command> [args...]");
  process.exit(2);
}
const name = argv[li + 1];
if (!/^[a-z][a-z0-9-]*$/.test(name)) {
  console.error(`with-lock: invalid lock name "${name}"`);
  process.exit(2);
}
const cmd = argv.slice(dd + 1);
const locksDir = path.join(webDir, ".locks");
const lockDir = path.join(locksDir, name);
const pidFile = path.join(lockDir, "pid");

function alive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === "EPERM";
  }
}

function tryAcquire() {
  fs.mkdirSync(locksDir, { recursive: true });
  try {
    fs.mkdirSync(lockDir);
  } catch (e) {
    if (e.code !== "EEXIST") throw e;
    let holder = NaN;
    let info = "";
    try {
      info = fs.readFileSync(pidFile, "utf8");
      holder = parseInt(info, 10);
    } catch {
      // pid file not written yet: the holder is between mkdir and write. Treat as held,
      // unless the directory is older than 30 s (a crash between the two steps).
      try {
        const age = Date.now() - fs.statSync(lockDir).mtimeMs;
        if (age > 30_000) {
          fs.rmSync(lockDir, { recursive: true, force: true });
          console.error(`with-lock: removed lock "${name}" with no pid file (age ${Math.round(age / 1000)} s)`);
          return tryAcquire();
        }
      } catch {
        return tryAcquire();
      }
      return { ok: false, holder: "unknown (starting)" };
    }
    if (!alive(holder)) {
      fs.rmSync(lockDir, { recursive: true, force: true });
      console.error(`with-lock: removed stale lock "${name}" (pid ${holder} is not running)`);
      return tryAcquire();
    }
    return { ok: false, holder: info.trim().replace(/\n/g, " ") };
  }
  fs.writeFileSync(pidFile, `${process.pid}\n${cmd.join(" ")}\n${new Date().toISOString()}\n`);
  return { ok: true };
}

function release() {
  try {
    const pid = parseInt(fs.readFileSync(pidFile, "utf8"), 10);
    if (pid === process.pid) fs.rmSync(lockDir, { recursive: true, force: true });
  } catch {
    // already gone
  }
}

async function main() {
  let lastMsg = 0;
  for (;;) {
    const r = tryAcquire();
    if (r.ok) break;
    if (Date.now() - lastMsg > 30_000) {
      console.error(`with-lock: waiting for lock "${name}" held by ${r.holder}`);
      lastMsg = Date.now();
    }
    await new Promise((res) => setTimeout(res, 2000));
  }
  const child = spawn(cmd[0], cmd.slice(1), { stdio: "inherit", cwd: process.cwd(), env: process.env });
  const forward = (sig) => () => child.kill(sig);
  process.on("SIGINT", forward("SIGINT"));
  process.on("SIGTERM", forward("SIGTERM"));
  child.on("error", (e) => {
    console.error(`with-lock: could not start ${cmd[0]}: ${e.message}`);
    release();
    process.exit(127);
  });
  child.on("exit", (code, signal) => {
    release();
    process.exit(code ?? (signal ? 1 : 0));
  });
}

main();
