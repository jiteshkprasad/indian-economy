"""V5 honesty and licences: checks on the export, the content files and the built site (PLAN s.7, row V5).

Report: docs/phase3/verify/V5_honesty_licences.md. Written by the V5 verifier, who built nothing in Phase 3. Each
test names its finding id. Fixed findings are plain tests (they must keep passing); findings that are still open
are strict xfails, so they turn into failures (XPASS) once fixed and the mark must then go.

Tests that read the built site (web/out/) skip when it is absent: build with `npm --prefix web run build`.
Nothing here imports `pipeline` code.
"""

from __future__ import annotations

import glob
import html
import json
import re
from functools import cache
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.export]

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
OUT = WEB / "out" / "en"
CONTENT = WEB / "content" / "en"


@cache
def vdir() -> Path:
    idx = json.loads((WEB / "public" / "data" / "index.json").read_text())
    assert idx["fixture"] is False, "V5 runs on the real export only"
    return WEB / "public" / "data" / idx["data_version"]


def jload(rel: str):
    return json.loads((vdir() / rel).read_text())


def page(rel: str) -> str:
    p = OUT / rel / "index.html" if rel else OUT / "index.html"
    if not p.exists():
        pytest.skip(f"built site absent ({p}); run npm --prefix web run build")
    return p.read_text()


def visible_text(h: str) -> str:
    """Page text without scripts, styles and the RSC payload, entities unescaped."""
    h = re.sub(r"<script\b.*?</script>", " ", h, flags=re.S)
    h = re.sub(r"<style\b.*?</style>", " ", h, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", h))


def all_entries() -> list[dict]:
    out: list[dict] = []
    for f in sorted((vdir() / "sam" / "entries").glob("*.json")):
        out.extend(json.loads(f.read_text())["entries"])
    return out


# --------------------------------------------------------------------------------------------- V5-01 (fixed) ----
def test_v5_01_export_pct_change_is_a_fraction():
    """pct_change = (v - prior) / |prior| as a fraction (0.05 = 5%), so the panel's pct format is right."""
    n = 0
    for e in all_entries():
        p, pr = e.get("pct_change"), e.get("prior")
        if p is None or not pr or abs(pr) < 1:
            continue
        n += 1
        exp = (e["v"] - pr) / abs(pr)
        assert abs(p - exp) <= max(0.005, 0.01 * abs(exp)), (e["row"], e["col"], e["ref"], p, exp)
    assert n > 3000
    # the round-1 example: K_HH <- H_U5, K4a, moved +7.3%
    hit = [e for e in all_entries() if e["row"] == "K_HH" and e["col"] == "H_U5" and e["ref"] == "K4a"]
    assert hit and abs(hit[0]["pct_change"] - 0.0726) < 0.001, hit


BEFORE_AFTER = re.compile(
    r'Before → after balancing<!-- -->: <span class="num" data-num-value="([-\d.e]+)"[^>]*>[^<]*</span> → '
    r'<span class="num" data-num-value="([-\d.e]+)"[^>]*>[^<]*</span> <!-- -->\(<span class="num" '
    r'data-num-value="([-\d.e]+)" data-num-fmt="pct">([^<]*)</span>'
)


def test_v5_01_flow_pages_before_after_percentages():
    """Every "Before → after balancing" line on every /en/flow/* page: the shown % is the move between the two
    shown values (round 1: "₹17,751 crore → ₹3,032 crore (−8,291.8%)")."""
    if not OUT.exists():
        pytest.skip("built site absent")
    n = 0
    for f in sorted(glob.glob(str(OUT / "flow" / "*" / "index.html"))):
        for a, b, p, txt in BEFORE_AFTER.findall(Path(f).read_text()):
            a, b, p = float(a), float(b), float(p)
            n += 1
            if abs(a) < 10:  # crore values rounded to 2 dp: the ratio of two rounded tiny values is not exact
                continue
            exp = (b - a) / abs(a)
            assert abs(p - exp) <= max(0.002, 0.01 * abs(exp)), (Path(f).parent.name, a, b, p, txt)
            assert abs(p) < 60, (Path(f).parent.name, txt)
    assert n > 400, n


# --------------------------------------------------------------------------------------------- V5-02 (fixed) ----
def test_v5_02_no_total_wording_not_on_single_figures():
    """The "not held to a single published figure" line is for sums only; the static GDP card and series value
    badges are rendered as single figures (data-badge-kind="single")."""
    h = page("")
    i = h.find("India&#x27;s GDP in") if "India&#x27;s GDP in" in h else h.find("India's GDP in")
    assert i >= 0
    seg = h[i : i + 4000]
    assert 'data-badge-kind="single"' in seg, "GDP badge is not a single-figure badge"
    for sid in ("F01", "F03", "M01"):
        s = page(f"series/{sid}")
        j = s.find("data-panel-value")
        assert j >= 0
        assert 'data-badge-kind="single"' in s[j : j + 6000], sid
    msgs = json.loads((WEB / "messages" / "en" / "common.json").read_text())
    assert "sum" in msgs["status"]["noTotal"].lower()


# ----------------------------------------------------------------------------------------- V5-03 (fixed) ----
def _badge_after(h: str, num_start: int) -> tuple[str, str] | None:
    """The status attributes of a badge that directly follows the figure at `num_start`."""
    end = h.find("</span>", num_start)
    tail = h[end : end + 600]
    badge = r'<span[^>]*data-status-total="([a-z]*)" data-status-split="([a-z_]+)"'
    m = re.match(r"</span>\s*(?:<!-- -->\s*)?" + badge, tail)
    return (m.group(1), m.group(2)) if m else None


def test_v5_03_methodology_economic_values_badged():
    """Every methodology figure that the export gives a status (split_label / total_label) shows that badge,
    and GDP shows its own label; the page's claim about badges matches this."""
    h = page("methodology")
    s = jload("summary.json")
    checked = 0
    for key, item in s["methodology"].items():
        if not isinstance(item, dict) or "split_label" not in item:
            continue
        v = item["value"]
        hits = [m.start() for m in re.finditer(r'data-num-value="([-\d.e]+)"', h) if abs(float(m.group(1)) - v) < 0.6]
        assert hits, f"methodology.{key} ({v}) not on the page"
        got = [_badge_after(h, i) for i in hits]
        want = (item["total_label"] or "", item["split_label"])
        assert want in got, (key, want, got)
        checked += 1
    assert checked >= 8, checked
    gdp = s["gdp"]["value"]
    gi = [m.start() for m in re.finditer(r'data-num-value="([-\d.e]+)"', h) if abs(float(m.group(1)) - gdp) < 0.6]
    assert any(_badge_after(h, i) and _badge_after(h, i)[1] == s["gdp"]["label"] for i in gi)
    status = (CONTENT / "methodology" / "status.mdx").read_text()
    assert "Every figure on this site carries a badge" not in status


# ----------------------------------------------------------------------------------------- V5-04 (fixed) ----
def test_v5_04_first_screen_parts_show_their_totals():
    """Each "per ₹100" household part shows its own total label (official for consumption and saving)."""
    h = page("")
    parts = jload("summary.json")["headline"]["hh_outlays"]["parts"]
    by = {p["key"]: p for p in parts}
    assert by["consumption"]["total_label"] == "official" and by["saving"]["total_label"] == "official"
    for key, p in by.items():
        i = h.find(f'data-part="{key}"')
        assert i >= 0, key
        m = re.search(r'data-status-total="([a-z]*)" data-status-split="([a-z_]+)"', h[i : i + 3000])
        assert m, key
        assert (m.group(1), m.group(2)) == (p["total_label"] or "", p["split_label"]), key


# ----------------------------------------------------------------------------------------- V5-05 (fixed) ----
PIN_ID = re.compile(
    r"\b(?:closure|households|capital_financial|rest_of_world|factors|production|taxes|government|fincorp):[a-z0-9_.]+|\bts:[FM]\d+\b"
)


def test_v5_05_no_raw_pin_ids_in_page_text():
    """No pin id ("ts:M05", "closure:d1.published_total") is shown as text on any built page."""
    if not OUT.exists():
        pytest.skip("built site absent")
    bad = {}
    for f in glob.glob(str(OUT / "**" / "index.html"), recursive=True):
        for m in PIN_ID.finditer(visible_text(Path(f).read_text())):
            bad.setdefault(m.group(0), Path(f).parent.name)
    assert not bad, bad


# ----------------------------------------------------------------------------------------- V5-06 (fixed) ----
def test_v5_06_rbi_republication_needs_permission():
    src = (CONTENT / "methodology" / "sources.mdx").read_text()
    assert "only for links and caching" not in src
    assert re.search(r"RBI needs to give permission for two things", src)
    assert "republish figures derived from its statistics" in src
    assert "before any public launch" in src
    issues = (CONTENT / "methodology" / "issues.mdx").read_text()
    assert "republishing figures derived from its statistics" in issues


# ----------------------------------------------------------------------------------------- V5-07 (fixed) ----
def test_v5_07_provisional_list_complete():
    t = (CONTENT / "methodology" / "provisional.mdx").read_text()
    for d in ("D2-20", "D2-19", "D2-24", "D2-11", "D2-13", "D2-21", "D2-4", "D2-8", "D2-7"):
        assert f"({d})" in t, d
    # CHECKPOINT_B s.6c: all thirteen items, by a phrase each
    for phrase in (
        "public sector companies keep",  # fincorp-37
        "banks and NBFCs",  # fincorp-34b
        "household saving profile",  # factors-24
        "survey does not capture",  # households-1
        "FISIM",  # households-19
        "private companies' dividends",  # fincorp-27
        "urban local bodies' capital",  # capital_financial-30d
        "general-government saving",  # government-2
        "overlap between revenue grants",  # government-28
        "foreign direct investment income",  # rest_of_world-27
        "premiums and claims",  # V-FIN-9
        "fund-held interest",  # V-FIN-10
        "ratio-linked",  # timeseries-5
    ):
        assert phrase in t, phrase
    assert "tolerance bands" in t


# ----------------------------------------------------------------------------------------- V5-08 (fixed) ----
def test_v5_08_every_cited_source_is_in_registry_yaml():
    reg = yaml.safe_load((ROOT / "data" / "registry.yaml").read_text())
    ids = {s["id"]: s for s in reg["sources"]}
    prov = jload("provenance.json")["sources"]
    assert prov
    for sid, s in prov.items():
        assert sid in ids, f"{sid} cited but not in data/registry.yaml"
        lic = ids[sid].get("license", {})
        assert s["attribution"] == lic.get("attribution"), sid
        assert s["licence"] == lic.get("name"), sid
        assert s.get("registry_status") != "unverified", sid


# --------------------------------------------------------------------------- round-1 checks that held (guards) ----
def test_no_rbi_links_anywhere_in_out():
    if not OUT.exists():
        pytest.skip("built site absent")
    out = OUT.parent
    hits = [
        str(p.relative_to(out))
        for p in out.rglob("*")
        if p.is_file()
        and p.suffix in {".html", ".js", ".json", ".txt"}
        and "rbi.org.in" in p.read_text(errors="ignore")
    ]
    assert not hits, hits[:10]


# ------------------------------------------------------------------------------------- open (low) findings ----
@pytest.mark.xfail(strict=True, reason="V5-09 open: series headline value carries no estimate stage")
def test_v5_09_series_headline_shows_stage():
    s = visible_text(page("series/F01"))
    i = s.find("Value in 2025-26")
    assert i >= 0
    assert re.search(r"provisional|\bPE\b", s[i : i + 200], flags=re.I)


@pytest.mark.xfail(strict=True, reason="V5-10 open: why excerpts quote an older balancing run's values")
def test_v5_10_why_excerpt_matches_balanced_value():
    s = visible_text(page("flow/CEN--NFC"))
    assert "17,751 -> 3,035" not in s


@pytest.mark.xfail(strict=True, reason="V5-11 open: SVG ribbon value labels are not bound numbers")
def test_v5_11_svg_value_labels_are_bound():
    h = page("")
    svg = re.findall(r"<svg\b.*?</svg>", h, flags=re.S)
    assert any("data-num-value" in s for s in svg)


@pytest.mark.xfail(strict=True, reason="V5-12 open: the licence paragraph's permission list omits CAG")
def test_v5_12_permission_list_names_cag():
    src = (CONTENT / "methodology" / "sources.mdx").read_text()
    para = src[src.find("**Licences.**") :]
    para = para[: para.find("\n\n")]
    assert "CAG" in para or "Comptroller" in para


@pytest.mark.xfail(strict=True, reason="V5-13 open: loadIndex() does not refuse fixture data outside check-data")
def test_v5_13_load_index_refuses_fixture():
    src = (WEB / "src" / "data" / "server.ts").read_text()
    body = src[src.find("export function loadIndex") :]
    body = body[: body.find("\n}\n")]
    assert "fixture" in body and "ALLOW_FIXTURE" in body


@pytest.mark.xfail(strict=True, reason="V5-14 open: banner calls the curated ribbons 'the n largest flows'")
def test_v5_14_banner_does_not_say_largest():
    m = json.loads((WEB / "messages" / "en" / "map.json").read_text())
    assert "largest" not in m["ts"]["banner"]
