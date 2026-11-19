import type { MDXProps } from "mdx/types";
import type { ComponentType } from "react";
import EnBuild from "@content/en/methodology/build.mdx";
import EnEstimates from "@content/en/methodology/estimates.mdx";
import EnIssues from "@content/en/methodology/issues.mdx";
import EnLimits from "@content/en/methodology/limits.mdx";
import EnProvisional from "@content/en/methodology/provisional.mdx";
import EnReproduce from "@content/en/methodology/reproduce.mdx";
import EnSources from "@content/en/methodology/sources.mdx";
import EnStatus from "@content/en/methodology/status.mdx";
import EnTimeSeries from "@content/en/methodology/time-series.mdx";
import EnWhat from "@content/en/methodology/what.mdx";

type Mdx = ComponentType<MDXProps>;

/**
 * Methodology prose per locale, keyed by the `mdx` name in sections.ts. Static
 * imports (not a template-literal import) so the bundler sees every file; adding a
 * locale means adding content/<locale>/methodology/*.mdx and one entry here.
 */
export const METHODOLOGY_MDX: Record<string, Record<string, Mdx>> = {
  en: {
    what: EnWhat,
    build: EnBuild,
    status: EnStatus,
    estimates: EnEstimates,
    limits: EnLimits,
    "time-series": EnTimeSeries,
    provisional: EnProvisional,
    sources: EnSources,
    reproduce: EnReproduce,
    issues: EnIssues,
  },
};
