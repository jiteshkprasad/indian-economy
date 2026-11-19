/**
 * Private preview of the Map site (Checkpoint C): static export in ../out behind HTTP Basic Auth, never indexed.
 * Password: Worker secret PREVIEW_PASS (). User name: "preview".
 */
interface Env { ASSETS: { fetch(r: Request): Promise<Response> }; PREVIEW_PASS: string }

const NOINDEX = "noindex, nofollow, noarchive";
const CSP = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'";

function same(a: string, b: string) {
  if (!a || !b || a.length !== b.length) return false;
  let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (url.pathname === "/robots.txt") return new Response("User-agent: *\nDisallow: /\n", { headers: { "content-type": "text/plain", "x-robots-tag": NOINDEX } });
    const auth = req.headers.get("authorization") ?? "";
    const ok = auth.startsWith("Basic ") && (() => { try { const [u, p] = atob(auth.slice(6)).split(":"); return u === "preview" && same(p ?? "", env.PREVIEW_PASS ?? ""); } catch { return false; } })();
    if (!ok) return new Response("Private preview.", { status: 401, headers: { "www-authenticate": 'Basic realm="India economy preview", charset="UTF-8"', "x-robots-tag": NOINDEX, "cache-control": "no-store" } });
    if (url.pathname === "/") return Response.redirect(url.origin + "/en/", 302);
    const res = await env.ASSETS.fetch(req);
    const h = new Headers(res.headers);
    h.set("x-robots-tag", NOINDEX);
    h.set("cache-control", "private, no-store");
    h.set("content-security-policy", CSP);
    h.set("x-content-type-options", "nosniff");
    h.set("referrer-policy", "strict-origin-when-cross-origin");
    return new Response(res.body, { status: res.status, headers: h });
  },
};
