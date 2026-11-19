"""K9: the residual that closes each domestic capital account, and its decomposition (plan s.2.10).

K9_s = [row total of K_s] - [column total of K_s], over every block's prior entries except K9 itself:
saving (K1, fincorp K2a, government K3a; for K_HH the NAS K4 total, because closure writes K4a later),
capital transfers (government K6, R2k, incl. RoW), D3, GFCF, inventories, valuables and every financial
entry. It is written in the asset cell I_OTHR <- K_s as a pair `residual_pos` (+) / `residual_neg` (-)
(XR-17, FRAMEWORK_REQUESTS P-9) so balancing can move the net across zero.

The pair is not an arbitrary margin: K9_s is decomposed exactly into its sources (NAS vs FSF net lending,
the FSF reconciliation by instrument, the household and RoW replacements, FSF items never read). The pair is
built from a coarser grouping of the same decomposition, the `pair:*` terms (published in satellite
k9_decomposition): nas_vs_fsf, row_counterparty (all RoW instruments as one term), fsf_unwritten, and one
`pair:hh_dom:<instrument>` per instrument that combines the household and domestic layers (an FSF cell published
without a counterparty, such as insurers' F6, is mostly households' and would otherwise show twice, as two
opposite lakh-crore terms). `residual_pos` = the sum of the positive `pair:*` terms, `residual_neg` = the sum of
the negative ones. The grouping is a weight choice: balancing's cost of moving a free entry scales with its
prior, so the gross size of the pair (not only its net K9) sets how cheaply balancing can move K9_s
(verification V-CF-2).
"""

from __future__ import annotations

import polars as pl

from pipeline.sam.blocks.capital_financial import params as P


def category(ref: str, component: str, block: str) -> str:
    """Which replacement layer a financial entry belongs to (for the decomposition)."""
    if ref in ("K7a", "K8a") or component == "hh_cp":
        return "hh"
    if component.startswith("row_cp") or block == "rest_of_world":
        return "row"
    return "dom"


def k9(
    entries: pl.DataFrame,
    group_of: dict[str, str],
    hh_saving: float,
    fsf_nets: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Per domestic K account: real (non-financial) net resources, SAM net financial transactions by layer and
    instrument (`sam:<layer>|<instrument>`), K9, its published decomposition (`term:*`) and the entry pair.
    `entries` has row, col, ref, component, value, block (all blocks, K9 excluded); `group_of` maps account ->
    group; `hh_saving` is NAS household saving (K4); `fsf_nets` from fsf.category_nets.

    Published decomposition (sums to K9 exactly): nas_vs_fsf = real - FSF net financial transactions;
    hh_counterparty and row_counterparty = FSF - SAM in the household and RoW layers; fsf_unwritten; and
    fsf_reconciliation:<instrument> = FSF - SAM in the domestic layer. The entry pair uses the `pair:*` terms
    (also returned, and published): the same terms with the household and domestic layers of each instrument
    combined (`pair:hh_dom:<instrument>`; an FSF cell published without a counterparty, such as insurers' F6,
    is mostly households' and would otherwise show twice) and the RoW layer as one term."""
    out: dict[str, dict[str, float]] = {}
    for s in P.K_DOMESTIC:
        d: dict[str, float] = {"real": hh_saving if s == "K_HH" else 0.0}
        sam: dict[str, float] = {}
        for r in entries.filter((pl.col("row") == s) | (pl.col("col") == s)).iter_rows(named=True):
            if r["row"] == s and r["col"] == s:
                continue  # a diagonal cell cancels in its own account
            if r["row"] == s:  # a resource of K_s: saving, capital transfer received, D3, or a liability
                other, sign = r["col"], +1.0
            else:  # a use of K_s: GFCF, CIS, valuables, capital transfer paid, or a financial asset
                other, sign = r["row"], -1.0
            if group_of[other] != "INST":
                d["real"] += sign * r["value"]
                continue
            key = f"{category(r['ref'], r['component'], r['block'])}|{other}"  # assets - liabilities, as FSF
            sam[key] = sam.get(key, 0.0) - sign * r["value"]
        d["k9"] = d["real"] - sum(sam.values())
        f = fsf_nets.get(s, {})
        d["fsf_total"] = f.get("total", 0.0)

        def diff(layer: str, inst: str | None = None, f: dict = f, sam: dict = sam) -> float:
            keys = {k for k in (*f, *sam) if k.startswith(f"{layer}|") and (inst is None or k.endswith(f"|{inst}"))}
            return sum(f.get(k, 0.0) - sam.get(k, 0.0) for k in keys)

        insts = sorted({k.split("|")[1] for k in (*f, *sam) if "|" in k})
        terms = {
            "nas_vs_fsf": d["real"] - d["fsf_total"],
            "hh_counterparty": diff("hh"),
            "row_counterparty": diff("row"),
            "fsf_unwritten": f.get("unwritten", 0.0),
        }
        for i in insts:
            terms[f"fsf_reconciliation:{i}"] = diff("dom", i)
        pair_terms = {
            "nas_vs_fsf": terms["nas_vs_fsf"],
            "row_counterparty": terms["row_counterparty"],
            "fsf_unwritten": terms["fsf_unwritten"],
        }
        for i in insts:
            pair_terms[f"hh_dom:{i}"] = diff("dom", i) + diff("hh", i)
        d.update({f"sam:{k}": v for k, v in sorted(sam.items())})
        d.update({f"fsf:{k}": v for k, v in sorted(f.items()) if "|" in k})
        d.update({f"term:{k}": v for k, v in terms.items()})
        d.update({f"pair:{k}": v for k, v in pair_terms.items()})
        d["pos"] = sum(v for v in pair_terms.values() if v > 0)
        d["neg"] = sum(v for v in pair_terms.values() if v < 0)
        d["check"] = sum(terms.values()) - d["k9"]
        d["check_pair"] = sum(pair_terms.values()) - d["k9"]
        out[s] = d
    return out


def residual_pair(d: dict[str, float]) -> dict[str, float]:
    """The K9 entries of one account: residual_pos / residual_neg with net exactly K9. The terms are
    rescaled by a common factor only if float noise leaves pos + neg != K9 (never by more than 1e-9)."""
    k, pos, neg = d["k9"], d["pos"], d["neg"]
    if abs(k) < P.K9_MIN:
        return {}
    if pos == 0.0 or neg == 0.0:  # every term has one sign: a single entry (logged by the caller)
        return {"residual_pos" if k > 0 else "residual_neg": k}
    # put the float noise on the larger side so pos + neg == k
    if abs(pos) >= abs(neg):
        pos = k - neg
    else:
        neg = k - pos
    return {"residual_pos": pos, "residual_neg": neg}
