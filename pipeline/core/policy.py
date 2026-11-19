"""The access policy (DECISIONS.md D1-1, D1-2) enforced in code, not only in the docs.

- D1-1c: GSTN and CBDT are not automated at all. Their figures come from the Union Finance
  Accounts, Budget documents and PIB releases instead.
- D1-2: no unit-level microdata (microdata.gov.in needs registration).
- D1-1b: sites whose terms forbid reuse are not automated. docs/phase1/ACCESS_PLAN.md s.5 classes the
  NSDL FPI Monitor and AMFI as blocked-terms; they are refused here by id and host, whatever the
  registry's `access.requires` says (finsector_markets framework request 1).
- D1-1a/b: public files only. A source whose registry `access.requires` is not `none`
  (registration, login, api_key, paid, manual_download) cannot be fetched, except for the public
  parts listed in PUBLIC_PARTS below.

Checked in three places: `check_contract` (a unit may not list a refused source in SOURCES), `fetch_file`
(the source and the first URL) and every redirect hop in `http_request` (the host denylist and
login pages). Changing this file is an orchestrator decision: agents file a "Framework request".
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

# Source ids that are never automated, whatever the registry says about access.
DENIED_SOURCE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("gstn_*", "GSTN is not automated (DECISIONS D1-1c): use Finance Accounts, Budget documents or PIB releases"),
    ("cbdt_*", "CBDT is not automated (DECISIONS D1-1c): use Finance Accounts, Budget documents or PIB releases"),
    ("*_unit_data", "no unit-level microdata (DECISIONS D1-2): use the published report tables"),
    ("*microdata*", "no unit-level microdata (DECISIONS D1-2): use the published report tables"),
    (
        "nsdl_fpi_monitor",
        "NSDL terms prohibit reproduction and redistribution (DECISIONS D1-1b; ACCESS_PLAN s.5 blocked-terms): use "
        "SEBI Handbook, RBI HBS and FSF tables",
    ),
    (
        "amfi_monthly_quarterly",
        "AMFI terms allow personal non-commercial use only (DECISIONS D1-1b; ACCESS_PLAN s.5 blocked-terms): use NAS "
        "and SEBI Handbook tables",
    ),
)

# Hosts (and all their subdomains) that are never contacted.
DENIED_HOSTS: dict[str, str] = {
    "gst.gov.in": "GSTN (DECISIONS D1-1c)",
    "incometax.gov.in": "CBDT e-filing portal (DECISIONS D1-1c)",
    "incometaxindia.gov.in": "CBDT (DECISIONS D1-1c)",
    "microdata.gov.in": "unit-level microdata portal (DECISIONS D1-2)",
    "fpi.nsdl.co.in": "NSDL FPI Monitor, terms prohibit reproduction (DECISIONS D1-1b; ACCESS_PLAN s.5)",
    "amfiindia.com": "AMFI, terms allow personal non-commercial use only (DECISIONS D1-1b; ACCESS_PLAN s.5)",
}

# Sources whose registry `access.requires` is not 'none' but which have a public part that the
# registry itself documents. Only URLs starting with one of the prefixes may be fetched.
PUBLIC_PARTS: dict[str, tuple[tuple[str, ...], str]] = {
    "mospi_asi": (
        ("https://api.mospi.gov.in/api/asi/", "https://www.mospi.gov.in/uploads/", "https://mospi.gov.in/uploads/"),
        "registry access.notes: 'Registration needed only for unit-level data; aggregates need none.'",
    ),
    "cag_state_finance_accounts": (
        ("https://cag.gov.in/",),
        "registry access.notes: 'Public PDFs need no login.' (the SharePoint data behind login is not used)",
    ),
    "un_comtrade": (
        ("https://comtradeapi.un.org/public/",),
        "registry access.method: keyless preview API (the keyed /data/ API is not used)",
    ),
}

# A redirect to (or a final URL on) a sign-in page means the file is behind a login (D1-1b).
# Matched against whole path segments (without extension) and host name prefixes.
LOGIN_SEGMENTS = frozenset(
    {
        "login",
        "log-in",
        "logon",
        "signin",
        "sign-in",
        "sign_in",
        "sso",
        "oauth",
        "oauth2",
        "auth",
        "register",
        "registration",
        "signup",
        "sign-up",
        "saml",
        "cas",
    }
)
LOGIN_HOST_PREFIXES = ("login.", "signin.", "sso.", "auth.", "accounts.", "idp.")
PASSWORD_INPUT_RE = re.compile(rb"<input[^>]+type\s*=\s*[\"']?password", re.I)


class PolicyViolation(Exception):
    """A request or source outside DECISIONS.md D1-1/D1-2. Never work around it."""


def denied_host(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    for d, why in DENIED_HOSTS.items():
        if host == d or host.endswith("." + d):
            return f"host {host} is not contacted: {why}"
    return None


def login_url(url: str) -> bool:
    """True if the URL is a sign-in/registration page ('/login.aspx', '/sso/...', 'login.example.com')."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host.startswith(LOGIN_HOST_PREFIXES):
        return True
    segs = [seg.lower().split(".", 1)[0] for seg in (parts.path or "").split("/") if seg]
    return any(seg in LOGIN_SEGMENTS for seg in segs)


def source_refusal(source_id: str, entry: Mapping[str, Any]) -> str | None:
    """Why this source may not be used by an ingest unit at all, or None if it may."""
    for pat, why in DENIED_SOURCE_PATTERNS:
        if fnmatch.fnmatchcase(source_id, pat):
            return f"source {source_id!r} is refused: {why}"
    urls = entry.get("urls") or {}
    landing = urls.get("landing") if isinstance(urls, Mapping) else None
    if isinstance(landing, str) and denied_host(landing):
        return f"source {source_id!r} is refused: its landing page is on a denied host ({denied_host(landing)})"
    requires = str((entry.get("access") or {}).get("requires", "none")).strip()
    if requires != "none" and source_id not in PUBLIC_PARTS:
        return (
            f"source {source_id!r} is refused: the registry says access.requires = {requires!r}, and only public "
            "files are fetched (DECISIONS D1-1a, D1-2). If part of it is public, file a Framework request to add it "
            "to PUBLIC_PARTS in pipeline/core/policy.py; otherwise use a substitute source and log the gap."
        )
    return None


def url_refusal(source_id: str, entry: Mapping[str, Any], url: str) -> str | None:
    """Why this URL may not be fetched for this source, or None if it may."""
    why = source_refusal(source_id, entry)
    if why:
        return why
    why = denied_host(url)
    if why:
        return why
    if login_url(url):
        return f"{url} looks like a sign-in or registration page (DECISIONS D1-1b: no logins)"
    if source_id in PUBLIC_PARTS:
        prefixes, reason = PUBLIC_PARTS[source_id]
        if not url.startswith(prefixes):
            return (
                f"{source_id!r} is fetched only under its public prefixes {list(prefixes)} ({reason}); {url} is not "
                "one of them"
            )
    return None
