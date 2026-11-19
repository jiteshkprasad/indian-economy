/**
 * Live site: the static export in ../out at indianeconomy.jitesh.app (founder, 10 Nov 2026).
 * Adds the security headers that vercel.json used to set, allows the Cloudflare Web Analytics beacon, and sends / to /en/.
 */
interface Env { ASSETS: { fetch(r: Request): Promise<Response> } }

const CSP = "default-src 'self'; script-src 'self' 'unsafe-inline' https://static.cloudflareinsights.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self' https://cloudflareinsights.com; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'";

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (url.pathname === "/") return Response.redirect(url.origin + "/en/", 301);
    const res = await env.ASSETS.fetch(req);
    const h = new Headers(res.headers);
    h.set("content-security-policy", CSP);
    h.set("x-content-type-options", "nosniff");
    h.set("referrer-policy", "strict-origin-when-cross-origin");
    const p = url.pathname;
    if (p.startsWith("/_next/static/") || (p.startsWith("/data/") && p !== "/data/index.json")) h.set("cache-control", "public, max-age=31536000, immutable");
    else if (p === "/data/index.json") h.set("cache-control", "public, max-age=0, must-revalidate");
    return new Response(res.body, { status: res.status, headers: h });
  },
};
