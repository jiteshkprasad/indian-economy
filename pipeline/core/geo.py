"""The project-wide code set for India's States and Union Territories (DECISIONS.md D1-9).

Every unit writes the `geography` of a State/UT row with a code from this module, and the schema
rejects any other 'IN-..' code (pipeline/core/schema.py), so two units can never disagree.

Current codes: ISO 3166-2:IN as it stands after the ISO change of 23 November 2023 (IN-CT -> IN-CG
Chhattisgarh, IN-OR -> IN-OD Odisha, IN-TG -> IN-TS Telangana, IN-UT -> IN-UK Uttarakhand), with
Ladakh (IN-LA) and the merged UT of Dadra and Nagar Haveli and Daman and Diu (IN-DH). 28 States +
8 Union Territories = 36 codes. Verified live on 2026-09-29 against two independent copies of the
ISO list (the ISO Online Browsing Platform itself answers 403 to non-browser clients):
  - Wikipedia "ISO 3166-2:IN" (current-codes table and change log; page last edited 2026-09-21):
    https://en.wikipedia.org/wiki/ISO_3166-2:IN
  - Debian iso-codes, data/iso_3166-2.json (maintained from ISO; last file update 2025-10-13,
    sha256 78c90ef7fc25b5c2631aac5f089bc9ff6ec22c025c05b6ddbc087a1f1be2e46a):
    https://salsa.debian.org/iso-codes-team/iso-codes/-/raw/main/data/iso_3166-2.json
Both list exactly the 36 codes below.

Historical entities (a territory that no longer exists with the same boundary) get project codes
'IN-X..'. They are NOT ISO codes (no ISO subdivision code has three letters, so they cannot
collide). Use them for rows whose period predates a reorganisation, e.g. undivided Andhra Pradesh
before 2 June 2014 is IN-XAP, not IN-AP.

Superseded ISO codes (IN-CT, IN-OR, IN-TG, IN-UT, IN-DD, IN-DN, ...) are refused with a hint.
"""

from __future__ import annotations

import re
import unicodedata

ISO_SOURCE = (
    "ISO 3166-2:IN after the ISO change of 2023-11-23, verified 2026-09-29 against "
    "https://en.wikipedia.org/wiki/ISO_3166-2:IN and Debian iso-codes data/iso_3166-2.json"
)

# code -> (English short name, 'state' | 'ut')
STATES_UTS: dict[str, tuple[str, str]] = {
    "IN-AN": ("Andaman and Nicobar Islands", "ut"),
    "IN-AP": ("Andhra Pradesh", "state"),
    "IN-AR": ("Arunachal Pradesh", "state"),
    "IN-AS": ("Assam", "state"),
    "IN-BR": ("Bihar", "state"),
    "IN-CG": ("Chhattisgarh", "state"),
    "IN-CH": ("Chandigarh", "ut"),
    "IN-DH": ("Dadra and Nagar Haveli and Daman and Diu", "ut"),
    "IN-DL": ("Delhi", "ut"),
    "IN-GA": ("Goa", "state"),
    "IN-GJ": ("Gujarat", "state"),
    "IN-HP": ("Himachal Pradesh", "state"),
    "IN-HR": ("Haryana", "state"),
    "IN-JH": ("Jharkhand", "state"),
    "IN-JK": ("Jammu and Kashmir", "ut"),
    "IN-KA": ("Karnataka", "state"),
    "IN-KL": ("Kerala", "state"),
    "IN-LA": ("Ladakh", "ut"),
    "IN-LD": ("Lakshadweep", "ut"),
    "IN-MH": ("Maharashtra", "state"),
    "IN-ML": ("Meghalaya", "state"),
    "IN-MN": ("Manipur", "state"),
    "IN-MP": ("Madhya Pradesh", "state"),
    "IN-MZ": ("Mizoram", "state"),
    "IN-NL": ("Nagaland", "state"),
    "IN-OD": ("Odisha", "state"),
    "IN-PB": ("Punjab", "state"),
    "IN-PY": ("Puducherry", "ut"),
    "IN-RJ": ("Rajasthan", "state"),
    "IN-SK": ("Sikkim", "state"),
    "IN-TN": ("Tamil Nadu", "state"),
    "IN-TR": ("Tripura", "state"),
    "IN-TS": ("Telangana", "state"),
    "IN-UK": ("Uttarakhand", "state"),
    "IN-UP": ("Uttar Pradesh", "state"),
    "IN-WB": ("West Bengal", "state"),
}

# Project codes for territories that no longer exist with the same boundary (not ISO codes).
# code -> (name, last day it existed, what replaced it)
HISTORICAL: dict[str, tuple[str, str, str]] = {
    "IN-XAP": ("Andhra Pradesh (undivided, incl. Telangana)", "2014-06-01", "IN-AP + IN-TS from 2014-06-02"),
    "IN-XJK": ("Jammu and Kashmir (State, incl. Ladakh)", "2019-10-30", "IN-JK + IN-LA (UTs) from 2019-10-31"),
    "IN-XDN": ("Dadra and Nagar Haveli (UT)", "2020-01-25", "IN-DH from 2020-01-26"),
    "IN-XDD": ("Daman and Diu (UT)", "2020-01-25", "IN-DH from 2020-01-26"),
    "IN-XMP": ("Madhya Pradesh (undivided, incl. Chhattisgarh)", "2000-10-31", "IN-MP + IN-CG from 2000-11-01"),
    "IN-XUP": ("Uttar Pradesh (undivided, incl. Uttarakhand)", "2000-11-08", "IN-UP + IN-UK from 2000-11-09"),
    "IN-XBR": ("Bihar (undivided, incl. Jharkhand)", "2000-11-14", "IN-BR + IN-JH from 2000-11-15"),
}

# ISO codes that ISO has withdrawn or replaced -> what to use instead.
SUPERSEDED: dict[str, str] = {
    "IN-CT": "IN-CG (Chhattisgarh; ISO change of 2023-11-23)",
    "IN-OR": "IN-OD (Odisha; ISO change of 2023-11-23)",
    "IN-TG": "IN-TS (Telangana; ISO change of 2023-11-23)",
    "IN-UT": "IN-UK (Uttarakhand; ISO change of 2023-11-23)",
    "IN-UL": "IN-UK (Uttaranchal, renamed Uttarakhand)",
    "IN-DD": "IN-DH for the merged UT, or IN-XDD for Daman and Diu before 2020-01-26",
    "IN-DN": "IN-DH for the merged UT, or IN-XDN for Dadra and Nagar Haveli before 2020-01-26",
}

ALL_CODES: frozenset[str] = frozenset(STATES_UTS) | frozenset(HISTORICAL)

# Normalised name -> code. Names are normalised by `_norm` (ASCII, lower case, '&' -> 'and',
# punctuation dropped, 'the'/'nct of'/'state of'/'ut of' removed).
_ALIASES: dict[str, str] = {
    "orissa": "IN-OD",
    "uttaranchal": "IN-UK",
    "uttrakhand": "IN-UK",
    "pondicherry": "IN-PY",
    "tamilnadu": "IN-TN",
    "chattisgarh": "IN-CG",
    "chhatisgarh": "IN-CG",
    "chhattishgarh": "IN-CG",
    "telengana": "IN-TS",
    "delhi ut": "IN-DL",
    "national capital territory of delhi": "IN-DL",
    "andaman and nicobar": "IN-AN",
    "andaman nicobar islands": "IN-AN",
    "a and n islands": "IN-AN",
    "jammu kashmir": "IN-JK",
    "dadra and nagar haveli and daman and diu": "IN-DH",
    "dadra nagar haveli and daman diu": "IN-DH",
    "dnh and dd": "IN-DH",
    "arunachal": "IN-AR",
    "himachal": "IN-HP",
}


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"^\s*\d+[.)]?\s+", "", s)  # '1. Andhra Pradesh'
    s = re.sub(r"[^a-z ]+", " ", s)
    s = re.sub(r"\b(the|nct of|state of|ut of|govt of|government of)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_BY_NAME: dict[str, str] = {_norm(n): c for c, (n, _) in STATES_UTS.items()} | {
    _norm(k): v for k, v in _ALIASES.items()
}


def state_code(name: str) -> str:
    """The code of a current State/UT from its printed name ('ODISHA', 'Orissa', 'NCT of Delhi',
    'Jammu & Kashmir', '12. Tamil Nadu'). Raises KeyError for anything unknown, including
    historical entities (map those explicitly to an IN-X.. code: only the unit knows the period)."""
    key = _norm(name)
    if key in _BY_NAME:
        return _BY_NAME[key]
    raise KeyError(f"unknown State/UT name {name!r} (normalised {key!r}); see pipeline/core/geo.py")


def state_name(code: str) -> str:
    """English short name of a current or historical code."""
    if code in STATES_UTS:
        return STATES_UTS[code][0]
    if code in HISTORICAL:
        return HISTORICAL[code][0]
    raise KeyError(f"unknown State/UT code {code!r}")


def geography_problem(code: str) -> str | None:
    """Why an 'IN-..' geography code is not in the project code set, or None if it is. 'IN' (all
    India) and non-Indian codes (partners' ISO 3166-1 alpha-3) are not this module's business."""
    if code == "IN" or not code.startswith("IN-"):
        return None
    if code in ALL_CODES:
        return None
    if code in SUPERSEDED:
        return f"{code} is a superseded ISO code: use {SUPERSEDED[code]}"
    return f"{code} is not a current ISO 3166-2:IN code nor a project historical code (pipeline/core/geo.py)"
