"""summary.json: the first screen's headline figures and the methodology numbers (PLAN s.3.6, s.4.0, s.4.10)."""

from __future__ import annotations

from typing import Any

import polars as pl

from pipeline.core.io import canonical_float
from pipeline.export.inputs import YEAR, ExportError, ExportInputs
from pipeline.export.pinned import PIN_ABS, PIN_REL, Pin, aggregate_total
from pipeline.export.sam_export import SamView, composition_json, label_counts, nonzero_cells, r2
from pipeline.export.status import SPLIT_SHARE
from pipeline.export.timeseries import NEW_BASE, TsData
from pipeline.sam.spec import EXPLAIN_ABS, EXPLAIN_MIN_ABS, EXPLAIN_REL

SHARE = 6
GDP_SAM_TOL = 1.0  # Rs crore (PLAN s.3.3)
D3_NAS_TOL = 0.01  # Rs crore: X_DISC D3 (all entries) vs the NAS derived S-I errors and omissions (closure check tol)

# Household outlays (the columns of the household accounts) by the level-0 node that receives them.
HH_PARTS = (
    ("consumption", ("PRDS",)),
    ("saving", ("SI",)),
    ("taxes", ("TAX",)),
    ("financial_services_and_interest", ("FC", "NFC")),
    ("transfers_abroad", ("ROW",)),
    ("to_government", ("CEN", "STA")),
    ("unallocated_residual", ("DISC",)),
)


def gdp_figure(td: TsData, inp: ExportInputs) -> dict[str, Any]:
    r = td.main["M01"].get(YEAR)
    if r is None or r["base_year"] != NEW_BASE or r["variant"] != "published":
        raise ExportError(f"no published new-base M01 row for {YEAR}")
    value = float(r["value"])
    if inp.gdp_sam_check is not None and abs(inp.gdp_sam_check - value) > GDP_SAM_TOL:
        raise ExportError(
            f"GDP from the SAM's production side ({inp.gdp_sam_check:,.2f}) differs from M01 ({value:,.2f}) by more "
            f"than Rs {GDP_SAM_TOL} crore"
        )
    return {"year": YEAR, "value": r2(value), "prov": r["prov_id"], "label": "official"}


def _prov_by_weight(view: SamView, ents: list[int]) -> list[str]:
    w: dict[str, float] = {}
    for i in ents:
        w[view.prov[i]] = w.get(view.prov[i], 0.0) + abs(float(view.v[i]))
    return [p for p, _ in sorted(w.items(), key=lambda kv: (-kv[1], kv[0]))]


def hh_outlays(view: SamView, pins: list[Pin]) -> dict[str, Any]:
    h = view.inp.hierarchy
    hh = set(h.node_accounts("HH"))
    parts = []
    all_ents: list[int] = []
    values: dict[str, float] = {}
    labels: dict[str, str] = {}
    totals: dict[str, dict[str, Any] | None] = {}
    covered: set[str] = set()
    for key, nodes in HH_PARTS:
        rows = {a for n in nodes for a in h.node_accounts(n)}
        covered |= set(nodes)
        ents = [i for c in hh for (r, cc), es in view.cell_entries.items() if cc == c and r in rows for i in es]
        if not ents:
            raise ExportError(f"household outlays: part {key} selects no entries")
        values[key] = float(sum(float(view.v[i]) for i in ents))
        labels[key] = view.split(ents)[1]
        totals[key] = aggregate_total(view, pins, sorted(ents))
        all_ents.extend(ents)
    other = [k for k in nonzero_cells(view) if k[1] in hh and h.l0(k[0]) not in covered | {"HH"}]
    if other:
        raise ExportError(f"household outlays: cells not assigned to a part: {other[:5]}")
    total = sum(values.values())
    for key, _ in HH_PARTS:
        parts.append(
            {
                "key": key,
                "value": r2(values[key]),
                "per100": canonical_float(100.0 * values[key] / total, SHARE),
                "split_label": labels[key],
                # the same exact-cover rule as sam/pinned.json (e.g. saving = HH--SI, held to NAS household saving)
                "total_label": None if totals[key] is None else totals[key]["total"],
                "pins": [] if totals[key] is None else totals[key]["pins"],
            }
        )
    tot = aggregate_total(view, pins, sorted(all_ents))
    return {
        "total": r2(total),
        "total_label": None if tot is None else tot["total"],
        "prov": _prov_by_weight(view, all_ents),
    } | {"parts": parts}


def summary_json(
    view: SamView,
    td: TsData,
    pins: list[Pin],
    methodology: dict[str, Any],
) -> dict[str, Any]:
    inp = view.inp
    cells = nonzero_cells(view)
    labels = label_counts(view)
    tot_abs = sum(x["abs"] for x in labels.values())
    comp = {
        "o": labels["official"]["abs"] / tot_abs,
        "d": labels["derived"]["abs"] / tot_abs,
        "e": labels["estimated"]["abs"] / tot_abs,
        "b": labels["balancing_set"]["abs"] / tot_abs,
    }
    change = inp.entries["change"].to_numpy()
    moved = float(abs(change).sum())
    abs_all = float(abs(view.v).sum())
    run = inp.run
    return {
        "gdp": gdp_figure(td, inp),
        "headline": {"hh_outlays": hh_outlays(view, pins), "gdp_note": None},
        "sam": {
            "accounts": len(view.codes),
            "cells_nonzero": len(cells),
            "entries": view.n,
            "refs": len(set(view.ref)),
            "grand_total": r2(sum(view.cell_value[k] for k in cells)),
            "composition": composition_json(comp),
            "labels": labels,
            "balancing": {
                "status": str(run.get("status")),
                "iterations": int(run.get("iterations") or 0),
                "max_imbalance": float(run.get("max_imbalance") or 0.0),
                "moved_abs": r2(moved),
                "moved_share_of_abs": canonical_float(moved / abs_all, SHARE),
            },
        },
        "methodology": methodology,
        "ts": {
            "flows": len(td.flow_ids),
            "core": sum(1 for f in td.flow_ids if td.defs[f]["tier"] == "core"),
            "memo": sum(1 for f in td.flow_ids if td.defs[f]["tier"] == "memo"),
            "first": td.periods[0],
            "last": td.periods[-1],
            "rows": inp.ts.height,
        },
    }


def _m(value: float, unit: str, prov: list[str] | None = None) -> dict[str, Any]:
    v = float(value)
    if unit == "inr":
        v = r2(v)
    elif unit in ("pct", "pct_gdp"):
        v = canonical_float(v, SHARE)
    return {"value": v, "unit": unit, "prov": sorted(set(prov or []))}


def methodology_json(
    view: SamView, td: TsData, gdp: float, extra: dict[str, Any], pins: list[Pin]
) -> dict[str, Any]:
    """The numbers U6's methodology page binds to (docs/phase3/requests/U6.md)."""
    inp = view.inp
    out: dict[str, Any] = {}

    def sel(pred: Any) -> list[int]:
        return [i for i in range(view.n) if pred(i)]

    def labelled(item: dict[str, Any], ents: list[int]) -> dict[str, Any]:
        """An economic value's status, as for a headline part (requests/U6.md V5-03): the headline split label
        of exactly the entries summed, and the total label and pins by the exact-cover rule of sam/pinned.json."""
        if not any(view.v[i] != 0 for i in ents):
            return item  # a zero amount (D4 in 2023-24) has no split label (PLAN s.3.4.2); the text says it is zero
        tot = aggregate_total(view, pins, sorted(ents))
        return item | {
            "split_label": view.split(ents)[1],
            "total_label": None if tot is None else tot["total"],
            "pins": [] if tot is None else tot["pins"],
        }

    # HCES coverage of PFCE: HCES consumption at HCES scale over NAS PFCE 2023-24 (F01 main, new base);
    # CHECKPOINT_B s.3 caveat 1
    # HCES consumption at HCES scale: A2 persons x average MPCE x 12 by household group (hh_keys hces_total)
    sat = inp.satellite("households/hh_keys")
    c = sat.filter((pl.col("key") == "hces_total") & (pl.col("measure") == "level"))
    if c.height != 10:
        raise ExportError(f"hh_keys: expected 10 hces_total levels (one per household group), found {c.height}")
    hces = float(c["value"].sum())
    pfce_row = td.main["F01"].get(YEAR)
    if pfce_row is None:
        raise ExportError("F01 has no 2023-24 value for the HCES coverage ratio")
    out["hces_pfce_coverage"] = _m(
        hces / float(pfce_row["value"]), "pct", [*c["prov_id"].unique().to_list(), pfce_row["prov_id"]]
    )
    fact = set(inp.hierarchy.node_accounts("FACT"))
    hh = set(inp.hierarchy.node_accounts("HH"))
    ents = sel(lambda i: view.col[i] in fact and view.row[i] in hh)
    out["hh_factor_income"] = labelled(
        _m(sum(view.v[i] for i in ents), "inr", [view.prov[i] for i in ents]), ents
    )
    for key, ref, comp in (
        ("disc_d1", "D1", None),
        ("disc_d2", "D2", None),
        ("disc_d3", "D3", None),
        ("disc_d3_valuables", "D3", "unsectored_valuables"),
        ("disc_d3_si_errors", "D3", "si_errors"),
        ("disc_d4", "D4", None),
    ):
        ents = sel(lambda i, ref=ref, comp=comp: view.ref[i] == ref and (comp is None or view.comp[i] == comp))
        if not ents:
            raise ExportError(f"methodology {key}: no entries with ref {ref} {comp or ''}")
        value = sum(view.v[i] for i in ents)
        prov = [view.prov[i] for i in ents]
        if key == "disc_d3" and "nas_si_errors" in inp.published:
            # the whole D3 is the NAS derived S-I errors and omissions (V2-02): say which record, and fail if not
            nas, nas_prov = inp.published["nas_si_errors"]
            if abs(value - nas) > D3_NAS_TOL:
                raise ExportError(
                    f"methodology disc_d3: X_DISC D3 entries sum to {value:,.2f}, the NAS derived saving-investment "
                    f"errors and omissions ({nas_prov}) is {nas:,.2f} (tolerance Rs {D3_NAS_TOL} crore)"
                )
            prov.append(nas_prov)
        elif key == "disc_d3" and not inp.fixture:
            raise ExportError("methodology disc_d3: the NAS derived saving-investment errors and omissions is not loaded")
        out[key] = labelled(_m(value, "inr", prov), ents)
    jb = sel(lambda i: "judgement_band" in view.flags[i])
    out["judgement_bands"] = _m(len(view.judgement_ids), "count")
    out["judgement_band_entries"] = _m(len(jb), "count")
    out["judgement_band_abs"] = labelled(
        _m(sum(abs(view.v[i]) for i in jb), "inr", [view.prov[i] for i in jb]), jb
    )
    ob = sel(lambda i: "old_base_structure" in view.flags[i])
    out["old_base_entries"] = _m(len(ob), "count")
    out["old_base_abs"] = labelled(_m(sum(abs(view.v[i]) for i in ob), "inr", [view.prov[i] for i in ob]), ob)
    cons = inp.constraints
    out["constraints"] = _m(cons.height, "count")
    out["constraints_binding"] = _m(int(cons["binding"].sum()), "count")
    ent_items = [it for k, it in inp.items.items() if k[2] != "*"]
    cell_items = [it for k, it in inp.items.items() if k[2] == "*"]
    for name, items in (("explain_entries", ent_items), ("explain_cells", cell_items)):
        out[name] = _m(len(items), "count")
        for v, suffix in (
            ("explained", "explained"),
            ("level unexplained", "level_unexplained"),
            ("unexplained", "unexplained"),
        ):
            out[f"{name}_{suffix}"] = _m(sum(1 for it in items if it["verdict"] == v), "count")
    moved = float(abs(inp.entries["change"].to_numpy()).sum())
    out["moved_abs_gdp"] = _m(moved / gdp, "pct_gdp")
    out["ts_linked_flows"] = _m(sum(1 for f in td.flow_ids if td.defs[f]["link_policy"] == "linked"), "count")
    flags = inp.ts["flags"].to_list()
    out["ts_segment_joins"] = _m(flags.count("segment_join"), "count")
    out["ts_base_changes"] = _m(flags.count("base_change"), "count")
    out["ts_concept_breaks"] = _m(flags.count("concept_break"), "count")
    verdicts = inp.ts_check["verdict"].to_list()
    out["ts_check_pass"] = _m(verdicts.count("pass"), "count")
    out["ts_check_explained"] = _m(verdicts.count("explained"), "count")
    out["ts_check_none"] = _m(verdicts.count("no_check"), "count")
    for k, v in extra.items():
        out[k] = _m(v, "count")
    # Rule constants, read from the code that applies them (requests/U6.md), so prose never types them:
    # the explanation threshold (pipeline.sam.spec.needs_explanation), the widest band that counts as a pin
    # (pinned.py, s.3.4.2) and the share that makes a label the headline split label (status.py, s.3.4.2).
    out["explain_abs"] = _m(EXPLAIN_ABS, "inr")
    out["explain_small_abs"] = _m(EXPLAIN_MIN_ABS, "inr")
    out["explain_small_rel"] = _m(EXPLAIN_REL, "pct")
    out["pin_width_abs"] = _m(PIN_ABS, "inr")
    out["pin_width_rel"] = _m(PIN_REL, "pct")
    out["split_headline_min"] = _m(SPLIT_SHARE, "pct")
    return out
