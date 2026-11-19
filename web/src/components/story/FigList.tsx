import { useTranslations } from "next-intl";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { format } from "@/lib/format";
import { isStorySlug, storyKey } from "@/lib/story/registry";
import { storyFigure } from "./StoryFig";
import s from "./story.module.css";

/** Splits the `ids` attribute ("a b c" or "a, b, c") of <FigList>. Exported for the fig-id test. */
export function figListIds(ids: string): string[] {
  return ids.split(/[\s,]+/).filter(Boolean);
}

/**
 * `<FigList ids="liab_cen_gsec liab_cen_ssav" caption="borrowCentre"/>` in story MDX: a table
 * of figures with their labels (messages/<locale>/story.json `figs.<slug>.<id>`), values
 * and badges. Used where a step lists the parts of a whole. Server component, bound to
 * its story by the page.
 */
export function FigList({ slug, ids, caption }: { slug: string; ids: string; caption?: string }) {
  const t = useTranslations("story");
  if (!isStorySlug(slug)) throw new Error(`FigList: unknown story "${slug}"`);
  const list = figListIds(ids);
  if (list.length === 0) throw new Error(`FigList in ${slug}: no ids`);
  return (
    <div className={s.tableWrap}>
      <table className={s.figTable}>
        {caption && <caption>{t(`captions.${slug}.${caption}`)}</caption>}
        <thead>
          <tr>
            <th scope="col">{t("list.item")}</th>
            <th scope="col" className={s.right}>
              {t("list.valueAndLabel")}
            </th>
          </tr>
        </thead>
        <tbody>
          {list.map((id) => {
            const fig = storyFigure(slug, id);
            return (
              <tr key={id}>
                <th scope="row">{t(storyKey.figLabel(slug, id))}</th>
                <td className={s.right}>
                  <span className={s.figValue}>
                    <span className="num" data-fig-id={id} data-num-value={String(fig.value)} data-num-fmt={fig.unit}>
                      {format(fig.value, fig.unit)}
                    </span>
                    <StatusBadge total={fig.total} split={fig.split} composition={fig.composition} compact />
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
