export type DataRoot = { kind: "public" | "fixtures" | "custom"; dir: string; base: "/data" | "/data-fixture"; explicit: boolean };
export function resolveDataRoot(webDir: string, env?: Record<string, string | undefined>): DataRoot;
