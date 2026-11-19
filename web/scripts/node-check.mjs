#!/usr/bin/env node
// Fails unless this is Node 24 (PLAN §4.15).
const major = Number(process.versions.node.split(".")[0]);
if (major !== 24) {
  console.error(
    `Node ${process.versions.node} found; this project needs Node 24. Run: export PATH=/opt/homebrew/opt/node@24/bin:$PATH`,
  );
  process.exit(1);
}
