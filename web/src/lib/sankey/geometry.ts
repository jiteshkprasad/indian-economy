import type { Pt, Station } from "./types";

/** Round to 2 decimals for compact, deterministic SVG path data. */
export function f2(n: number): string {
  const r = Math.round(n * 100) / 100;
  return Object.is(r, -0) ? "0" : String(r);
}

function dedupe(route: Pt[]): Pt[] {
  const out: Pt[] = [];
  for (const p of route) {
    const q = out[out.length - 1];
    if (!q || Math.abs(q.x - p.x) > 1e-9 || Math.abs(q.y - p.y) > 1e-9) out.push(p);
  }
  return out;
}

function dir(a: Pt, b: Pt): Pt {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  return { x: dx / len, y: dy / len };
}

/** Left normal of a direction in screen coordinates. */
function normal(d: Pt): Pt {
  return { x: d.y, y: -d.x };
}

/**
 * Offset an orthogonal polyline by `off` (positive = left of the direction of travel). Corners are
 * mitred, which is exact for right angles. A 180° turn gets a square cap.
 */
export function offsetPolyline(routeIn: Pt[], off: number): Pt[] {
  const route = dedupe(routeIn);
  const out: Pt[] = [];
  const n = route.length;
  for (let i = 0; i < n; i++) {
    const p = route[i];
    const dPrev = i > 0 ? dir(route[i - 1], p) : null;
    const dNext = i < n - 1 ? dir(p, route[i + 1]) : null;
    if (dPrev && dNext) {
      const dot = dPrev.x * dNext.x + dPrev.y * dNext.y;
      const nP = normal(dPrev);
      const nN = normal(dNext);
      if (dot > 0.999) {
        out.push({ x: p.x + nP.x * off, y: p.y + nP.y * off });
      } else if (dot < -0.999) {
        const cap = Math.abs(off);
        out.push({ x: p.x + nP.x * off + dPrev.x * cap, y: p.y + nP.y * off + dPrev.y * cap });
        out.push({ x: p.x + nN.x * off + dPrev.x * cap, y: p.y + nN.y * off + dPrev.y * cap });
      } else {
        out.push({ x: p.x + (nP.x + nN.x) * off, y: p.y + (nP.y + nN.y) * off });
      }
    } else {
      const d = (dPrev ?? dNext) as Pt;
      const nn = normal(d);
      out.push({ x: p.x + nn.x * off, y: p.y + nn.y * off });
    }
  }
  return out;
}

/**
 * Round the corners of an orthogonal route: each corner becomes a quarter circle (sampled) of
 * radius ≈ w/2 + 6, limited by half of each adjacent segment. Endpoints are unchanged.
 */
export function smoothRoute(routeIn: Pt[], w: number, steps = 8): Pt[] {
  const r0 = Math.max(w / 2 + 6, 10);
  const route = dedupe(routeIn);
  if (route.length < 3) return route;
  const out: Pt[] = [route[0]];
  for (let i = 1; i < route.length - 1; i++) {
    const a = route[i - 1];
    const p = route[i];
    const b = route[i + 1];
    const lenA = Math.hypot(p.x - a.x, p.y - a.y);
    const lenB = Math.hypot(b.x - p.x, b.y - p.y);
    const limA = i === 1 ? lenA : lenA / 2;
    const limB = i === route.length - 2 ? lenB : lenB / 2;
    const r = Math.min(r0, limA, limB);
    const dA = dir(a, p);
    const dB = dir(p, b);
    const dot = dA.x * dB.x + dA.y * dB.y;
    if (r <= 1e-6 || Math.abs(dot) > 0.999) {
      out.push(p);
      continue;
    }
    const s0 = { x: p.x - dA.x * r, y: p.y - dA.y * r };
    // quadratic-like quarter: circle centre at s0 + n*r where n points toward the turn
    const cross = dA.x * dB.y - dA.y * dB.x;
    const nx = cross > 0 ? -dA.y : dA.y;
    const ny = cross > 0 ? dA.x : -dA.x;
    const c = { x: s0.x + nx * r, y: s0.y + ny * r };
    const a0 = Math.atan2(s0.y - c.y, s0.x - c.x);
    const sweep = cross > 0 ? Math.PI / 2 : -Math.PI / 2;
    for (let k = 0; k <= steps; k++) {
      const t = a0 + (sweep * k) / steps;
      out.push({ x: c.x + Math.cos(t) * r, y: c.y + Math.sin(t) * r });
    }
  }
  out.push(route[route.length - 1]);
  return dedupe(out);
}

/** Offset a general polyline by `off` (left of travel), with mitred joins (limited). */
export function offsetSmooth(line: Pt[], off: number): Pt[] {
  const n = line.length;
  const out: Pt[] = [];
  for (let i = 0; i < n; i++) {
    const p = line[i];
    const dPrev = i > 0 ? dir(line[i - 1], p) : null;
    const dNext = i < n - 1 ? dir(p, line[i + 1]) : null;
    const nP = dPrev ? normal(dPrev) : null;
    const nN = dNext ? normal(dNext) : null;
    let m: Pt;
    if (nP && nN) {
      const sx = nP.x + nN.x;
      const sy = nP.y + nN.y;
      const len = Math.hypot(sx, sy);
      if (len < 1e-6) m = nP;
      else {
        const ux = sx / len;
        const uy = sy / len;
        const cos = ux * nP.x + uy * nP.y;
        const k = 1 / Math.max(cos, 0.25);
        m = { x: ux * k, y: uy * k };
      }
    } else m = (nP ?? nN) as Pt;
    out.push({ x: p.x + m.x * off, y: p.y + m.y * off });
  }
  return out;
}

/** Filled outline of a rounded orthogonal route of width `w` (return arcs and same-column side arcs). */
export function routeOutlineD(route: Pt[], w: number): string {
  const line = smoothRoute(route, w);
  const left = offsetSmooth(line, w / 2);
  const right = offsetSmooth(line, -w / 2).reverse();
  const pts = [...left, ...right];
  return "M" + pts.map((p) => `${f2(p.x)},${f2(p.y)}`).join("L") + "Z";
}

/**
 * Forward ribbon through its stations. The first and last stations are the source's right edge and
 * the target's left edge (x0 = x1). Between stations the band is a cubic Bézier with horizontal
 * tangents; through an intermediate column it runs straight along its gutter slot.
 */
export function ribbonD(st: Station[], w: number): string {
  const parts: string[] = [];
  const a0 = st[0];
  parts.push(`M${f2(a0.x0)},${f2(a0.y)}`);
  if (a0.x1 > a0.x0) parts.push(`L${f2(a0.x1)},${f2(a0.y)}`);
  for (let i = 1; i < st.length; i++) {
    const a = st[i - 1];
    const b = st[i];
    const mx = (a.x1 + b.x0) / 2;
    parts.push(`C${f2(mx)},${f2(a.y)} ${f2(mx)},${f2(b.y)} ${f2(b.x0)},${f2(b.y)}`);
    if (b.x1 > b.x0) parts.push(`L${f2(b.x1)},${f2(b.y)}`);
  }
  const last = st[st.length - 1];
  parts.push(`L${f2(last.x1)},${f2(last.y + w)}`);
  if (last.x1 > last.x0) parts.push(`L${f2(last.x0)},${f2(last.y + w)}`);
  for (let i = st.length - 1; i >= 1; i--) {
    const b = st[i];
    const a = st[i - 1];
    const mx = (a.x1 + b.x0) / 2;
    parts.push(`C${f2(mx)},${f2(b.y + w)} ${f2(mx)},${f2(a.y + w)} ${f2(a.x1)},${f2(a.y + w)}`);
    if (a.x1 > a.x0) parts.push(`L${f2(a.x0)},${f2(a.y + w)}`);
  }
  parts.push("Z");
  return parts.join("");
}

function cubic(p0: number, p1: number, p2: number, p3: number, t: number): number {
  const u = 1 - t;
  return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3;
}

/**
 * Sample points across and along a forward ribbon: lines at fractions 0, ¼, ½, ¾, 1 of its width,
 * each sampled along every curve and straight piece. Used by the geometric invariant tests.
 */
export function sampleRibbon(st: Station[], w: number, steps = 24): Pt[] {
  const pts: Pt[] = [];
  for (const f of [0, 0.25, 0.5, 0.75, 1]) {
    const dy = w * f;
    for (let i = 0; i < st.length; i++) {
      const b = st[i];
      if (b.x1 > b.x0) {
        for (let k = 0; k <= steps; k++) pts.push({ x: b.x0 + ((b.x1 - b.x0) * k) / steps, y: b.y + dy });
      }
      if (i === 0) continue;
      const a = st[i - 1];
      const mx = (a.x1 + b.x0) / 2;
      for (let k = 0; k <= steps; k++) {
        const t = k / steps;
        pts.push({ x: cubic(a.x1, mx, mx, b.x0, t), y: cubic(a.y, a.y, b.y, b.y, t) + dy });
      }
    }
  }
  return pts;
}

/** Sample points across and along an orthogonal route of width `w`. */
export function sampleRoute(route: Pt[], w: number, step = 2): Pt[] {
  const pts: Pt[] = [];
  const smooth = smoothRoute(route, w);
  for (const f of [-0.5, -0.25, 0, 0.25, 0.5]) {
    const line = f === 0 ? smooth : offsetSmooth(smooth, w * f);
    for (let i = 1; i < line.length; i++) {
      const a = line[i - 1];
      const b = line[i];
      const len = Math.hypot(b.x - a.x, b.y - a.y);
      const n = Math.max(1, Math.ceil(len / step));
      for (let k = 0; k <= n; k++) pts.push({ x: a.x + ((b.x - a.x) * k) / n, y: a.y + ((b.y - a.y) * k) / n });
    }
  }
  return pts;
}

export type Seg = { a: Pt; b: Pt };

/** Segments of an orthogonal centreline. */
export function segments(route: Pt[]): Seg[] {
  const r = dedupe(route);
  const out: Seg[] = [];
  for (let i = 1; i < r.length; i++) out.push({ a: r[i - 1], b: r[i] });
  return out;
}

/** Proper crossing of two axis-aligned segments (one horizontal, one vertical); touching ends do not count. */
export function crosses(s: Seg, t: Seg, eps = 1e-6): boolean {
  const sH = Math.abs(s.a.y - s.b.y) < eps;
  const tH = Math.abs(t.a.y - t.b.y) < eps;
  if (sH === tH) return false;
  const h = sH ? s : t;
  const v = sH ? t : s;
  const hx0 = Math.min(h.a.x, h.b.x);
  const hx1 = Math.max(h.a.x, h.b.x);
  const vy0 = Math.min(v.a.y, v.b.y);
  const vy1 = Math.max(v.a.y, v.b.y);
  const vx = v.a.x;
  const hy = h.a.y;
  return vx > hx0 + eps && vx < hx1 - eps && hy > vy0 + eps && hy < vy1 - eps;
}
