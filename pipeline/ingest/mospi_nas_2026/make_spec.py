"""Regenerate the frozen row specs from the pinned statement files (a maintainer tool, not run by
the build): `uv run python -m pipeline.ingest.mospi_nas_2026.make_spec`.

Run it only after a reviewed revision of the source files; then re-read the diff of
spec_*.json (labels, header/data roles, blank-cell masks, codes) and the unit tests. The build
itself never regenerates a spec: it only checks the files against it.
"""

from __future__ import annotations

import json

from pipeline.core.fetch import pinned_raw
from pipeline.core.paths import Layout
from pipeline.ingest.mospi_nas_2026 import grid, oldbase, stmts2026


def _write(name: str, spec: dict) -> None:
    text = json.dumps(spec, indent=1, ensure_ascii=False) + "\n"
    (grid.SPEC_DIR / name).write_bytes(text.encode("utf-8"))  # LF endings on every OS


def main() -> None:
    layout = Layout.default()
    spec: dict[str, list[list[str]]] = {}
    for cfg in stmts2026.CFGS:
        raw = pinned_raw(layout, stmts2026.UNIT, stmts2026.SRC, f"{cfg.stmt}.xlsx")
        spec[cfg.spec_key] = stmts2026.spec_rows(stmts2026.parse(raw, cfg))
    _write(stmts2026.SPEC_FILE, spec)
    old: dict[str, list[list[str]]] = {}
    for cfg in oldbase.CFGS:
        raw = pinned_raw(layout, oldbase.UNIT, oldbase.SRC, cfg.file)
        old[cfg.key] = oldbase.spec_rows(oldbase.parse(raw, cfg))
    _write(oldbase.SPEC_FILE, old)
    print(f"wrote {len(spec)} new-base and {len(old)} old-base statement specs")


if __name__ == "__main__":
    main()
