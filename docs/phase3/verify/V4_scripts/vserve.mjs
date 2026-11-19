// Vercel-like static server for web/out: vercel.json redirects + headers (last match wins per key),
// directory index.html, 404.html, brotli/gzip compression of text types.
import http from "node:http"; import fs from "node:fs"; import path from "node:path"; import zlib from "node:zlib";
const web = process.argv[2]; const port = Number(process.argv[3] || 4748);
const out = path.join(web, "out"); const v = JSON.parse(fs.readFileSync(path.join(web, "vercel.json"), "utf8"));
const rx = (s) => new RegExp("^" + s.replace(/\(\.\*\)/g, "(.*)") + "$");
const types = { ".html": "text/html; charset=utf-8", ".js": "application/javascript", ".css": "text/css", ".json": "application/json", ".txt": "text/plain; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2" };
http.createServer((req, res) => {
  const u = new URL(req.url, "http://x"); let p = decodeURIComponent(u.pathname);
  const hdrs = {}; for (const h of v.headers) if (rx(h.source).test(p)) for (const kv of h.headers) hdrs[kv.key.toLowerCase()] = kv.value;
  for (const r of v.redirects) if (rx(r.source).test(p)) { res.writeHead(r.permanent ? 308 : 307, { ...hdrs, location: r.destination }); return res.end(); }
  let f = path.join(out, p); let status = 200;
  if (fs.existsSync(f) && fs.statSync(f).isDirectory()) { if (!p.endsWith("/")) { res.writeHead(308, { location: p + "/" }); return res.end(); } f = path.join(f, "index.html"); }
  if (!fs.existsSync(f)) { f = path.join(out, "404.html"); status = 404; }
  let body = fs.readFileSync(f); const ext = path.extname(f); const ct = types[ext] || "application/octet-stream";
  const ae = req.headers["accept-encoding"] || ""; const h = { ...hdrs, "content-type": ct };
  if (!process.env.NOCOMP && /text|javascript|json|svg/.test(ct)) { if (ae.includes("br")) { body = zlib.brotliCompressSync(body); h["content-encoding"] = "br"; } else if (ae.includes("gzip")) { body = zlib.gzipSync(body); h["content-encoding"] = "gzip"; } h["vary"] = "Accept-Encoding"; }
  h["content-length"] = body.length; res.writeHead(status, h); res.end(req.method === "HEAD" ? undefined : body);
}).listen(port, "127.0.0.1", () => console.log("vserve http://127.0.0.1:" + port + "/"));
