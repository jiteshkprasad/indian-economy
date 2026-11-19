import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { GAP_CAUSES, type GapCause, type GapFigure } from "@/data/gaps";
import { loadSummary, summaryPath } from "@/data/server";
import { format } from "@/lib/format";
import s from "@/components/gaps/gaps.module.css";

type Props = { params: Promise<{ locale: string }> };

const TITLE = "What this model can't tell you yet, and why";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  setRequestLocale(locale);
  return {
    title: TITLE,
    description:
      "The known gaps in the map of India's economy, grouped by why they exist, with their size in GDP terms where the project's issue log gives one.",
  };
}

/** ₹ crore for a figure: an issue-log number, or a summary.json value bound at build time. */
function crore(f: GapFigure): number {
  if (f.kind === "issues") return f.crore;
  const v = summaryPath(f.path);
  const n = typeof v === "number" ? v : (v as { value?: unknown })?.value;
  if (typeof n !== "number") throw new Error(`gaps: summary path "${f.path}" is not a number`);
  return n;
}

function source(f: GapFigure): string {
  return f.kind === "issues" ? `issue log ${f.ref}` : "the map's own data export";
}

type Row = { cause: GapCause; label: string; title: string; crore: number; share: number; src: string };

export default async function GapsPage({ params }: Props) {
  const { locale } = await params;
  setRequestLocale(locale);
  const gdp = loadSummary().gdp.value;

  // Two different kinds of size: a gap (a difference between numbers), and the value of flows
  // that rest on an assumption. They are charted apart so one is never read as the other.
  const gapRows: Row[] = [];
  const restRows: Row[] = [];
  for (const cause of GAP_CAUSES) {
    for (const item of cause.items) {
      for (const f of item.figures) {
        const c = crore(f);
        const row = { cause, label: f.label, title: item.title, crore: c, share: c / gdp, src: source(f) };
        (f.kind === "summary" ? restRows : gapRows).push(row);
      }
    }
  }
  const sortDesc = (a: Row, b: Row) => b.crore - a.crore;
  gapRows.sort(sortDesc);
  restRows.sort(sortDesc);
  const max = Math.max(...gapRows.map((r) => r.crore), ...restRows.map((r) => r.crore));

  const chart = (rows: Row[], caption: string) => (
    <div className={s.chart}>
      <table>
        <caption style={{ textAlign: "left", fontWeight: 600, padding: "4px 0 8px" }}>{caption}</caption>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.title}-${r.label}`}>
              <th scope="row">
                <a href={`#${r.cause.id}`}>{r.title}</a>: {r.label}
              </th>
              <td className={s.barCell} aria-hidden="true">
                <div className={`${s.bar} ${s[`tone-${r.cause.tone}`]}`} style={{ width: `${(100 * r.crore) / max}%` }} />
              </td>
              <td className={s.val}>
                {format(r.share, "pct_gdp")}
                <br />
                <span className={s.chartNote}>{format(r.crore, "inr")}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <article className={`container ${s.page}`}>
      <header className={s.header}>
        <h1>{TITLE}</h1>
        <p className={s.lede}>
          This map is built from official statistics, and official statistics leave holes. Rather than hide them, this
          page lists every known gap, groups them by <em>why</em> they exist, and gives a size in GDP terms wherever the
          project&apos;s issue log supports one. Where it does not, the page says so instead of guessing.
        </p>
        <p className={s.note}>
          <strong>The short version.</strong> The big totals (GDP, consumption, investment, trade, saving) are official.
          What is uncertain is mostly <em>who pays whom</em> inside those totals: interest, dividends and transfers
          between households, companies, banks and governments. Most of that uncertainty comes from India&apos;s new GDP
          series not yet publishing those details.
        </p>
      </header>

      <section aria-labelledby="how-h">
        <h2 id="how-h">How a number reaches the map, and where it can go wrong</h2>
        <div className={s.flow}>
          <div className={s.flowStep}>
            <h3>1. Official statistics</h3>
            <p>MoSPI, RBI, Finance Accounts, budgets, surveys.</p>
            <ul>
              <li><a href="#data">Some data is not public</a></li>
              <li><a href="#coverage">Some is only partly published</a></li>
            </ul>
          </div>
          <div className={s.flowStep}>
            <h3>2. Combine and fill</h3>
            <p>Put sources together; fill missing splits.</p>
            <ul>
              <li><a href="#disagree">Sources disagree</a></li>
              <li><a href="#base">Old and new GDP series don&apos;t line up</a></li>
            </ul>
          </div>
          <div className={s.flowStep}>
            <h3>3. Balance</h3>
            <p>Make every account add up: what each group receives equals what it pays or saves.</p>
            <ul>
              <li><a href="#saving">Saving doesn&apos;t add up by sector</a></li>
              <li><a href="#judgement">Some levels are judgement calls</a></li>
            </ul>
          </div>
          <div className={s.flowStep}>
            <h3>4. The map</h3>
            <p>Every number carries a label: official, derived, estimated or set by balancing.</p>
            <ul>
              <li><a href="#framework">Some parts are not built yet</a></li>
            </ul>
          </div>
        </div>
      </section>

      <section aria-labelledby="size-h" style={{ marginTop: 32 }}>
        <h2 id="size-h">How big are they?</h2>
        <p className={s.chartNote} style={{ maxWidth: "72ch" }}>
          Two different things are measured below, so they are shown apart. The first chart is the size of each
          gap: a difference between two numbers that should agree. The second is how much of the map rests on an
          assumption: the value of flows whose level depends on it, not an error of that size. GDP for 2023-24 is{" "}
          {format(gdp, "inr")}.
        </p>
        {chart(gapRows, "Size of each gap")}
        {chart(restRows, "Value of the map that rests on an assumption")}
      </section>

      {GAP_CAUSES.map((cause) => (
        <section key={cause.id} id={cause.id} aria-labelledby={`${cause.id}-h`} className={s.cause}>
          <div className={s.causeHead}>
            <span aria-hidden="true" className={`${s.swatch} ${s[`tone-${cause.tone}`]}`} />
            <h2 id={`${cause.id}-h`}>{cause.name}</h2>
          </div>
          <p style={{ margin: "4px 0 0" }}>{cause.short}.</p>
          <div className={s.items}>
            {cause.items.map((item) => (
              <div key={item.title} className={s.item}>
                <h3>{item.title}</h3>
                <p style={{ margin: 0 }}>{item.plain}</p>
                <dl>
                  <dt>Why</dt>
                  <dd>{item.why}</dd>
                  <dt>Size</dt>
                  <dd>
                    {item.figures.length === 0 && item.noSize}
                    {item.figures.map((f) => {
                      const c = crore(f);
                      return (
                        <div key={f.label} className={s.size}>
                          {f.label}: <strong>{format(c, "inr")}</strong> ({format(c / gdp, "pct_gdp")})
                        </div>
                      );
                    })}
                  </dd>
                  <dt>What would close it</dt>
                  <dd>{item.fix}</dd>
                </dl>
                <p className={s.refs}>Issue log: {item.refs.join(", ")}</p>
              </div>
            ))}
          </div>
        </section>
      ))}

      <section aria-labelledby="more-h">
        <h2 id="more-h">Also shown, not hidden</h2>
        <p style={{ maxWidth: "72ch" }}>
          The official accounts for 2023-24 do not fully close on their own: there is a household residual, a
          services-imports reconciliation item and saving-investment errors and omissions. The map carries them in a
          separate account instead of balancing them away. Their sizes, and the full technical detail behind this page,
          are on the <Link href="/methodology/#limits">methodology page</Link>. The complete issue log is the{" "}
          <code>ISSUES.md</code> file in the project&apos;s repository.
        </p>
      </section>
    </article>
  );
}
