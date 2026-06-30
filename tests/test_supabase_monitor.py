"""Unit tests for scripts/supabase_monitor.py (OPS-002, OD-015, Lesson 200).

Pure mocks — NO network. A fake httpx-style client returns canned responses so
every branch (healthy, over-quota, paused, no-token, transport error,
keep-alive) is exercised deterministically.
"""

from __future__ import annotations

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
    """Routes GET/POST by URL substring to canned FakeResponse objects.

    `get_map` / `post_map` map a URL-substring -> FakeResponse OR a callable
    raising to simulate a transport error.
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
                return resp
        raise AssertionError(f"unexpected URL: {url}")

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url))
        return self._resolve(self.get_map, url)

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        return self._resolve(self.post_map, url)

    def close(self):
        self.closed = True


HEALTH = "https://example.test/health"
REF = "testref123"


# --------------------------------------------------------------------------- #
# check_health_endpoint
# --------------------------------------------------------------------------- #
def test_health_ok():
    client = FakeClient(get_map={"/health": FakeResponse(200, {"supabase": "ok"})})
    r = mon.check_health_endpoint(HEALTH, client)
    assert r["ok"] is True
    assert r["supabase"] == "ok"


def test_health_skipped_is_healthy():
    # "skipped" is the in-app once-per-hour ping throttle — benign.
    client = FakeClient(get_map={"/health": FakeResponse(200, {"supabase": "skipped"})})
    r = mon.check_health_endpoint(HEALTH, client)
    assert r["ok"] is True


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
    r = mon.check_project_status("sbp_token", REF, client)
    assert r["ok"] is True
    assert r["status"] == "ACTIVE_HEALTHY"


def test_project_paused_alerts():
    client = FakeClient(get_map={"/v1/projects/": FakeResponse(200, {"status": "PAUSED"})})
    r = mon.check_project_status("sbp_token", REF, client)
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
    r = mon.check_project_status("sbp_token", REF, client)
    assert r["ok"] is False
    assert "401" in r["error"]


# --------------------------------------------------------------------------- #
# keep_alive
# --------------------------------------------------------------------------- #
def test_keep_alive_runs_select_1():
    client = FakeClient(post_map={"/database/query": FakeResponse(201, [{"?column?": 1}])})
    r = mon.keep_alive("sbp_token", REF, client)
    assert r["ok"] is True
    # the trivial query was actually sent
    assert any(call[0] == "POST" and call[2] == {"query": "SELECT 1"} for call in client.calls)


def test_keep_alive_no_token_skips():
    client = FakeClient()
    r = mon.keep_alive(None, REF, client)
    assert r["ok"] is False
    assert "skipped" in r["error"]
    assert client.calls == []


def test_keep_alive_failure_reported():
    client = FakeClient(post_map={"/database/query": FakeResponse(500, {})})
    r = mon.keep_alive("sbp_token", REF, client)
    assert r["ok"] is False


# --------------------------------------------------------------------------- #
# run_monitor orchestration
# --------------------------------------------------------------------------- #
def test_run_monitor_all_healthy_no_alert():
    client = FakeClient(
        get_map={
            "/health": FakeResponse(200, {"supabase": "ok"}),
            "/v1/projects/": FakeResponse(200, {"status": "ACTIVE_HEALTHY"}),
        }
    )
    report = mon.run_monitor(health_url=HEALTH, token="sbp", project_ref=REF, client=client)
    assert report["alert"] is False


def test_run_monitor_health_failure_alerts():
    client = FakeClient(
        get_map={
            "/health": FakeResponse(200, {"supabase": "error:402"}),
            "/v1/projects/": FakeResponse(200, {"status": "ACTIVE_HEALTHY"}),
        }
    )
    report = mon.run_monitor(health_url=HEALTH, token="sbp", project_ref=REF, client=client)
    assert report["alert"] is True


def test_run_monitor_project_paused_alerts():
    client = FakeClient(
        get_map={
            "/health": FakeResponse(200, {"supabase": "ok"}),
            "/v1/projects/": FakeResponse(200, {"status": "PAUSED"}),
        }
    )
    report = mon.run_monitor(health_url=HEALTH, token="sbp", project_ref=REF, client=client)
    assert report["alert"] is True


def test_run_monitor_no_token_skips_project_no_alert():
    # Health is fine; project status is SKIPPED (no token) → not an alert.
    client = FakeClient(get_map={"/health": FakeResponse(200, {"supabase": "ok"})})
    report = mon.run_monitor(health_url=HEALTH, token=None, project_ref=REF, client=client)
    assert report["alert"] is False
    statuses = {c["check"]: c["ok"] for c in report["checks"]}
    assert statuses["project_status"] is None


def test_run_monitor_keep_alive_failure_does_not_alert():
    client = FakeClient(
        get_map={
            "/health": FakeResponse(200, {"supabase": "ok"}),
            "/v1/projects/": FakeResponse(200, {"status": "ACTIVE_HEALTHY"}),
        },
        post_map={"/database/query": FakeResponse(500, {})},
    )
    report = mon.run_monitor(
        health_url=HEALTH, token="sbp", project_ref=REF, do_keep_alive=True, client=client
    )
    # keep-alive failed but the two health signals are green → no alert
    assert report["alert"] is False
    assert any(c["check"] == "keep_alive" and c["ok"] is False for c in report["checks"])


# --------------------------------------------------------------------------- #
# main() exit codes
# --------------------------------------------------------------------------- #
def test_main_requires_check_flag(capsys):
    import pytest

    with pytest.raises(SystemExit):
        mon.main([])


def test_main_exit_zero_on_healthy(monkeypatch):
    healthy = {"alert": False, "checks": [{"check": "health_endpoint", "ok": True, "supabase": "ok"}]}
    monkeypatch.setattr(mon, "run_monitor", lambda **kw: healthy)
    assert mon.main(["--check"]) == 0


def test_main_exit_one_on_alert(monkeypatch):
    bad = {"alert": True, "checks": [{"check": "health_endpoint", "ok": False, "error": "error:402"}]}
    monkeypatch.setattr(mon, "run_monitor", lambda **kw: bad)
    assert mon.main(["--check"]) == 1
