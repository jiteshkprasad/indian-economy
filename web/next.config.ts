import fs from "node:fs";
import path from "node:path";
import createMDX from "@next/mdx";
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

// PLAN §4.14. Static export; data is read at build time by src/data/server.ts.
// Dev servers with a per-unit NEXT_DIST_DIR use their own gitignored tsconfig
// (scripts/dev.mjs creates it) so they do not rewrite the committed tsconfig.json.
const distDir = process.env.NEXT_DIST_DIR;
const devTsconfig = distDir ? `tsconfig.${path.basename(distDir).replace(/^\.+/, "")}.json` : null;
const tsconfigPath = devTsconfig && fs.existsSync(path.join(process.cwd(), devTsconfig)) ? devTsconfig : "tsconfig.json";

const nextConfig: NextConfig = {
  typescript: { tsconfigPath },
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  pageExtensions: ["ts", "tsx", "md", "mdx"],
  distDir: distDir ?? ".next",
  typedRoutes: false,
  poweredByHeader: false,
};

// Turbopack accepts remark/rehype plugins only as serialisable strings.
const withMDX = createMDX({
  extension: /\.mdx?$/,
  options: { remarkPlugins: ["remark-gfm"] },
});

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

export default withNextIntl(withMDX(nextConfig));
