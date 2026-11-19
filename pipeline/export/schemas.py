"""JSON Schemas of the web data contract (docs/phase3/PLAN.md s.3.6). Owner: U1.

This module is the source of `pipeline/export/schema/*.schema.json` (draft-07). Regenerate with
`uv run python -m pipeline.export.schemas`; `tests/export/test_schemas.py` fails when the committed JSON
files are stale. U2's `npm run gen:contract` turns the JSON files into `web/src/data/contract.gen.ts`
(each schema's `title` is the exported TypeScript type name), and `web/tests/unit/contract/` validates
the fixture and the real export against them with ajv.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pipeline.core import io

SCHEMA_DIR = Path(__file__).resolve().parent / "schema"
DRAFT = "http://json-schema.org/draft-07/schema#"

LABELS = ["official", "derived", "estimated", "balancing_set"]
KINDS = ["production", "factors", "households", "corporations", "government", "row", "capital", "discrepancy"]
UNITS = ["inr", "pct_gdp", "per100", "pct"]
VERSION_RE = r"^\d{4}-\d{2}\.([0-9a-f]{10}|fixture0000)$"


def _num() -> dict[str, Any]:
    return {"type": "number"}


def _nnum() -> dict[str, Any]:
    return {"type": ["number", "null"]}


def _str() -> dict[str, Any]:
    return {"type": "string"}


def _nstr() -> dict[str, Any]:
    return {"type": ["string", "null"]}


def _int(minimum: int = 0) -> dict[str, Any]:
    return {"type": "integer", "minimum": minimum}


def _arr(items: dict[str, Any], **kw: Any) -> dict[str, Any]:
    return {"type": "array", "items": items, **kw}


def _obj(props: dict[str, Any], required: list[str] | None = None, **kw: Any) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": list(props) if required is None else required,
        "additionalProperties": False,
        **kw,
    }


def _rec(values: dict[str, Any], **kw: Any) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": values, **kw}


def _enum(values: list[Any]) -> dict[str, Any]:
    return {"enum": list(values)}


def _composition() -> dict[str, Any]:
    return _obj({k: {"type": "number", "minimum": 0, "maximum": 1} for k in ("o", "d", "e", "b")})


def _root(title: str, description: str, body: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {"$schema": DRAFT, "title": title, "description": description, **body, **extra}


def index_schema() -> dict[str, Any]:
    return _root(
        "DataIndex",
        "web/public/data/index.json (unversioned): which data version to load (PLAN s.3.1, s.3.6).",
        _obj(
            {
                "schema_version": {"const": 2},
                "data_version": {"type": "string", "pattern": VERSION_RE},
                "fixture": {"type": "boolean"},
                "reference_year": {"const": "2023-24"},
                "gdp_base_year": {"const": "2022-23"},
                "inputs": _rec(_str()),
                "export_code_hash": _str(),
                "files": _rec(_obj({"sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "bytes": _int()})),
            }
        ),
    )


def summary_schema() -> dict[str, Any]:
    part = _obj(
        {
            "key": _enum(
                [
                    "consumption",
                    "saving",
                    "taxes",
                    "financial_services_and_interest",
                    "transfers_abroad",
                    "to_government",
                    "unallocated_residual",
                ]
            ),
            "value": _num(),
            "per100": _num(),
            "split_label": _enum(LABELS),
            "total_label": {
                **_enum(["official", "derived", None]),
                "description": "Whether this part's sum is held to published figures (PLAN s.3.4.2), as for a "
                "link in sam/pinned.json; null = no published total.",
            },
            "pins": {
                **_arr(_str()),
                "description": "What holds the total (constraint ids or 'ts:<flow id>'); empty when total_label "
                "is null.",
            },
        }
    )
    return _root(
        "Summary",
        "<v>/summary.json: headline figures for the first screen and the methodology page (PLAN s.3.6, s.4.0).",
        _obj(
            {
                "gdp": _obj(
                    {"year": {"const": "2023-24"}, "value": _num(), "prov": _str(), "label": {"const": "official"}}
                ),
                "headline": _obj(
                    {
                        "hh_outlays": _obj(
                            {
                                "total": _num(),
                                "total_label": _enum(["official", "derived", None]),
                                "prov": _arr(_str()),
                                "parts": _arr(part),
                            }
                        ),
                        "gdp_note": _nstr(),
                    }
                ),
                "sam": _obj(
                    {
                        "accounts": {"const": 128},
                        "cells_nonzero": _int(),
                        "entries": _int(),
                        "refs": _int(),
                        "grand_total": _num(),
                        "composition": _composition(),
                        "labels": _obj({k: _obj({"entries": _int(), "abs": _num()}) for k in LABELS}),
                        "balancing": _obj(
                            {
                                "status": _str(),
                                "iterations": _int(),
                                "max_imbalance": _num(),
                                "moved_abs": _num(),
                                "moved_share_of_abs": _num(),
                            }
                        ),
                    }
                ),
                "methodology": _rec(
                    _obj(
                        {
                            "value": _num(),
                            "unit": _enum(["inr", "pct_gdp", "pct", "count"]),
                            "prov": _arr(_str()),
                            "split_label": {
                                **_enum(LABELS),
                                "description": "Economic values only (sums of SAM entries): the headline split label "
                                "of exactly the entries summed (PLAN s.3.4.2). Absent on counts and rule constants.",
                            },
                            "total_label": {
                                **_enum(["official", "derived", None]),
                                "description": "Economic values only: whether the sum is held to published figures, "
                                "by the exact-cover rule of sam/pinned.json; null = no published total.",
                            },
                            "pins": {
                                **_arr(_str()),
                                "description": "Economic values only: what holds the total; empty when total_label "
                                "is null.",
                            },
                        },
                        required=["value", "unit", "prov"],
                    )
                ),
                "ts": _obj(
                    {
                        "flows": {"const": 69},
                        "core": {"const": 54},
                        "memo": {"const": 15},
                        "first": {"const": "1950-51"},
                        "last": {"const": "2025-26"},
                        "rows": _int(),
                    }
                ),
            }
        ),
    )


def hierarchy_schema() -> dict[str, Any]:
    node = _obj(
        {
            "id": _str(),
            "level": _enum([0, 1, 2]),
            "parent": _nstr(),
            "children": _arr(_str()),
            "accounts": _arr(_str()),
            "order": _int(),
            "col": _int(),
            "kind": _enum(KINDS),
            "expandable": {"type": "boolean"},
        }
    )
    account = _obj({"code": _str(), "idx": _int(), "group": _str(), "l0": _str(), "l1": _nstr(), "name_tech": _str()})
    preset = _obj(
        {
            "merges": _rec(_arr(_str())),
            "columns": _arr(_arr(_str())),
            "split_node": _str(),
            "return_flows": _enum(["arcs", "stubs"]),
        }
    )
    ts_node = _obj({"id": _str(), "accounts": _arr(_str()), "order": _int(), "col": _int(), "kind": _enum(KINDS)})
    return _root(
        "Hierarchy",
        "<v>/hierarchy.json: zoom hierarchy, presets and top-flows nodes (PLAN s.3.2).",
        _obj(
            {
                "nodes": _arr(node, minItems=168, maxItems=168),
                "accounts": _arr(account, minItems=128, maxItems=128),
                "columns": _arr(_arr(_str())),
                "split_node": {"const": "PRDS"},
                "presets": _obj({"simple": preset, "full": preset}),
                "ts_nodes": _arr(ts_node),
            }
        ),
    )


def cells_schema() -> dict[str, Any]:
    return _root(
        "Cells",
        "<v>/sam/cells.json: every non-zero account cell (the atoms), columnar; row receives, col pays.",
        _obj(
            {
                "n": _int(),
                "row": _arr(_int()),
                "col": _arr(_int()),
                "v": _arr(_num()),
                "abs_o": _arr(_num()),
                "abs_d": _arr(_num()),
                "abs_e": _arr(_num()),
                "abs_b": _arr(_num()),
                "split": _arr(_enum([0, 1, 2, 3])),
                "flags": _arr(_int()),
                "n_entries": _arr(_int(1)),
                "refs": _arr(_arr(_str())),
            }
        ),
    )


def pinned_schema() -> dict[str, Any]:
    return _root(
        "Pinned",
        "<v>/sam/pinned.json: link ids (any zoom; positive part, '~neg' part, '~pair') whose total is held "
        "to published figures (PLAN s.3.4.2). A link not listed has no official total.",
        _rec(_obj({"total": _enum(["official", "derived"]), "pins": _arr(_str(), minItems=1)})),
    )


def entries_schema() -> dict[str, Any]:
    entry = _obj(
        {
            "row": _str(),
            "col": _str(),
            "ref": _str(),
            "component": _str(),
            "v": _num(),
            "prior": _num(),
            "change": _num(),
            "pct_change": {
                **_nnum(),
                "description": "Balancing move as a fraction of the prior: (v - prior) / |prior| (0.05 = 5%); "
                "null when the prior is zero.",
            },
            "status": _enum(["official", "derived", "estimated", "balanced"]),
            "prior_status": _enum(["official", "derived", "estimated"]),
            "role": _enum(["fixed", "anchored", "free"]),
            "label": _enum(LABELS),
            "confidence": _enum(["high", "medium", "low", None]),
            "bop_function": _nstr(),
            "prov": _str(),
            "flags": _arr(
                _enum(
                    [
                        "judgement_band",
                        "unexplained",
                        "level_unexplained",
                        "old_base_structure",
                        "discrepancy",
                        "has_negative",
                        "depends_on_assumption",
                    ]
                )
            ),
            "verdict": _enum(["explained", "level unexplained", "unexplained", None]),
            "why": _nstr(),
            "binding": _arr(_str()),
        }
    )
    return _root(
        "Entries",
        "<v>/sam/entries/<L0 id>.json: the entries whose row account is in that level-0 node (PLAN s.3.6).",
        _obj({"node": _str(), "entries": _arr(entry)}),
    )


def constraints_schema() -> dict[str, Any]:
    return _root(
        "Constraints",
        "<v>/sam/constraints.json: every balancing constraint, keyed by constraint id.",
        _rec(
            _obj(
                {
                    "kind": _enum(["band", "equal", "max", "min"]),
                    "ref": _str(),
                    "description": _str(),
                    "target": _num(),
                    "lo": _nnum(),
                    "hi": _nnum(),
                    "balanced_sum": _num(),
                    "binding": {"type": "boolean"},
                    "judgement": {"type": "boolean"},
                    "prov": _str(),
                }
            )
        ),
    )


def refs_schema() -> dict[str, Any]:
    return _root(
        "Refs",
        "<v>/sam/refs.json: the gap-map refs used by the entries (data/gap_map.csv).",
        _rec(
            _obj(
                {
                    "row_block": _str(),
                    "col_block": _str(),
                    "description": _str(),
                    "gap_status": _str(),
                    "primary_source": _str(),
                    "method": _str(),
                }
            )
        ),
    )


def provenance_schema() -> dict[str, Any]:
    cite = _obj(
        {
            "source": _str(),
            "tables": _arr(_str()),
            "urls": _arr(_nstr()),
            "withheld": {"type": "boolean"},
            "retrieved": _arr(_nstr(), minItems=2, maxItems=2),
        }
    )
    record = _obj(
        {
            "source": _str(),
            "status": _enum(["official", "derived", "estimated"]),
            "table": _str(),
            "locator": _nstr(),
            "method": _str(),
            "vintage": _nstr(),
            "base_year": _nstr(),
            "price_basis": _str(),
            "unit": _str(),
            "conversion": _nstr(),
            "assumption": {"type": "boolean"},
            "depends_on_assumption": {"type": "boolean"},
            "cites": _arr(cite),
        }
    )
    source = _obj(
        {
            "name": _str(),
            "publisher": _str(),
            "landing": _nstr(),
            "link_mode": _enum(["deep", "landing", "withheld"]),
            "licence": _str(),
            "attribution": _str(),
            "registry_status": _str(),
        }
    )
    return _root(
        "Provenance",
        "<v>/provenance.json: provenance records used by the export, with resolved citations (PLAN s.3.5).",
        _obj({"records": _rec(record), "sources": _rec(source)}),
    )


def series_schema() -> dict[str, Any]:
    arrays = _obj(
        {
            "v": _arr(_nnum()),
            "share": _arr(_nnum()),
            "base": _arr(_nstr()),
            "status": _arr(_enum(["official", "derived", None])),
            "stage": _arr(_nstr()),
            "flags": _arr(_nstr()),
            "segment": _arr(_nstr()),
            "prov": _arr(_nstr()),
        }
    )
    arrays["title"] = "SeriesArrays"
    ref = {"$ref": "#/definitions/SeriesArrays"}
    flow = _obj(
        {
            "id": _str(),
            "tier": _enum(["core", "memo"]),
            "group": _str(),
            "display_sign": _enum([1, -1]),
            "name_tech": _str(),
            "check": _obj(
                {
                    "class": _str(),
                    "verdict": _enum(["pass", "explained", "no_check"]),
                    "ts_value": _nnum(),
                    "sam_value": _nnum(),
                    "rel_diff": _nnum(),
                    "explanation": _nstr(),
                }
            ),
            "link_policy": _enum(["linked", "refused"]),
            "link_reason": _nstr(),
            "markers": _arr(
                _obj(
                    {
                        "period": _str(),
                        "kind": _enum(["base_change", "concept_break", "segment_join", "segment", "break"]),
                        "note": _str(),
                    }
                )
            ),
            "main": ref,
            "linked": {"oneOf": [ref, {"type": "null"}]},
            "alts": _arr(_obj({"variant": _enum(["fc16_definition", "proxy_total_portfolio"]), "arrays": ref})),
        }
    )
    return _root(
        "Series",
        "<v>/ts/series.json: the 69 top-flow series over 76 periods (PLAN s.3.7). Arrays align with `periods`.",
        _obj(
            {
                "periods": _arr(_str(), minItems=76, maxItems=76),
                "gdp": _obj(
                    {
                        "main": _arr(_nnum()),
                        "main_base": _arr(_nstr()),
                        "linked": _arr(_nnum()),
                        "prov": _arr(_nstr()),
                    }
                ),
                "flows": _arr(flow),
            }
        ),
        definitions={"SeriesArrays": arrays},
    )


def ts_view_schema() -> dict[str, Any]:
    return _root(
        "TsView",
        "<v>/ts/view.json: the top-flows board: ribbons, internal flows and slot sizes (PLAN s.3.7.3).",
        _obj(
            {
                "coverage": _arr(_int()),
                "ribbons": _arr(
                    _obj(
                        {
                            "flow": _str(),
                            "from": _str(),
                            "to": _str(),
                            "reversible": {"type": "boolean"},
                            "reversed_text_key": _nstr(),
                        }
                    )
                ),
                "internal": _rec(_arr(_str())),
                "slot_share": _rec(_num()),
            }
        ),
    )


def cover_schema() -> dict[str, Any]:
    return _root(
        "Cover",
        "<v>/ts/cover.json: the SAM cells each series measures in 2023-24, [row idx, col idx, signed value].",
        _rec(
            _obj(
                {
                    "cells": _arr(_arr({"type": "number"}, minItems=3, maxItems=3)),
                    "abs_total": _num(),
                }
            )
        ),
    )


def story_schema() -> dict[str, Any]:
    figure = _obj(
        {
            "value": _num(),
            "unit": _enum(UNITS),
            "total": _enum(["official", "derived", None]),
            "split": _enum(LABELS),
            "composition": _composition(),
            "flags": _arr(_str()),
            "prov": _arr(_str()),
            "method": _str(),
            "note_key": _nstr(),
        }
    )
    step = _obj(
        {
            "id": _str(),
            "view": _obj(
                {
                    "view": _enum(["sam", "ts"]),
                    "preset": _enum(["simple", "full"]),
                    "year": _str(),
                    "expanded": _arr(_str()),
                    "highlight": _arr(_str()),
                    "select": _nstr(),
                }
            ),
            "figures": _arr(_str()),
        }
    )
    return _root(
        "Story",
        "<v>/stories/<slug>.json: a story's figures, computed by the exporter from its YAML spec (PLAN s.3.8).",
        _obj({"slug": _str(), "figures": _rec(figure), "steps": _arr(step)}),
    )


SCHEMAS = {
    "index": index_schema,
    "summary": summary_schema,
    "hierarchy": hierarchy_schema,
    "cells": cells_schema,
    "pinned": pinned_schema,
    "entries": entries_schema,
    "constraints": constraints_schema,
    "refs": refs_schema,
    "provenance": provenance_schema,
    "series": series_schema,
    "ts_view": ts_view_schema,
    "cover": cover_schema,
    "story": story_schema,
}

# Which schema validates which exported file (paths relative to the data version folder; index.json is
# the unversioned top file). Patterns use fnmatch.
FILE_SCHEMAS = {
    "summary.json": "summary",
    "hierarchy.json": "hierarchy",
    "sam/cells.json": "cells",
    "sam/pinned.json": "pinned",
    "sam/entries/*.json": "entries",
    "sam/constraints.json": "constraints",
    "sam/refs.json": "refs",
    "provenance.json": "provenance",
    "ts/series.json": "series",
    "ts/view.json": "ts_view",
    "ts/cover.json": "cover",
    "stories/*.json": "story",
}


def rendered() -> dict[str, str]:
    return {f"{name}.schema.json": io.dumps_json(fn(), indent=2) for name, fn in SCHEMAS.items()}


def write(check: bool = False) -> int:
    stale = []
    for fname, text in rendered().items():
        path = SCHEMA_DIR / fname
        have = path.read_text(encoding="utf-8") if path.exists() else None
        if have != text:
            stale.append(fname)
            if not check:
                io.write_text(path, text)
    if check and stale:
        print("stale schema files (run `uv run python -m pipeline.export.schemas`): " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(write(check="--check" in sys.argv[1:]))
