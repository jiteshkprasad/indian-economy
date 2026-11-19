import { format, type FmtKind } from "@/lib/format";

/**
 * A formatted figure. Carries data-num-value and data-num-fmt so the fidelity
 * test can check that the text equals format(value) (PLAN §4.7, §5.3).
 * Pair it with a <StatusBadge> wherever the figure is shown.
 */
export function Num({ value, fmt, className }: { value: number; fmt: FmtKind; className?: string }) {
  return (
    <span className={className ? `num ${className}` : "num"} data-num-value={String(value)} data-num-fmt={fmt}>
      {format(value, fmt)}
    </span>
  );
}
