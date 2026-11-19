import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { NAMESPACES } from "@/i18n/routing";

// PLAN §4.12: every key used through useTranslations / getTranslations exists in
// messages/en/<namespace>.json. Checks calls with a string-literal key on a
// translator bound to a string-literal namespace; template-literal keys are
// listed separately and their static prefix must exist.
const web = path.resolve(__dirname, "../../..");
const src = path.join(web, "src");

function walk(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? walk(p) : /\.(tsx?|mdx)$/.test(e.name) ? [p] : [];
  });
}

function loadMessages(): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const ns of NAMESPACES) {
    const p = path.join(web, "messages", "en", `${ns}.json`);
    out[ns] = fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf8")) : undefined;
  }
  return out;
}

function has(obj: unknown, dotted: string): boolean {
  let cur = obj;
  for (const part of dotted.split(".")) {
    if (cur === null || typeof cur !== "object" || !(part in (cur as Record<string, unknown>))) return false;
    cur = (cur as Record<string, unknown>)[part];
  }
  return true;
}

type Use = { file: string; key: string; dynamic: boolean };

function collect(): Use[] {
  const uses: Use[] = [];
  const bind =
    /(?:const|let)\s+(\w+)\s*=\s*(?:await\s+)?(?:useTranslations|getTranslations)\(\s*(?:"([^"]*)"|'([^']*)'|\{[^}]*?namespace:\s*"([^"]*)"[^}]*\})?\s*\)/g;
  for (const file of walk(src)) {
    const text = fs.readFileSync(file, "utf8");
    // Bindings in source order; a call belongs to the nearest preceding binding of
    // its variable name (an approximation of lexical scope that is right for
    // components and generateMetadata declared one after another).
    const bindings: Array<{ v: string; ns: string; at: number }> = [];
    let m: RegExpExecArray | null;
    bind.lastIndex = 0;
    while ((m = bind.exec(text))) bindings.push({ v: m[1], ns: m[2] ?? m[3] ?? m[4] ?? "", at: m.index });
    for (const v of new Set(bindings.map((b) => b.v))) {
      const call = new RegExp(`\\b${v}(?:\\.rich|\\.markup|\\.raw|\\.has)?\\(\\s*(?:"([^"]+)"|'([^']+)'|\`([^\`]+)\`)`, "g");
      let c: RegExpExecArray | null;
      while ((c = call.exec(text))) {
        const b = bindings.filter((x) => x.v === v && x.at < c!.index).pop();
        if (!b) continue;
        const ns = b.ns;
        const lit = c[1] ?? c[2];
        const key = (k: string) => (ns ? `${ns}.${k}` : k);
        if (lit) uses.push({ file: path.relative(web, file), key: key(lit), dynamic: false });
        else if (c[3]) {
          // the object that holds the dynamic key: everything before the last "." of the static prefix
          const head = c[3].split("${")[0];
          const parent = head.includes(".") ? head.slice(0, head.lastIndexOf(".")) : "";
          uses.push({ file: path.relative(web, file), key: parent ? key(parent) : ns, dynamic: true });
        }
      }
    }
  }
  return uses;
}

const messages = loadMessages();
const uses = collect();

describe("message keys", () => {
  it("finds translator calls", () => {
    expect(uses.length).toBeGreaterThan(10);
  });
  it("every namespace file in use exists and is valid JSON", () => {
    const used = new Set(uses.map((u) => u.key.split(".")[0]));
    const missing = [...used].filter((ns) => (NAMESPACES as readonly string[]).includes(ns) && messages[ns] === undefined);
    expect(missing, `missing messages/en/<ns>.json for: ${missing.join(", ")}`).toEqual([]);
  });
  it("every static key exists", () => {
    const missing = uses.filter((u) => !u.dynamic && !has(messages, u.key)).map((u) => `${u.file}: ${u.key}`);
    expect(missing).toEqual([]);
  });
  it("the static prefix of every dynamic key exists", () => {
    const missing = uses.filter((u) => u.dynamic && u.key !== "" && !has(messages, u.key)).map((u) => `${u.file}: ${u.key}…`);
    expect(missing).toEqual([]);
  });
});
