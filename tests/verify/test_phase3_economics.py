"""V2 economics: checks behind docs/phase3/verify/V2_economics.md (PLAN s.7, row V2).

Written by the V2 verifier, who built nothing in Phase 3. Nothing here imports `pipeline` code. The balanced
SAM entries, the NAS derived residuals, the provenance and the time series are read with DuckDB straight from
Parquet; the exported JSON, the text sources (map-text, map-desc, messages, MDX, story YAML) and the built
static site (web/out/en) are read as data.

Each test names the finding it guards. A fixed finding's test passes normally. A finding that is still open is a
strict xfail: it turns into a failure (XPASS) once fixed, so the mark must then go and the report be updated.
Tests that read the built site skip when web/out/ is absent: build with `npm --prefix web run build`.
"""

from __future__ import annotations

import html
import json
import re
from functools import cache
from pathlib import Path

import duckdb
import pytest
import yaml

pytestmark = [pytest.mark.export]

ROOT = Path(__file__).resolve().parents[2]
SAM = ROOT / "data" / "sam" / "2023-24"
ENTRIES = SAM / "sam_entries_balanced.parquet"
PROV = SAM / "_provenance.parquet"
NAS_DERIVED = ROOT / "data" / "clean" / "mospi_nas_2026" / "mospi_nas_2026_derived_residuals.parquet"
TF = ROOT / "data" / "timeseries" / "top_flows.parquet"
WEB = ROOT / "web"
OUT = WEB / "out" / "en"
CONTENT = WEB / "content" / "en"
MSG = WEB / "messages" / "en"
STORY_YAML = ROOT / "pipeline" / "export" / "stories"

CON = duckdb.connect()
NO_TOTAL = "not held to a single published figure"


def q(sql: str) -> list[tuple]:
    return CON.sql(sql).fetchall()


@cache
def vdir() -> Path:
    idx = json.loads((WEB / "public" / "data" / "index.json").read_text())
    assert idx["fixture"] is False, "V2 runs on the real export only"
    return WEB / "public" / "data" / idx["data_version"]


@cache
def jload(rel: str):
    return json.loads((vdir() / rel).read_text())


@cache
def src_json(path: Path):
    return json.loads(path.read_text())


def map_text() -> dict:
    return src_json(CONTENT / "map-text.json")


def map_desc() -> dict:
    return src_json(CONTENT / "map-desc.json")


def msg(name: str) -> dict:
    return src_json(MSG / f"{name}.json")


def mdx(rel: str) -> str:
    return (CONTENT / rel).read_text()


def story_fig(slug: str, fid: str) -> dict:
    return jload(f"stories/{slug}.json")["figures"][fid]


def story_spec(slug: str) -> dict:
    return yaml.safe_load((STORY_YAML / f"{slug}.yaml").read_text())


def entry_sum(where: str) -> float:
    return q(f"select coalesce(sum(value), 0) from '{ENTRIES}' where {where}")[0][0]


def _built(rel: str) -> str:
    p = OUT / rel
    if not p.exists():
        pytest.skip(f"{p} not built (npm --prefix web run build)")
    return p.read_text()


def _text(h: str) -> str:
    h = re.sub(r"<script.*?</script>", " ", h, flags=re.S)
    h = re.sub(r"<style.*?</style>", " ", h, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))


def _desc(key: str) -> str:
    d = map_desc()
    for section in ("links", "series", "refs", "nodes"):
        if isinstance(d[section].get(key), str):
            return d[section][key]
    raise KeyError(key)


def _label(kind: str, key: str) -> str:
    return map_text()[kind][key]["label"]


# ---------------------------------------------------------------------------------------------------------------
# V2-01 (high): net lending was shown as "net borrowing"
# ---------------------------------------------------------------------------------------------------------------
def test_v2_01_net_borrowing_figures_are_positive_and_match_the_sam():
    figs = jload("stories/deficit-funding.json")["figures"]
    assert not [k for k in figs if k.startswith("nl_")], "net-lending figures are still exported"
    # Independent recomputation: net borrowing = non-financial payments - receipts of the capital account
    # = liabilities incurred - financial assets acquired. Here: the I_* (instrument) side of each K account.
    for gov, acc in (("cen", "K_GCEN"), ("sta", "K_GSTA")):
        liab = entry_sum(f"row = '{acc}' and col like 'I\\_%' escape '\\'")
        assets = entry_sum(f"col = '{acc}' and row like 'I\\_%' escape '\\'")
        nb = figs[f"nb_{gov}"]["value"]
        assert nb > 0, f"nb_{gov} = {nb}: both governments were net borrowers in 2023-24"
        assert abs(nb - (liab - assets)) < 0.02, (gov, nb, liab - assets)
        assert figs[f"nb_{gov}_gdp"]["value"] > 0
    assert abs(figs["nb_gg"]["value"] - figs["nb_cen"]["value"] - figs["nb_sta"]["value"]) < 0.02


def test_v2_01_no_borrowing_label_on_a_negative_figure():
    labels = msg("story")["figs"]
    bad = []
    for slug, lab in labels.items():
        figs = jload(f"stories/{slug}.json")["figures"]
        for fid, text in lab.items():
            if re.search(r"borrow", text, re.I) and fid in figs and figs[fid]["value"] < 0:
                bad.append((slug, fid, text, figs[fid]["value"]))
    caps = msg("story")["captions"]["deficit-funding"]
    assert "lending" not in caps["gap"].lower() or "borrowing (−)" in caps["gap"]
    assert not bad, bad


def test_v2_01_rendered_deficit_story_says_positive_net_borrowing():
    t = _text(_built("story/deficit-funding/index.html"))
    m = re.search(r"Net borrowing by the Centre came to (\S+)", t)
    assert m, "sentence not rendered"
    assert not m.group(1).startswith(("−", "-")), m.group(0)
    assert "both the Centre and the States were net borrowers" in t


# ---------------------------------------------------------------------------------------------------------------
# V2-02 (high): saving-investment errors and omissions given as Rs 1.55 lakh crore "as published"
# ---------------------------------------------------------------------------------------------------------------
@cache
def nas_si_errors() -> float:
    rows = q(
        f"select value from '{NAS_DERIVED}' where series_id = 'derived.si_errors_omissions.current' "
        "and period = '2023-24'"
    )
    assert len(rows) == 1
    return rows[0][0]


def test_v2_02_d3_total_is_the_nas_derived_si_errors():
    d3 = entry_sum("(row = 'X_DISC' or col = 'X_DISC') and ref = 'D3'")
    assert abs(d3 - nas_si_errors()) < 0.01
    m = jload("summary.json")["methodology"]
    assert abs(m["disc_d3"]["value"] - nas_si_errors()) < 0.01
    assert abs(m["disc_d3"]["value"] - m["disc_d3_valuables"]["value"] - m["disc_d3_si_errors"]["value"]) < 0.02
    assert "mospi_nas_2026:6d3d42dacce0" in m["disc_d3"]["prov"]


def test_v2_02_methodology_states_the_whole_d3_and_not_as_published():
    src = mdx("methodology/limits.mdx")
    bullet = next(line for line in src.splitlines() if "Saving-investment errors and omissions" in line)
    assert 'path="methodology.disc_d3"' in bullet
    assert "as published" not in bullet
    t = _text(_built("methodology/index.html"))
    i = t.find("Saving-investment errors and omissions ,")
    assert i >= 0
    assert "₹3.59 lakh crore" in t[i : i + 80], t[i : i + 200]


def test_v2_02_d3_texts_do_not_call_the_component_published():
    assert "Two published items" not in _desc("DISC--SI")
    assert "derived" in _desc("DISC--SI")
    assert "published total" not in _desc("D3").lower()
    disc = msg("map")["disc"]
    assert "The total is published" not in disc["D3_si_errors"]
    dt = yaml.safe_load((ROOT / "pipeline" / "export" / "disc_text.yaml").read_text())["disc_text"]
    assert not dt["D3.si_errors"]["summary"].startswith("Published total")


@pytest.mark.xfail(
    strict=True,
    reason="V2-22 (low, open): DISC--SI equals the NAS derived S-I errors exactly, but no balancing constraint pins "
    "it, so its badge says the sum is not held to a single published figure (integrator: needs a closure constraint)",
)
def test_v2_22_disc_si_link_is_pinned_to_the_nas_residual():
    assert "DISC--SI" in jload("sam/pinned.json")


# ---------------------------------------------------------------------------------------------------------------
# V2-03 (medium): RBI surplus timing item described the opposite way to D0-7; offset hidden in the residual
# ---------------------------------------------------------------------------------------------------------------
def test_v2_03_centre_residual_line_nets_the_k9b_offset():
    k9 = entry_sum("row = 'I_OTHR' and col = 'K_GCEN' and ref = 'K9'")
    k9b = entry_sum("row = 'I_OTHR' and col = 'K_GCEN' and ref = 'K9b'")
    figs = jload("stories/deficit-funding.json")["figures"]
    assert abs(figs["assets_cen_k9_net"]["value"] - (k9 + k9b)) < 0.02
    src = mdx("stories/deficit-funding.mdx")
    lists = re.findall(r'<FigList ids="([^"]+)"', src)
    shown = {x for ids in lists for x in ids.split()}
    assert "assets_cen_k9_net" in shown and "assets_cen_k9" not in shown
    assert "is counted in the year it is earned" not in src
    assert "in cash" in src


# ---------------------------------------------------------------------------------------------------------------
# V2-04 (medium): "subsidies are negative taxes instead of adding to what they spend" (NAS counts them as spending)
# ---------------------------------------------------------------------------------------------------------------
def test_v2_04_subsidy_convention_described_as_this_maps_and_sized():
    src = mdx("stories/gst-rupee.mdx")
    assert "instead of adding to what they spend" not in src
    assert re.search(r"In this map, as in the supply and use tables", src)
    figs = jload("stories/gst-rupee.json")["figures"]
    paid = -(figs["gg_product_subsidies"]["value"] + figs["gg_production_subsidies"]["value"])
    assert paid > 0
    assert abs(figs["gg_subsidies_paid"]["value"] - paid) < 0.02
    per100 = 100 * paid / figs["gg_outlays"]["value"]
    assert abs(figs["gg_subsidies_per100"]["value"] - per100) < 1e-4
    # Independent of the story spec: every negative entry the governments receive from a tax account is a subsidy
    # (P9a product subsidies, P10a gross production subsidies), booked as a negative tax.
    p9_p10 = entry_sum("row in ('G_CEN', 'G_STA') and col like 'T\\_%' escape '\\' and value < 0")
    assert abs(-p9_p10 - paid) / paid < 0.01, (p9_p10, paid)


# ---------------------------------------------------------------------------------------------------------------
# V2-05 (medium): "railways" in government investment; Centre's equity read as share purchases
# ---------------------------------------------------------------------------------------------------------------
def test_v2_05_railways_outside_government_investment():
    src = mdx("stories/deficit-funding.mdx")
    invest = next(line for line in src.splitlines() if line.startswith("Governments also invest"))
    assert "railways" not in invest.lower()
    assert "put money into shares" not in src
    assert re.search(r"Railways and the Posts are not in these figures", src)
    # The Centre's GFCF key excludes the departmental commercial heads (Railways 5002/5003, Posts 5201).
    pids = [r[0] for r in q(f"select distinct prov_id from '{ENTRIES}' where col = 'K_GCEN' and ref = 'I1a'")]
    assert pids
    for pid in pids:
        method = q(f"select method from '{PROV}' where prov_id = '{pid}'")[0][0]
        assert all(h in method for h in ("5002", "5003", "5201")), pid


# ---------------------------------------------------------------------------------------------------------------
# V2-06 (medium): "Taxes kept by the Centre" on gross Union taxes before devolution
# ---------------------------------------------------------------------------------------------------------------
def test_v2_06_union_tax_label_says_before_sharing():
    lab = _label("links", "TAX--CEN")
    assert "kept" not in lab.lower()
    assert "before" in lab.lower()
    t = _text(_built("index.html"))
    assert "Taxes kept by the Centre" not in t


# ---------------------------------------------------------------------------------------------------------------
# V2-07 (medium): first screen said households pay "Taxes Rs 3.3" of every Rs 100
# ---------------------------------------------------------------------------------------------------------------
def test_v2_07_first_screen_income_tax_label_and_note():
    hh = msg("map")["first"]["hh"]
    assert hh["parts"]["taxes"] != "Taxes" and "income" in hh["parts"]["taxes"].lower()
    assert "pay out" not in hh["title"]
    t = _text(_built("index.html"))
    assert "Income tax ₹3.3" in t
    assert "taxes on purchases are inside goods and services" in t
    # The base really is household income: the H column total equals the H row total (all receipts).
    col = entry_sum("col like 'H\\_%' escape '\\'")
    row = entry_sum("row like 'H\\_%' escape '\\'")
    assert abs(col - row) < 1.0
    parts = jload("summary.json")["headline"]["hh_outlays"]["parts"]
    assert abs(sum(p["value"] for p in parts) - col) < 1.0


@pytest.mark.xfail(
    strict=True,
    reason="V2-21 (low, open): the remittance story lists the same per-100 split (saving included) as "
    "'Of every hundred rupees that households paid out', while the first screen now calls it household income",
)
def test_v2_21_remittance_story_does_not_call_saving_paid_out():
    t = _text(_built("story/remittance-dubai/index.html"))
    assert "households paid out" not in t


# ---------------------------------------------------------------------------------------------------------------
# V2-08 (medium): "Official ... The total is not held to a single published figure"
# ---------------------------------------------------------------------------------------------------------------
def _badges(page: str) -> list[tuple[str, str, str, str]]:
    """(label text, data-status-total, panel kind, panel text) for every expandable badge in a built page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page, "lxml")
    out = []
    for b in soup.select("button[aria-controls][data-status-total]"):
        panel = soup.find(id=b["aria-controls"])
        if panel is None:
            continue
        out.append(
            (
                b.get_text(" ", strip=True),
                b["data-status-total"],
                panel.get("data-badge-kind", ""),
                panel.get_text(" ", strip=True),
            )
        )
    return out


def test_v2_08_gdp_badge_is_not_contradicted():
    page = _built("index.html")
    from bs4 import BeautifulSoup

    card = BeautifulSoup(page, "lxml").select_one('[data-headline="gdp"]')
    assert card is not None
    gdp = _badges(str(card))
    assert gdp, "GDP badge not found"
    label, total, kind, panel = gdp[0]
    assert total == jload("summary.json")["gdp"]["label"] == "official"
    assert kind == "single"
    assert NO_TOTAL not in panel


def test_v2_08_no_official_or_derived_total_badge_says_unpinned_anywhere():
    if not OUT.exists():
        pytest.skip("web/out not built")
    bad, seen = [], 0
    for f in sorted(OUT.rglob("index.html")):
        for label, total, kind, panel in _badges(f.read_text()):
            seen += 1
            if total in ("official", "derived") and NO_TOTAL in panel:
                bad.append((str(f.relative_to(OUT)), label))
            if kind == "single" and NO_TOTAL in panel:
                bad.append((str(f.relative_to(OUT)), label, "single"))
    assert seen > 50
    assert not bad, bad[:10]


# ---------------------------------------------------------------------------------------------------------------
# V2-09 (medium): F32 "negative in some years"; also every other sign claim in a series description
# ---------------------------------------------------------------------------------------------------------------
def _signs(fid: str) -> tuple[int, int, int]:
    return q(
        f"select count(*), count(*) filter (where value < 0), count(*) filter (where value > 0) "
        f"from '{TF}' where flow_id = '{fid}'"
    )[0]


def test_v2_09_series_sign_claims_match_the_data():
    n, neg, pos = _signs("F32")
    assert n > 0 and neg == n
    f32 = _desc("F32")
    assert "some years" not in f32 and re.search(r"every year", f32)
    for fid in ("F11",):  # "negative in most years"
        n, neg, _ = _signs(fid)
        assert "most years" in _desc(fid) and neg / n > 0.75
    for fid in ("F49",):  # "in a few years it was a surplus" (stored negative)
        n, neg, _ = _signs(fid)
        assert "few years" in _desc(fid) and 0 < neg <= 5
    for fid in ("M10",):  # "in some years stocks were run down"
        n, neg, _ = _signs(fid)
        assert "some years" in _desc(fid) and 0 < neg < n / 2


# ---------------------------------------------------------------------------------------------------------------
# Low findings still open (strict xfails: remove the mark when the text is fixed)
# ---------------------------------------------------------------------------------------------------------------
@pytest.mark.xfail(strict=True, reason="V2-10 (low, open): old-base flag text '(2022-23 NAS)' reads as the new base")
def test_v2_10_old_base_flag_text_names_the_2011_12_series():
    assert "2022-23 NAS" not in msg("common")["flags"]["old_base_structure"]


@pytest.mark.xfail(strict=True, reason="V2-11 (low, open): household T3a uses the same old-base D5 share, not flagged")
def test_v2_11_household_income_tax_in_old_base_scope():
    scope = yaml.safe_load((ROOT / "pipeline" / "export" / "old_base_scope.yaml").read_text())
    assert "sam_taxes:4279ef5046b4" in json.dumps(scope)


@pytest.mark.xfail(strict=True, reason="V2-12 (low, open): GST 'net' glossed as credit only, not refunds (D0-5)")
def test_v2_12_gst_net_mentions_refunds():
    line = next(x for x in mdx("stories/gst-rupee.mdx").splitlines() if "**net**" in x)
    assert "refund" in line


@pytest.mark.xfail(strict=True, reason="V2-13 (low, open): 'the economically final part of GST' ignores GFCF/GFCE")
def test_v2_13_household_share_not_the_only_final_part():
    assert "the economically final part of GST" not in mdx("stories/gst-rupee.mdx")


@pytest.mark.xfail(strict=True, reason="V2-14 (low, open): SI--PRDS 'The totals follow national accounts' vs Estimated")
def test_v2_14_si_prds_wording_follows_badge():
    assert "The totals follow national accounts" not in _desc("SI--PRDS")


@pytest.mark.xfail(strict=True, reason="V2-16 (low, open): issues/U1.md still says the disc.* request is open")
def test_v2_16_u1_issue_note_closed():
    assert "Request to U3 still open" not in (ROOT / "docs" / "phase3" / "issues" / "U1.md").read_text()


@pytest.mark.xfail(strict=True, reason="V2-17 (low, open): FC--TAX omits quasi-corporate income tax of banks")
def test_v2_17_fc_tax_mentions_quasi_corporate_income_tax():
    assert re.search(r"income tax|quasi|treat as companies", _desc("FC--TAX"), re.I)


@pytest.mark.xfail(strict=True, reason="V2-18 (low, open): F13 description silent on the food-subsidy base break")
def test_v2_18_f13_mentions_base_break():
    assert re.search(r"food", _desc("F13"), re.I)


@pytest.mark.xfail(strict=True, reason="V2-19 (low, open): remittance groups are fifths of persons per area")
def test_v2_19_remittance_groups_not_fifth_of_households():
    figs = msg("story")["figs"]["remittance-dubai"]
    assert "fifth of households" not in figs["remit_top_per100"]
    assert "fifth of households" not in figs["remit_bottom_per100"]


@pytest.mark.xfail(
    strict=True, reason="V2-20 (low, open): household residual text says 'published', badge 'Derived total'"
)
def test_v2_20_household_residual_not_called_published():
    assert "The total is the published figure" not in _desc("HH--DISC")
    assert "published" not in _label("links", "HH--DISC").lower()
    assert "Published total" not in _desc("D1")
