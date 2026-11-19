"""A small JSON Schema (draft-07 subset) validator for the export's own schemas.

The browser side validates with ajv (web/tests/unit/contract/). This mirror lets the exporter refuse to write
files that break the contract, and lets pytest check the fixture and the real export without extra packages.
Supported keywords: type, properties, required, additionalProperties, items, enum, const, minItems, maxItems,
pattern, minimum, maximum, oneOf, $ref (local #/definitions/...).
"""

from __future__ import annotations

import fnmatch
import re
from typing import Any

from pipeline.export.schemas import FILE_SCHEMAS, SCHEMAS

_TYPES = {
    "object": lambda x: isinstance(x, dict),
    "array": lambda x: isinstance(x, list),
    "string": lambda x: isinstance(x, str),
    "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
    "integer": lambda x: (isinstance(x, int) and not isinstance(x, bool)) or (isinstance(x, float) and x.is_integer()),
    "boolean": lambda x: isinstance(x, bool),
    "null": lambda x: x is None,
}


def validate(obj: Any, schema: dict[str, Any], root: dict[str, Any] | None = None, path: str = "$") -> list[str]:
    root = root or schema
    errs: list[str] = []
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return validate(obj, root["definitions"][name], root, path)
    if "oneOf" in schema:
        ok = [s for s in schema["oneOf"] if not validate(obj, s, root, path)]
        if len(ok) != 1:
            errs.append(f"{path}: matches {len(ok)} of oneOf")
        return errs
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES[x](obj) for x in types):
            return [f"{path}: expected {types}, got {type(obj).__name__}"]
    if "const" in schema and obj != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}, got {obj!r}")
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} not in {schema['enum']}")
    if isinstance(obj, str) and "pattern" in schema and not re.search(schema["pattern"], obj):
        errs.append(f"{path}: {obj!r} does not match {schema['pattern']}")
    if _TYPES["number"](obj):
        if "minimum" in schema and obj < schema["minimum"]:
            errs.append(f"{path}: {obj} < minimum {schema['minimum']}")
        if "maximum" in schema and obj > schema["maximum"]:
            errs.append(f"{path}: {obj} > maximum {schema['maximum']}")
    if isinstance(obj, list):
        if "minItems" in schema and len(obj) < schema["minItems"]:
            errs.append(f"{path}: {len(obj)} items < {schema['minItems']}")
        if "maxItems" in schema and len(obj) > schema["maxItems"]:
            errs.append(f"{path}: {len(obj)} items > {schema['maxItems']}")
        if "items" in schema:
            for i, x in enumerate(obj):
                errs.extend(validate(x, schema["items"], root, f"{path}[{i}]"))
                if len(errs) > 20:
                    return errs
    if isinstance(obj, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in obj:
                errs.append(f"{path}: missing required {k!r}")
        addl = schema.get("additionalProperties", True)
        for k, v in obj.items():
            if k in props:
                errs.extend(validate(v, props[k], root, f"{path}.{k}"))
            elif addl is False:
                errs.append(f"{path}: unexpected key {k!r}")
            elif isinstance(addl, dict):
                errs.extend(validate(v, addl, root, f"{path}.{k}"))
            if len(errs) > 20:
                return errs
    return errs


def schema_for(rel_path: str) -> str:
    """Schema name for a file path relative to the data version folder ('index.json' for the index)."""
    if rel_path == "index.json":
        return "index"
    for pat, name in FILE_SCHEMAS.items():
        if fnmatch.fnmatch(rel_path, pat):
            return name
    raise KeyError(f"no schema for exported file {rel_path!r}")


def validate_file(rel_path: str, obj: Any) -> list[str]:
    return validate(obj, SCHEMAS[schema_for(rel_path)]())
