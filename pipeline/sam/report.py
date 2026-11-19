"""BALANCING.md (generated from the balancing outputs) and the over-threshold explanation check.

Everything in the report is read from data/sam/<year>/ (balancing_run.json, balancing_log.parquet,
balancing_constraints.parquet, prior_diagnostics.parquet), pipeline/sam/explanations.yaml and the per-block
pipeline/sam/explanations/<block>.yaml files, so
`sam-report` regenerates it byte-identically without re-balancing. No timestamps.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.core import io
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.accounts import SAM_DIR
from pipeline.sam.framework import SamError, SamPaths

EXPLANATIONS_FILE = SAM_DIR / "explanations.yaml"  # the shared file
EXPLANATIONS_DIR = SAM_DIR / "explanations"  # per-block files <block>.yaml (DECISIONS D2-22)
KEY = ("row", "col", "ref", "component")
SOURCE = "_file"  # added to every loaded item: the file it came from (shared file, or '<block>.yaml')


CELL = "*"  # ref and component of a cell-level explanation (the whole (row, col) cell)


def explanation_files(path: Path = EXPLANATIONS_FILE, block_dir: Path = EXPLANATIONS_DIR) -> list[Path]:
    """The shared file, then pipeline/sam/explanations/<block>.yaml in name order. A file there whose stem is
    not a DESIGN_BRIEF block (or that is not .yaml) is an error: an item in a misnamed file would be silently
    ignored."""
    from pipeline.sam.accounts import EXPECTED_BLOCKS

    files = [path] if path.exists() else []
    if block_dir.exists():
        bad = sorted(f.name for f in block_dir.iterdir() if f.suffix != ".yaml" or f.stem not in EXPECTED_BLOCKS)
        if bad:
            raise SamError(
                f"{block_dir}: {bad} are not <block>.yaml files for a DESIGN_BRIEF block ({', '.join(EXPECTED_BLOCKS)})"
            )
        files += sorted(block_dir.glob("*.yaml"))
    return files


def _load_file(f: Path, out: dict[tuple[str, str, str, str], dict[str, Any]]) -> None:
    name = f.name if f.parent.name != "explanations" else f"explanations/{f.name}"
    doc = io.read_yaml(f) or {}
    if not isinstance(doc, dict) or set(doc) - {"explanations"}:
        raise SamError(f"{name}: the file holds one key, 'explanations', a list of items")
    items = doc.get("explanations") or []
    for it in items:
        if not isinstance(it, dict) or not all(isinstance(it.get(k), str) for k in (*KEY, "why")):
            raise SamError(f"{name}: each item needs row, col, ref, component and why: {it!r}")
        if not all(
            isinstance(it.get(k), (int, float)) and not isinstance(it.get(k), bool) for k in ("prior", "balanced")
        ):
            raise SamError(f"{name}: each item records the prior and balanced value it explains: {it!r}")
        if (it["ref"] == CELL) != (it["component"] == CELL):
            raise SamError(f"{name}: a cell-level item has ref and component both '*': {it!r}")
        if len(it["why"].strip()) < 40:
            raise SamError(f"{name}: 'why' is too short to say why the prior was off: {it!r}")
        key = tuple(it[k] for k in KEY)
        if key in out:
            where = out[key][SOURCE]
            raise SamError(
                f"{name}: {key} explained twice" + (f" (also in {where})" if where != name else " in this file")
            )
        out[key] = {**it, SOURCE: name}  # type: ignore[index]


def load_explanations(
    path: Path = EXPLANATIONS_FILE, block_dir: Path = EXPLANATIONS_DIR
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    """explanations.yaml and every pipeline/sam/explanations/<block>.yaml (DECISIONS D2-22; same item format)
    -> {(row, col, ref, component): item}. An item explains one entry, or a whole cell with ref: "*" and
    component: "*". Each records the `prior` and `balanced` value it explains, so a later run that moves the
    entry (or cell) differently makes it stale (spec.EXPLAIN_DRIFT_*). A key explained in two files (or twice
    in one) is an error. Each item carries the file it came from (`_file`): an entry-level item in a block's
    file must explain an entry of that block (stale_explanations), a cell-level item may sit in any file."""
    out: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for f in explanation_files(path, block_dir):
        _load_file(f, out)
    return out


def _fits(item: dict[str, Any], change: float) -> bool:
    """The explanation still describes this run: its change and the current one agree within the drift."""
    explained = float(item["balanced"]) - float(item["prior"])
    return abs(change - explained) <= max(spec.EXPLAIN_DRIFT_REL * abs(explained), spec.EXPLAIN_DRIFT_ABS)


def cell_changes(log: pl.DataFrame) -> pl.DataFrame:
    """Per (row, col) cell: prior, balanced, change, entry count, and whether the cell needs an explanation."""
    cells = (
        log.group_by(["row", "col"], maintain_order=True)
        .agg(pl.col("prior").sum(), pl.col("balanced").sum(), pl.len().cast(pl.Int64).alias("n_entries"))
        .sort(["row", "col"])
        .with_columns((pl.col("balanced") - pl.col("prior")).alias("change"))
    )
    need = [spec.needs_explanation(a, b) for a, b in zip(cells["prior"].to_list(), cells["balanced"].to_list())]
    return cells.with_columns(pl.Series("explanation_required", need, dtype=pl.Boolean))


def unexplained(log: pl.DataFrame, explanations: dict | None = None) -> pl.DataFrame:
    """What needs an explanation (spec.needs_explanation, SPEC s.6) and has no current one: entries, and cells
    (ref = component = '*') whose total moved over the threshold. A cell is explained by a cell-level item,
    or, if it has a single entry, by that entry's item. An item whose change no longer fits (drift) does
    not count. Columns: row, col, ref, component, prior, balanced, change."""
    ex = load_explanations() if explanations is None else explanations
    cols = ["row", "col", "ref", "component", "prior", "balanced", "change"]
    rows: list[dict[str, Any]] = []
    for r in log.filter(pl.col("explanation_required")).iter_rows(named=True):
        it = ex.get(tuple(r[k] for k in KEY))
        if it is None or not _fits(it, r["change"]):
            rows.append({k: r[k] for k in cols})
    # a cell with one entry is that entry (handled above); a cell with several needs a cell-level item
    for c in cell_changes(log).filter(pl.col("explanation_required") & (pl.col("n_entries") > 1)).iter_rows(named=True):
        it = ex.get((c["row"], c["col"], CELL, CELL))
        if it is None or not _fits(it, c["change"]):
            rows.append({"row": c["row"], "col": c["col"], "ref": CELL, "component": CELL, "prior": c["prior"],
                         "balanced": c["balanced"], "change": c["change"]})  # fmt: skip
    schema = {"row": pl.String(), "col": pl.String(), "ref": pl.String(), "component": pl.String(),
              "prior": pl.Float64(), "balanced": pl.Float64(), "change": pl.Float64()}  # fmt: skip
    return pl.DataFrame(rows, schema=schema, orient="row") if rows else pl.DataFrame(schema=schema)


def stale_explanations(log: pl.DataFrame, explanations: dict | None = None) -> list[str]:
    """Items (shared or per-block file) that explain nothing this run needs, whose change no longer fits, or
    that sit in another block's file."""
    ex = load_explanations() if explanations is None else explanations
    by_entry = {tuple(r[k] for k in KEY): r for r in log.iter_rows(named=True)}
    cells = {(r["row"], r["col"]): r for r in cell_changes(log).iter_rows(named=True)}
    out = []
    for key, it in sorted(ex.items()):
        if key[2] == CELL:
            c = cells.get((key[0], key[1]))
            if c is None or not c["explanation_required"] or c["n_entries"] == 1:
                out.append(f"{key}: the cell does not need a cell-level explanation in this run")
            elif not _fits(it, c["change"]):
                out.append(f"{key}: explains a change of {it['balanced'] - it['prior']:,.2f}, now {c['change']:,.2f}")
            continue
        r = by_entry.get(key)
        src = str(it.get(SOURCE, ""))
        if r is None:
            out.append(f"{key}: no such entry")
        elif src.startswith("explanations/") and "block" in r and src != f"explanations/{r['block']}.yaml":
            out.append(f"{key}: explained in {src}, but the entry belongs to block {r['block']} (move the item to "
                       f"explanations/{r['block']}.yaml or the shared file)")  # fmt: skip
        elif not r["explanation_required"]:
            out.append(f"{key}: the entry does not need an explanation in this run")
        elif not _fits(it, r["change"]):
            out.append(f"{key}: explains a change of {it['balanced'] - it['prior']:,.2f}, now {r['change']:,.2f}")
    return out


def inr(x: float | None, decimals: int = 0) -> str:
    """Indian digit grouping: 1,23,45,678 (lakh/crore style)."""
    if x is None:
        return "-"
    neg = x < 0
    s = f"{abs(x):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return ("-" if neg else "") + whole + ("." + frac if frac else "")


def _pct(x: float | None) -> str:
    return "-" if x is None else f"{x:+.2f}%"


def _table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return out


CLOSURE_INSTITUTIONS = ("HH", "E_NFPR", "E_NFPU", "FC", "GG", "DOMESTIC")  # FR-closure-1

# audit BS-2 (2026-10-01): the report counts what the explanation items say, not only whether they exist
VERDICTS = ("explained", "level unexplained", "unexplained", "no verdict word")
ROUNDING_ONLY = 10.0  # Rs crore: pre-balancing imbalances below this are listed as one line (SUT rounding)
GRAS_SHOWN = 60
WHY_CHARS = 400  # the adjustments table quotes each item's first sentences; the full text is in its file
HEADLINE = (  # declared totals shown in the acceptance table (read from balancing_constraints.parquet)
    ("households:hh.c1.total", "PFCE (households)"),
    ("government:gov.c2.total", "GFCE (NAS 1.14)"),
    ("capital_financial:cf.k4.hh_saving", "Household saving (NAS 1.9)"),
    ("fincorp:k2.fc_saving_total", "Financial corporations' saving (NAS 1.9)"),
    ("government:gov.k3.gg_saving", "General government saving (NAS 1.9)"),
    ("government:gov.cofog.current_transfers", "GG current transfers (NAS 4.2 COFOG)"),
    ("government:gov.cofog.capital_transfers", "GG capital transfers (NAS 4.2 COFOG)"),
    ("closure:d1.published_total", "Statistical discrepancy to households (D1)"),
    ("factors:f1.total", "Compensation of employees received by residents"),
    ("taxes:p7a.total", "Product taxes (SUT)"),
    ("taxes:t4.total", "Corporation tax (Receipt Budget)"),
    ("taxes:t3.total", "Other taxes on income (cash)"),
    ("rest_of_world:row.current_receipts", "RoW current receipts (NAS 6.1)"),
    ("rest_of_world:row.current_disbursements", "RoW current disbursements (NAS 6.1)"),
    ("rest_of_world:row.k8b_liabilities_to_row", "Foreign liabilities incurred (NAS 6.1)"),
    ("capital_financial:cf.i3a.cis.total", "Change in inventories"),
)
INSTITUTIONS = {"Households": "HH", "Government": "GOV", "Public NFCs": ("E_NFPU",), "Private NFCs": ("E_NFPR",),
                "Financial corporations": "FC"}  # fmt: skip


def verdict(why: str) -> str:
    """The verdict an explanation item states in its first words (SAM_GUIDE s.12 files start `why` with one)."""
    w = " ".join(why.split()).lower()
    if w.startswith("explained in direction") or "level unexplained" in w[:90]:
        return "level unexplained"
    if w.startswith("unexplained"):
        return "unexplained"
    if w.startswith("explained"):
        return "explained"
    return "no verdict word"


def current_items(log: pl.DataFrame, ex: dict) -> list[tuple[tuple[str, str, str, str], dict[str, Any]]]:
    """The items that currently explain an over-threshold entry or multi-entry cell of this run."""
    out = []
    for r in log.filter(pl.col("explanation_required")).iter_rows(named=True):
        key = tuple(r[k] for k in KEY)
        it = ex.get(key)
        if it is not None and _fits(it, r["change"]):
            out.append((key, it))
    for c in cell_changes(log).filter(pl.col("explanation_required") & (pl.col("n_entries") > 1)).iter_rows(named=True):
        key = (c["row"], c["col"], CELL, CELL)
        it = ex.get(key)
        if it is not None and _fits(it, c["change"]):
            out.append((key, it))
    return out


def _verdict_counts(items: list[tuple[tuple[str, str, str, str], dict[str, Any]]]) -> dict[str, int]:
    n = dict.fromkeys(VERDICTS, 0)
    for _, it in items:
        n[verdict(str(it.get("why", "")))] += 1
    return n


def glossary() -> list[str]:
    return [
        "",
        "## Glossary",
        "",
        "- **Prior**: the SAM the nine blocks built from the sources, before balancing. **Balanced**: after it.",
        "- **z** = balanced / prior for one entry (1.00 = unchanged; 1.50 = raised by half; signs never flip).",
        "- **Fixed** entries never move (published cells trusted exactly). **Anchored** entries are official "
        "figures that may move only inside a small box (their `tol_rel`, e.g. cash vs accrual). **Free** entries "
        "are estimates; their confidence (high / medium / low) sets how costly a move is (weights 4 / 1 / 0.25).",
        "- **Constraint** (band): a published total that a group of entries must add up to, within a stated "
        "tolerance. **Binding**: the balanced sum sits on the edge of the band (the solver pushed hardest there).",
        "- **Cross-entropy**: the balancing rule. It finds the smallest weighted relative change to the prior that "
        "makes every account's receipts equal its payments and keeps every constraint; large moves land on the "
        "low-confidence entries of the accounts whose prior gaps are largest.",
        "- **Dual Newton / interior point**: the two numerical methods that solve it (the second is the fallback "
        "when the first stalls, DECISIONS D2-23). **KKT certificate**: the check that the answer really is that "
        "minimum (balance, bands and boxes hold; optimality conditions met); a failed certificate fails the run.",
        "- **Phase 1 / slack**: before the solve, an LP (HiGHS) checks that all bands and boxes can hold together; "
        "if not, the smallest widening needed (slack) is reported as a finding, never hidden.",
        "- **GRAS**: a simpler balancing method (no weights, no constraints) run as a cross-check.",
        "- **Z**: the household saving gap of the prior (saving the household accounts deliver less NAS "
        "household saving).",
        "- Explanation verdicts: **Explained** (the prior was off for a documented source disagreement and the "
        "move goes toward other evidence), **Explained in direction; level unexplained** (why the account needed "
        "the move is documented, but no source supports this entry's balanced level), **Unexplained** (a "
        "finding for Checkpoint B).",
    ]


def _plain_certificate(run: dict[str, Any]) -> list[str]:
    c, ph, po = run["certificate"], run["phase1"], run["polish"]
    return [
        f"- KKT certificate (proof that this is the minimum-adjustment answer): "
        f"{'passed' if c.get('ok') else 'FAILED'}; largest account residual {c.get('max_balance_residual', 0):g} "
        f"crore, largest band violation {c.get('max_band_violation', 0):g}, largest box violation "
        f"{c.get('max_box_violation', 0):g}, relative duality gap {c.get('duality_gap_rel', 0):g}; "
        f"{c.get('entries_at_bounds', 0)} anchored entries on the edge of their box, "
        f"{c.get('entries_forced_to_zero', 0)} entries forced to zero. (Raw record: 'Technical detail' at the end.)",
        f"- Phase 1 (can every band and box hold at once?): total slack {ph.get('total_slack', 0):g} crore; "
        f"{ph.get('widened_bands', 0)} bands and {ph.get('widened_anchored', 0)} anchored boxes had to be widened.",
        f"- Polish (a last exact-balance step on free entries): {'applied' if po.get('applied') else 'not needed'}; "
        f"{po.get('entries_adjusted', 0)} entries adjusted, {po.get('sign_flips', 0)} sign flips.",
    ]


def what_balancing_did(log: pl.DataFrame, acc_groups: dict[str, list[str]]) -> list[str]:
    """Audit BS-2: the moves by gap-map ref, and each institution's net receipts by ref, in plain terms."""
    L = ["", "## What balancing did (by ref and by institution)", ""]
    moved = log.with_columns((pl.col("balanced") - pl.col("prior")).alias("d"))
    by_ref = (
        moved.group_by("ref", maintain_order=True)
        .agg(
            pl.col("d").sum().alias("net"),
            pl.col("d").abs().sum().alias("gross"),
            pl.col("explanation_required").sum().alias("n_req"),
            pl.col("prior").abs().sum().alias("prior_abs"),
        )
        .filter(pl.col("gross") >= spec.EXPLAIN_MIN_ABS)
        .sort(["gross", "ref"], descending=[True, False])
    )
    L += [
        "Every ref whose entries moved by Rs 500 crore or more in total (gross = sum of absolute moves; net = "
        "sum of signed moves; gross / prior = the share of the ref's prior that moved):",
        "",
    ]
    rows = []
    for r in by_ref.iter_rows(named=True):
        share = f"{100.0 * r['gross'] / r['prior_abs']:.1f}%" if r["prior_abs"] else "-"
        rows.append([r["ref"], inr(r["gross"]), inr(r["net"]), share, str(r["n_req"])])
    L += _table(["Ref", "Gross move", "Net move", "Gross / prior", "Entries over the threshold"], rows)
    L += [
        "",
        "Change in each institution's net receipts, by ref (receipts +, payments -; the six refs that moved it "
        "most). Saving is a payment into the capital account, so a rise in saving shows as a negative line:",
        "",
    ]
    rows = []
    for name, grp in INSTITUTIONS.items():
        accts = sorted(acc_groups.get(grp, [])) if isinstance(grp, str) else sorted(grp)
        inside = pl.col("row").is_in(accts) & pl.col("col").is_in(accts)
        rec = moved.filter(pl.col("row").is_in(accts) & ~inside).select("ref", "d")
        pay = moved.filter(pl.col("col").is_in(accts) & ~inside).select("ref", (-pl.col("d")).alias("d"))
        net = (
            pl.concat([rec, pay])
            .group_by("ref", maintain_order=True)
            .agg(pl.col("d").sum())
            .filter(pl.col("d").abs() >= 1.0)
            .sort([pl.col("d").abs(), "ref"], descending=[True, False])
        )
        for r in net.head(6).iter_rows(named=True):
            rows.append([name, r["ref"], inr(r["d"])])
    L += _table(["Institution", "Ref", "Change in net receipts"], rows) if rows else ["None."]
    return L


def acceptance_section(cons: pl.DataFrame | None, run: dict[str, Any]) -> list[str]:
    """Audit BS-2: the declared totals the SAM must meet, as balanced (the full SPEC acceptance tests are
    tests/sam/test_sam_identities.py and tests/verify/test_sam_balanced_audit.py)."""
    L = ["", "## Acceptance: declared totals after balancing", ""]
    if cons is None or cons.height == 0:
        return L + ["No constraint status file."]
    tol = 1e-3
    held = (pl.col("lo").is_null() | (pl.col("balanced_sum") >= pl.col("lo") - tol)) & (
        pl.col("hi").is_null() | (pl.col("balanced_sum") <= pl.col("hi") + tol)
    )  # a one-sided (min / max) constraint has no lo or no hi
    n_in = cons.filter(held).height
    L += [
        f"- {cons.height} declared constraints: {n_in} hold within their band (numerical slack Rs {tol:g} crore), "
        f"{cons.height - n_in} do not; {int(cons['binding'].sum())} sit on a band edge (listed under 'Constraints "
        f"at a bound'). Slack findings: {len(run['band_violation'])} bands, {len(run['anchor_violation'])} "
        "anchored boxes.",
        "- The SPEC s.6 acceptance tests (GDP three ways, taxes against the Finance Accounts and RBI State "
        "Finances, BoP, flow of funds, saving by sector) run in `tests/sam/test_sam_identities.py` and, "
        "independently, in `tests/verify/test_sam_balanced_audit.py`. The headline totals:",
        "",
    ]
    idx = {r["constraint_id"]: r for r in cons.iter_rows(named=True)}
    rows = []
    for cid, label in HEADLINE:
        r = idx.get(cid)
        if r is None:
            continue
        lo = -float("inf") if r["lo"] is None else r["lo"]
        hi = float("inf") if r["hi"] is None else r["hi"]
        ok = lo - tol <= r["balanced_sum"] <= hi + tol
        band = (f"{'-inf' if r['lo'] is None else inr(lo - r['target'], 2)} .. "
                f"{'+inf' if r['hi'] is None else '+' + inr(hi - r['target'], 2)}")  # fmt: skip
        rows.append([label, f"`{cid}`", inr(r["target"], 2), inr(r["balanced_sum"], 2),
                     inr(r["balanced_sum"] - r["target"], 2), band,
                     ("yes" if ok else "**NO**") + (" (edge)" if r["binding"] else "")])  # fmt: skip
    L += _table(["Total", "Constraint", "Target", "Balanced", "Difference", "Band", "Holds"], rows) if rows else [
        "None."
    ]
    return L


def closure_section(paths: SamPaths, run: dict[str, Any]) -> list[str]:
    """'Before balancing' tables from closure's satellites (FR-closure-1; DESIGN_BRIEF s.5.4: a large prior
    imbalance must be traced to a source disagreement): Z (hh_saving `all.z`), what each institution's income
    flows deliver against what its accounts require, by flow class (institution_gaps), and the constraints
    the prior already violates (constraint_gaps, outside_band = yes). Read-only. If closure was rebuilt after
    this balancing run (its entries' sha256 differs from balancing_run.json), the section says so."""
    sat = paths.satellites("closure")
    names = ("hh_saving", "institution_gaps", "constraint_gaps")
    L = ["", "## Before balancing: where the gaps come from (closure's satellites)", ""]
    missing = [n for n in names if not (sat / f"{n}.parquet").exists()]
    if missing:
        return L + [f"Not available: closure's satellite(s) {', '.join(missing)} do not exist (build closure)."]
    used = run.get("block_inputs", {}).get("closure", {}).get("entries")
    now = io.sha256_file(paths.entries("closure")) if paths.entries("closure").exists() else None
    if used is not None and used != now:
        L += ["**Note: closure was rebuilt after this balancing run; the tables below describe its current outputs, "
              "not the prior that was balanced.**", ""]  # fmt: skip
    hs = pl.read_parquet(sat / "hh_saving.parquet")
    hv = {r["series_id"]: r["value"] for r in hs.select("series_id", "value").iter_rows(named=True)}
    if "all.z" in hv:
        L.append(
            f"- **Z (household saving gap, `hh_saving` all.z): {inr(hv['all.z'], 2)} crore**"
            + (f" = saving the household accounts deliver (K4a sum {inr(hv['all.k4a_sum'], 2)}) - NAS household "
               f"saving (K4 {inr(hv['all.k4_nas'], 2)})." if "all.k4a_sum" in hv and "all.k4_nas" in hv else ".")
        )  # fmt: skip
    else:
        L.append("- Z: closure's `hh_saving` has no `all.z` row.")
    ig = pl.read_parquet(sat / "institution_gaps.parquet").filter(pl.col("institution").is_in(CLOSURE_INSTITUTIONS))
    val = {(r["institution"], r["measure"]): r["value"]
           for r in ig.select("institution", "measure", "value").iter_rows(named=True)}  # fmt: skip
    insts = [i for i in CLOSURE_INSTITUTIONS if any(k[0] == i for k in val)]
    L += ["", "What each institution's income flows deliver (net) against what its own accounts require (net), and the "
          "gap (`institution_gaps`; the domestic gaps sum to about zero: one institution's surplus is another's "
          "shortfall):", ""]  # fmt: skip
    L += _table(
        ["Institution", "Delivered (net)", "Required (net)", "Gap"],
        [[i, inr(val.get((i, "delivered_net")), 2), inr(val.get((i, "required_net")), 2), inr(val.get((i, "gap")), 2)]
         for i in insts],
    ) if insts else ["None (no rows for these institutions)."]  # fmt: skip
    flows = sorted({k[1] for k in val if k[1].endswith(".net") and k[1] not in ("delivered_net", "required_net")})
    flows = [f for f in flows if any(abs(val.get((i, f)) or 0.0) > spec.BALANCE_TOL for i in insts)]
    if flows and insts:
        L += ["", "Delivered, by flow class (Rs crore, net receipts):", ""]
        L += _table(["Flow class", *insts], [[f.removesuffix(".net"), *(inr(val.get((i, f)), 0) for i in insts)]
                                              for f in flows])  # fmt: skip
    cg = pl.read_parquet(sat / "constraint_gaps.parquet").filter(pl.col("outside_band") == "yes")
    L += ["", "Constraints the prior already violates (`constraint_gaps`, largest gap first):", ""]
    if cg.height == 0:
        L.append("None.")
    else:
        cv: dict[str, dict[str, Any]] = {}
        for r in cg.iter_rows(named=True):
            d = cv.setdefault(r["constraint_id"], {"kind": r["kind"]})
            d[r["measure"]] = r["value"]
        order = sorted(cv, key=lambda k: (-abs(cv[k].get("gap") or 0.0), k))
        L += _table(
            ["Constraint", "Kind", "Target", "Band", "Prior sum", "Gap"],
            [[k, cv[k]["kind"], inr(cv[k].get("target"), 2), f"{inr(cv[k].get('lo'), 2)} .. {inr(cv[k].get('hi'), 2)}",
              inr(cv[k].get("prior_sum"), 2), inr(cv[k].get("gap"), 2)] for k in order],
        )  # fmt: skip
    return L


def render(paths: SamPaths) -> str:
    if not paths.run_json.exists():
        raise SamError(f"{paths.run_json} does not exist: run `sam` with every block built first")
    run = json.loads(paths.run_json.read_text(encoding="utf-8"))
    log = pl.read_parquet(paths.log)
    cons = pl.read_parquet(paths.constraint_status) if paths.constraint_status.exists() else None
    diag = pl.read_parquet(paths.diagnostics)
    ex = load_explanations()
    missing = unexplained(log, ex)
    stale = stale_explanations(log, ex)
    vc = _verdict_counts(current_items(log, ex))
    from pipeline.sam.accounts import Accounts

    acc = Accounts.load()
    acc_groups = {g: acc.in_group(g) for g in ("HH", "GOV", "FC")}

    L: list[str] = [
        f"# Balancing report: SAM {run['year']}",
        "",
        "Generated by `uv run python -m pipeline sam` (regenerate with `sam-report`). Do not edit by hand: "
        "explanations go in `pipeline/sam/explanations/<block>.yaml` (or the shared `pipeline/sam/explanations.yaml`). "
        "Rules: docs/phase2/DESIGN_BRIEF.md s.5; "
        "how-to: docs/phase2/SAM_GUIDE.md. Amounts in Rs crore, current prices.",
        "",
        "## Summary",
        "",
    ]
    ok = run["ok"]
    L += [
        f"- **Result: {'BALANCED' if ok else 'NOT BALANCED (the run failed; see findings)'}**",
        f"- Method: {run['method']}; solver {run['solver']} (status `{run['status']}`, "
        f"{run['iterations']} iterations, objective {run['objective']}).",
        f"- Entries: {run['counts']['entries']} ({run['counts']['variable']} could move: "
        f"{run['counts']['anchored']} anchored, {run['counts']['free']} free; {run['counts']['fixed']} fixed). "
        f"Constraints: {run['counts']['constraints']}.",
        f"- Largest account imbalance after balancing: {run['max_imbalance']:.6f} crore "
        f"(tolerance {spec.BALANCE_TOL} crore).",
        *_plain_certificate(run),
        f"- Entries moved materially (>= Rs {spec.MATERIAL_CHANGE:g} crore): {run['counts']['moved']}; "
        f"needing an explanation: {run['counts']['explanation_required']} entries and "
        f"{run['counts'].get('cells_explanation_required', 0)} cells; with no current explanation item: "
        f"{missing.height}; stale items: {len(stale)}.",
        f"- **What the explanation items say** (their verdicts; audit BS-2): {vc['explained']} explained, "
        f"{vc['level unexplained']} explained in direction but with the level unexplained, **{vc['unexplained']} "
        f"unexplained** (findings for Checkpoint B), {vc['no verdict word']} without a verdict word.",
        f"- Slack findings: {len(run['balance_slack'])} account-balance, {len(run['band_violation'])} constraint-band, "
        f"{len(run['anchor_violation'])} anchored-bound.",
        (
            f"- GRAS cross-check: converged in {run['gras']['iterations']} iterations; "
            f"{run['counts']['gras_findings']} entries differ from cross-entropy by more than the "
            "explanation threshold."
            if run["gras"]["converged"]
            else f"- GRAS cross-check: did NOT converge in {run['gras']['iterations']} iterations: no GRAS findings "
            "are computed from it (its mean-of-row-and-column targets are not attainable; see messages)."
        ),
    ]
    for m in run.get("messages", []):
        L.append(f"- Solver note: {m}")
    L += [
        "",
        "## Thresholds and weights (stated, then tested)",
        "",
        f"- Balance: |row - column| <= Rs {spec.BALANCE_TOL} crore for every account.",
        f"- Explanation required when |x - a| >= Rs {inr(spec.EXPLAIN_ABS)} crore, "
        f"or >= Rs {inr(spec.EXPLAIN_MIN_ABS)} crore and >= {spec.EXPLAIN_REL:.0%} of the prior.",
        f"- Weights: free high {spec.CONFIDENCE_WEIGHTS['high']:g}, medium {spec.CONFIDENCE_WEIGHTS['medium']:g}, "
        f"low {spec.CONFIDENCE_WEIGHTS['low']:g}; anchored {spec.ANCHORED_WEIGHT:g}; fixed entries never move.",
        "- Slack: phase 1 (an LP) finds the minimum total slack on anchored bounds and constraint bands; slack "
        "appears only when they cannot all hold together (it is then placed on few constraints: another "
        f"placement with the same total may exist). Slack above Rs {spec.SLACK_REPORT_TOL} crore is a finding.",
    ]
    L += glossary()
    L += [
        "",
        "## Findings: slack (infeasibilities that were not silently absorbed)",
        "",
    ]
    if not (run["balance_slack"] or run["band_violation"] or run["anchor_violation"]):
        L.append("None.")
    for k, v in sorted(run["balance_slack"].items()):
        L.append(f"- The infeasibility shows at account {k}: row - column {inr(v, 2)} crore cannot be closed "
                 "(the run failed; see the solver notes for the accounts that cause it).")  # fmt: skip
    for k, v in sorted(run["band_violation"].items()):
        L.append(f"- Constraint `{k}` is outside its band by {inr(v, 2)} crore.")
    for k, v in sorted(run["anchor_violation"].items()):
        L.append(f"- Anchored entry {k} is outside its bound by {inr(v, 2)} crore.")
    L += ["", "## Pre-balancing imbalances (prior row total - column total), largest first", ""]
    over = diag.filter(pl.col("imbalance").abs() > spec.BALANCE_TOL)
    top = over.filter(pl.col("imbalance").abs() >= ROUNDING_ONLY)
    small = over.filter(pl.col("imbalance").abs() < ROUNDING_ONLY)
    L += (
        _table(
            ["#", "Account", "Row total", "Column total", "Imbalance", "% of larger"],
            [
                [
                    str(r["rank"]),
                    r["account"],
                    inr(r["row_total"]),
                    inr(r["col_total"]),
                    inr(r["imbalance"], 2),
                    _pct(r["imbalance_pct"]),
                ]  # fmt: skip
                for r in top.iter_rows(named=True)
            ],
        )
        if top.height
        else [f"None of Rs {ROUNDING_ONLY:g} crore or more."]
    )
    if small.height:
        L += [
            "",
            f"Plus {small.height} accounts off by less than Rs {ROUNDING_ONLY:g} crore each (largest "
            f"{inr(float(small['imbalance'].abs().max()), 2)}, net {inr(float(small['imbalance'].sum()), 2)}): the "
            "SUT is published rounded and production anchors each cell within Rs 1 crore (D2-2), so these are "
            "rounding, not findings.",
        ]
    L += closure_section(paths, run)
    L += what_balancing_did(log, acc_groups)
    L += acceptance_section(cons, run)
    L += ["", "## Adjustments that need an explanation (entries, and cells whose total moved over the threshold)", ""]
    req = log.filter(pl.col("explanation_required")).select("row", "col", "ref", "component", "prior", "balanced",
                                                            "change")  # fmt: skip
    creq = (
        cell_changes(log)
        .filter(pl.col("explanation_required") & (pl.col("n_entries") > 1))
        .select("row", "col", pl.lit(CELL).alias("ref"), pl.lit(CELL).alias("component"), "prior", "balanced", "change")
    )
    req = pl.concat([req, creq]).sort(
        [pl.col("change").abs(), "row", "col", "ref"], descending=[True, False, False, False]
    )
    missing_keys = {tuple(r[k] for k in KEY) for r in missing.iter_rows(named=True)}
    if req.height == 0:
        L.append("None.")
    else:
        rows = []
        for r in req.iter_rows(named=True):
            key = tuple(r[k] for k in KEY)
            why = "**MISSING**" if key in missing_keys else ex.get(key, {}).get("why", "(explained at entry level)")
            why = why.strip().replace("\n", " ")
            pct = None if r["prior"] == 0 else 100.0 * r["change"] / abs(r["prior"])
            vd = "-" if key in missing_keys or key not in ex else verdict(why)
            if key in ex and len(why) > WHY_CHARS:  # audit BS-2: the full text stays in the explanation file
                cut = why.rfind(". ", 0, WHY_CHARS)
                why = why[: cut + 1 if cut > 0 else WHY_CHARS] + f" [... full text: {ex[key].get(SOURCE, '')}]"
            rows.append([f"{r['row']} <- {r['col']}", f"{r['ref']}/{r['component']}", inr(r["prior"]),
                         inr(r["balanced"]), inr(r["change"]), _pct(pct), vd, why])  # fmt: skip
        L += _table(["Cell", "Ref/component", "Prior", "Balanced", "Change", "%", "Verdict", "Why"], rows)
    if stale:
        L += ["", "Stale explanations (explain nothing this run needs, or a different change):", ""]
        L += [f"- {x}" for x in stale]
    L += ["", "## Largest adjustments (top 40 by absolute change)", ""]
    big = log.filter(pl.col("change").abs() > 0).sort(
        [pl.col("change").abs(), "row", "col"], descending=[True, False, False]
    )
    L += _table(
        ["Cell", "Ref/component", "Role", "Weight", "Prior", "Balanced", "Change", "%", "Binding constraints"],
        [
            [f"{r['row']} <- {r['col']}", f"{r['ref']}/{r['component']}", r["role"], f"{r['weight']:g}",
             inr(r["prior"]), inr(r["balanced"]), inr(r["change"], 2), _pct(r["pct_change"]), r["binding"] or ""]
            for r in big.head(40).iter_rows(named=True)
        ],
    ) if big.height else ["No entry moved."]  # fmt: skip
    if cons is not None and cons.height:
        L += ["", "## Constraints at a bound after balancing", ""]
        b = cons.filter(pl.col("binding"))
        L += (
            _table(
                ["Constraint", "Target", "Band", "Prior sum", "Balanced sum"],
                [
                    [
                        r["constraint_id"],
                        inr(r["target"]),
                        f"{inr(r['lo'])} .. {inr(r['hi'])}",
                        inr(r["prior_sum"]),
                        inr(r["balanced_sum"]),
                    ]  # fmt: skip
                    for r in b.iter_rows(named=True)
                ],
            )
            if b.height
            else ["None."]
        )
    L += ["", "## GRAS cross-check: entries where GRAS and cross-entropy differ beyond the threshold", ""]
    gf = log.filter(pl.col("gras_finding")).sort(pl.col("gras_diff").abs(), descending=True)
    if gf.height:
        L += [
            f"The {min(GRAS_SHOWN, gf.height)} largest of {gf.height} differences (all are in balancing_log.parquet, "
            "column `gras_finding`). GRAS ignores the declared constraints and the confidence weights (it only "
            "matches row and column totals), so a difference is weak evidence on its own: it shows where a "
            "constraint or a weight, not the data, set the cross-entropy answer.",
            "",
        ]
    L += (
        _table(
            ["Cell", "Ref/component", "Prior", "Cross-entropy", "GRAS", "GRAS - CE"],
            [
                [
                    f"{r['row']} <- {r['col']}",
                    f"{r['ref']}/{r['component']}",
                    inr(r["prior"]),
                    inr(r["balanced"]),
                    inr(r["gras"]),
                    inr(r["gras_diff"]),
                ]  # fmt: skip
                for r in gf.head(GRAS_SHOWN).iter_rows(named=True)
            ],
        )
        if gf.height
        else ["None."]
    )
    k7b = log.filter(pl.col("ref") == "K7b")
    if k7b.height:
        L += ["", "## Counterparty postings (gap map K7b)", ""]
        L += _table(
            ["Cell", "Component", "Prior", "Balanced"],
            [
                [f"{r['row']} <- {r['col']}", r["component"], inr(r["prior"]), inr(r["balanced"])]
                for r in k7b.iter_rows(named=True)
            ],  # fmt: skip
        )
    L += [
        "",
        "## Technical detail (raw solver records)",
        "",
        f"- KKT certificate: `{json.dumps(run['certificate'], sort_keys=True)}`",
        f"- Phase 1 (minimum slack): `{json.dumps(run['phase1'], sort_keys=True)}`",
        f"- Polish on free entries: `{json.dumps(run['polish'], sort_keys=True)}`",
    ]
    return "\n".join(L) + "\n"


def write_report(layout: Layout) -> Path:
    paths = SamPaths(layout)
    text = render(paths)
    io.write_text(layout.balancing_report, text)
    return layout.balancing_report
