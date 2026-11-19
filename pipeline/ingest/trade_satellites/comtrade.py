"""UN Comtrade keyless preview API: India goods trade by HS 2-digit chapter and partner, monthly,
April 2023 to March 2024 (FY 2023-24), plus fiscal-year sums.

Access: only the public keyless preview (`https://comtradeapi.un.org/public/`, policy.PUBLIC_PARTS,
DECISIONS D1-3). The keyed /data/ API is not used. The preview returns at most 500 records and
one period per call, so the pulls are:
- the monthly dataset listing (getDA) for the release dates (the vintage of each month);
- TOTAL (all commodities) x every partner, each month (about 400 records);
- HS chapters (AG2) x World, each month (194 records);
- HS chapters x partner for the top N_TOP partners by FY 2023-24 exports + imports (ranked from
  the TOTAL pulls), two partners per call (at most 388 records).
A response with 500 records (possible truncation) is an error.

Comtrade's India data originate from DGCI&S (India's customs): exports FOB, imports CIF, calendar
months, HS 2022 (H6). Values are in US$ units and converted to US$ million.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

import polars as pl

from pipeline.core.unit import BuildContext, Dataset, FetchContext, RawFile
from pipeline.core.units import clean_label

from ._common import CONV_USD_UNITS, UNIT, USD_UNITS_TO_MILLION, fy_sums, partner_dims, sid

SRC = "un_comtrade"
BASE = "https://comtradeapi.un.org/public/v1"
REPORTER = 699  # India
MONTHS = [f"{y}{m:02d}" for y, m in [(2023, m) for m in range(4, 13)] + [(2024, m) for m in range(1, 4)]]
N_TOP = 30
PER_CALL = 2  # partners per HS-chapter call: 97 chapters x 2 flows x 2 partners = 388 < 500
MAX_RECORDS = 500
WORLD, AREAS_NES = 0, 899
FLOWS = {"X": ("exports", "fobvalue", "FOB"), "M": ("imports", "cifvalue", "CIF")}
TABLE = "UN Comtrade C/M/HS preview (reporter 699 India, classification H6)"
RELEASE = "UN Comtrade database, public preview API v1 (monthly, HS)"
F_GETDA = "ct_getda_c_m_hs.json"


def _q(period: str, cmd: str, partners: list[int] | None) -> str:
    q = f"{BASE}/preview/C/M/HS?reporterCode={REPORTER}&period={period}"
    if partners is not None:
        q += "&partnerCode=" + ",".join(str(p) for p in partners)
    return q + f"&flowCode=X,M&cmdCode={cmd}&includeDesc=true"


def _f_total(period: str) -> str:
    return f"ct_m_total_allpartners_{period}.json"


def _f_ag2_world(period: str) -> str:
    return f"ct_m_ag2_world_{period}.json"


def _f_ag2_pair(period: str, pair: tuple[int, ...]) -> str:
    return f"ct_m_ag2_p{'_'.join(str(p) for p in pair)}_{period}.json"


def fetch(ctx: FetchContext) -> None:
    ctx.fetch(SRC, f"{BASE}/getDA/C/M/HS?reporterCode={REPORTER}", name=F_GETDA)
    for p in MONTHS:
        ctx.fetch(SRC, _q(p, "TOTAL", None), name=_f_total(p), expect="json")
    for p in MONTHS:
        ctx.fetch(SRC, _q(p, "AG2", [WORLD]), name=_f_ag2_world(p), expect="json")
    pairs = top_partner_pairs(ctx)
    ctx.log(f"Comtrade: HS chapters for the top {N_TOP} partners in {len(pairs)} pairs x {len(MONTHS)} months")
    for p in MONTHS:
        for pair in pairs:
            ctx.fetch(SRC, _q(p, "AG2", list(pair)), name=_f_ag2_pair(p, pair), expect="json")


# ---------------------------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------------------------


def _records(raw: RawFile, period: str, cmd: str) -> list[dict[str, Any]]:
    doc = json.loads(raw.path.read_text(encoding="utf-8"))
    if doc.get("error"):
        raise ValueError(f"{raw.name}: API error {doc['error']!r}")
    data = doc.get("data")
    if not isinstance(data, list) or doc.get("count") != len(data):
        raise ValueError(f"{raw.name}: count {doc.get('count')} does not match {type(data).__name__} of records")
    if len(data) >= MAX_RECORDS:
        raise ValueError(f"{raw.name}: {len(data)} records = the preview cap of {MAX_RECORDS}; the pull may be truncated")
    if not data:
        raise ValueError(f"{raw.name}: no records")
    for r in data:
        want = {
            "typeCode": "C",
            "freqCode": "M",
            "period": period,
            "reporterCode": REPORTER,
            "classificationCode": "H6",
            "customsCode": "C00",
            "motCode": 0,
            "partner2Code": 0,
            "mosCode": "0",
        }
        bad = {k: r.get(k) for k, v in want.items() if r.get(k) != v}
        if bad:
            raise ValueError(f"{raw.name}: record outside the expected slice: {bad}")
        if r["flowCode"] not in FLOWS:
            raise ValueError(f"{raw.name}: unexpected flowCode {r['flowCode']!r}")
        if cmd == "TOTAL" and r["cmdCode"] != "TOTAL":
            raise ValueError(f"{raw.name}: cmdCode {r['cmdCode']!r} in a TOTAL pull")
        if cmd == "AG2" and not (len(r["cmdCode"]) == 2 and r["cmdCode"].isdigit()):
            raise ValueError(f"{raw.name}: cmdCode {r['cmdCode']!r} is not an HS chapter")
        v, alt = r["primaryValue"], r.get(FLOWS[r["flowCode"]][1])
        if v is None or v < 0 or (alt is not None and abs(alt - v) > 1e-6 * max(1.0, abs(v))):
            raise ValueError(f"{raw.name}: primaryValue {v} vs {FLOWS[r['flowCode']][1]} {alt}")
    keys = [(r["flowCode"], r["cmdCode"], r["partnerCode"]) for r in data]
    if len(set(keys)) != len(keys):
        raise ValueError(f"{raw.name}: duplicate flow x commodity x partner records")
    return data


def top_partner_pairs(ctx: Any) -> list[tuple[int, ...]]:
    """The N_TOP partners by FY 2023-24 exports + imports in the pinned TOTAL pulls, in pairs.
    Every partner except World and 'Areas, nes' counts (incl. 490 'Other Asia, nes' = Taiwan)."""
    tot: dict[int, float] = defaultdict(float)
    for p in MONTHS:
        for r in _records(ctx.raw(SRC, _f_total(p)), p, "TOTAL"):
            if r["partnerCode"] not in (WORLD, AREAS_NES):
                tot[r["partnerCode"]] += r["primaryValue"]
    ranked = sorted(tot, key=lambda c: (-tot[c], c))[:N_TOP]
    return [tuple(ranked[i : i + PER_CALL]) for i in range(0, len(ranked), PER_CALL)]


def _release_dates(raw: RawFile) -> dict[str, str]:
    doc = json.loads(raw.path.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for d in doc["data"]:
        p = str(d["period"])
        if p in MONTHS:
            if d["reporterCode"] != REPORTER or d["classificationCode"] != "H6" or d["freqCode"] != "M":
                raise ValueError(f"{raw.name}: unexpected dataset entry for {p}: {d}")
            if p in out:
                raise ValueError(f"{raw.name}: two datasets for {p}")
            out[p] = str(d["lastReleased"])[:10]
    missing = sorted(set(MONTHS) - set(out))
    if missing:
        raise ValueError(f"{raw.name}: no release listed for {missing}")
    return out


# ---------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------


def _prov(ctx: BuildContext, raw: RawFile, period: str, cmd: str, partners: str, vintage: str) -> str:
    return ctx.prov(
        raw=raw,
        table_id=TABLE,
        locator=f"JSON data[] records period={period}, cmdCode={cmd}, partnerCode={partners}, flowCode X and M; "
        "field primaryValue (= fobvalue for X, cifvalue for M)",
        unit_as_published="US$ (units)",
        conversion=CONV_USD_UNITS,
        price_basis="current",
        vintage=vintage,
        release=f"{RELEASE}; dataset for {period} last released {vintage} (getDA listing)",
        notes="Reporter India (data from DGCI&S). Calendar month; HS 2022 (H6); customs procedure, mode of "
        "transport and second partner are the totals (C00, 0, 0). Licence: UN Comtrade data for internal use; "
        "free-of-charge visualisation allowed (registry un_comtrade).",
    )


def build(ctx: BuildContext) -> list[Dataset]:
    releases = _release_dates(ctx.raw(SRC, F_GETDA))
    pairs = top_partner_pairs(ctx)
    pulls: list[tuple[str, str, str, list[int] | None]] = []
    for p in MONTHS:
        pulls.append((_f_total(p), p, "TOTAL", None))
        pulls.append((_f_ag2_world(p), p, "AG2", [WORLD]))
        pulls.extend((_f_ag2_pair(p, pair), p, "AG2", list(pair)) for pair in pairs)

    rows: list[dict[str, Any]] = []
    group_of: dict[str, str] = {}  # prov_id -> input group for the FY record
    for name, period, cmd, partners in pulls:
        raw = ctx.raw(SRC, name)
        recs = _records(raw, period, cmd)
        if partners is not None:
            got = {r["partnerCode"] for r in recs}
            if not got <= set(partners):
                raise ValueError(f"{name}: partners {sorted(got)} outside the requested {partners}")
        vintage = releases[period]
        pid = _prov(ctx, raw, period, cmd, "all" if partners is None else ",".join(map(str, partners)), vintage)
        group_of[pid] = f"{cmd}:{partners}"
        month = f"{period[:4]}-{period[4:]}"
        for r in recs:
            flow, _, basis = FLOWS[r["flowCode"]]
            partner = (r["partnerISO"] or "").strip()
            if not partner:
                raise ValueError(f"{name}: partner {r['partnerCode']} has no ISO code")
            rows.append(
                {
                    "series_id": f"ct.{flow}.{sid(r['cmdCode'])}.{sid(partner)}.current",
                    "source_id": SRC,
                    "table_id": TABLE,
                    "item_code": flow,
                    "item_label": clean_label(
                        f"{r['flowDesc']} ({basis}) | {r['cmdCode']} {r['cmdDesc']} | partner: {r['partnerDesc']} "
                        f"({r['partnerCode']})"
                    ),
                    "product": r["cmdCode"],
                    **partner_dims(partner),
                    "stock_flow": "flow",
                    "period": month,
                    "period_type": "month",
                    "value": r["primaryValue"] * USD_UNITS_TO_MILLION,
                    "unit": "USD_million",
                    "price_basis": "current",
                    "vintage": vintage,
                    "estimate_stage": "n.a.",
                    "status": "official",
                    "prov_id": pid,
                }
            )
    monthly = pl.DataFrame(rows, infer_schema_length=None).sort("series_id", "period")
    dup = monthly.select("series_id", "period").is_duplicated()
    if dup.any():
        raise ValueError(f"Comtrade: duplicate series-months across pulls: {monthly.filter(dup).head(5)}")

    # Fiscal-year sums (derived). One provenance record per pull group (the 12 monthly records).
    monthly = monthly.with_columns(pl.col("prov_id").replace_strict(group_of).alias("_grp"))
    keys = ["series_id", "_grp"]
    complete, incomplete = fy_sums(monthly, keys)
    fy_vintage = max(releases.values())
    fy_prov: dict[str, str] = {}
    for grp in sorted(set(group_of.values())):
        inputs = sorted(pid for pid, g in group_of.items() if g == grp)
        fy_prov[grp] = ctx.prov(
            raw=None,
            source_id=SRC,
            table_id=TABLE,
            locator=f"sums of the 12 monthly pulls 2023-04..2024-03 of cmdCode/partner group {grp}",
            unit_as_published="US$ (units)",
            conversion=CONV_USD_UNITS,
            price_basis="current",
            vintage=fy_vintage,
            release=f"{RELEASE}; latest monthly release used {fy_vintage}",
            status="derived",
            method=(
                "Indian fiscal year 2023-24 = sum of the 12 monthly Comtrade values April 2023..March 2024 for each "
                "flow x HS chapter x partner. Emitted only when all 12 months have a record; a series with a missing "
                "month is not summed (Comtrade publishes no zero records, but a missing month is not assumed to be "
                "zero here) and the dropped value is reported in docs/phase1/issues/trade_satellites.md."
            ),
            inputs=inputs,
        )
    first = monthly.unique("series_id", keep="first", maintain_order=True).drop("period", "value", "vintage", "prov_id")
    fy = (
        complete.join(first, on=keys, how="left", maintain_order="left")
        .with_columns(
            pl.col("fy").alias("period"),
            pl.lit("fy").alias("period_type"),
            pl.lit(fy_vintage).alias("vintage"),
            pl.lit("derived").alias("status"),
            pl.col("_grp").replace_strict(fy_prov).alias("prov_id"),
        )
        .drop("fy", "n_months", "_grp")
        .select(monthly.drop("_grp").columns)
        .sort("series_id")
    )
    dropped = incomplete.join(first.select("series_id", "item_code"), on="series_id")
    ctx.log(
        f"Comtrade FY 2023-24: {fy.height} complete series; {dropped.height} series with <12 months not summed "
        f"(US$ {dropped['value'].sum():,.1f} mn)"
    )
    return [
        Dataset(
            f"{UNIT}_comtrade_monthly_2324",
            monthly.drop("_grp"),
            f"UN Comtrade preview: India goods X (FOB) / M (CIF) by HS chapter x partner (World + top {N_TOP} "
            "partners) and totals by every partner, monthly Apr 2023..Mar 2024, US$ mn",
        ),
        Dataset(
            f"{UNIT}_comtrade_fy_2324",
            fy,
            "UN Comtrade preview: the same series summed to FY 2023-24 (derived; only series with all 12 months)",
        ),
    ]
