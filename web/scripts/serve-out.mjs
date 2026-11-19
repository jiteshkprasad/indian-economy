#!/usr/bin/env node
// Serves web/out/ like Vercel would (PLAN §4.14): the vercel.json redirects and
// headers, trailing slashes, 404.html. PORT=0 (default) picks a free port; the URL
// is printed as "serve-out: http://127.0.0.1:<port>/".
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import handler from "serve-handler";

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(webDir, "out");

export function serveConfig() {
  const vercel = JSON.parse(fs.readFileSync(path.join(webDir, "vercel.json"), "utf8"));
  // vercel.json uses path-to-regexp sources ("/data/(.*)"); serve-handler uses globs.
  const glob = (src) => src.replace(/\(\.\*\)/g, "**");
  return {
    public: outDir,
    // serve-handler only serves <dir>/index.html with cleanUrls on; Vercel serves directory
    // indexes for static output by default. (Side effect: /x/index.html redirects to /x/.)
    cleanUrls: true,
    trailingSlash: true,
    directoryListing: false,
    redirects: (vercel.redirects ?? []).map((r) => ({ source: r.source, destination: r.destination, type: r.permanent ? 308 : 307 })),
    headers: (vercel.headers ?? []).map((h) => ({ source: glob(h.source), headers: h.headers })),
  };
}

export function startServer(port = Number(process.env.PORT ?? 0), host = "127.0.0.1") {
  if (!fs.existsSync(path.join(outDir, "index.html")) && !fs.existsSync(path.join(outDir, "en", "index.html"))) {
    throw new Error("serve-out: web/out/ has no build; run `npm run build` first");
  }
  const config = serveConfig();
  const server = http.createServer((req, res) => handler(req, res, config));
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => {
      const addr = server.address();
      resolve({ server, url: `http://${host}:${addr.port}` });
    });
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { url } = await startServer();
  console.log(`serve-out: ${url}/`);
}
