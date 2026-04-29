"""Tests for app/admin_db_routes.py — /api/admin/db-size endpoint."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient


@pytest.fixture
def db_size_app():
    """A minimal FastHTML app with the db-size route registered for testing.

    We don't piggy-back on app.main.app because that would couple this test to
    the (unrelated) main app's startup state. We build a tiny app with the
    same `_check_admin` interface."""
    from fasthtml.common import FastHTML

    app = FastHTML()

    # Register the route on this fresh app
    from app.admin_db_routes import register_admin_db_routes
    register_admin_db_routes(app)
    return app


def test_db_size_admin_allowed_returns_200(db_size_app):
    """An admin-authorized session returns the expected JSON shape."""
    fake_result = {
        "total_bytes": 524_288_000,
        "total_pretty": "500 MB",
        "top_tables": [
            {"name": "gedcom_individuals", "bytes": 1024, "pretty": "1024 bytes",
             "approx_rows": 100},
        ],
    }
    # _check_admin returns None when allowed.
    with patch("app.main._check_admin", return_value=None), \
         patch("app.admin_db_routes._query_db_size", return_value=fake_result):
        client = TestClient(db_size_app)
        resp = client.get("/api/admin/db-size")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_bytes"] == 524_288_000
    assert body["total_pretty"] == "500 MB"
    assert len(body["top_tables"]) == 1
    assert body["top_tables"][0]["name"] == "gedcom_individuals"
    assert body["status"] == "ok"  # 500 MB is well under 800 MB warn threshold
    assert body["thresholds"]["warn_bytes"] == 800 * 1024 * 1024


def test_db_size_status_warn_at_800mb(db_size_app):
    fake_result = {
        "total_bytes": 850 * 1024 * 1024,  # 850 MB
        "total_pretty": "850 MB",
        "top_tables": [],
    }
    with patch("app.main._check_admin", return_value=None), \
         patch("app.admin_db_routes._query_db_size", return_value=fake_result):
        client = TestClient(db_size_app)
        resp = client.get("/api/admin/db-size")
    assert resp.status_code == 200
    assert resp.json()["status"] == "warn"


def test_db_size_status_critical_at_1gb(db_size_app):
    fake_result = {
        "total_bytes": 1050 * 1024 * 1024,  # 1.05 GB
        "total_pretty": "1050 MB",
        "top_tables": [],
    }
    with patch("app.main._check_admin", return_value=None), \
         patch("app.admin_db_routes._query_db_size", return_value=fake_result):
        client = TestClient(db_size_app)
        resp = client.get("/api/admin/db-size")
    assert resp.status_code == 200
    assert resp.json()["status"] == "critical"


def test_db_size_status_ceiling_at_1100mb(db_size_app):
    fake_result = {
        "total_bytes": 1200 * 1024 * 1024,  # 1.2 GB > 1.1 GB ceiling
        "total_pretty": "1200 MB",
        "top_tables": [],
    }
    with patch("app.main._check_admin", return_value=None), \
         patch("app.admin_db_routes._query_db_size", return_value=fake_result):
        client = TestClient(db_size_app)
        resp = client.get("/api/admin/db-size")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ceiling"


def test_db_size_non_admin_blocked(db_size_app):
    """A non-admin session must be blocked. We simulate _check_admin returning
    a 403 Response — the endpoint must return that without querying the DB."""
    from starlette.responses import Response

    blocking = Response("forbidden", status_code=403)
    with patch("app.main._check_admin", return_value=blocking), \
         patch("app.admin_db_routes._query_db_size") as mock_query:
        client = TestClient(db_size_app)
        resp = client.get("/api/admin/db-size")
    assert resp.status_code == 403
    # Must have refused BEFORE touching the DB
    assert mock_query.call_count == 0


def test_db_size_unauthenticated_blocked(db_size_app):
    """A logged-out session: _check_admin returns 401 Response."""
    from starlette.responses import Response

    blocking = Response("unauthorized", status_code=401)
    with patch("app.main._check_admin", return_value=blocking), \
         patch("app.admin_db_routes._query_db_size") as mock_query:
        client = TestClient(db_size_app)
        resp = client.get("/api/admin/db-size")
    assert resp.status_code == 401
    assert mock_query.call_count == 0


def test_db_size_query_error_returns_503(db_size_app):
    """When the Supabase query fails, we return 503 with a sanitized message,
    not 500 (which Sentry would page)."""
    with patch("app.main._check_admin", return_value=None), \
         patch("app.admin_db_routes._query_db_size",
               return_value={"error": "connect failed: timeout"}):
        client = TestClient(db_size_app)
        resp = client.get("/api/admin/db-size")
    assert resp.status_code == 503
    assert "connect failed" in resp.json()["error"]


def test_db_size_password_in_error_is_redacted(db_size_app):
    """Defense in depth: if a connection error message includes 'password' or
    'auth', return a sanitized message — never leak credentials."""
    with patch("app.main._check_admin", return_value=None), \
         patch("app.admin_db_routes._query_db_size",
               return_value={"error": "FATAL: password authentication failed"}):
        client = TestClient(db_size_app)
        resp = client.get("/api/admin/db-size")
    assert resp.status_code == 503
    body = resp.json()
    assert "password" not in body["error"]
    assert body["error"] == "supabase admin connection failed"


def test_query_db_size_handles_missing_password():
    """Direct unit test of the helper: SUPABASE_DB_PASSWORD missing → error,
    no connection attempt."""
    from app import admin_db_routes
    with patch.dict("os.environ", {}, clear=False):
        import os
        os.environ.pop("SUPABASE_DB_PASSWORD", None)
        result = admin_db_routes._query_db_size()
    assert "error" in result
    assert "SUPABASE_DB_PASSWORD" in result["error"]


def test_register_admin_db_routes_can_be_called_multiple_times(db_size_app):
    """Idempotent registration — calling register_admin_db_routes twice on
    the same app should not crash even if it adds a duplicate route."""
    from app.admin_db_routes import register_admin_db_routes
    # First call already happened in fixture. Second call should not raise.
    register_admin_db_routes(db_size_app)
