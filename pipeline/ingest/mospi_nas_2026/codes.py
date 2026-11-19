"""Stable codes for NAS industries, institutional sectors and column variables.

Labels are normalised (numbering prefixes, '&', '*' and punctuation removed) and looked up in
fixed maps; an unknown label raises, so a new or renamed industry cannot slip in unmapped.
Industry codes are the NAS 2026 industry rows (Statement 7.1 / 1.6 aggregation), documented slugs.
"""

from __future__ import annotations

import re

INDUSTRY: dict[str, str] = {
    "agriculture livestock forestry and fishing": "agri",
    "crops": "crops",
    "livestock": "livestock",
    "forestry and logging": "forestry",
    "fishing and aquaculture": "fishing",
    "mining and quarrying": "mining",
    "manufacturing": "manufacturing",
    "food products beverages and tobacco": "mfg_food",
    "textiles apparel and leather products": "mfg_textiles",
    "metal products": "mfg_metal",
    "machinery and equipment": "mfg_machinery",
    "other manufactured goods": "mfg_other",
    "electricity gas water supply and other utility services": "utilities",
    "construction": "construction",
    "trade repair hotels and restaurants": "trade_hotels",
    "trade and repair services": "trade_repair",
    "hotels and restaurants": "hotels",
    "transport storage communication and services related to broadcasting": "transport_comm",
    "railways": "railways",
    "road transport": "road_transport",
    "water transport": "water_transport",
    "air transport": "air_transport",
    "services incidental to transport": "transport_services",
    "storage": "storage",
    "communication and services related to broadcasting": "communication",
    "financial services": "financial",
    "real estate ownership of dwelling and professional services": "real_estate_prof",
    "public administration and defence": "public_admin",
    "other services": "other_services",
    # totals as printed in the different statements
    "total": "total",
    "total gva at basic prices": "total",
    "total nva at basic prices": "total",
    "total cfc at basic prices": "total",
    "total gcf by industry of use": "total",
    "gva at basic prices": "total",
    # broad sectors (8.17.2, 8.18.x)
    "primary sector": "primary",
    "secondary sector": "secondary",
    "tertiary sector": "tertiary",
    "trade hotels transport communication and services related to broadcasting storage": "trade_transport_comm",
    "financial real estate it professional services and ownership of dwelling": "financial_real_estate_prof",
    "public administration defence and other services": "public_admin_other",
}

INSTITUTION: dict[str, str] = {
    "public non financial corporations": "nfc_public",
    "private non financial corporations": "nfc_private",
    "public financial corporations": "fc_public",
    "private financial corporations": "fc_private",
    "general government": "gg",
    "households including npish": "households_npish",
}

VARS: dict[str, dict[str, str]] = {
    "7.1": {
        "gross output": "output",
        "intermediate consumption": "ic",
        "gross value added": "gva",
        "production taxes less production subsidies": "net_production_taxes",
        "consumption of fixed capital": "cfc",
        "compensation of employee": "ce",
        "operating surplus": "os",
        "operating surplus mixed income": "os_mi",
    },
    "7.2": {"gfcf": "gfcf", "cis": "cis", "gcf": "gcf_excl_valuables", "cfc": "cfc"},
    "7.3": {
        "gfcf": "gfcf",
        "dwellings other buildings structures": "gfcf_dwellings_structures",
        "machinery and equipment": "gfcf_machinery_equipment",
        "cultivated biological resources": "gfcf_cultivated_biological",
        "ipp": "gfcf_ipp",
    },
    "7.4": {"nfcs": "net_fixed_capital_stock", "inventory": "inventories", "ncs": "net_capital_stock"},
    "8.16": {"dep": "book_depreciation", "cfc": "cfc"},
    "5.2": {
        "household individual consumption expenditure": "hh_ice",
        "general government individual consumption expenditure": "gg_ice",
        "actual individual consumption": "aic",
    },
    "8.18": {"q1": "q1", "q2": "q2", "q3": "q3", "q4": "q4"},
}

# 4.2 columns by position: COFOG division (and the sub-groups NAS prints), with the expected header.
COFOG_COLS: dict[str, tuple[str, str]] = {
    "C": ("01", "general public services"),
    "D": ("02", "defence"),
    "E": ("03", "public order and safety"),
    "F": ("04", "economic affairs"),
    "G": ("04.admin", "general administration regulation and research"),
    "H": ("04.agri", "agriculture forestry and fishing"),
    "I": ("04.mining_mfg_constr", "mining manufacturing and construction"),
    "J": ("04.energy", "electricity gas steam and other sources of energy"),
    "K": ("04.water_supply", "water supply"),
    "L": ("04.transport_comm", "transport and communication"),
    "M": ("04.other", "other economic services"),
    "N": ("05", "environment protection"),
    "O": ("06", "housing and community amenities"),
    "P": ("07", "health"),
    "Q": ("07.admin", "administration regulation and research"),
    "R": ("07.health_services", "health services"),
    "S": ("08", "recreation culture and religion"),
    "T": ("09", "education"),
    "U": ("09.admin", "administration regulation and research"),
    "V": ("09.educational_services", "educational services"),
    "W": ("10", "social protection"),
    "X": ("total", "total"),
}


def norm(label: str) -> str:
    s = label.lower()
    s = re.sub(r"^\d+(\.\d+)*\.?\s+", "", s)
    s = s.replace("&", " and ").replace("*", " ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def industry_code(label: str) -> str:
    k = norm(label)
    if k not in INDUSTRY:
        raise ValueError(f"unmapped NAS industry label {label!r} (normalised {k!r})")
    return INDUSTRY[k]


def is_industry(label: str) -> bool:
    return norm(label) in INDUSTRY


def institution_code(label: str) -> str:
    k = norm(label)
    if k not in INSTITUTION:
        raise ValueError(f"unmapped institutional sector label {label!r} (normalised {k!r})")
    return INSTITUTION[k]


def is_institution(label: str) -> bool:
    return norm(label) in INSTITUTION


def var_code(stmt: str, col: str, label: str) -> str:
    """Code of a column variable (two-level headers)."""
    k = norm(label)
    if stmt == "4.2":
        code, want = COFOG_COLS[col]
        if k != want:
            raise ValueError(f"4.2 column {col}: expected {want!r}, found {label!r}")
        return code
    fam = stmt if stmt in VARS else ("8.18" if stmt.startswith("8.18") else stmt[:3])
    if stmt.startswith("8.15"):
        fam = "7.1"
    table = VARS.get(fam)
    if table is None or k not in table:
        raise ValueError(f"{stmt}: unmapped column variable {label!r} (normalised {k!r})")
    return table[k]
