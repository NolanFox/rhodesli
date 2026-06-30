"""Unit tests for scripts/supabase_monitor.py (OPS-002, OD-015, Lesson 200).

Pure mocks — NO network. A fake httpx-style client returns canned responses so
every branch (healthy, over-quota, paused, no-token, transport error,
keep-alive, inconclusive, secret-redaction) is exercised deterministically.
"""

from __future__ import annotations

import json

import pytest

import scripts.supabase_monitor as mon


# --------------------------------------------------------------------------- #
# Fake HTTP client
# --------------------------------------------------------------------------- #
class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {}

    def json(self):
        return self._body


class FakeClient:
    """Routes GET/POST by URL substring to canned responses.

    A mapping value may be a FakeResponse, an Exception INSTANCE (raised), or a
    zero-arg callable (called; may raise) — to simulate transport errors.
    `calls` records (method, url, headers, json) so tests can assert that the
    Management API token is sent ONLY in headers.
    """

    def __init__(self, get_map=None, post_map=None):
        self.get_map = get_map or {}
        self.post_map = post_map or {}
        self.calls = []
        self.closed = False

    def _resolve(self, mapping, url):
        for needle, resp in mapping.items():
            if needle in url:
                if isinstance(resp, Exception):
                    raise resp
                if callable(resp):
                    return resp()
                return resp
        raise AssertionError(f"unexpected URL: {url}")

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url, headers or {}, None))
        return self._resolve(self.get_map, url)

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("POST", url, headers or {}, json))
        return self._resolve(self.post_map, url)

    def close(self):
        self.closed = True


HEALTH = "https://example.test/health"
SB_URL = "https://proj.supabase.co"
ANON = "anon_key_123"
REF = "testref123"
TOKEN = "sbp_secret_token_value"


def _healthy_maps():
    return {
        "/auth/v1/health": FakeResponse(200, {}),
        "/health": FakeResponse(200, {"supabase": "ok"}),
        "/v1/projects/": FakeResponse(200, {"status": "ACTIVE_HEALTHY"}),
    }


# --------------------------------------------------------------------------- #
# check_supabase_rest (PRIMARY fresh probe)
# --------------------------------------------------------------------------- #
def test_rest_probe_ok():
    client = FakeClient(get_map={"/auth/v1/health": FakeResponse(200, {})})
    r = mon.check_supabase_rest(SB_URL, ANON, client)
    assert r["ok"] is True


def test_rest_probe_402_over_quota_fails():
    client = FakeClient(get_map={"/auth/v1/health": FakeResponse(402, {})})
    r = mon.check_supabase_rest(SB_URL, ANON, client)
    assert r["ok"] is False
    assert "402" in r["error"]


def test_rest_probe_transport_error_fails():
    client = FakeClient(get_map={"/auth/v1/health": RuntimeError("NXDOMAIN")})
    r = mon.check_supabase_rest(SB_URL, ANON, client)
    assert r["ok"] is False
    assert "RuntimeError" in r["error"]


def test_rest_probe_no_creds_skips():
    client = FakeClient()
    r = mon.check_supabase_rest(None, None, client)
    assert r["ok"] is None
    assert client.calls == []


def test_rest_probe_sends_apikey_header_only():
    client = FakeClient(get_map={"/auth/v1/health": FakeResponse(200, {})})
    mon.check_supabase_rest(SB_URL, ANON, client)
    _, url, headers, _ = client.calls[0]
    assert headers.get("apikey") == ANON
    assert ANON not in url  # never in the URL


# --------------------------------------------------------------------------- #
# check_health_endpoint
# --------------------------------------------------------------------------- #
def test_health_ok():
    client = FakeClient(get_map={"/health": FakeResponse(200, {"supabase": "ok"})})
    r = mon.check_health_endpoint(HEALTH, client)
    assert r["ok"] is True
    assert r["supabase"] == "ok"


def test_health_skipped_is_inconclusive_not_pass():
    # Codex P1: "skipped" is the throttled no-signal value — NOT a pass.
    client = FakeClient(get_map={"/health": FakeResponse(200, {"supabase": "skipped"})})
    r = mon.check_health_endpoint(HEALTH, client)
    assert r["ok"] is None  # inconclusive, neither pass nor alert


def test_health_over_quota_error_field():
    client = FakeClient(get_map={"/health": FakeResponse(200, {"supabase": "error:402"})})
    r = mon.check_health_endpoint(HEALTH, client)
    assert r["ok"] is False
    assert "error:402" in r["error"]


def test_health_not_configured():
    client = FakeClient(get_map={"/health": FakeResponse(200, {"supabase": "not_configured"})})
    r = mon.check_health_endpoint(HEALTH, client)
    assert r["ok"] is False


def test_health_non_200():
    client = FakeClient(get_map={"/health": FakeResponse(503, {})})
    r = mon.check_health_endpoint(HEALTH, client)
    assert r["ok"] is False
    assert "503" in r["error"]


def test_health_transport_error():
    client = FakeClient(get_map={"/health": RuntimeError("dns fail")})
    r = mon.check_health_endpoint(HEALTH, client)
    assert r["ok"] is False
    assert "RuntimeError" in r["error"]


# --------------------------------------------------------------------------- #
# check_project_status
# --------------------------------------------------------------------------- #
def test_project_active_healthy():
    client = FakeClient(get_map={"/v1/projects/": FakeResponse(200, {"status": "ACTIVE_HEALTHY"})})
    r = mon.check_project_status(TOKEN, REF, client)
    assert r["ok"] is True
    assert r["status"] == "ACTIVE_HEALTHY"


def test_project_paused_alerts():
    client = FakeClient(get_map={"/v1/projects/": FakeResponse(200, {"status": "PAUSED"})})
    r = mon.check_project_status(TOKEN, REF, client)
    assert r["ok"] is False
    assert "PAUSED" in r["error"]


def test_project_no_token_skips_by_default():
    client = FakeClient()
    r = mon.check_project_status(None, REF, client)
    assert r["ok"] is None  # skipped, not a failure
    assert "not set" in r["error"]
    assert client.calls == []  # no network call attempted


def test_project_no_token_required_fails():
    client = FakeClient()
    r = mon.check_project_status(None, REF, client, require=True)
    assert r["ok"] is False


def test_project_mgmt_non_200():
    client = FakeClient(get_map={"/v1/projects/": FakeResponse(401, {})})
    r = mon.check_project_status(TOKEN, REF, client)
    assert r["ok"] is False
    assert "401" in r["error"]


def test_project_mgmt_transport_exception_fails():
    client = FakeClient(get_map={"/v1/projects/": ConnectionError("boom")})
    r = mon.check_project_status(TOKEN, REF, client)
    assert r["ok"] is False
    assert "ConnectionError" in r["error"]


def test_project_sends_bearer_header_only():
    client = FakeClient(get_map={"/v1/projects/": FakeResponse(200, {"status": "ACTIVE_HEALTHY"})})
    mon.check_project_status(TOKEN, REF, client)
    _, url, headers, _ = client.calls[0]
    assert headers.get("Authorization") == f"Bearer {TOKEN}"
    assert TOKEN not in url


# --------------------------------------------------------------------------- #
# keep_alive
# --------------------------------------------------------------------------- #
def test_keep_alive_runs_select_1():
    client = FakeClient(post_map={"/database/query": FakeResponse(201, [{"?column?": 1}])})
    r = mon.keep_alive(TOKEN, REF, client)
    assert r["ok"] is True
    # the trivial query was actually sent
    assert any(c[0] == "POST" and c[3] == {"query": "SELECT 1"} for c in client.calls)


def test_keep_alive_no_token_skips():
    client = FakeClient()
    r = mon.keep_alive(None, REF, client)
    assert r["ok"] is False
    assert "skipped" in r["error"]
    assert client.calls == []


def test_keep_alive_failure_reported():
    client = FakeClient(post_map={"/database/query": FakeResponse(500, {})})
    r = mon.keep_alive(TOKEN, REF, client)
    assert r["ok"] is False


def test_keep_alive_transport_exception_reported():
    client = FakeClient(post_map={"/database/query": TimeoutError("slow")})
    r = mon.keep_alive(TOKEN, REF, client)
    assert r["ok"] is False
    assert "TimeoutError" in r["error"]


# --------------------------------------------------------------------------- #
# run_monitor orchestration
# --------------------------------------------------------------------------- #
def test_run_monitor_all_healthy_no_alert():
    client = FakeClient(get_map=_healthy_maps())
    report = mon.run_monitor(
        health_url=HEALTH, token=TOKEN, project_ref=REF, supabase_url=SB_URL, anon_key=ANON, client=client
    )
    assert report["alert"] is False
    assert report["inconclusive"] is False


def test_run_monitor_rest_402_alerts_even_if_health_skipped():
    # The exact masking failure from Codex P1: app reports "skipped" but the
    # fresh REST probe sees a 402 → must alert.
    maps = _healthy_maps()
    maps["/auth/v1/health"] = FakeResponse(402, {})
    maps["/health"] = FakeResponse(200, {"supabase": "skipped"})
    client = FakeClient(get_map=maps)
    report = mon.run_monitor(
        health_url=HEALTH, token=TOKEN, project_ref=REF, supabase_url=SB_URL, anon_key=ANON, client=client
    )
    assert report["alert"] is True


def test_run_monitor_health_failure_alerts():
    maps = _healthy_maps()
    maps["/health"] = FakeResponse(200, {"supabase": "error:402"})
    client = FakeClient(get_map=maps)
    report = mon.run_monitor(
        health_url=HEALTH, token=TOKEN, project_ref=REF, supabase_url=SB_URL, anon_key=ANON, client=client
    )
    assert report["alert"] is True


def test_run_monitor_project_paused_alerts():
    maps = _healthy_maps()
    maps["/v1/projects/"] = FakeResponse(200, {"status": "PAUSED"})
    client = FakeClient(get_map=maps)
    report = mon.run_monitor(
        health_url=HEALTH, token=TOKEN, project_ref=REF, supabase_url=SB_URL, anon_key=ANON, client=client
    )
    assert report["alert"] is True


def test_run_monitor_all_inconclusive_warns_no_alert():
    # No creds (rest skipped), health "skipped", no token (project skipped) → WARN.
    client = FakeClient(get_map={"/health": FakeResponse(200, {"supabase": "skipped"})})
    report = mon.run_monitor(
        health_url=HEALTH, token=None, project_ref=REF, supabase_url=None, anon_key=None, client=client
    )
    assert report["alert"] is False
    assert report["inconclusive"] is True


def test_run_monitor_require_mgmt_no_token_alerts():
    # Codex P2: require_mgmt + missing token must alert through run_monitor.
    client = FakeClient(
        get_map={
            "/auth/v1/health": FakeResponse(200, {}),
            "/health": FakeResponse(200, {"supabase": "ok"}),
        }
    )
    report = mon.run_monitor(
        health_url=HEALTH,
        token=None,
        project_ref=REF,
        supabase_url=SB_URL,
        anon_key=ANON,
        require_mgmt=True,
        client=client,
    )
    assert report["alert"] is True


def test_run_monitor_keep_alive_failure_does_not_alert():
    maps = _healthy_maps()
    client = FakeClient(get_map=maps, post_map={"/database/query": FakeResponse(500, {})})
    report = mon.run_monitor(
        health_url=HEALTH,
        token=TOKEN,
        project_ref=REF,
        supabase_url=SB_URL,
        anon_key=ANON,
        do_keep_alive=True,
        client=client,
    )
    assert report["alert"] is False
    assert any(c["check"] == "keep_alive" and c["ok"] is False for c in report["checks"])


# --------------------------------------------------------------------------- #
# Secret redaction — token must never appear in formatted/JSON output
# --------------------------------------------------------------------------- #
def test_token_never_appears_in_output():
    maps = _healthy_maps()
    maps["/v1/projects/"] = FakeResponse(200, {"status": "PAUSED"})  # force a populated report
    client = FakeClient(get_map=maps, post_map={"/database/query": FakeResponse(500, {})})
    report = mon.run_monitor(
        health_url=HEALTH,
        token=TOKEN,
        project_ref=REF,
        supabase_url=SB_URL,
        anon_key=ANON,
        do_keep_alive=True,
        client=client,
    )
    text = mon._format_report(report)
    assert TOKEN not in text
    assert ANON not in text
    assert TOKEN not in json.dumps(report)
    assert ANON not in json.dumps(report)


# --------------------------------------------------------------------------- #
# main() exit codes + output streams
# --------------------------------------------------------------------------- #
def test_main_requires_check_flag():
    with pytest.raises(SystemExit):
        mon.main([])


def test_main_exit_zero_on_healthy(monkeypatch, capsys):
    healthy = {"alert": False, "inconclusive": False, "checks": [{"check": "supabase_rest", "ok": True}]}
    monkeypatch.setattr(mon, "run_monitor", lambda **kw: healthy)
    assert mon.main(["--check"]) == 0
    captured = capsys.readouterr()
    assert "OK:" in captured.out
    assert captured.err == ""


def test_main_exit_one_on_alert_prints_alert_to_stderr(monkeypatch, capsys):
    bad = {"alert": True, "inconclusive": False, "checks": [{"check": "supabase_rest", "ok": False, "error": "HTTP 402"}]}
    monkeypatch.setattr(mon, "run_monitor", lambda **kw: bad)
    assert mon.main(["--check"]) == 1
    captured = capsys.readouterr()
    assert "ALERT:" in captured.err  # alerts go to stderr
    assert captured.out == ""


def test_main_json_output(monkeypatch, capsys):
    rep = {"alert": False, "inconclusive": False, "checks": [{"check": "supabase_rest", "ok": True}]}
    monkeypatch.setattr(mon, "run_monitor", lambda **kw: rep)
    assert mon.main(["--check", "--json"]) == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["alert"] is False


def test_main_require_mgmt_threads_through(monkeypatch):
    seen = {}

    def fake_run(**kw):
        seen.update(kw)
        return {"alert": False, "inconclusive": False, "checks": []}

    monkeypatch.setattr(mon, "run_monitor", fake_run)
    mon.main(["--check", "--require-mgmt"])
    assert seen["require_mgmt"] is True
