"""fetch.py against a local HTTP server (no internet needed)."""

import datetime as dt
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pipeline.core import fetch as F
from pipeline.core.paths import HOST_LOCK_DIR_VAR
from pipeline.core.registry import UnknownSourceError

pytestmark = pytest.mark.unit
SRC = "mospi_nas_2026_publication"
XLSX = b"PK\x03\x04" + b"fake workbook bytes" * 10
CHALLENGE = b"<html><head><script>window.rbzns={};</script></head><body>Please wait</body></html>"


class State:
    def __init__(self):
        self.requests: list[tuple[float, str, str, dict]] = []
        self.content = XLSX
        self.fail_next = 0


@pytest.fixture
def server(monkeypatch, tmp_path_factory):
    monkeypatch.setattr(F, "MIN_HOST_INTERVAL_S", 0.3)
    monkeypatch.setattr(F, "BACKOFF_BASE_S", 0.05)
    # Host locks for the throwaway 127.0.0.1:<port> servers go to a temp folder, not the real
    # machine-wide one (still shared by every layout in the test, which is what is tested).
    monkeypatch.setenv(HOST_LOCK_DIR_VAR, str(tmp_path_factory.mktemp("host-locks")))
    state = State()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, where):
            self.send_response(302)
            self.send_header("Location", where)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            state.requests.append((time.monotonic(), "GET", self.path, dict(self.headers)))
            if self.path == "/cf503":
                page = b"<html><title>Just a moment...</title>cf-chl challenge-platform</html>"
                return self._send(503, page, "text/html")
            if self.path == "/retry-long":
                self.send_response(503)
                self.send_header("Retry-After", "3600")
                self.send_header("Content-Length", "4")
                self.end_headers()
                return self.wfile.write(b"busy")
            if self.path == "/redir":
                return self._redirect("/file.xlsx")
            if self.path == "/redir-login":
                return self._redirect("/account/login.aspx?next=/report")
            if self.path == "/to-localhost":  # a redirect that crosses hosts (same server, other host name)
                return self._redirect(f"http://localhost:{state.port}/file.xlsx")
            if self.path == "/redir-denied":
                return self._redirect("https://microdata.gov.in/NADA/index.php/catalog/1")
            if self.path == "/form":
                page = b"<html><body><form><input name=u><input type='password' name=p></form></body></html>"
                return self._send(200, page, "text/html")
            if self.path == "/file.xlsx":
                if state.fail_next:
                    state.fail_next -= 1
                    return self._send(503, b"busy", "text/plain")
                return self._send(200, state.content, "application/octet-stream")
            if self.path == "/challenge.xlsx":
                return self._send(200, CHALLENGE, "text/html")
            if self.path == "/forbidden.xlsx":
                return self._send(403, b"<html>403 Forbidden</html>", "text/html")
            return self._send(404, b"nope", "text/plain")

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            state.requests.append((time.monotonic(), "POST", self.path, dict(self.headers)))
            if self.headers.get("Content-Type") == "application/x-www-form-urlencoded":
                from urllib.parse import parse_qsl

                page = "<html><body>" + json.dumps(parse_qsl(body.decode("ascii"))) + "</body></html>"
                return self._send(200, page.encode(), "text/html")
            return self._send(200, json.dumps({"echo": json.loads(body)}).encode(), "application/json")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    state.port = srv.server_port
    state.base = f"http://127.0.0.1:{srv.server_port}"
    yield state
    srv.shutdown()


def _fetch(layout, store, url, name="file.xlsx", **kw):
    return F.fetch_file(layout, store, source_id=SRC, url=url, name=name, log=lambda m: None, **kw)


def test_new_pin_meta_headers_and_cache(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    raw = _fetch(tmp_layout, store, server.base + "/file.xlsx")
    store.save()
    assert raw.read_bytes() == XLSX and raw.sha256 == F.io.sha256_bytes(XLSX)
    assert raw.rel_path.startswith(f"data/raw/{SRC}/") and raw.rel_path.endswith("/file.xlsx")
    meta = raw.meta
    assert meta["sha256"] == raw.sha256 and meta["status"] == 200 and meta["bytes"] == len(XLSX)
    assert meta["request_headers"]["User-Agent"].startswith("Mozilla/5.0")
    sent = server.requests[0][3]
    assert sent["Sec-Fetch-Mode"] == "navigate" and "Cookie" not in sent
    pins = F.io.read_yaml(tmp_layout.pins / "demo.yaml")
    assert pins["pins"][f"{SRC}/file.xlsx"]["sha256"] == raw.sha256
    # second call: served from the pinned cache, no request
    n = len(server.requests)
    again = _fetch(tmp_layout, F.PinStore.load(tmp_layout, "demo"), server.base + "/file.xlsx")
    assert again.path == raw.path and len(server.requests) == n
    # offline works from the cache, and build-side lookup verifies the hash
    assert _fetch(tmp_layout, F.PinStore.load(tmp_layout, "demo"), server.base + "/file.xlsx", offline=True).sha256
    assert F.pinned_raw(tmp_layout, "demo", SRC, "file.xlsx").sha256 == raw.sha256


def test_challenge_and_refusal_raise_access_blocked_and_save_nothing(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    with pytest.raises(F.AccessBlocked, match="F5 BIG-IP"):
        _fetch(tmp_layout, store, server.base + "/challenge.xlsx", name="challenge.xlsx")
    with pytest.raises(F.AccessBlocked, match="HTTP 403"):
        _fetch(tmp_layout, store, server.base + "/forbidden.xlsx", name="forbidden.xlsx")
    assert not store.pins
    assert not [p for p in tmp_layout.raw.rglob("*") if p.is_file() and ".hosts" not in p.parts]


def test_http_error_is_fetch_error(server, tmp_layout):
    with pytest.raises(F.FetchError, match="HTTP 404"):
        _fetch(tmp_layout, F.PinStore.load(tmp_layout, "demo"), server.base + "/missing.xlsx", name="missing.xlsx")


def test_retry_on_503(server, tmp_layout):
    server.fail_next = 1
    raw = _fetch(tmp_layout, F.PinStore.load(tmp_layout, "demo"), server.base + "/file.xlsx")
    assert raw.meta["attempts"] == 2


def test_post_json_uses_api_headers_and_pins_body(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    raw = _fetch(tmp_layout, store, server.base + "/api", name="list.json", method="POST", json_body={"id": 2861})
    assert raw.read_json() == {"echo": {"id": 2861}}
    sent = server.requests[-1][3]
    assert sent["Content-Type"] == "application/json" and sent["Sec-Fetch-Mode"] == "cors"
    assert sent["Origin"] == server.base
    assert store.pins[f"{SRC}/list.json"]["body_sha256"]
    # a different body is a different request: offline must refuse the old pin
    with pytest.raises(F.OfflineMissing, match="changed"):
        _fetch(
            tmp_layout, store, server.base + "/api", name="list.json", method="POST", json_body={"id": 1}, offline=True
        )


def test_rate_limit_per_host(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    for i in range(3):
        _fetch(tmp_layout, store, server.base + f"/api?{i}", name=f"r{i}.json", method="POST", json_body={"i": i})
    times = [t for t, *_ in server.requests[-3:]]
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert min(gaps) >= F.MIN_HOST_INTERVAL_S * 0.95, gaps


def test_offline_missing_and_pin_mismatch(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    with pytest.raises(F.OfflineMissing, match="no pin"):
        _fetch(tmp_layout, store, server.base + "/file.xlsx", offline=True)
    raw = _fetch(tmp_layout, store, server.base + "/file.xlsx")
    store.save()
    raw.path.write_bytes(b"PK\x03\x04 edited by hand")
    with pytest.raises(F.PinMismatch):
        F.pinned_raw(tmp_layout, "demo", SRC, "file.xlsx")
    raw.path.unlink()
    with pytest.raises(F.OfflineMissing, match="missing"):
        F.pinned_raw(tmp_layout, "demo", SRC, "file.xlsx")
    with pytest.raises(F.OfflineMissing):
        F.pinned_raw(tmp_layout, "demo", SRC, "never.xlsx")


def test_upstream_change_creates_new_pin_and_never_overwrites(server, tmp_layout, monkeypatch):
    store = F.PinStore.load(tmp_layout, "demo")
    first = _fetch(tmp_layout, store, server.base + "/file.xlsx")
    assert "/demo/file.xlsx" in first.rel_path  # the unit is part of the raw path
    server.content = XLSX + b"revised"
    warnings = []
    # same day, different bytes: a second folder <date>-r2, the first file untouched
    second = _fetch(tmp_layout, store, server.base + "/file.xlsx", refresh=True, warn=warnings.append)
    assert second.path != first.path and "-r2/demo/" in second.rel_path and first.path.read_bytes() == XLSX
    assert warnings and "REVISION" in warnings[0]
    # next day: a new dated file, a new pin, both old pins in history
    tomorrow = F._utc_now() + dt.timedelta(days=1)
    monkeypatch.setattr(F, "_utc_now", lambda: tomorrow)
    server.content = XLSX + b"revised again"
    third = _fetch(tmp_layout, store, server.base + "/file.xlsx", refresh=True)
    assert third.path.parent.parent.name == tomorrow.strftime("%Y-%m-%d")
    pin = store.pins[f"{SRC}/file.xlsx"]
    assert pin["sha256"] == third.sha256
    assert [h["sha256"] for h in pin["history"]] == [first.sha256, second.sha256]
    # refresh with unchanged bytes keeps the pin as is
    before = dict(store.pins)
    _fetch(tmp_layout, store, server.base + "/file.xlsx", refresh=True)
    assert store.pins == before


def test_restoring_a_missing_pinned_file_never_silently_repins(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    first = _fetch(tmp_layout, store, server.base + "/file.xlsx")
    first.path.unlink()  # a fresh clone: pin present, raw file absent
    server.content = XLSX + b"revised"
    with pytest.raises(F.FetchError, match="cannot be restored"):
        _fetch(tmp_layout, store, server.base + "/file.xlsx")
    assert store.pins[f"{SRC}/file.xlsx"]["sha256"] == first.sha256 and not first.path.exists()
    # --refresh accepts the new version at a path that never held the old bytes
    new = _fetch(tmp_layout, store, server.base + "/file.xlsx", refresh=True)
    assert new.rel_path != first.rel_path
    assert store.pins[f"{SRC}/file.xlsx"]["history"][0]["path"] == first.rel_path
    # unchanged upstream bytes restore the pinned file in place
    server.content = XLSX + b"revised"
    new.path.unlink()
    again = _fetch(tmp_layout, store, server.base + "/file.xlsx")
    assert again.path == new.path and again.sha256 == new.sha256


def test_challenge_served_with_5xx_is_blocked_without_retry(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    with pytest.raises(F.AccessBlocked, match="Cloudflare"):
        _fetch(tmp_layout, store, server.base + "/cf503", name="a.xlsx")
    assert [p for _, _, p, _ in server.requests] == ["/cf503"]  # asked once, not 4 times


def test_long_retry_after_stops_instead_of_retrying_early(server, tmp_layout):
    with pytest.raises(F.AccessBlocked, match="Retry-After"):
        _fetch(tmp_layout, F.PinStore.load(tmp_layout, "demo"), server.base + "/retry-long", name="b.xlsx")
    assert len(server.requests) == 1
    assert F._retry_after_s("120") == 120.0 and F._retry_after_s("") is None
    assert F._retry_after_s("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0  # an HTTP-date in the past


def test_redirects_are_followed_by_hand_with_rate_limit_and_policy(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    raw = _fetch(tmp_layout, store, server.base + "/redir")
    assert raw.read_bytes() == XLSX
    assert raw.meta["redirects"] == [server.base + "/redir"] and raw.meta["final_url"].endswith("/file.xlsx")
    (t0, *_), (t1, *_) = server.requests[-2:]
    assert t1 - t0 >= F.MIN_HOST_INTERVAL_S * 0.95  # the redirect hop waited its turn
    n = len(server.requests)
    with pytest.raises(F.AccessBlocked, match="sign-in"):
        _fetch(tmp_layout, store, server.base + "/redir-login", name="report")
    with pytest.raises(F.AccessBlocked, match="microdata"):
        _fetch(tmp_layout, store, server.base + "/redir-denied", name="c.xlsx")
    assert len(server.requests) == n + 2  # the login page and the denied host were never requested


def test_login_form_is_blocked(server, tmp_layout):
    with pytest.raises(F.AccessBlocked, match="password"):
        _fetch(tmp_layout, F.PinStore.load(tmp_layout, "demo"), server.base + "/form", name="page.html")


def test_host_lock_is_shared_across_layouts(server, tmp_path):
    a, b = F.Layout.scratch(tmp_path / "a"), F.Layout.scratch(tmp_path / "b")
    _fetch(a, F.PinStore.load(a, "demo"), server.base + "/file.xlsx")
    _fetch(b, F.PinStore.load(b, "demo"), server.base + "/file.xlsx")
    (t0, *_), (t1, *_) = server.requests[-2:]
    assert t1 - t0 >= F.MIN_HOST_INTERVAL_S * 0.95
    assert not (a.raw / ".hosts").exists()  # locks live in paths.host_lock_dir(), not in the layout


def test_policy_guards(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    for bad in ({"Cookie": "session=1"}, {"Cookie ": "x=1"}, {"X-Auth-Token": "secret"}, {"Authorization": "x"}):
        with pytest.raises(F.FetchError, match="not allowed"):
            _fetch(tmp_layout, store, server.base + "/file.xlsx", headers=bad)
    assert not server.requests  # refused before any request
    ok = _fetch(tmp_layout, store, server.base + "/file.xlsx", headers={"Accept": "*/*"})
    assert ok.sha256
    with pytest.raises(F.AccessBlocked, match="GSTN is not automated"):
        F.fetch_file(tmp_layout, store, source_id="gstn_gst_statistics", url=server.base + "/f.xlsx", name="f.xlsx")
    with pytest.raises(F.AccessBlocked, match="CBDT"):
        _fetch(tmp_layout, store, "https://www.incometaxindia.gov.in/x.pdf", name="x.pdf")
    with pytest.raises(UnknownSourceError):
        F.fetch_file(tmp_layout, store, source_id="nope", url=server.base + "/f.xlsx", name="f.xlsx")
    with pytest.raises(ValueError):
        _fetch(tmp_layout, store, server.base + "/file.xlsx", name="../escape.xlsx")


@pytest.mark.parametrize(
    "status, ctype, body, expect, blocked",
    [
        (200, "application/octet-stream", XLSX, "xlsx", False),
        (200, "text/html", CHALLENGE, "xlsx", True),
        (200, "text/html", b"<!DOCTYPE html><html><body>hi</body></html>", "pdf", True),
        (200, "application/pdf", b"%PDF-1.7 ...", "pdf", False),
        (200, "application/octet-stream", b"garbage", "xls", True),
        (200, "application/json", b'{"a": 1}', "json", False),
        (200, "text/html", b"<html>Just a moment...</html>", "json", True),
        (200, "text/html", b"<html><body>" + b"x" * 30000 + b"cf-chl</body></html>", "html", True),
        (200, "text/html", b"<html><body>An ordinary page</body></html>", "html", False),
        (200, "text/csv", b"a,b\n1,2\n", "csv", False),
        (403, "text/html", b"<html>Forbidden</html>", "xlsx", True),
        (429, "text/plain", b"slow down", "xlsx", True),
        (404, "text/plain", b"nope", "xlsx", False),  # a plain HTTP error, not a block
        (503, "text/html", b"<html>Just a moment... cf-chl</html>", "xlsx", True),  # challenge with 5xx
        (500, "text/html", b"<html>Internal error</html>", "xlsx", False),
        (200, "text/html", b"<html><form><input type=password></form></html>", "any", True),
    ],
)
def test_detect_block(status, ctype, body, expect, blocked):
    assert (F.detect_block(status, ctype, body, expect) is not None) == blocked


def test_detect_block_final_url():
    assert "sign-in" in F.detect_block(200, "text/html", b"<html>hi</html>", "html", final_url="https://x.org/login")
    assert F.detect_block(200, "text/html", b"<html>hi</html>", "html", final_url="https://x.org/data") is None


# ---------------------------------------------------------------------------------------------
# Phase 1 close-out (docs/phase1/FRAMEWORK_REQUESTS.md)
# ---------------------------------------------------------------------------------------------


def _ctx(layout, **kw):
    from pipeline.core.unit import FetchContext

    return FetchContext(unit="demo", sources=(SRC,), layout=layout, store=F.PinStore.load(layout, "demo"), **kw)


def test_reused_raw_path_takes_retrieved_at_from_its_sidecar(server, tmp_layout, monkeypatch):
    """trade_satellites-14: a run saved the file and sidecar, then crashed before saving the pin. The
    rerun gets the same bytes, reuses the path, and the pin must agree with the ORIGINAL sidecar."""
    t0 = dt.datetime(2026, 9, 29, 10, 47, 3, tzinfo=dt.UTC)
    monkeypatch.setattr(F, "_utc_now", lambda: t0)
    first = _fetch(tmp_layout, F.PinStore.load(tmp_layout, "demo"), server.base + "/file.xlsx")  # pin never saved
    monkeypatch.setattr(F, "_utc_now", lambda: t0 + dt.timedelta(seconds=28))
    store = F.PinStore.load(tmp_layout, "demo")
    again = _fetch(tmp_layout, store, server.base + "/file.xlsx")
    assert again.path == first.path
    assert store.pins[f"{SRC}/file.xlsx"]["retrieved_at"] == again.meta["retrieved_at"] == "2026-09-29T10:47:03Z"


def test_pin_save_retries_a_windows_sharing_violation(tmp_layout, monkeypatch):
    store = F.PinStore.load(tmp_layout, "demo")
    store.set(f"{SRC}/x.csv", {"sha256": "0" * 64, "retrieved_at": "2026-09-29T00:00:00Z", "path": "data/raw/x"})
    calls = []
    real = F.io.write_yaml

    def flaky(*a, **kw):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("another process has the file open")
        return real(*a, **kw)

    monkeypatch.setattr(F.io, "write_yaml", flaky)
    monkeypatch.setattr(F, "PIN_SAVE_BACKOFF_S", 0.01)
    store.save()
    assert len(calls) == 3 and not store.changed and store.path.exists()


def test_form_post_is_pinned_by_body_and_refuses_credentials(server, tmp_layout):
    store = F.PinStore.load(tmp_layout, "demo")
    form = {"__VIEWSTATE": "abc", "ctl00$date": "01/04/2023"}
    raw = _fetch(tmp_layout, store, server.base + "/allRel.aspx", name="rel.html", method="POST", form_body=form)
    sent = server.requests[-1][3]
    assert sent["Content-Type"] == "application/x-www-form-urlencoded" and sent["Sec-Fetch-Mode"] == "navigate"
    assert sent["Origin"] == server.base and "Cookie" not in sent
    assert b"ctl00$date" in raw.read_bytes()
    pin = store.pins[f"{SRC}/rel.html"]
    assert pin["body_type"] == "form" and pin["body_sha256"] == F.io.sha256_bytes(F.encode_form(form))
    assert raw.meta["request_body_type"] == "form" and raw.meta["request_body"] == form
    n = len(server.requests)
    assert _fetch(tmp_layout, store, server.base + "/allRel.aspx", name="rel.html", method="POST", form_body=form)
    assert len(server.requests) == n  # cached
    with pytest.raises(F.OfflineMissing, match="changed"):
        _fetch(
            tmp_layout, store, server.base + "/allRel.aspx", name="rel.html", method="POST",
            form_body={"__VIEWSTATE": "other"}, offline=True,
        )  # fmt: skip
    for bad in ({"_token": "x"}, {"password": "x"}, {"csrfmiddlewaretoken": "x"}, {"ASP.NET_SessionId": "x"}):
        with pytest.raises(F.FetchError, match="D1-7"):
            _fetch(tmp_layout, store, server.base + "/allRel.aspx", name="bad.html", method="POST", form_body=bad)
    with pytest.raises(ValueError, match="form_body"):
        _fetch(tmp_layout, store, server.base + "/allRel.aspx", name="bad.html", form_body=form)  # GET
    assert len(server.requests) == n
    # a JSON POST keeps the original three-key request spec (existing pins stay valid)
    assert set(F._request_spec("https://x.org/a", "POST", {"a": 1})) == {"url", "method", "body_sha256"}


def test_per_host_minimum_gap(server, tmp_layout, monkeypatch):
    monkeypatch.setitem(F.HOST_MIN_INTERVAL_S, "127.0.0.1", 0.8)
    store = F.PinStore.load(tmp_layout, "demo")
    _fetch(tmp_layout, store, server.base + "/api?a", name="a.json", method="POST", json_body={"i": 1})
    _fetch(tmp_layout, store, server.base + "/api?b", name="b.json", method="POST", json_body={"i": 2})
    (t0, *_), (t1, *_) = server.requests[-2:]
    assert t1 - t0 >= 0.8 * 0.95
    assert F.min_interval_s("https://rbidocs.rbi.org.in/rdocs/x.pdf") == 10.0
    assert F.min_interval_s("https://www.rbi.org.in/x") == F.MIN_HOST_INTERVAL_S


def test_legacy_tls_only_for_listed_hosts(server, tmp_layout, monkeypatch):
    import ssl

    assert F.needs_legacy_tls("https://api.mospi.gov.in/api/plfs/x") and not F.needs_legacy_tls(
        "https://mospi.gov.in/x"
    )
    ctx = F._ssl_context(True)
    assert ctx.options & ssl.OP_LEGACY_SERVER_CONNECT and ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
    assert not F._ssl_context(False).options & ssl.OP_LEGACY_SERVER_CONNECT
    seen: list[bool] = []
    real = F._ssl_context
    monkeypatch.setattr(F, "_ssl_context", lambda legacy=False: seen.append(legacy) or real(legacy))
    F.http_request(tmp_layout, server.base + "/file.xlsx")
    monkeypatch.setattr(F, "LEGACY_RENEGOTIATION_HOSTS", frozenset({"127.0.0.1"}))
    F.http_request(tmp_layout, server.base + "/file.xlsx")
    assert seen == [False, True]


def test_legacy_tls_is_chosen_per_redirect_hop(server, tmp_layout, monkeypatch):
    """A redirect from a listed host to another host drops the legacy context, and the other way
    round only the listed hop gets it (review of FRAMEWORK_REQUESTS #8)."""
    seen: list[bool] = []
    real = F._ssl_context
    monkeypatch.setattr(F, "_ssl_context", lambda legacy=False: seen.append(legacy) or real(legacy))
    monkeypatch.setattr(F, "LEGACY_RENEGOTIATION_HOSTS", frozenset({"127.0.0.1"}))
    r = F.http_request(tmp_layout, server.base + "/to-localhost")
    assert r.status == 200 and r.final_url.startswith("http://localhost:") and seen == [True, False]
    seen.clear()
    monkeypatch.setattr(F, "LEGACY_RENEGOTIATION_HOSTS", frozenset({"localhost"}))
    assert F.http_request(tmp_layout, server.base + "/to-localhost").status == 200
    assert seen == [False, True]


def test_challenged_host_is_not_contacted_on_a_redirect_hop(server, tmp_layout):
    target = f"http://localhost:{server.port}/file.xlsx"
    n = len(server.requests)
    with pytest.raises(F.ChallengeServed, match="earlier in this run"):
        F.http_request(tmp_layout, server.base + "/to-localhost", stop_hosts={F.host_key(target): "test"})
    assert [r[2] for r in server.requests[n:]] == ["/to-localhost"]  # the redirect target was never requested


def test_first_challenge_stops_the_host_for_the_run(server, tmp_layout):
    ctx = _ctx(tmp_layout)
    with pytest.raises(F.ChallengeServed, match="F5 BIG-IP") as e:
        ctx.fetch(SRC, server.base + "/challenge.xlsx", name="challenge.xlsx")
    assert isinstance(e.value, F.AccessBlocked) and e.value.host in ctx.challenged_hosts
    n = len(server.requests)
    with pytest.raises(F.ChallengeServed, match="earlier in this run"):
        ctx.fetch(SRC, server.base + "/file.xlsx", name="file.xlsx")
    assert len(server.requests) == n  # never contacted
    assert len([w for w in ctx.warnings if "bot challenge" in w]) == 1
    # a plain 403 (e.g. MoSPI's answer for a missing file) is not a challenge: the host stays usable
    ctx2 = _ctx(tmp_layout)
    with pytest.raises(F.AccessBlocked) as e2:
        ctx2.fetch(SRC, server.base + "/forbidden.xlsx", name="forbidden.xlsx")
    assert not isinstance(e2.value, F.ChallengeServed) and not ctx2.challenged_hosts
    assert ctx2.fetch(SRC, server.base + "/file.xlsx", name="file.xlsx").sha256


def test_is_pinned(server, tmp_layout):
    ctx = _ctx(tmp_layout)
    url = server.base + "/file.xlsx"
    assert not ctx.is_pinned(SRC, "file.xlsx")
    raw = ctx.fetch(SRC, url, name="file.xlsx")
    assert ctx.is_pinned(SRC, "file.xlsx") and ctx.is_pinned(SRC, "file.xlsx", url=url)
    assert not ctx.is_pinned(SRC, "file.xlsx", url=url + "?v=2")
    assert not _ctx(tmp_layout, refresh=True).is_pinned(SRC, "file.xlsx")
    raw.path.unlink()
    assert not ctx.is_pinned(SRC, "file.xlsx")
    assert ctx.requested == {f"{SRC}/file.xlsx"}
