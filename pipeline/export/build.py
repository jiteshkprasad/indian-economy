"""`python -m pipeline export [--out DIR] [--check] [--fixture]` (docs/phase3/PLAN.md s.3.1).

build_payload(inputs) computes every file of the web data contract (s.3.6) as Python objects;
write_export() serialises them deterministically into <out>/<data_version>/ and replaces <out>/index.json last,
atomically; --check exports into a temporary folder and compares bytes with what is on disk.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from pipeline.core import io
from pipeline.core.manifest import repo_lock
from pipeline.core.paths import Layout
from pipeline.export.inputs import GDP_BASE, YEAR, ExportError, ExportInputs

EXPORT_DIR = Path(__file__).resolve().parent
SCHEMA_VERSION = 2
VERSION_DIR_RE = re.compile(r"^\d{4}-\d{2}\.[0-9a-f]{10}$")
FIXTURE_VERSION = f"{YEAR}.fixture0000"
ISSUES_FILE = Path("docs/phase3/issues/U1.md")


def export_code_hash(root: Path) -> str:
    """sha256 over pipeline/export/** (path + content), like pipeline.core.manifest.code_hash."""
    base = root / "pipeline" / "export"
    files = sorted(
        (p for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(root).as_posix().encode() + b"\0")
        h.update(hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).digest())
    return h.hexdigest()


def build_payload(inp: ExportInputs) -> tuple[dict[str, Any], list[str]]:
    """{relative path: JSON object} for every file in the data version folder, plus warnings."""
    from pipeline.export import pinned as pn
    from pipeline.export import provenance as pv
    from pipeline.export import sam_export as se
    from pipeline.export import stories as st
    from pipeline.export import summary as sm
    from pipeline.export import timeseries as ts

    warnings: list[str] = []
    td = ts.TsData(inp)
    # entry-level provenance flags first (depends_on_assumption feeds the entry flags)
    _, pflags = pv.provenance_json(inp, sorted(set(inp.entries["prov_id"].to_list())))
    view = se.build_view(inp, pflags)
    ent = se.pl_entries(view)
    flow_entries = pn.flow_entry_indices(view, inp.ts_flows, ent)
    pins = pn.constraint_pins(view) + pn.ts_pins(
        view, {k: [i for i, _ in v] for k, v in flow_entries.items()}, td.status_2023()
    )
    pinned, _ = pn.pinned_json(view, pins)
    files: dict[str, Any] = {
        "hierarchy.json": inp.hierarchy.to_json(),
        "sam/cells.json": se.cells_json(view),
        "sam/pinned.json": pinned,
        "sam/constraints.json": se.constraints_json(view),
        "sam/refs.json": se.refs_json(view),
    }
    for node, obj in se.entries_json(view).items():
        files[f"sam/entries/{node}.json"] = obj
    files["ts/series.json"] = ts.series_json(td)
    tsv, w = ts.view_json(view, td, flow_entries)
    warnings.extend(w)
    files["ts/view.json"] = tsv
    files["ts/cover.json"] = ts.cover_json(view, flow_entries)
    gdp = sm.gdp_figure(td, inp)
    story_prov: list[str] = []
    for slug, spec in sorted(inp.stories.items()):
        story = st.evaluate_story(slug, spec, view, td, pins, flow_entries, float(gdp["value"]), gdp["prov"])
        files[f"stories/{slug}.json"] = story
        for f in story["figures"].values():
            story_prov.extend(f["prov"])
    used = set(inp.entries["prov_id"].to_list())
    used |= {p for p in inp.ts["prov_id"].to_list() if p}
    used |= set(inp.constraints["prov_id"].to_list())
    used |= set(story_prov)
    used.add(gdp["prov"])
    # the methodology counts that need the provenance walk do not depend on `used`
    extra = {
        "withheld_urls": pv.withheld_url_count(inp),
        "assumption_records": pv.assumption_dependents(inp),
        "assumption_records_direct": pv.assumption_dependents(inp, direct=True),
    }
    meth = sm.methodology_json(view, td, float(gdp["value"]), extra, pins)
    for m in meth.values():
        used |= set(m["prov"])
    provenance, _ = pv.provenance_json(inp, sorted(used))
    files["provenance.json"] = provenance
    meth["sources"] = sm._m(len(provenance["sources"]), "count")
    meth["sources_withheld"] = sm._m(
        sum(1 for s in provenance["sources"].values() if s["link_mode"] == "withheld"), "count"
    )
    summary = sm.summary_json(view, td, pins, meth)
    files["summary.json"] = summary
    # every prov id referenced anywhere must be in provenance.json
    missing = sorted(_referenced_prov(files) - set(provenance["records"]))
    if missing:
        raise ExportError(f"provenance ids referenced but not exported: {missing[:10]}")
    from pipeline.export.validate import validate_file

    for rel, obj in sorted(files.items()):
        errs = validate_file(rel, obj)
        if errs:
            raise ExportError(f"{rel} breaks its JSON schema: " + "; ".join(errs[:5]))
    return files, warnings


def _referenced_prov(files: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for rel, obj in files.items():
        if rel.startswith("sam/entries/"):
            out |= {e["prov"] for e in obj["entries"]}
        elif rel == "sam/constraints.json":
            out |= {c["prov"] for c in obj.values()}
        elif rel == "ts/series.json":
            for f in obj["flows"]:
                arrs = [f["main"], *([f["linked"]] if f["linked"] else []), *(a["arrays"] for a in f["alts"])]
                for a in arrs:
                    out |= {p for p in a["prov"] if p}
            out |= {p for p in obj["gdp"]["prov"] if p}
        elif rel.startswith("stories/"):
            for f in obj["figures"].values():
                out |= set(f["prov"])
        elif rel == "summary.json":
            out.add(obj["gdp"]["prov"])
            out |= set(obj["headline"]["hh_outlays"]["prov"])
            for m in obj["methodology"].values():
                out |= set(m["prov"])
    return out


def serialise(files: dict[str, Any], *, fixture: bool, inputs: dict[str, str], code_hash: str) -> dict[str, bytes]:
    """{path relative to the data root: bytes}, including index.json and the version folder."""
    blobs = {rel: io.dumps_json(obj, indent=None).encode("utf-8") for rel, obj in sorted(files.items())}
    fmap = {rel: {"sha256": io.sha256_bytes(b), "bytes": len(b)} for rel, b in blobs.items()}
    if fixture:
        version = FIXTURE_VERSION
    else:
        version = f"{YEAR}." + io.sha256_bytes(io.dumps_json(fmap, indent=None).encode("utf-8"))[:10]
    index = {
        "schema_version": SCHEMA_VERSION,
        "data_version": version,
        "fixture": fixture,
        "reference_year": YEAR,
        "gdp_base_year": GDP_BASE,
        "inputs": dict(sorted(inputs.items())),
        "export_code_hash": code_hash,
        "files": fmap,
    }
    from pipeline.export.validate import validate_file

    errs = validate_file("index.json", index)
    if errs:
        raise ExportError("index.json breaks its JSON schema: " + "; ".join(errs[:5]))
    out = {f"{version}/{rel}": b for rel, b in blobs.items()}
    out["index.json"] = io.dumps_json(index, indent=None).encode("utf-8")
    return out


def write_tree(root: Path, blobs: dict[str, bytes]) -> str:
    """Write the version folder first, then index.json atomically, then delete other version folders."""
    root.mkdir(parents=True, exist_ok=True)
    version = next(k.split("/", 1)[0] for k in blobs if k != "index.json")
    vdir = root / version
    if vdir.exists():
        shutil.rmtree(vdir)
    for rel, b in sorted(blobs.items()):
        if rel != "index.json":
            io.atomic_write_bytes(root / rel, b)
            (root / rel).chmod(0o644)
    io.atomic_write_bytes(root / "index.json", blobs["index.json"])
    (root / "index.json").chmod(0o644)
    pattern = re.compile(r"^\d{4}-\d{2}\.([0-9a-f]{10}|fixture0000)$")
    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name != version and pattern.match(d.name):
            shutil.rmtree(d)
    return version


def compare_tree(root: Path, blobs: dict[str, bytes]) -> list[str]:
    diffs: list[str] = []
    version = next(k.split("/", 1)[0] for k in blobs if k != "index.json")
    for rel, b in sorted(blobs.items()):
        p = root / rel
        if not p.exists():
            diffs.append(f"missing: {rel}")
        elif p.read_bytes() != b:
            diffs.append(f"differs: {rel}")
    vdir = root / version
    if vdir.exists():
        for p in sorted(vdir.rglob("*")):
            rel = p.relative_to(root).as_posix()
            if p.is_file() and rel not in blobs:
                diffs.append(f"extra: {rel}")
    if root.exists():
        for d in sorted(root.iterdir()):
            if d.is_dir() and d.name != version and VERSION_DIR_RE.match(d.name):
                diffs.append(f"extra version folder: {d.name}")
    return diffs


def run_export(layout: Layout, *, fixture: bool) -> tuple[dict[str, bytes], list[str]]:
    if fixture:
        from pipeline.export.fixture import fixture_inputs

        inp = fixture_inputs()
    else:
        from pipeline.export.inputs import load_real

        inp = load_real(layout)
    files, warnings = build_payload(inp)
    inputs = dict(inp.input_hashes)
    blobs = serialise(files, fixture=fixture, inputs=inputs, code_hash=export_code_hash(layout.root))
    return blobs, warnings


def default_out(layout: Layout, fixture: bool) -> Path:
    return layout.root / "web" / ("fixtures/data" if fixture else "public/data")


def _log_warnings(layout: Layout, warnings: list[str]) -> None:
    if not warnings:
        return
    for w in warnings:
        print(f"warning: {w}")
    path = layout.root / ISSUES_FILE
    have = path.read_text(encoding="utf-8") if path.exists() else "# U1 issues (Data export)\n\n"
    block = "\n".join(f"- export warning: {w}" for w in warnings)
    if block not in have:
        io.write_text(path, have.rstrip("\n") + "\n\n" + block + "\n")


def cmd_export(layout: Layout, args: Any) -> int:
    fixture = bool(getattr(args, "fixture", False))
    out = Path(args.out).resolve() if getattr(args, "out", None) else default_out(layout, fixture)
    try:
        blobs, warnings = run_export(layout, fixture=fixture)
    except ExportError as e:
        print(f"EXPORT FAILED: {e}", file=sys.stderr)
        return 1
    if getattr(args, "check", False):
        with tempfile.TemporaryDirectory(prefix="export-check-") as tmp:
            write_tree(Path(tmp), blobs)
        diffs = compare_tree(out, blobs)
        if diffs:
            print(f"export --check: {out} differs from a fresh export:\n  " + "\n  ".join(diffs))
            return 1
        print(f"export --check: {out} matches a fresh export ({len(blobs)} files)")
        return 0
    with repo_lock(layout):
        version = write_tree(out, blobs)
    _log_warnings(layout, warnings)
    total = sum(len(b) for b in blobs.values())
    print(f"exported {len(blobs) - 1} files ({total:,} bytes) to {out}/{version} (fixture={fixture})")
    return 0
