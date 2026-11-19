/**
 * Display formatting, PLAN §3.3. One rule set; pipeline/export/formats.py mirrors
 * it and both reproduce pipeline/export/golden/format_cases.json (its `rules`
 * are the specification):
 *  - rounding is half away from zero on the exact binary value of the double
 *    (Number.prototype.toFixed on |v|);
 *  - a leading U+2212 minus when v < 0 and the formatted magnitude is not zero;
 *  - tiers are chosen on the rounded magnitude ("₹1,000 crore", never "₹1000 crore" or "1.00%");
 *  - en-IN grouping on the integer part of every number.
 * Inputs: inr in ₹ crore; pct_gdp and pct are fractions; per100 is ₹ per ₹100.
 */
export type FmtKind = "inr" | "pct_gdp" | "per100" | "pct" | "count";

export const MINUS = "−";

/** |x| rounded half away from zero to d decimals (exact binary value), as a string. */
export function fixedAbs(x: number, d: number): string {
  if (!Number.isFinite(x)) throw new Error(`format: non-finite value ${x}`);
  const a = Math.abs(x);
  if (a >= 1e21) throw new Error(`format: value out of range ${x}`);
  return a.toFixed(d);
}

/** Indian digit grouping of the integer part of an unsigned decimal string: "29073287.5" -> "2,90,73,287.5". */
export function groupIndian(s: string): string {
  const dot = s.indexOf(".");
  const ip = dot < 0 ? s : s.slice(0, dot);
  const frac = dot < 0 ? "" : s.slice(dot);
  if (ip.length <= 3) return ip + frac;
  const last3 = ip.slice(-3);
  let rest = ip.slice(0, -3);
  const parts: string[] = [];
  while (rest.length > 2) {
    parts.unshift(rest.slice(-2));
    rest = rest.slice(0, -2);
  }
  if (rest) parts.unshift(rest);
  return `${parts.join(",")},${last3}${frac}`;
}

const isZero = (s: string) => !/[1-9]/.test(s);

function sign(v: number, magnitude: string, body: string): string {
  return v < 0 && !isZero(magnitude) ? `${MINUS}${body}` : body;
}

/** ₹ crore -> "₹2.09 lakh crore", "₹25,102 crore", "₹236 crore", "₹7.5 crore". */
export function formatInr(v: number): string {
  const r0 = fixedAbs(v, 0);
  if (Number(r0) >= 1e5) {
    const m = fixedAbs(v / 1e5, 2);
    return sign(v, m, `₹${groupIndian(m)} lakh crore`);
  }
  const r1 = fixedAbs(v, 1);
  if (Number(r1) >= 10) return sign(v, r0, `₹${groupIndian(r0)} crore`);
  return sign(v, r1, `₹${r1} crore`);
}

/** A share of GDP (fraction) -> "56.5% of GDP", "0.72% of GDP", "<0.01% of GDP". */
export function formatPctGdp(v: number): string {
  if (!Number.isFinite(v)) throw new Error(`format: non-finite value ${v}`);
  const p = 100 * Math.abs(v);
  const p1 = p.toFixed(1);
  if (Number(p1) >= 1) return sign(v, p1, `${groupIndian(p1)}% of GDP`);
  const p2 = p.toFixed(2);
  if (Number(p2) >= 0.01) return sign(v, p2, `${p2}% of GDP`);
  if (v === 0) return "0% of GDP";
  return v < 0 ? `${MINUS}<0.01% of GDP` : "<0.01% of GDP";
}

/** Rupees per ₹100 -> "₹46.9". */
export function formatPer100(v: number): string {
  const m = fixedAbs(v, 1);
  return sign(v, m, `₹${groupIndian(m)}`);
}

/** A share that is not of GDP (fraction) -> "19.2%". */
export function formatPct(v: number): string {
  if (!Number.isFinite(v)) throw new Error(`format: non-finite value ${v}`);
  const m = (100 * Math.abs(v)).toFixed(1);
  return sign(v, m, `${groupIndian(m)}%`);
}

/** A count -> "2,169" (en-IN grouping). */
export function formatCount(n: number): string {
  const m = fixedAbs(n, 0);
  return sign(n, m, groupIndian(m));
}

export function format(value: number, kind: FmtKind): string {
  switch (kind) {
    case "inr":
      return formatInr(value);
    case "pct_gdp":
      return formatPctGdp(value);
    case "per100":
      return formatPer100(value);
    case "pct":
      return formatPct(value);
    case "count":
      return formatCount(value);
    default: {
      const k: never = kind;
      throw new Error(`format: unknown kind ${String(k)}`);
    }
  }
}
