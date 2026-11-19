"""Independent verification of the trade_satellites unit (Phase 1, verifier first pass, 2026-09-29).

This file does NOT import the unit's code (pipeline.ingest.trade_satellites) or polars. It re-reads
the pinned raw files with the standard library (csv, json, hashlib, re), and reads the clean
parquet files with DuckDB. Every mapping (indicator codes, partner codes, periods, fiscal years,
measures, unit scaling) is re-implemented here from the publishers' documentation.

Method
- Every raw file's sha256 is checked against data/raw_pins/trade_satellites.yaml.
- FULL comparison, not a sample: every clean row of all seven datasets (240,746 values) is matched
  by its label keys (indicator/flow, partner code, HS chapter or EBOPS item, measure, period) to the
  raw observation, and the raw key set must equal the clean key set (no dropped or invented rows).
  Official rows: value == raw / 1e6 (IMF, Comtrade: US$ units) or == raw (BaTIS: US$ million).
  Derived FY rows: recomputed here from the raw months (April..March, all 12 months present).
- A seeded stratified random sample (seed 20260929, 10% of each dataset x period_type x status
  stratum, >= 50 per dataset) is re-located by a second, text-level route: the literal SDMX-CSV line
  (or the JSON record) is searched for in the raw file text, not via the csv reader.
- Hand anchors typed from the raw files (not produced by any parser).
- Metadata: status per measure, vintages against the raw attribute / listing / annotation, units,
  period types, partner-code placement (ISO3 -> geography; groups -> dim_other).

Close-out pass (2026-09-29): re-run against the current pins after the framework repair of
trade_satellites-14 (fw-19; one pin's retrieved_at changed, bytes unchanged) and the builder's V2 fix
(YAR/YMD -> dim_other). No value expectation changed. Section 7 adds provenance checks against the
current pins: pin == sidecar, every provenance record == its pin, every row's record names the raw
file that holds its number, and every derived FY record cites its 12 monthly inputs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import defaultdict
from functools import cache
from pathlib import Path

import duckdb
import pytest
import yaml

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean" / "trade_satellites"
PINS = ROOT / "data" / "raw_pins" / "trade_satellites.yaml"
SEED = 20260929
TOL = 1.5e-6  # clean values are rounded to 6 decimals on write

IMF_IND = {"exports_fob": "XG_FOB_USD", "imports_cif": "MG_CIF_USD"}
CT_FLOW = {"exports": "X", "imports": "M"}
BATIS_FLOW = {"exports": "X", "imports": "M"}
BATIS_MEAS = {"balanced": "B", "adjusted_imputed": "F", "reported": "N"}
BATIS_STATUS = {"B": "estimated", "F": "estimated", "N": "official"}
FY_MONTHS = [(2023, m) for m in range(4, 13)] + [(2024, m) for m in range(1, 4)]


# ------------------------------------------------------------------------------------------------
# raw access (independent)
# ------------------------------------------------------------------------------------------------


@cache
def pins() -> dict:
    return yaml.safe_load(PINS.read_text(encoding="utf-8"))["pins"]


def raw_path(key: str) -> Path:
    return ROOT / pins()[key]["path"]


@cache
def imf_obs(name: str) -> dict[tuple[str, str, str], float]:
    """(INDICATOR, COUNTERPART_COUNTRY, TIME_PERIOD) -> OBS_VALUE in US$ units."""
    out: dict[tuple[str, str, str], float] = {}
    with raw_path(f"imf_sdmx/{name}").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            assert r["COUNTRY"] == "IND" and r["DATAFLOW"] == "IMF.STA:IMTS(1.0.0)"
            if not r["TIME_PERIOD"]:
                continue
            k = (r["INDICATOR"], r["COUNTERPART_COUNTRY"], r["TIME_PERIOD"])
            assert k not in out, k
            out[k] = float(r["OBS_VALUE"])
    return out


@cache
def imf_attr_rows() -> list[dict]:
    with raw_path("imf_sdmx/imts_ind_m_2023_24_attrs.csv").open(encoding="utf-8", newline="") as fh:
        return [r for r in csv.DictReader(fh) if r["TIME_PERIOD"]]


@cache
def comtrade() -> tuple[dict, dict, dict]:
    """(flow, cmd, partnerISO, 'YYYY-MM') -> (US$ units, partnerCode); release date per month; files."""
    obs: dict = {}
    files: dict[str, list] = {}
    for key, pin in pins().items():
        if not key.startswith("un_comtrade/ct_m_"):
            continue
        doc = json.loads((ROOT / pin["path"]).read_text(encoding="utf-8"))
        assert not doc.get("error") and doc["count"] == len(doc["data"]) < 500, key
        files[key] = doc["data"]
        for r in doc["data"]:
            assert r["reporterCode"] == 699 and r["classificationCode"] == "H6" and r["freqCode"] == "M"
            assert r["customsCode"] == "C00" and r["motCode"] == 0 and r["partner2Code"] == 0
            val = r["fobvalue"] if r["flowCode"] == "X" else r["cifvalue"]
            assert val is not None and abs(val - r["primaryValue"]) < 1e-3
            per = f"{r['period'][:4]}-{r['period'][4:]}"
            k = (r["flowCode"], r["cmdCode"], r["partnerISO"].strip(), per)
            assert k not in obs, (key, k)
            obs[k] = (r["primaryValue"], r["partnerCode"])
    da = json.loads(raw_path("un_comtrade/ct_getda_c_m_hs.json").read_text(encoding="utf-8"))
    rel = {f"{str(d['period'])[:4]}-{str(d['period'])[4:]}": d["lastReleased"][:10] for d in da["data"]}
    return obs, rel, files


@cache
def batis_obs(name: str) -> dict[tuple[str, str, str, str, str], tuple[float, str, str]]:
    """(area, flow, service, adjustment, year) -> (US$ million, OBS_STATUS, METHODOLOGY_TYPE)."""
    out = {}
    with raw_path(f"oecd_wto_batis/{name}").open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            assert r["REF_AREA"] == "IND" and r["UNIT_MEASURE"] == "USD_EXC" and r["UNIT_MULT"] == "6"
            assert r["CURRENCY"] == "USD" and r["FREQ"] == "A"
            k = (r["COUNTERPART_AREA"], r["TRADE_FLOW"], r["SERVICE"], r["ADJUSTMENT"], r["TIME_PERIOD"])
            assert k not in out
            out[k] = (float(r["OBS_VALUE"]), r["OBS_STATUS"], r["METHODOLOGY_TYPE"])
    return out


@cache
def clean(ds: str) -> list[dict]:
    con = duckdb.connect()
    rel = con.sql(f"select * from read_parquet('{(CLEAN / f'trade_satellites_{ds}.parquet').as_posix()}')")
    cols = rel.columns
    return [dict(zip(cols, row)) for row in rel.fetchall()]


def partner_of(row: dict) -> str:
    if row["geography"] is not None:
        return row["geography"]
    kv = dict(p.split("=", 1) for p in row["dim_other"].split(";"))
    return kv["partner_group"]


def fy_of(y: int, m: int) -> str:
    s = y if m >= 4 else y - 1
    return f"{s}-{str(s + 1)[2:]}"


def close(a: float, b: float) -> bool:
    return abs(a - b) <= TOL + 1e-9 * abs(b)


# ------------------------------------------------------------------------------------------------
# 0. raw integrity
# ------------------------------------------------------------------------------------------------


def test_raw_hashes_match_pins():
    assert len(pins()) == 212
    for key, pin in pins().items():
        p = ROOT / pin["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == pin["sha256"], key


def test_raw_urls_are_public_keyless_endpoints():
    """D1-1 / D1-3: only keyless public endpoints; no auth headers, cookies or keys in any sidecar."""
    allowed = ("https://api.imf.org/external/sdmx/2.1/", "https://sdmx.oecd.org/public/rest/",
               "https://comtradeapi.un.org/public/v1/")  # fmt: skip
    for key, pin in pins().items():
        assert pin["url"].startswith(allowed), key
        assert not re.search(r"(?i)subscription-key|apikey|token|password", pin["url"]), key
        meta = json.loads(Path(str(ROOT / pin["path"]) + ".meta.json").read_text(encoding="utf-8"))
        hdrs = {h.lower() for h in meta["request_headers"]}
        assert not hdrs & {"cookie", "authorization", "ocp-apim-subscription-key", "x-api-key"}, key
        assert meta["status"] == 200 and meta["method"] == "GET" and meta["request_body"] is None, key


# ------------------------------------------------------------------------------------------------
# 1. IMF IMTS: full comparison
# ------------------------------------------------------------------------------------------------


def _imf_key(row: dict, freq: str) -> tuple[str, str, str]:
    per = row["period"]
    if freq == "M":
        assert re.fullmatch(r"\d{4}-\d{2}", per)
        per = per.replace("-", "-M")
    return (IMF_IND[row["item_code"]], partner_of(row), per)


@pytest.mark.parametrize("ds, raw, freq, ptype", [
    ("imf_imts_monthly", "imts_ind_m_2011on.csv", "M", "month"),
    ("imf_imts_annual", "imts_ind_a.csv", "A", "cy"),
])  # fmt: skip
def test_imf_official_full(ds, raw, freq, ptype):
    obs = imf_obs(raw)
    rows = clean(ds)
    seen = set()
    bad = []
    for r in rows:
        assert r["period_type"] == ptype and r["unit"] == "USD_million" and r["status"] == "official"
        k = _imf_key(r, freq)
        seen.add(k)
        if k not in obs or not close(r["value"], obs[k] / 1e6):
            bad.append((r["series_id"], r["period"], r["value"], obs.get(k)))
        # the partner code printed in the label must be the partner used
        assert r["item_label"].endswith(f"({k[1]})"), r["item_label"]
        assert ("Exports" in r["item_label"]) == (k[0] == "XG_FOB_USD")
    assert not bad, bad[:10]
    assert seen == set(obs), (len(seen), len(obs), sorted(set(obs) - seen)[:10])
    assert len(rows) == len(obs)


def test_imf_fy_recomputed_from_raw_months():
    obs = imf_obs("imts_ind_m_2011on.csv")
    acc: dict = defaultdict(lambda: [0.0, set()])
    for (ind, par, tp), v in obs.items():
        y, m = int(tp[:4]), int(tp[6:])
        a = acc[(ind, par, fy_of(y, m))]
        a[0] += v
        a[1].add(m)
    want = {k: a[0] / 1e6 for k, a in acc.items() if len(a[1]) == 12}
    rows = clean("imf_imts_fy")
    got = {}
    for r in rows:
        assert r["period_type"] == "fy" and r["status"] == "derived" and r["unit"] == "USD_million"
        got[(IMF_IND[r["item_code"]], partner_of(r), r["period"])] = r["value"]
    assert set(got) == set(want)
    bad = [(k, got[k], want[k]) for k in got if not close(got[k], want[k])]
    assert not bad, bad[:10]
    # FY 2023-24 world, typed from the builder's report and recomputed here from raw
    assert abs(want[("XG_FOB_USD", "G001", "2023-24")] - 437722) < 1
    assert abs(want[("MG_CIF_USD", "G001", "2023-24")] - 672861) < 1


def test_imf_vintage_is_publication_date():
    pubs = {r["PUBLICATION_DATE"][:10] for r in imf_attr_rows()}
    assert pubs == {"2026-08-31"}
    assert {r["UNIT"] for r in imf_attr_rows()} == {"USD"}
    assert {r["SCALE"] for r in imf_attr_rows()} == {"6"}  # the SCALE quirk: values are US$ units anyway
    for ds in ("imf_imts_monthly", "imf_imts_fy", "imf_imts_annual"):
        assert {r["vintage"] for r in clean(ds)} == {"2026-08-31"}


def test_imf_scale_is_us_dollars_not_millions():
    obs = imf_obs("imts_ind_m_2011on.csv")
    # India's world exports in Apr 2023 are ~US$ 35 bn: OBS_VALUE must be ~3.5e10, i.e. US$ units.
    v = obs[("XG_FOB_USD", "G001", "2023-M04")]
    assert 3.0e10 < v < 4.0e10


# ------------------------------------------------------------------------------------------------
# 2. UN Comtrade: full comparison
# ------------------------------------------------------------------------------------------------


def test_comtrade_monthly_full():
    obs, rel, _ = comtrade()
    rows = clean("comtrade_monthly_2324")
    seen, bad = set(), []
    for r in rows:
        assert r["period_type"] == "month" and r["status"] == "official" and r["unit"] == "USD_million"
        k = (CT_FLOW[r["item_code"]], r["product"], partner_of(r), r["period"])
        seen.add(k)
        if k not in obs or not close(r["value"], obs[k][0] / 1e6):
            bad.append((r["series_id"], r["period"], r["value"], obs.get(k)))
            continue
        assert r["item_label"].endswith(f"({obs[k][1]})"), r["item_label"]  # partnerCode in label
        assert r["vintage"] == rel[r["period"]]
    assert not bad, bad[:10]
    assert seen == set(obs)


def test_comtrade_fy_recomputed_from_raw_months():
    obs, rel, _ = comtrade()
    acc: dict = defaultdict(lambda: [0.0, set()])
    for (fl, cmd, par, per), (v, _) in obs.items():
        a = acc[(fl, cmd, par)]
        a[0] += v
        a[1].add(per)
    want = {k: a[0] / 1e6 for k, a in acc.items() if len(a[1]) == 12}
    got = {}
    for r in clean("comtrade_fy_2324"):
        assert r["period"] == "2023-24" and r["period_type"] == "fy" and r["status"] == "derived"
        assert r["vintage"] == max(rel[f"{y}-{m:02d}"] for y, m in FY_MONTHS)
        got[(CT_FLOW[r["item_code"]], r["product"], partner_of(r))] = r["value"]
    assert set(got) == set(want)
    bad = [(k, got[k], want[k]) for k in got if not close(got[k], want[k])]
    assert not bad, bad[:10]
    assert abs(want[("X", "TOTAL", "W00")] - 436918) < 1
    assert abs(want[("M", "TOTAL", "W00")] - 675387) < 1


def test_comtrade_top30_partners_independently_ranked():
    obs, _, files = comtrade()
    tot: dict = defaultdict(float)
    for (_fl, cmd, _par, _per), (v, code) in obs.items():
        if cmd == "TOTAL" and code not in (0, 899):
            tot[code] += v
    top = sorted(tot, key=lambda c: (-tot[c], c))[:30]
    pulled = set()
    for key in files:
        m = re.search(r"ct_m_ag2_p([\d_]+)_\d{6}\.json$", key)
        if m:
            pulled |= {int(x) for x in m.group(1).split("_")}
    assert pulled == set(top)
    share = sum(tot[c] for c in top) / sum(v for (fl, cmd, par, per), (v, _) in obs.items()
                                           if cmd == "TOTAL" and par == "W00")  # fmt: skip
    assert 0.815 < share < 0.822  # builder's 81.9%


# ------------------------------------------------------------------------------------------------
# 3. BaTIS: full comparison
# ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("ds, raw", [
    ("batis_2023_2024", "batis_ind_2023_2024.csv"),
    ("batis_history", "batis_ind_2005_2022.csv"),
])  # fmt: skip
def test_batis_full(ds, raw):
    obs = batis_obs(raw)
    if ds == "batis_history":
        obs = {k: v for k, v in obs.items() if k[2] == "S" or k[0] == "W"}
    seen, bad = set(), []
    for r in clean(ds):
        assert r["period_type"] == "cy" and r["unit"] == "USD_million" and r["vintage"] == "2025-12"
        kv = dict(p.split("=", 1) for p in r["dim_other"].split(";"))
        adj = BATIS_MEAS[kv["batis_measure"]]
        k = (partner_of(r), BATIS_FLOW[r["item_code"]], r["product"], adj, r["period"])
        seen.add(k)
        if k not in obs or not close(r["value"], obs[k][0]):
            bad.append((r["series_id"], r["period"], r["value"], obs.get(k)))
            continue
        assert r["status"] == BATIS_STATUS[adj], (r["series_id"], r["status"])
    assert not bad, bad[:10]
    assert seen == set(obs)


def test_batis_edition_annotation():
    t = raw_path("oecd_wto_batis/batis_dataflow.xml").read_text(encoding="utf-8")
    assert set(re.findall(r"BATIS_BPM6_(\w+?)_bulk", t)) == {"December2025"}


# ------------------------------------------------------------------------------------------------
# 4. seeded stratified sample, re-located by raw text (second route)
# ------------------------------------------------------------------------------------------------


def _sample(ds: str, frac: float = 0.10, floor: int = 50) -> list[dict]:
    rows = clean(ds)
    strata: dict = defaultdict(list)
    for r in rows:
        strata[(r["period_type"], r["status"], r["period"][:4])].append(r)
    rng = random.Random(f"{SEED}-{ds}")
    out = []
    for key in sorted(strata):
        grp = strata[key]
        out += rng.sample(grp, max(1, round(frac * len(grp))))
    if len(out) < floor:
        ids = {id(r) for r in out}
        out += rng.sample([r for r in rows if id(r) not in ids], floor - len(out))
    return out


@cache
def _text(key: str) -> str:
    return raw_path(key).read_text(encoding="utf-8")


@cache
def _line_index(key: str, nkey: int) -> dict[str, str]:
    """Raw text route: each line split naively on ',' (no csv reader); the first `nkey` fields joined
    back with ',' -> the next field (OBS_VALUE). The key fields hold no quotes or commas."""
    out: dict[str, str] = {}
    for line in _text(key).splitlines()[1:]:
        f = line.split(",", nkey + 1)
        k = ",".join(f[:nkey])
        assert k not in out, k
        out[k] = f[nkey]
    return out


@pytest.mark.parametrize("ds, raw, freq", [
    ("imf_imts_monthly", "imf_sdmx/imts_ind_m_2011on.csv", "M"),
    ("imf_imts_annual", "imf_sdmx/imts_ind_a.csv", "A"),
])  # fmt: skip
def test_sample_imf_by_raw_text(ds, raw, freq):
    idx = _line_index(raw, 6)
    rows = _sample(ds)
    assert len(rows) >= max(50, int(0.1 * len(clean(ds))) - 5)
    for r in rows:
        ind, par, per = _imf_key(r, freq)
        cell = idx.get(f"IMF.STA:IMTS(1.0.0),IND,{ind},{par},{freq},{per}")
        assert cell, (r["series_id"], r["period"])
        assert close(r["value"], float(cell) / 1e6), (r["series_id"], r["period"], cell)


@pytest.mark.parametrize("ds, raw", [
    ("batis_2023_2024", "oecd_wto_batis/batis_ind_2023_2024.csv"),
    ("batis_history", "oecd_wto_batis/batis_ind_2005_2022.csv"),
])  # fmt: skip
def test_sample_batis_by_raw_text(ds, raw):
    idx = _line_index(raw, 10)
    rows = _sample(ds)
    assert len(rows) >= 50
    for r in rows:
        kv = dict(p.split("=", 1) for p in r["dim_other"].split(";"))
        adj = BATIS_MEAS[kv["batis_measure"]]
        k = (f"OECD.SDD.TPS:DSD_BATIS@DF_BATIS(1.0),IND,{partner_of(r)},{BATIS_FLOW[r['item_code']]},S,"
             f"{r['product']},A,USD_EXC,{adj},{r['period']}")  # fmt: skip
        assert k in idx, (r["series_id"], r["period"])
        assert close(r["value"], float(idx[k])), (r["series_id"], r["period"])


@cache
def _ct_fragments(per: str) -> dict:
    """Literal JSON record fragments of one month's files, indexed by (flow, cmd, partnerISO)."""
    _, _, files = comtrade()
    out: dict = defaultdict(list)
    for key in files:
        if not key.endswith(f"_{per}.json"):
            continue
        for m in re.finditer(r'\{"typeCode":"C".*?"isAggregate":(?:true|false)\}', _text(key)):
            s = m.group(0)
            fl = re.search(r'"flowCode":"(\w+)"', s).group(1)
            cmd = re.search(r'"cmdCode":"(\w+)"', s).group(1)
            iso = re.search(r'"partnerISO":"([^"]*)"', s).group(1).strip()
            out[(fl, cmd, iso)].append(float(re.search(r'"primaryValue":([0-9.eE+-]+)', s).group(1)))
    return out


def test_sample_comtrade_by_raw_text():
    """Find the literal JSON fragment of each sampled record in the files of its month (regex on text)."""
    rows = _sample("comtrade_monthly_2324")
    for r in rows:
        frag = _ct_fragments(r["period"].replace("-", ""))
        hits = frag.get((CT_FLOW[r["item_code"]], r["product"], partner_of(r)), [])
        assert len(hits) == 1, (r["series_id"], r["period"], hits)
        assert close(r["value"], hits[0] / 1e6)


# ------------------------------------------------------------------------------------------------
# 5. hand anchors (typed from the raw files)
# ------------------------------------------------------------------------------------------------


def _val(ds, sid, period):
    v = [r["value"] for r in clean(ds) if r["series_id"] == sid and r["period"] == period]
    assert len(v) == 1, (ds, sid, period, v)
    return v[0]


@pytest.mark.parametrize("ds, sid, period, want", [
    # imts_ind_m_2023_24_attrs.csv line 2: IND,MG_CIF_USD,ABW,M,2023-M04,59186
    ("imf_imts_monthly", "imts.imports_cif.abw.current", "2023-04", 0.059186),
    # imts_ind_a.csv line 2: IND,MG_CIF_USD,ABW,A,2008,15450
    ("imf_imts_annual", "imts.imports_cif.abw.current", "2008", 0.015450),
    # ct_m_total_allpartners_202304.json: flowCode M, partner 0 World, cifvalue 49056049877.696
    ("comtrade_monthly_2324", "ct.imports.total.w00.current", "2023-04", 49056.049878),
    # same file: flowCode X, partner 842 USA, fobvalue 5908769968.877
    ("comtrade_monthly_2324", "ct.exports.total.usa.current", "2023-04", 5908.769969),
    # same file: flowCode M, partner 490 Other Asia nes (S19), 680322982.557
    ("comtrade_monthly_2324", "ct.imports.total.s19.current", "2023-04", 680.322983),
    # batis_ind_2023_2024.csv: IND,W,X,S,S,...,N,2023,337539.6894
    ("batis_2023_2024", "batis.exports.s.w.reported.current", "2023", 337539.6894),
    # batis_ind_2023_2024.csv: IND,W,M,S,SJ,...,N,2024,67188.491245
    ("batis_2023_2024", "batis.imports.sj.w.reported.current", "2024", 67188.491245),
])  # fmt: skip
def test_hand_anchors(ds, sid, period, want):
    assert abs(_val(ds, sid, period) - want) < 2e-6


# ------------------------------------------------------------------------------------------------
# 6. systematic-error hunts
# ------------------------------------------------------------------------------------------------


def test_partner_codes_placement():
    """ISO3 countries in geography; IMF groups (G..., GX..., TX...), Comtrade W00/S19/_X and BaTIS W/WXD
    in dim_other. Flags withdrawn ISO codes that slipped into geography."""
    geo = set()
    for ds in ("imf_imts_monthly", "imf_imts_annual", "comtrade_monthly_2324", "batis_2023_2024", "batis_history"):
        for r in clean(ds):
            if r["geography"] is not None:
                geo.add(r["geography"])
                assert re.fullmatch(r"[A-Z]{3}", r["geography"])
            else:
                assert "partner_group=" in r["dim_other"]
    assert not geo & {"W00", "G001", "WXD", "S19", "SUN", "YUG", "CSK", "DDR", "ANT", "SCG", "WBG", "KOS"}
    # YAR / YMD (the two pre-1990 Yemens, withdrawn ISO codes) were in geography in the first build
    # (verifier V2, minor). The builder fixed it (NON_ISO_3), so the pin is now the strict check.
    assert not geo & {"YAR", "YMD"}


def test_imf_annual_matches_monthly_calendar_sums_2011_2025():
    m = imf_obs("imts_ind_m_2011on.csv")
    a = imf_obs("imts_ind_a.csv")
    for ind in IMF_IND.values():
        for y in range(2011, 2026):
            s = sum(m[(ind, "G001", f"{y}-M{mm:02d}")] for mm in range(1, 13))
            assert abs(s / a[(ind, "G001", str(y))] - 1) < 0.002, (ind, y)


def test_comtrade_world_chapters_sum_to_total_each_month():
    obs, _, _ = comtrade()
    for y, mo in FY_MONTHS:
        per = f"{y}-{mo:02d}"
        for fl in "XM":
            chap = sum(v for (f, c, p, pp), (v, _) in obs.items()
                       if f == fl and p == "W00" and pp == per and c != "TOTAL")  # fmt: skip
            tot = obs[(fl, "TOTAL", "W00", per)][0]
            assert abs(chap / tot - 1) < 1e-6, (fl, per)


def test_imf_fy_world_exports_vs_tradestat_quoted_in_recon():
    """docs/phase0/recon/external.md s16 quotes TradeStat EIDB: "India's Total Export 437704.58 [2024-25]
    441452.14 [2025-26]" (US$ mn). Recomputed here from the raw IMF months, not from the clean table."""
    m = imf_obs("imts_ind_m_2011on.csv")
    for start, tradestat in ((2024, 437704.58), (2025, 441452.14)):
        months = [(start, mm) for mm in range(4, 13)] + [(start + 1, mm) for mm in range(1, 4)]
        s = sum(m[("XG_FOB_USD", "G001", f"{y}-M{mm:02d}")] for y, mm in months) / 1e6
        assert abs(s / tradestat - 1) < 0.005, (start, s)


def test_goods_fy_2324_imf_vs_comtrade():
    fy = {(r["item_code"], partner_of(r), r["period"]): r["value"] for r in clean("imf_imts_fy")}
    ct = {(r["item_code"], r["product"], partner_of(r)): r["value"] for r in clean("comtrade_fy_2324")}
    assert abs(fy[("exports_fob", "G001", "2023-24")] / ct[("exports", "TOTAL", "W00")] - 1) < 0.01
    assert abs(fy[("imports_cif", "G001", "2023-24")] / ct[("imports", "TOTAL", "W00")] - 1) < 0.01


# ------------------------------------------------------------------------------------------------
# 7. provenance against the CURRENT pins (added in the close-out pass, 2026-09-29)
#    The framework repaired trade_satellites-14 (fw-19): the pin of ct_m_ag2_p634_251_202402.json
#    now carries the sidecar's retrieved_at 10:47:03Z (was 10:47:31Z), which changed that file's
#    provenance record, the derived FY record citing it, and their prov_ids. These tests make sure
#    every provenance record agrees with the pins as they stand now and that rows point to the
#    record of the raw file that actually holds their number.
# ------------------------------------------------------------------------------------------------

DATASETS = ("imf_imts_monthly", "imf_imts_fy", "imf_imts_annual", "comtrade_monthly_2324", "comtrade_fy_2324",
            "batis_2023_2024", "batis_history")  # fmt: skip


@cache
def prov() -> dict[str, dict]:
    con = duckdb.connect()
    rel = con.sql(f"select * from read_parquet('{(CLEAN / '_provenance.parquet').as_posix()}')")
    cols = rel.columns
    out = {}
    for row in rel.fetchall():
        d = dict(zip(cols, row))
        assert d["prov_id"] not in out
        out[d["prov_id"]] = d
    return out


def test_pins_agree_with_sidecars():
    """Each pin's sha256, bytes, url and retrieved_at equal its raw file's .meta.json (fw-19 repair)."""
    for key, pin in pins().items():
        p = ROOT / pin["path"]
        meta = json.loads(Path(str(p) + ".meta.json").read_text(encoding="utf-8"))
        assert (meta["sha256"], meta["bytes"], meta["url"], meta["retrieved_at"]) == (
            pin["sha256"], pin["bytes"], pin["url"], pin["retrieved_at"]), key  # fmt: skip
        assert p.stat().st_size == pin["bytes"], key
    # the repaired pin, typed from the sidecar written by the first (interrupted) fetch
    rep = pins()["un_comtrade/ct_m_ag2_p634_251_202402.json"]
    assert rep["retrieved_at"] == "2026-09-29T10:47:03Z"
    assert rep["sha256"] == "ae5fc37a6c5e5266cb63ed6942b9bcce9f75b5cf42d20f9e66d6498b7218c1ce"


def test_provenance_records_match_current_pins():
    """Every record that cites a raw file cites it exactly as pinned now (path, sha256, url, retrieved_at),
    every pinned data file is cited, and every record is used by at least one row."""
    by_path = {pin["path"]: (key, pin) for key, pin in pins().items()}
    cited = set()
    for pid, d in prov().items():
        assert d["ingest_unit"] == "trade_satellites" and pid.startswith("trade_satellites:")
        if d["raw_path"] is None:
            assert d["status"] == "derived" and d["inputs"] and d["method"], pid
            continue
        key, pin = by_path[d["raw_path"]]
        cited.add(key)
        assert (d["raw_sha256"], d["url"], d["retrieved_at"]) == (pin["sha256"], pin["url"], pin["retrieved_at"]), pid
        assert d["source_id"] == key.split("/", 1)[0], pid
    # every pin except the metadata files (IMF attribute file and CL_IMTS_COUNTRY codelist used for
    # partner names, Comtrade getDA release listing, BaTIS dataflow): they carry no values
    meta_files = {"imf_sdmx/imts_ind_m_2023_24_attrs.csv", "imf_sdmx/imts_cl_country.xml",
                  "un_comtrade/ct_getda_c_m_hs.json", "oecd_wto_batis/batis_dataflow.xml"}  # fmt: skip
    assert set(pins()) - cited <= meta_files, sorted(set(pins()) - cited - meta_files)[:10]
    used = {r["prov_id"] for ds in DATASETS for r in clean(ds)}
    assert used == set(prov()), (len(used), len(prov()))


def test_rows_point_to_the_raw_file_that_holds_them():
    """Official rows: the record's raw file contains the row's observation, and the record's status and
    vintage equal the row's. Comtrade is checked per pull (each file is one month x one partner set)."""
    p = prov()
    raw_of = {pin["path"]: key for key, pin in pins().items()}
    _, _, files = comtrade()
    ct_keys = {k: {(r["flowCode"], r["cmdCode"], r["partnerISO"].strip(), f"{r['period'][:4]}-{r['period'][4:]}")
                   for r in recs} for k, recs in files.items()}  # fmt: skip
    want_file = {"imf_imts_monthly": "imf_sdmx/imts_ind_m_2011on.csv", "imf_imts_annual": "imf_sdmx/imts_ind_a.csv",
                 "batis_2023_2024": "oecd_wto_batis/batis_ind_2023_2024.csv",
                 "batis_history": "oecd_wto_batis/batis_ind_2005_2022.csv"}  # fmt: skip
    n = 0
    for ds in ("imf_imts_monthly", "imf_imts_annual", "comtrade_monthly_2324", "batis_2023_2024", "batis_history"):
        for r in clean(ds):
            d = p[r["prov_id"]]
            assert d["status"] == r["status"] and d["vintage"] == r["vintage"], (ds, r["series_id"])
            key = raw_of[d["raw_path"]]
            if ds == "comtrade_monthly_2324":
                k = (CT_FLOW[r["item_code"]], r["product"], partner_of(r), r["period"])
                assert k in ct_keys[key], (r["series_id"], r["period"], key)
            else:
                assert key == want_file[ds], (ds, r["series_id"], key)
            n += 1
    assert n == 76069 + 24798 + 62443 + 49936 + 17377


def test_derived_fy_rows_cite_their_monthly_inputs():
    """Each FY row's derived record lists (at least) the prov_ids of the 12 monthly rows it sums."""
    p = prov()
    for fy_ds, m_ds, key_of in (
        ("imf_imts_fy", "imf_imts_monthly", lambda r: (r["item_code"], partner_of(r))),
        ("comtrade_fy_2324", "comtrade_monthly_2324", lambda r: (r["item_code"], r["product"], partner_of(r))),
    ):
        mp: dict = defaultdict(set)
        for r in clean(m_ds):
            y, mo = int(r["period"][:4]), int(r["period"][5:])
            mp[(*key_of(r), fy_of(y, mo))].add(r["prov_id"])
        for r in clean(fy_ds):
            d = p[r["prov_id"]]
            assert d["status"] == "derived" == r["status"] and d["method"] and d["vintage"] == r["vintage"]
            inputs = set(d["inputs"].split(","))
            need = mp[(*key_of(r), r["period"])]
            assert need and need <= inputs, (fy_ds, r["series_id"], r["period"], need - inputs)
            assert all(p[i]["status"] == "official" for i in inputs), (fy_ds, r["prov_id"])
