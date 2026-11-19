import type { Cells, Hierarchy, Pinned, Summary, TsView } from "@/lib/sankey/contract";
import type { NodeScope } from "@/lib/sankey/select";

export type MapInitialData = {
  summary: Summary;
  hierarchy: Hierarchy;
  cells: Cells;
  pinned: Pinned;
  tsView: TsView;
};

export type MapViewProps = {
  /** controlled = driven by props (stories) */
  mode: "interactive" | "controlled";
  view: "sam" | "ts";
  preset: "simple" | "full";
  year: string;
  expanded: string[];
  selected?: string | null;
  /** link/node ids; others dimmed */
  highlight?: string[];
  /** stories on phones: draw only highlighted links */
  onlyHighlighted?: boolean;
  onSelect?: (id: string | null) => void;
  returnFlows?: "stubs" | "arcs";
  height?: number;
  initialData?: MapInitialData;
};

export type FlowDetailPanelProps = {
  id: string;
  year: string;
  onClose?: () => void;
  /** where the selection is drawn (the same id can name different accounts in each preset); default: the hierarchy node */
  scope?: NodeScope;
};

export type FirstScreenProps = { summary: Summary };
