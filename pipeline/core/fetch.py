"""The ONLY way pipeline code downloads anything (DECISIONS.md D1-1).

Policy implemented here:
- Public files only: no logins, no API keys, no cookies from anyone's browser, no JavaScript or
  CAPTCHA solving. A normal browser-like header set is sent (D1-1a); a unit may add only the
  headers in UNIT_HEADERS. Sources and hosts outside D1-1c/D1-2 are refused (pipeline/core/policy.py).
- At least 2 s between requests to the same host, across all processes on this machine (an OS
  lock per host in paths.host_lock_dir(), independent of the data layout). Redirects are followed
  by hand, one hop at a time, each through the same host lock and policy checks.
- Retries with exponential backoff on timeouts, connection errors, 429 and 5xx. A challenge page
  (any status), a login page, or an HTML page where a file was expected raises `AccessBlocked`
  at once, as does a Retry-After longer than MAX_RETRY_AFTER_S. Nothing is saved. Log it in
  docs/phase1/issues/<unit>.md and stop (D1-1b).
- Every file is saved once as data/raw/<source_id>/<YYYY-MM-DD>/<unit>/<name> with
  <name>.meta.json. Existing files are never overwritten: another version on the same day goes
  to <YYYY-MM-DD>-r2/, -r3/, ...
- Each unit pins its raw files in data/raw_pins/<unit>.yaml (key '<source_id>/<name>' -> url,
  sha256, path). Builds read exactly the pinned bytes. Changed upstream bytes are accepted only
  with --refresh: a new file and a new pin, the old pin moved to `history`, and a warning.
- Offline mode never touches the network and fails loudly when a pinned file is missing.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import json
import re
import ssl
import sys
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from pipeline.core import io
from pipeline.core.locks import file_lock
from pipeline.core.paths import Layout, host_lock_dir
from pipeline.core.policy import PASSWORD_INPUT_RE, denied_host, login_url, url_refusal
from pipeline.core.registry import get_source

MIN_HOST_INTERVAL_S = 2.0
# Hosts that need a longer gap than MIN_HOST_INTERVAL_S (host name -> seconds). The wait is
# enforced through the same machine-wide host lock, so it holds across units and processes.
HOST_MIN_INTERVAL_S: dict[str, float] = {
    "rbidocs.rbi.org.in": 10.0,  # DECISIONS D1-4 (F5 challenge after ~18 fetches on 29 Sep 2026)
}
# Hosts whose TLS server needs legacy (unsafe) renegotiation, which OpenSSL 3 refuses by default
# (UNSAFE_LEGACY_RENEGOTIATION_DISABLED). Only these hosts get ssl.OP_LEGACY_SERVER_CONNECT;
# certificate and host-name verification stay on. DECISIONS D1-6: a TLS-compatibility setting
# for a public keyless API, not an access control.
LEGACY_RENEGOTIATION_HOSTS: frozenset[str] = frozenset({"api.mospi.gov.in"})
MAX_ATTEMPTS = 4
BACKOFF_BASE_S = 2.0
CONNECT_TIMEOUT_S = 20.0
READ_TIMEOUT_S = 120.0
MAX_RETRY_AFTER_S = 120.0  # a server asking for a longer wait is obeyed by stopping, never by retrying early
MAX_REDIRECTS = 5
HOST_LOCK_TIMEOUT_S = 1800.0  # a live holder may be downloading a large file

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
)
# A document navigation, as a browser sends when you click a download link.
NAVIGATE_HEADERS: dict[str, str] = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}
# An XHR/fetch() call from a public web page to its own public JSON API.
API_HEADERS: dict[str, str] = {
    "User-Agent": BROWSER_UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en-GB;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}
# The only headers a unit may add or override. Everything else (cookies, tokens, keys, auth) is
# outside the access policy. Referer is set with the `referer` argument.
UNIT_HEADERS = frozenset({"accept", "accept-language", "range", "x-requested-with"})
_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]+$")

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,150}$")

# ---------------------------------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------------------------------


class FetchError(RuntimeError):
    """A download failed. Log it; do not work around it."""


class AccessBlocked(FetchError):
    """The server refused us, served a bot challenge / login / HTML page instead of the file, or
    the access policy refuses the source or host (D1-1b/c, D1-2)."""


class ChallengeServed(AccessBlocked):
    """The host served a bot challenge or WAF block page (F5/TSPD, Cloudflare, Imperva, CAPTCHA).
    `host` is the rate-limit key of the host that served it. FetchContext then refuses every later
    request to that host in the same run without contacting it (DECISIONS D1-1b, D1-4)."""

    def __init__(self, message: str, host: str) -> None:
        super().__init__(message)
        self.host = host


class OfflineMissing(FetchError):
    """Offline mode (every build) needs a pinned raw file that is not on disk."""


class PinMismatch(FetchError):
    """A raw file on disk does not have the pinned sha256 (edited by hand or corrupted)."""


# ---------------------------------------------------------------------------------------------
# raw files and pins
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RawFile:
    """A pinned, hash-verified raw file."""

    source_id: str
    name: str
    url: str
    sha256: str
    path: Path  # absolute path on this machine
    rel_path: str  # 'data/raw/<source_id>/<date>/<unit>/<name>' (portable)
    retrieved_at: str  # ISO UTC 'YYYY-MM-DDTHH:MM:SSZ'
    method: str = "GET"

    @property
    def key(self) -> str:
        return f"{self.source_id}/{self.name}"

    def read_bytes(self) -> bytes:
        return self.path.read_bytes()

    def read_json(self) -> Any:
        return json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def meta(self) -> dict[str, Any]:
        p = meta_path(self.path)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def meta_path(path: Path) -> Path:
    return path.with_name(path.name + ".meta.json")


PIN_SAVE_ATTEMPTS = 6
PIN_SAVE_BACKOFF_S = 0.5

PIN_HEADER = (
    "# Pinned raw files for one ingest unit. Written by `python -m pipeline fetch`; do not edit by hand.\n"
    "# key '<source_id>/<name>' -> the exact bytes (sha256) every build uses. `history` keeps superseded pins."
)


@dataclass
class PinStore:
    """data/raw_pins/<unit>.yaml."""

    unit: str
    path: Path
    pins: dict[str, dict[str, Any]] = field(default_factory=dict)
    changed: bool = False

    @classmethod
    def load(cls, layout: Layout, unit: str) -> PinStore:
        path = layout.pins / f"{unit}.yaml"
        pins: dict[str, dict[str, Any]] = {}
        if path.exists():
            doc = io.read_yaml(path) or {}
            if doc.get("unit") != unit:
                raise FetchError(f"{path}: 'unit' is {doc.get('unit')!r}, expected {unit!r}")
            pins = doc.get("pins") or {}
        return cls(unit=unit, path=path, pins=pins)

    def save(self) -> None:
        """Write the pin file. On Windows a reader holding the YAML open makes the final rename fail
        with PermissionError; retry for a few seconds before giving up (trade_satellites-14)."""
        if not self.changed:
            return
        for attempt in range(1, PIN_SAVE_ATTEMPTS + 1):
            try:
                io.write_yaml(self.path, {"unit": self.unit, "pins": self.pins}, header=PIN_HEADER)
                break
            except PermissionError:
                if attempt == PIN_SAVE_ATTEMPTS:
                    raise
                time.sleep(PIN_SAVE_BACKOFF_S * attempt)
        self.changed = False

    def set(self, key: str, pin: dict[str, Any]) -> None:
        old = self.pins.get(key)
        if old is not None and old.get("sha256") != pin["sha256"]:
            hist = list(old.get("history") or [])
            hist.append(
                {k: old[k] for k in ("sha256", "path", "retrieved_at", "url") if k in old}
                | {"superseded_at": pin["retrieved_at"]}
            )
            pin = pin | {"history": hist}
        elif old is not None and old.get("history"):
            pin = pin | {"history": old["history"]}
        self.pins[key] = pin
        self.changed = True

    def paths_in_use(self) -> dict[str, str]:
        """{rel_path: sha256} for every current and superseded pin (a path never gets new bytes)."""
        out: dict[str, str] = {}
        for pin in self.pins.values():
            out[pin["path"]] = pin["sha256"]
            for h in pin.get("history") or []:
                if "path" in h:
                    out[h["path"]] = h["sha256"]
        return out


def _request_spec(url: str, method: str, json_body: Any, form_body: Mapping[str, str] | None = None) -> dict[str, Any]:
    """What identifies a request in its pin. A form POST adds `body_type: form` (JSON and bodiless
    requests keep the original three keys, so existing pins stay valid)."""
    if form_body is not None:
        return {
            "url": url,
            "method": method,
            "body_sha256": io.sha256_bytes(encode_form(form_body)),
            "body_type": "form",
        }
    body_sha = io.sha256_bytes(io.dumps_json(json_body, indent=None).encode()) if json_body is not None else None
    return {"url": url, "method": method, "body_sha256": body_sha}


# Form fields that carry credentials or a server-session/CSRF token. DECISIONS D1-7: form POSTs are
# allowed for public, keyless pages (e.g. an ASP.NET archive's __VIEWSTATE/__EVENTVALIDATION
# postback); flows that need a login, a key or a session-bound CSRF token stay out of scope.
FORBIDDEN_FORM_FIELD = re.compile(
    r"pass(word|wd)?|pwd|token|csrf|xsrf|captcha|otp|api_?key|secret|session|auth|login|user_?name", re.I
)


def encode_form(form_body: Mapping[str, str]) -> bytes:
    """application/x-www-form-urlencoded bytes, fields in the order given (deterministic for a
    dict literal). Refuses non-string values and credential/CSRF/session fields (D1-7)."""
    from urllib.parse import urlencode

    bad = [k for k in form_body if FORBIDDEN_FORM_FIELD.search(str(k))]
    if bad:
        raise FetchError(
            f"form field(s) {bad} look like credentials, a session or a CSRF token; only public keyless forms "
            "may be posted (DECISIONS D1-7)"
        )
    wrong = [k for k, v in form_body.items() if not isinstance(k, str) or not isinstance(v, str)]
    if wrong:
        raise FetchError(f"form fields must be str -> str; bad: {wrong}")
    return urlencode(list(form_body.items())).encode("ascii")


def _verify_pinned(layout: Layout, key: str, pin: Mapping[str, Any]) -> RawFile:
    path = layout.raw_abs(pin["path"])
    if not path.exists():
        raise OfflineMissing(
            f"pinned raw file for {key!r} is missing: {pin['path']}. Run `uv run python -m pipeline fetch "
            "<unit>` (network) to restore it; builds never download."
        )
    sha = io.sha256_file(path)
    if sha != pin["sha256"]:
        raise PinMismatch(
            f"{pin['path']}: sha256 {sha[:12]}... does not match the pin {pin['sha256'][:12]}.... Raw files must "
            "never be edited. Delete it and re-fetch; if upstream changed, fetch with --refresh."
        )
    source_id, name = key.split("/", 1)
    return RawFile(
        source_id=source_id,
        name=name,
        url=pin["url"],
        sha256=pin["sha256"],
        path=path,
        rel_path=pin["path"],
        retrieved_at=pin["retrieved_at"],
        method=pin.get("method", "GET"),
    )


def pinned_raw(layout: Layout, unit: str, source_id: str, name: str) -> RawFile:
    """Offline lookup used by builds: the pinned bytes, verified, or a loud error."""
    store = PinStore.load(layout, unit)
    key = f"{source_id}/{name}"
    pin = store.pins.get(key)
    if pin is None:
        raise OfflineMissing(
            f"no pin for {key!r} in {store.path.name}. The unit's fetch() must fetch it first "
            f"(`uv run python -m pipeline fetch {unit}`)."
        )
    return _verify_pinned(layout, key, pin)


# ---------------------------------------------------------------------------------------------
# block / challenge detection
# ---------------------------------------------------------------------------------------------

MAGIC: dict[str, tuple[bytes, ...]] = {
    "xlsx": (b"PK\x03\x04",),
    "xlsm": (b"PK\x03\x04",),
    "xlsb": (b"PK\x03\x04",),
    "docx": (b"PK\x03\x04",),
    "zip": (b"PK\x03\x04",),
    "ods": (b"PK\x03\x04",),
    "xls": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    "doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
    "pdf": (b"%PDF",),
    "gz": (b"\x1f\x8b",),
}
TEXT_KINDS = frozenset({"csv", "txt", "tsv", "json", "xml", "html"})

# (marker, what it is). Checked case-insensitively in the first 64 KB of the body.
CHALLENGE_MARKERS: tuple[tuple[str, str], ...] = (
    ("window.rbzns", "F5 BIG-IP bot defence (TSPD) JavaScript challenge"),
    ("tspd", "F5 BIG-IP bot defence (TSPD) JavaScript challenge"),
    ("bobcmn", "F5 BIG-IP bot defence JavaScript challenge"),
    ("the requested url was rejected", "F5 ASM block page"),
    ("request rejected", "WAF block page"),
    ("cf-chl", "Cloudflare challenge"),
    ("challenge-platform", "Cloudflare challenge"),
    ("just a moment...", "Cloudflare interstitial"),
    ("attention required! | cloudflare", "Cloudflare block page"),
    ("_incapsula_resource", "Imperva/Incapsula challenge"),
    ("incapsula incident", "Imperva/Incapsula block page"),
    ("g-recaptcha", "reCAPTCHA"),
    ("hcaptcha", "hCaptcha"),
    ("captcha", "CAPTCHA"),
    ("access denied", "access-denied page"),
    ("unauthorised access", "unauthorised-access page"),
    ("unauthorized access", "unauthorised-access page"),
)
_WEAK_MARKERS = frozenset({"CAPTCHA", "access-denied page", "WAF block page"})


def challenge_marker(body: bytes) -> str | None:
    """What kind of bot challenge / block page this body looks like, or None."""
    text = body[:65536].decode("latin-1").lower()
    return next((what for m, what in CHALLENGE_MARKERS if m in text), None)


def _looks_html(body: bytes) -> bool:
    head = body[:2048].lstrip().lower()
    return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<html" in head[:512]


def detect_block(status: int, content_type: str, body: bytes, expect: str, final_url: str | None = None) -> str | None:
    """Return a reason string if this response is a refusal/challenge/login/wrong content, else None.

    `expect` is the kind of file wanted: a key of MAGIC, one of TEXT_KINDS, or 'any'.
    """
    ct = (content_type or "").lower()
    marker = challenge_marker(body)

    if final_url and login_url(final_url):
        return f"the request ended on a sign-in or registration page ({final_url}); the file is behind a login"
    if final_url and denied_host(final_url):
        return denied_host(final_url)
    if status in (401, 403, 407, 451):
        extra = f"; body looks like: {marker}" if marker else ""
        return (
            f"HTTP {status} (refused{extra}). Note: some hosts (e.g. MoSPI /uploads/) also answer 403 for "
            "files that do not exist, so check the URL before assuming a block"
        )
    if status == 429:
        return "HTTP 429 Too Many Requests after retries (rate limited)"
    if status >= 400:
        if marker:  # e.g. a Cloudflare challenge served with 503
            return f"HTTP {status} with a bot challenge or block page: {marker}"
        return None  # a plain HTTP error, handled by the caller as FetchError

    if (expect in ("html", "any") or _looks_html(body)) and PASSWORD_INPUT_RE.search(body[:262144]):
        return "the page contains a password field (a login form); the file is behind a login"
    if expect in MAGIC:
        if any(body.startswith(m) for m in MAGIC[expect]):
            return None
        if _looks_html(body) or "html" in ct:
            return f"expected a {expect} file but got an HTML page ({marker or 'no known challenge marker'})"
        return f"expected a {expect} file but the bytes do not start with its signature (content-type {ct!r})"
    if expect == "json":
        try:
            json.loads(body.decode("utf-8-sig"))
        except UnicodeDecodeError, json.JSONDecodeError:
            if _looks_html(body) or "html" in ct:
                return f"expected JSON but got an HTML page ({marker or 'no known challenge marker'})"
            return "expected JSON but the body does not parse as JSON"
        return None
    if expect in ("csv", "txt", "tsv", "xml"):
        if _looks_html(body):
            return f"expected {expect} but got an HTML page ({marker or 'no known challenge marker'})"
        return None
    if expect in ("html", "any"):
        # For HTML we can only look for challenge markers. 'captcha' and 'access denied' alone can
        # appear in ordinary pages, so require a strong marker or a tiny page.
        strong = marker and marker not in _WEAK_MARKERS
        if strong or (marker and len(body) < 20_000):
            return f"page looks like a bot challenge or block page: {marker}"
        return None
    raise ValueError(f"unknown expect kind {expect!r}")


def expect_from_name(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext in MAGIC or ext in TEXT_KINDS:
        return ext
    if ext == "htm":
        return "html"
    return "any"


# ---------------------------------------------------------------------------------------------
# polite HTTP
# ---------------------------------------------------------------------------------------------


def host_key(url: str) -> str:
    """Rate-limit key: the host name, plus the port when one is given explicitly."""
    parts = urlsplit(url)
    key = (parts.hostname or "unknown").lower()
    if parts.port is not None:
        key += f"_{parts.port}"
    return re.sub(r"[^a-z0-9._-]", "_", key)


@contextmanager
def _host_lock(key: str) -> Iterator[Path]:
    """Exclusive per-host lock shared by every process on this machine (not per data layout).
    Yields the path of the host's last-request stamp. Released by the OS if the holder dies."""
    d = host_lock_dir()
    with file_lock(d / f"{key}.lock", timeout_s=HOST_LOCK_TIMEOUT_S, what=f"the fetch lock for {key}"):
        yield d / f"{key}.last"


def _stamp(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{time.time():.3f}", encoding="utf-8")


def _last(path: Path) -> float:
    try:
        return float(path.read_text(encoding="utf-8"))
    except FileNotFoundError, ValueError:
        return 0.0


def min_interval_s(url: str) -> float:
    """Minimum seconds between two requests to this URL's host (HOST_MIN_INTERVAL_S or the default)."""
    host = (urlsplit(url).hostname or "").lower()
    return max(MIN_HOST_INTERVAL_S, HOST_MIN_INTERVAL_S.get(host, 0.0))


def needs_legacy_tls(url: str) -> bool:
    return (urlsplit(url).hostname or "").lower() in LEGACY_RENEGOTIATION_HOSTS


def _ssl_context(legacy_renegotiation: bool = False) -> ssl.SSLContext:
    import truststore  # OS trust store (Windows cert store / system CAs); verification stays on

    ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if legacy_renegotiation:  # only for LEGACY_RENEGOTIATION_HOSTS (D1-6); verification unchanged
        ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
    return ctx


@dataclass
class Response:
    status: int
    final_url: str
    content_type: str
    body: bytes
    headers: dict[str, str]
    request_headers: dict[str, str]
    attempts: int
    redirects: list[str] = field(default_factory=list)  # the URLs that redirected, in order


def _retry_after_s(value: str) -> float | None:
    """Seconds from a Retry-After header (delta-seconds or HTTP-date), or None if absent/unparseable."""
    value = (value or "").strip()
    if not value:
        return None
    if value.isdigit():
        return float(value)
    try:
        when = email.utils.parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.UTC)
    return max(0.0, (when - dt.datetime.now(dt.UTC)).total_seconds())


def _check_hop(url: str, stop_hosts: Mapping[str, str] | None = None) -> None:
    """Policy checks applied to the first URL and to every redirect target, before any request.
    `stop_hosts` ({host key: reason}) are hosts that served a challenge earlier in this run."""
    if not url.startswith(("https://", "http://")):
        raise AccessBlocked(f"redirect to a non-http(s) URL {url!r}; nothing was saved")
    if stop_hosts and host_key(url) in stop_hosts:
        key = host_key(url)
        raise ChallengeServed(
            f"{url}: not requested. {key} served a bot challenge earlier in this run ({stop_hosts[key]}); every later "
            "request to it in this run is refused without contacting it (DECISIONS D1-1b, D1-4). Log it.",
            key,
        )
    why = denied_host(url)
    if why:
        raise AccessBlocked(f"{url}: {why}. Nothing was saved (DECISIONS.md D1-1c/D1-2).")
    if login_url(url):
        raise AccessBlocked(
            f"{url} is a sign-in or registration page: the file is behind a login. Nothing was saved (DECISIONS.md "
            "D1-1b); log it in docs/phase1/issues/<unit>.md."
        )


def _send(client: Any, method: str, url: str, headers: dict[str, str], content: bytes | None) -> Response:
    """One URL, no redirect following, with the per-host wait and retries. Returns the last response."""
    import httpx

    key = host_key(url)
    gap = min_interval_s(url)
    last_exc: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        r = None
        exc: Exception | None = None
        with _host_lock(key) as stamp:
            wait = _last(stamp) + gap - time.time()
            if wait > 0:
                time.sleep(wait)
            _stamp(stamp)
            try:
                r = client.request(method, url, headers=headers, content=content)
                body = r.content
            except (httpx.LocalProtocolError, httpx.UnsupportedProtocol) as e:
                raise FetchError(f"{method} {url}: the request could not be sent ({e!r}); not retried") from None
            except httpx.TransportError as e:  # timeouts, connection resets, DNS
                exc = e
            finally:
                _stamp(stamp)
        backoff = BACKOFF_BASE_S * 2 ** (attempt - 1)
        if exc is not None or r is None:
            last_exc = exc
            print(f"  fetch: {type(exc).__name__} on {url} (attempt {attempt}/{MAX_ATTEMPTS})", file=sys.stderr)
            if attempt < MAX_ATTEMPTS:
                time.sleep(backoff)
            continue
        resp = Response(
            status=r.status_code,
            final_url=url,
            content_type=r.headers.get("content-type", ""),
            body=body,
            headers={k.lower(): v for k, v in r.headers.items()},
            request_headers=dict(headers),
            attempts=attempt,
        )
        if not (r.status_code == 429 or r.status_code >= 500):
            return resp
        marker = challenge_marker(body)
        if marker:  # a challenge is never retried (D1-1b)
            raise ChallengeServed(
                f"{method} {url}: HTTP {r.status_code} with a bot challenge or block page ({marker}). Nothing was "
                "saved. Do not work around this; log it in docs/phase1/issues/<unit>.md (DECISIONS.md D1-1b).",
                key,
            )
        ra = _retry_after_s(r.headers.get("retry-after", ""))
        if ra is not None and ra > MAX_RETRY_AFTER_S:
            raise AccessBlocked(
                f"{method} {url}: HTTP {r.status_code} and the server asks us to wait {ra:.0f} s (Retry-After), more "
                f"than {MAX_RETRY_AFTER_S:.0f} s. Stopped instead of retrying early; fetch again later and log it."
            )
        print(f"  fetch: HTTP {r.status_code} on {url} (attempt {attempt}/{MAX_ATTEMPTS})", file=sys.stderr)
        if attempt == MAX_ATTEMPTS:
            return resp
        time.sleep(max(backoff, ra or 0.0))
    raise FetchError(f"{method} {url}: failed after {MAX_ATTEMPTS} attempts: {last_exc!r}")


def http_request(
    layout: Layout,
    url: str,
    *,
    method: str = "GET",
    json_body: Any = None,
    headers: Mapping[str, str] | None = None,
    referer: str | None = None,
    mode: str | None = None,
    form_body: Mapping[str, str] | None = None,
    stop_hosts: Mapping[str, str] | None = None,
) -> Response:
    """One polite request with rate limiting, retries and hand-followed redirects: every hop goes
    through the host lock and the policy checks. Returns the final response (any status).

    form_body: an HTML form submission (application/x-www-form-urlencoded POST from the site's own
    public page; DECISIONS D1-7). It is sent with navigation headers, as a browser submits a form.
    stop_hosts: hosts that served a challenge earlier in this run; they are never contacted.
    `layout` is kept for API stability; host locks are machine-wide and do not depend on it."""
    import httpx

    method = method.upper()
    if form_body is not None and json_body is not None:
        raise FetchError("pass either json_body or form_body, not both")
    if form_body is not None and method != "POST":
        raise FetchError("form_body needs method='POST'")
    mode = mode or (
        "form" if form_body is not None else "api" if method == "POST" or json_body is not None else "navigate"
    )
    base = dict(API_HEADERS if mode == "api" else NAVIGATE_HEADERS)
    parts = urlsplit(url)
    if referer:
        base["Referer"] = referer
        if mode in ("navigate", "form"):
            ref_host = urlsplit(referer).hostname
            base["Sec-Fetch-Site"] = "same-origin" if ref_host == parts.hostname else "cross-site"
    if mode in ("api", "form"):
        base["Origin"] = f"{parts.scheme}://{parts.netloc}"
        if json_body is not None:
            base["Content-Type"] = "application/json"
        if form_body is not None:
            base["Content-Type"] = "application/x-www-form-urlencoded"
            base["Cache-Control"] = "max-age=0"
            if not referer:
                base["Sec-Fetch-Site"] = "same-origin"  # a form is submitted from the site's own page
    for k, v in (headers or {}).items():
        if not _HEADER_NAME.match(k) or k.lower() not in UNIT_HEADERS:
            raise FetchError(
                f"header {k!r} is not allowed by the access policy (DECISIONS.md D1-1); a unit may set only "
                f"{sorted(UNIT_HEADERS)} (and Referer via `referer=`)"
            )
        base[k] = v
    if form_body is not None:
        content: bytes | None = encode_form(form_body)
    else:
        content = json.dumps(json_body, separators=(",", ":")).encode() if json_body is not None else None

    timeout = httpx.Timeout(READ_TIMEOUT_S, connect=CONNECT_TIMEOUT_S)
    chain: list[str] = []
    current = url
    # One client per TLS profile: the legacy-renegotiation context is used only for hops whose
    # host is in LEGACY_RENEGOTIATION_HOSTS, also when a redirect crosses hosts.
    clients: dict[bool, Any] = {}
    try:
        for _hop in range(MAX_REDIRECTS + 1):
            _check_hop(current, stop_hosts)
            legacy = needs_legacy_tls(current)
            if legacy not in clients:
                clients[legacy] = httpx.Client(
                    verify=_ssl_context(legacy), timeout=timeout, follow_redirects=False, http2=False, trust_env=False
                )
            resp = _send(clients[legacy], method, current, base, content)
            location = resp.headers.get("location")
            if resp.status in (301, 302, 303, 307, 308) and location:
                chain.append(current)
                if resp.status == 303 or (resp.status in (301, 302) and method == "POST"):
                    method, content = "GET", None
                    base.pop("Content-Type", None)
                    base.pop("Cache-Control", None)
                current = urljoin(current, location)
                continue
            resp.redirects = chain
            return resp
    finally:
        for c in clients.values():
            c.close()
    raise FetchError(f"{url}: more than {MAX_REDIRECTS} redirects: {' -> '.join(chain)}")


# ---------------------------------------------------------------------------------------------
# fetch with cache + pins
# ---------------------------------------------------------------------------------------------


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(microsecond=0)


def _new_raw_path(layout: Layout, store: PinStore, source_id: str, name: str, sha: str, now: dt.datetime) -> Path:
    """data/raw/<source_id>/<date>[-rN]/<unit>/<name>: the first candidate that is free or already
    holds these exact bytes, and that no current or superseded pin uses for other bytes."""
    in_use = store.paths_in_use()
    day = now.strftime("%Y-%m-%d")
    for n in range(1, 100):
        folder = day if n == 1 else f"{day}-r{n}"
        path = layout.raw / source_id / folder / store.unit / name
        rel = layout.raw_rel(path)
        if rel in in_use and in_use[rel] != sha:
            continue
        if path.exists() and io.sha256_file(path) != sha:
            continue
        return path
    raise FetchError(f"{source_id}/{name}: 99 different versions today; upstream is churning, log it and stop")


def fetch_file(
    layout: Layout,
    store: PinStore,
    *,
    source_id: str,
    url: str,
    name: str,
    method: str = "GET",
    json_body: Any = None,
    headers: Mapping[str, str] | None = None,
    referer: str | None = None,
    expect: str | None = None,
    offline: bool = False,
    refresh: bool = False,
    log: Callable[[str], Any] = print,
    warn: Callable[[str], Any] | None = None,
    form_body: Mapping[str, str] | None = None,
    stop_hosts: Mapping[str, str] | None = None,
) -> RawFile:
    """Return the pinned raw file for (source_id, name), downloading only when needed.

    - offline: never download; the pinned file must exist with the pinned sha256.
    - default: download only if there is no pin, the request (url/method/body) changed, or the
      pinned file is missing locally. Restoring a missing file whose upstream bytes changed is an
      error: the pinned version can no longer be had, so accepting the new one needs --refresh.
    - refresh: re-download and compare with the pin; changed bytes become a new pin (a warning).
    - form_body: a public, keyless HTML form POST (D1-7); pinned by the hash of the encoded body.
    - stop_hosts: hosts that served a challenge earlier in this run; raises ChallengeServed without
      contacting them. A challenge served now raises ChallengeServed (a subclass of AccessBlocked).
    """
    warn = warn or log
    entry = get_source(source_id, layout)  # unknown id = hard error
    if not _SAFE_NAME.match(name) or name.endswith(".meta.json"):
        raise ValueError(f"raw file name {name!r} must match {_SAFE_NAME.pattern} and not end in .meta.json")
    if not url.startswith(("https://", "http://")):
        raise ValueError(f"not an http(s) URL: {url!r}")
    method = method.upper()
    expect = expect or ("json" if name.lower().endswith(".json") else expect_from_name(name))
    key = f"{source_id}/{name}"
    if form_body is not None and (method != "POST" or json_body is not None):
        raise ValueError("form_body needs method='POST' and no json_body")
    spec = _request_spec(url, method, json_body, form_body)
    pin = store.pins.get(key)
    spec_same = pin is not None and all(pin.get(k) == v for k, v in spec.items())

    if offline:
        if pin is None:
            raise OfflineMissing(f"offline: no pin for {key!r} in {store.path.name}; fetch it online first")
        if not spec_same:
            raise OfflineMissing(f"offline: the request for {key!r} changed (url/method/body) since it was pinned")
        return _verify_pinned(layout, key, pin)

    restoring = False
    if pin is not None and spec_same and not refresh:
        try:
            return _verify_pinned(layout, key, pin)
        except OfflineMissing:
            restoring = True
            log(f"  {key}: pinned file missing locally, downloading to restore it")

    refusal = url_refusal(source_id, entry, url)
    if refusal:
        raise AccessBlocked(f"{method} {url}: {refusal}. Nothing was fetched (DECISIONS.md D1-1/D1-2).")

    resp = http_request(
        layout,
        url,
        method=method,
        json_body=json_body,
        headers=headers,
        referer=referer,
        form_body=form_body,
        stop_hosts=stop_hosts,
    )
    reason = detect_block(resp.status, resp.content_type, resp.body, expect, final_url=resp.final_url)
    if reason:
        msg = (
            f"{method} {url}: {reason}. Nothing was saved. Do not work around this; "
            "log it in docs/phase1/issues/<unit>.md (DECISIONS.md D1-1b)."
        )
        marker = challenge_marker(resp.body)
        if marker and marker not in _WEAK_MARKERS:
            raise ChallengeServed(msg, host_key(resp.final_url))
        raise AccessBlocked(msg)
    if resp.status >= 400 or not resp.body:
        raise FetchError(f"{method} {url}: HTTP {resp.status}, {len(resp.body)} bytes. Nothing was saved.")

    now = _utc_now()
    sha = io.sha256_bytes(resp.body)
    retrieved_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    if pin is not None and pin["sha256"] == sha:
        pinned_path = layout.raw_abs(pin["path"])
        if not pinned_path.exists():
            io.atomic_write_bytes(pinned_path, resp.body)
            if not meta_path(pinned_path).exists():
                io.write_json(
                    meta_path(pinned_path),
                    _meta(
                        key,
                        source_id,
                        name,
                        url,
                        method,
                        json_body,
                        resp,
                        sha,
                        pin["retrieved_at"],
                        form_body=form_body,
                    ),
                )
            log(f"  {key}: restored pinned file ({len(resp.body):,} bytes, sha256 {sha[:12]})")
        else:
            log(f"  {key}: upstream unchanged (sha256 {sha[:12]})")
        if not spec_same:  # same bytes from a new URL: record the new request, keep the original file
            store.set(key, pin | spec)
        return _verify_pinned(layout, key, store.pins[key])

    if restoring:
        raise FetchError(
            f"{key}: the pinned file {pin['path']} is missing locally and upstream now serves different bytes "
            f"({pin['sha256'][:12]} pinned, {sha[:12]} now), so the pinned version cannot be restored. Nothing was "
            "saved. To accept the new version run `fetch <unit> --refresh`, record the revision in your issues "
            "file and re-check your tests."
        )

    path = _new_raw_path(layout, store, source_id, name, sha, now)
    if not path.exists():
        io.atomic_write_bytes(path, resp.body)
    mp = meta_path(path)
    if mp.exists():
        # The path already held these exact bytes (e.g. an earlier run saved the file and its
        # sidecar, then crashed before saving the pin). The sidecar is never rewritten, so the pin
        # takes the sidecar's retrieved_at: pin and meta must agree (trade_satellites-14).
        old_meta = json.loads(mp.read_text(encoding="utf-8"))
        if old_meta.get("sha256") != sha:
            raise FetchError(
                f"{layout.raw_rel(mp)} describes other bytes ({str(old_meta.get('sha256'))[:12]}) than the file "
                f"({sha[:12]}); raw sidecars are never edited. Log it and investigate."
            )
        retrieved_at = old_meta["retrieved_at"]
    else:
        io.write_json(
            mp, _meta(key, source_id, name, url, method, json_body, resp, sha, retrieved_at, form_body=form_body)
        )
    new_pin = spec | {
        "sha256": sha,
        "bytes": len(resp.body),
        "path": layout.raw_rel(path),
        "retrieved_at": retrieved_at,
    }
    if pin is None:
        log(f"  {key}: NEW PIN ({len(resp.body):,} bytes, sha256 {sha[:12]})")
    else:
        warn(
            f"{key}: REVISION - upstream bytes changed: {pin['sha256'][:12]} -> {sha[:12]}. New pin written "
            f"({layout.raw_rel(path)}); old pin kept in history. Record this in docs/phase1/issues/<unit>.md and "
            "re-check your tests."
        )
    store.set(key, new_pin)
    return _verify_pinned(layout, key, store.pins[key])


def _meta(
    key: str,
    source_id: str,
    name: str,
    url: str,
    method: str,
    json_body: Any,
    resp: Response,
    sha: str,
    retrieved_at: str,
    *,
    form_body: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    keep = ("content-length", "content-type", "etag", "last-modified", "content-disposition", "server")
    extra = {"request_body_type": "form"} if form_body is not None else {}
    return extra | {
        "key": key,
        "source_id": source_id,
        "name": name,
        "url": url,
        "final_url": resp.final_url,
        "redirects": resp.redirects,
        "method": method,
        "request_body": dict(form_body) if form_body is not None else json_body,
        "request_headers": dict(sorted(resp.request_headers.items())),
        "status": resp.status,
        "content_type": resp.content_type,
        "bytes": len(resp.body),
        "sha256": sha,
        "retrieved_at": retrieved_at,
        "response_headers": {k: v for k, v in sorted(resp.headers.items()) if k in keep},
        "attempts": resp.attempts,
        "access_policy": "DECISIONS.md D1-1 (public file, browser-like headers, >=2 s per host)",
    }
