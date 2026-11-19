"""Direct taxes: T3 (income tax other than corporation tax, split households / quasi-corporations),
T3a (household income tax by group), T4/T4a (corporation tax by paying sector). Plan s.2.6-2.7,
DECISIONS D2-11 (quasi-corporate share), D2-12 (STT in T_PIT), D2-14 (co-operative banks private),
CROSS_REVIEW XR-6 (deposit-taking NBFCs/HFCs belong to E_BANK)."""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from pipeline.sam.framework import BlockContext, SamError

from .common import (
    FC16_ACC,
    FSF_BS,
    IFPRI,
    IRDAI_LIFE,
    IRDAI_NONLIFE,
    NAS11,
    OLD,
    OLD_YEAR,
    RB,
    RTP_BANKS,
    RTP_COOP,
    RTP_NBFI,
    RTP_VINTAGE,
    pids,
    prefixed,
)
from .receipts import Cash

THRESHOLD = 700_000.0  # Rs per household per year: new-regime rebate limit 2023-24 (Finance Act 2023)
SENSITIVITY = (500_000.0, 700_000.0, 1_000_000.0)
FSF_END = "2024-03-31"
# RBI RTP SCB profit table groups (they add up to 'scb'): public sector, private, foreign, small finance, payments
SCB_GROUPS = ("psb", "pvb", "fb", "sfb", "pb")
SCB_ROUNDING = 5.0  # Rs crore: the published groups may miss the published SCB total by rounding
BANKS_PUBLIC = ("psb", "rrb")  # public-sector banks and regional rural banks (Centre/State/sponsor-bank owned)
HH_GROUPS = ("H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5")


# ---------------------------------------------------------------------------------------------------
# T3: household vs quasi-corporate share of MH 0021
# ---------------------------------------------------------------------------------------------------


@dataclass
class T3Split:
    share: float  # household share of MH 0021 (old-base NAS 2022-23)
    ifpri_share: float  # cross-check
    hh_income_tax: float  # Union: h x MH 0021 + STT + MH 0028 + MH 0031/0032
    state_taxes: float  # States: professions tax + agricultural income tax
    qc_nfpr: float
    qc_bank: float  # co-operative banks (UCB) tax provisions
    inputs_share: list[str] = field(default_factory=list)
    inputs_qc_bank: list[str] = field(default_factory=list)
    parts: dict[str, float] = field(default_factory=dict)

    @property
    def household_total(self) -> float:
        return self.hh_income_tax + self.state_taxes

    @property
    def qc_total(self) -> float:
        return self.qc_nfpr + self.qc_bank


def t3_split(ctx: BlockContext, cash: Cash) -> T3Split:
    d5_hh, p1 = ctx.value(OLD.format("s5_0"), "oldbase_soa_s5_0.secondary_distribution_of_income.uses.d5.current",
                          period=OLD_YEAR, vintage="latest")  # fmt: skip
    mh21_old = prefixed(ctx, RB, "rb.tr.0021.", OLD_YEAR, vintage="latest")
    pt_old = prefixed(ctx, FC16_ACC, "fa.revenue_receipts.mh0028.in-", OLD_YEAR, vintage="latest")
    m21o, pto = float(mh21_old["value"].sum()), float(pt_old["value"].sum())
    h = (d5_hh - pto) / m21o
    ifpri_hh, p4 = ctx.value(IFPRI, "ifpri.t8.taxes.households.current", period=OLD_YEAR, vintage="latest")
    if not 0.5 < h < 1.0:
        raise SamError(f"household share of MH 0021 {h:.4f} outside (0.5, 1)")
    ucb, pu = ctx.value(RTP_COOP, "rtp.ucb_pl.tax_provisions.ucb.current", vintage=RTP_VINTAGE)
    mh21 = cash.x("mh0021")
    qc = (1 - h) * mh21 + cash.x("firm_heads")
    parts = {
        "mh0021_household": h * mh21,
        "stt": cash.x("stt"),
        "mh0028_expenditure_tax": cash.x("mh0028"),
        "mh0031_0032_wealth_estate": cash.x("wealth_tax"),
        "professions_tax": cash.x("professions_tax"),
        "agricultural_income_tax": cash.x("agricultural_income_tax"),
        "mh0021_quasi_corporate": (1 - h) * mh21,
        "mh0023_0024_0026_firm_heads": cash.x("firm_heads"),
    }
    return T3Split(
        share=h,
        ifpri_share=ifpri_hh / m21o,
        hh_income_tax=h * mh21 + cash.x("stt") + cash.x("mh0028") + cash.x("wealth_tax"),
        state_taxes=cash.x("state_income_taxes"),
        qc_nfpr=qc - ucb,
        qc_bank=ucb,
        inputs_share=pids([p1, p4], mh21_old["prov_id"].to_list(), pt_old["prov_id"].to_list()),
        inputs_qc_bank=[pu],
        parts=parts,
    )


# ---------------------------------------------------------------------------------------------------
# T3a: household income tax by group (threshold-excess key; no open input, low confidence)
# ---------------------------------------------------------------------------------------------------


@dataclass
class Fractiles:
    table: pl.DataFrame  # class, group, persons, households, mpce
    k: float  # NAS PFCE / HCES aggregate
    saving: dict[str, float]  # group -> saving rate (share)
    inputs: list[str]
    saving_note: str


MEASURES = ("persons", "households", "avg_mpce")


def fractile_table(hh_group_map: pl.DataFrame) -> pl.DataFrame:
    """households' hh_group_map (long: hces_class, household_group, measure in persons/households/avg_mpce, value)
    -> one row per HCES fractile class: class, group, persons, households, avg_mpce (HCES 2023-24 A2)."""
    need = {"hces_class", "household_group", "measure", "value"}
    if not need <= set(hh_group_map.columns):
        raise SamError(f"households' hh_group_map lacks columns {sorted(need - set(hh_group_map.columns))}")
    d = hh_group_map.filter(pl.col("measure").is_in(MEASURES))
    groups = d.select("hces_class", "household_group").unique(maintain_order=True)
    if groups.height != 24 or groups["hces_class"].n_unique() != 24:
        raise SamError(f"hh_group_map: expected 24 fractile classes each in one group, got {groups.height} rows")
    bad = sorted(set(groups["household_group"].to_list()) - set(HH_GROUPS))
    if bad:
        raise SamError(f"hh_group_map: unknown groups {bad}")
    rows = []
    for cls, g in groups.sort("hces_class").iter_rows():
        v = {}
        for m in MEASURES:
            x = d.filter((pl.col("hces_class") == cls) & (pl.col("measure") == m))
            if x.height != 1:
                raise SamError(f"hh_group_map: {cls} {m}: {x.height} rows")
            v[m] = float(x["value"][0])
        if min(v.values()) <= 0:
            raise SamError(f"hh_group_map: non-positive value for {cls}: {v}")
        rows.append({"class": cls, "group": g, **v})
    return pl.DataFrame(rows)


def fractiles(ctx: BlockContext, table: pl.DataFrame, table_pids: list[str], xwalk: pl.DataFrame | None) -> Fractiles:
    """table: fractile_table(households' hh_group_map); xwalk: households' hh_national_quintile_xwalk or None."""
    hces = float((table["persons"] * table["avg_mpce"] * 12).sum()) / 1e7  # Rs crore / yr at HCES scale
    pfce, pp = ctx.value(NAS11, "s1_1.pfce.current", vintage="latest")
    q = {}
    qp = []
    for i in range(1, 6):
        v, p = ctx.value(IFPRI, f"ifpri.t11.savings_rate.q{i}", period=OLD_YEAR, vintage="latest", unit="percent",
                         price_basis=None)  # fmt: skip
        q[f"q{i}"] = v / 100
        qp.append(p)
    if xwalk is not None:
        saving = xwalk_rates(xwalk, q)
        note = "IFPRI T11 national-quintile saving rates, person-weighted with households' hh_national_quintile_xwalk"
    else:
        saving = {g: q[f"q{g[-1]}"] for g in HH_GROUPS}
        note = (
            "IFPRI T11 national-quintile saving rates, quintile n applied to H_Rn and H_Un (assumption: households' "
            "hh_national_quintile_xwalk is not published)"
        )
    return Fractiles(table, pfce / hces, saving, pids(table_pids, [pp], qp), note)


def xwalk_rates(xwalk: pl.DataFrame, q: dict[str, float]) -> dict[str, float]:
    """Person-weighted saving rate per group from households' national-quintile crosswalk (household_group,
    national_quintile q1..q5, measure 'persons')."""
    need = {"household_group", "national_quintile", "measure", "value"}
    if not need <= set(xwalk.columns):
        raise SamError(f"hh_national_quintile_xwalk lacks columns {sorted(need - set(xwalk.columns))}")
    d = xwalk.filter((pl.col("measure") == "persons") & pl.col("national_quintile").is_in(list(q)))
    out = {}
    for g in HH_GROUPS:
        sub = d.filter(pl.col("household_group") == g)
        w = float(sub["value"].sum())
        if w <= 0:
            raise SamError(f"hh_national_quintile_xwalk: no persons for {g}")
        out[g] = sum(r["value"] * q[r["national_quintile"]] for r in sub.iter_rows(named=True)) / w
    return out


def t3a_key(fr: Fractiles, threshold: float) -> dict[str, float]:
    """Shares by group of household income above `threshold` (Rs per household per year)."""
    key: dict[str, float] = {g: 0.0 for g in HH_GROUPS}
    for r in fr.table.iter_rows(named=True):
        y = 12 * r["avg_mpce"] * r["persons"] / r["households"] * fr.k / (1 - fr.saving[r["group"]])
        key[r["group"]] += r["households"] * max(0.0, y - threshold)
    s = sum(key.values())
    if s <= 0:
        raise SamError(f"T3a: no household above the Rs {threshold:,.0f} threshold")
    return {g: v / s for g, v in key.items()}


# ---------------------------------------------------------------------------------------------------
# T4a: corporation tax by paying sector
# ---------------------------------------------------------------------------------------------------


@dataclass
class T4aSplit:
    cells: dict[tuple[str, str], float]  # (account, component) -> value
    shares: dict[str, float]  # old-base D5 shares
    detail: dict[str, float]
    inputs_shares: list[str]
    inputs_fc: list[str]
    insp_target: float
    nbfc_target: float
    fc_total: float


def t4a_split(ctx: BlockContext, cash: Cash, t3: T3Split) -> T4aSplit:
    d5 = {}
    ps = []
    for key, s in (("pub_nfc", "s2_1"), ("pvt_nfc", "s2_2"), ("pub_fc", "s3_1"), ("pvt_fc", "s3_2")):
        d5[key], p = ctx.value(OLD.format(s), f"oldbase_soa_{s}.secondary_distribution_of_income.uses.d5.current",
                               period=OLD_YEAR, vintage="latest")  # fmt: skip
        ps.append(p)
    tot = sum(d5.values())
    sh = {k: v / tot for k, v in d5.items()}
    cit = cash.x("cit")
    corp = cit + t3.qc_total  # corporate D5 prior 2023-24 (quasi-corporations included, as in NAS)
    sector = {k: corp * v for k, v in sh.items()}
    pvt_nfc = sector["pvt_nfc"] - t3.qc_nfpr
    pvt_fc = sector["pvt_fc"] - t3.qc_bank
    if pvt_nfc <= 0 or pvt_fc <= 0:
        raise SamError(f"T4a: quasi-corporate MH 0021 exceeds the private sector's D5 (NFC {pvt_nfc}, FC {pvt_fc})")
    pub_fc = sector["pub_fc"]

    # FC sub-sectors bottom-up (insurers: IRDAI tax provisions; NBFC/HFC/AIFI: RBI RTP tax provisions)
    def v(ds: str, sid: str, vint: str = "latest", period: str = ctx.year) -> float:
        x, p = ctx.value(ds, sid, period=period, vintage=vint)
        fc_in.append(p)
        return x

    fc_in: list[str] = []
    life_all = v(IRDAI_LIFE, "t24.provision_for_tax.insurers_life.current") + v(
        IRDAI_LIFE, "t25.provision_for_tax.insurers_life.current"
    )
    lic = v(IRDAI_LIFE, "t24.provision_for_tax.lic.current") + v(IRDAI_LIFE, "t25.provision_for_tax.lic.current")
    nl = {g: v(IRDAI_NONLIFE, f"t51.provision_for_tax.{g}.current")
          for g in ("general_public", "general_private", "health_standalone", "general_specialized")}  # fmt: skip
    insp_pub = lic + nl["general_public"] + nl["general_specialized"]
    insp_pvt = (life_all - lic) + nl["general_private"] + nl["health_standalone"]
    ul = v(RTP_NBFI, "rtp.nbfc_layer_pl.tax_provisions.nbfc_ul.current", RTP_VINTAGE)
    ml = v(RTP_NBFI, "rtp.nbfc_layer_pl.tax_provisions.nbfc_ml.current", RTP_VINTAGE)
    hfc = v(RTP_NBFI, "rtp.hfc_pl.tax_provisions.hfc.current", RTP_VINTAGE)
    aifi = v(RTP_NBFI, "rtp.aifi_pl.tax_provisions.aifi.current", RTP_VINTAGE)
    # FSF stocks at end-March 2024 (period '2024-03-31')
    stock = {k: v(FSF_BS, f"fsf.fc_{k}.assets.outstanding.total.all.current", period=FSF_END) for k in
             ("odc_nbfc_dt", "ofc_nbfc_ndt", "odc_hfc_dt", "ofc_hfc_ndt")}  # fmt: skip
    dt_nbfc = stock["odc_nbfc_dt"] / (stock["odc_nbfc_dt"] + stock["ofc_nbfc_ndt"])
    dt_hfc = stock["odc_hfc_dt"] / (stock["odc_hfc_dt"] + stock["ofc_hfc_ndt"])
    to_bank = (ul + ml) * dt_nbfc + hfc * dt_hfc  # deposit-taking NBFCs/HFCs are ODCs (E_BANK), private
    nbfc = ul + ml + hfc + aifi - to_bank
    pub_ratio = sh["pub_fc"] / (sh["pub_fc"] + sh["pvt_fc"])
    nbfc_pub = aifi + (nbfc - aifi) * pub_ratio
    nbfc_pvt = nbfc - nbfc_pub
    # E_BANK = the residual of the FC total (unchanged by the split below)
    bank = pub_fc + pvt_fc - (insp_pub + insp_pvt) - nbfc
    # public / private within E_BANK (plan s.2.7 step 4; verification V-TX-1): the deposit-taking NBFC/HFC share
    # moved in (to_bank) is private (XR-6); the banks' own tax is split by RBI RTP 2023-24 net profit, public = PSBs
    # + RRBs, private = PVBs + foreign banks + SFBs + payments banks (inside the SCB table) + local area banks.
    # Tax by bank group is not published (it sits inside 'provisions and contingencies'), so net profit is the key.
    npf = {g: v(RTP_BANKS, f"rtp.scb_pl.net_profit.{g}.current", RTP_VINTAGE) for g in SCB_GROUPS}
    scb = v(RTP_BANKS, "rtp.scb_pl.net_profit.scb.current", RTP_VINTAGE)
    if abs(sum(npf.values()) - scb) > SCB_ROUNDING:
        raise SamError(f"RTP SCB net profit by group {sum(npf.values()):,.2f} does not add up to SCB {scb:,.2f}")
    npf["rrb"] = v(RTP_BANKS, "rtp.rrb_pl.net_profit.rrb.current", RTP_VINTAGE)
    npf["lab"] = v(RTP_BANKS, "rtp.lab_pl.net_profit.lab.current", RTP_VINTAGE)
    np_pub = sum(npf[g] for g in BANKS_PUBLIC)
    np_pvt = sum(x for g, x in npf.items() if g not in BANKS_PUBLIC)
    if np_pub <= 0 or np_pvt <= 0:
        raise SamError(f"RTP bank net profit not positive (public {np_pub:,.2f}, private {np_pvt:,.2f})")
    bank_share_pub = np_pub / (np_pub + np_pvt)
    bank_own = bank - to_bank
    bank_pub = bank_own * bank_share_pub
    bank_pvt = bank_own * (1 - bank_share_pub) + to_bank
    if min(bank_pub, bank_pvt, bank_own) <= 0:
        raise SamError(f"T4a: E_BANK residual not positive (public {bank_pub:,.2f}, private {bank_pvt:,.2f})")
    cells = {
        ("E_NFPU", "total"): sector["pub_nfc"],
        ("E_NFPR", "total"): pvt_nfc,
        ("E_BANK", "public"): bank_pub,
        ("E_BANK", "private"): bank_pvt,
        ("E_NBFC", "public"): nbfc_pub,
        ("E_NBFC", "private"): nbfc_pvt,
        ("E_INSP", "public"): insp_pub,
        ("E_INSP", "private"): insp_pvt,
    }
    if abs(sum(cells.values()) - cit) > 1e-6:
        raise SamError("T4a cells do not add up to corporation tax")
    detail = {
        "corporate_d5_prior": corp, **{f"old_base_share_{k}": x for k, x in sh.items()},
        "nbfc_ul": ul, "nbfc_ml": ml, "hfc": hfc, "aifi": aifi, "deposit_taking_share_nbfc": dt_nbfc,
        "deposit_taking_share_hfc": dt_hfc, "moved_to_e_bank": to_bank, "insurers_life": life_all, "lic": lic,
        **{f"nonlife_{k}": x for k, x in nl.items()},
        "e_bank_residual": bank, "e_bank_own_banks": bank_own,
        **{f"bank_net_profit_{g}": x for g, x in npf.items()},
        "bank_net_profit_public": np_pub, "bank_net_profit_private": np_pvt,
        "bank_public_share_net_profit": bank_share_pub,
        # cross-check: the public FC total the old-base share alone would give (the pre-V-TX-1 method)
        "public_fc_old_base_prior": pub_fc, "public_fc_written": insp_pub + nbfc_pub + bank_pub,
    }  # fmt: skip
    return T4aSplit(cells, sh, detail, sorted(set(ps)), sorted(set(fc_in)), insp_pub + insp_pvt, nbfc,
                    pub_fc + pvt_fc)  # fmt: skip
