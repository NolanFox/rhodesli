"""Integration tests for app/admin_rhodes_inbox_routes.py (Session 161 Phase 6).

Verifies the 4 admin routes:
  - GET  /admin/rhodes-inbox
  - GET  /admin/rhodes-inbox/<slug>
  - POST /admin/rhodes-inbox/<slug>/approve
  - POST /admin/rhodes-inbox/<slug>/reject

Auth + production-gate matrix:
  - Production (RAILWAY_ENVIRONMENT set) → all routes 404
  - rhodes-wiki path absent → all routes 404
  - Non-admin session → routes return 401 / 403 via _check_admin
  - Admin session → routes work

Mirrors the test_admin_db_routes.py pattern: build a minimal FastHTML app
with just our routes registered, so the test doesn't depend on app.main's
startup state.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient


# Reuse the rhodes_inbox test fixture
from tests.test_rhodes_inbox import MINIMAL_POST


@pytest.fixture
def fake_inbox(tmp_path, monkeypatch):
    """Same setup as test_rhodes_inbox.fake_inbox."""
    root = tmp_path / "rhodes-wiki"
    (root / "inbox" / "pending" / "2026-04-28_2360240064471306").mkdir(parents=True)
    (root / "inbox" / "approved").mkdir()
    (root / "inbox" / "rejected").mkdir()
    post_path = root / "inbox" / "pending" / "2026-04-28_2360240064471306" / "post.json"
    post_path.write_text(json.dumps(MINIMAL_POST), encoding="utf-8")
    monkeypatch.setenv("RHODES_WIKI_ROOT", str(root))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    return root


@pytest.fixture
def admin_inbox_app():
    """A minimal FastHTML app with just the 4 admin routes registered."""
    from fasthtml.common import FastHTML
    app = FastHTML()
    from app.admin_rhodes_inbox_routes import register_admin_rhodes_inbox_routes
    register_admin_rhodes_inbox_routes(app)
    return app


# ---------------------------------------------------------------------------
# Production gate (Codex P1-2)
# ---------------------------------------------------------------------------

def test_list_route_404_on_railway(fake_inbox, admin_inbox_app, monkeypatch):
    """All routes MUST return 404 when RAILWAY_ENVIRONMENT is set."""
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    client = TestClient(admin_inbox_app)
    resp = client.get("/admin/rhodes-inbox")
    assert resp.status_code == 404


def test_detail_route_404_on_railway(fake_inbox, admin_inbox_app, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    client = TestClient(admin_inbox_app)
    resp = client.get("/admin/rhodes-inbox/2026-04-28_2360240064471306")
    assert resp.status_code == 404


def test_approve_route_404_on_railway(fake_inbox, admin_inbox_app, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    client = TestClient(admin_inbox_app)
    resp = client.post("/admin/rhodes-inbox/2026-04-28_2360240064471306/approve")
    assert resp.status_code == 404


def test_reject_route_404_on_railway(fake_inbox, admin_inbox_app, monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    client = TestClient(admin_inbox_app)
    resp = client.post("/admin/rhodes-inbox/2026-04-28_2360240064471306/reject", data={"reason": "no"})
    assert resp.status_code == 404


def test_routes_404_when_path_absent(tmp_path, admin_inbox_app, monkeypatch):
    """All routes MUST return 404 when ~/rhodes-wiki/inbox/ doesn't exist."""
    monkeypatch.setenv("RHODES_WIKI_ROOT", str(tmp_path / "does-not-exist"))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    client = TestClient(admin_inbox_app)
    for path in [
        "/admin/rhodes-inbox",
        "/admin/rhodes-inbox/2026-04-28_2360240064471306",
    ]:
        resp = client.get(path)
        assert resp.status_code == 404, f"GET {path} expected 404, got {resp.status_code}"


# ---------------------------------------------------------------------------
# Admin auth gate
# ---------------------------------------------------------------------------

def test_list_route_blocked_without_admin(fake_inbox, admin_inbox_app):
    """When _check_admin returns a 401/403 response, the list route must
    surface it. (Default test app has auth disabled → returns None → allowed;
    so we patch _check_admin to simulate a real auth failure.)"""
    from starlette.responses import Response as StarletteResponse
    with patch("app.main._check_admin", return_value=StarletteResponse("unauth", status_code=401)):
        client = TestClient(admin_inbox_app)
        resp = client.get("/admin/rhodes-inbox")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Slug validation (Codex P0-2)
# ---------------------------------------------------------------------------

def test_detail_route_rejects_path_traversal_slug(fake_inbox, admin_inbox_app):
    """A path-traversal slug must 400 before any filesystem op."""
    with patch("app.main._check_admin", return_value=None):
        client = TestClient(admin_inbox_app)
        resp = client.get("/admin/rhodes-inbox/..%2F..%2Fetc%2Fpasswd")
    # Either 400 (caught by _validate_slug) or 404 (caught by routing)
    assert resp.status_code in (400, 404)


def test_approve_route_rejects_path_traversal_slug(fake_inbox, admin_inbox_app):
    """POST approve with traversal slug must 400 before any Supabase op."""
    with patch("app.main._check_admin", return_value=None), \
         patch("app.auth._check_origin", return_value=None):
        client = TestClient(admin_inbox_app)
        resp = client.post("/admin/rhodes-inbox/..%2F..%2Fetc/approve")
    assert resp.status_code in (400, 404)


# ---------------------------------------------------------------------------
# Happy path: list view
# ---------------------------------------------------------------------------

def test_list_route_shows_session_160_entry(fake_inbox, admin_inbox_app):
    """The list view renders the fixture's pending entry."""
    with patch("app.main._check_admin", return_value=None):
        client = TestClient(admin_inbox_app)
        resp = client.get("/admin/rhodes-inbox")
    assert resp.status_code == 200
    body = resp.text
    assert "Martha Girgenti" in body
    assert "2026-04-28_2360240064471306" in body
    # Status badge for pending should appear
    assert "pending" in body.lower()


def test_list_view_renders_all_three_state_tabs(fake_inbox, admin_inbox_app):
    """List view always shows Pending / Approved / Rejected tabs."""
    with patch("app.main._check_admin", return_value=None):
        client = TestClient(admin_inbox_app)
        resp = client.get("/admin/rhodes-inbox")
    assert resp.status_code == 200
    body = resp.text.lower()
    assert "pending" in body
    assert "approved" in body
    assert "rejected" in body


# ---------------------------------------------------------------------------
# Happy path: detail view
# ---------------------------------------------------------------------------

def test_detail_route_renders_caption_and_comments(fake_inbox, admin_inbox_app):
    """The detail view renders the caption and all comments."""
    with patch("app.main._check_admin", return_value=None), \
         patch("app.rhodes_inbox._supabase_client", return_value=None):
        client = TestClient(admin_inbox_app)
        resp = client.get("/admin/rhodes-inbox/2026-04-28_2360240064471306")
    assert resp.status_code == 200
    body = resp.text
    assert "Edward and Renee Menasche" in body
    assert "Stella Hanan Cohen" in body  # commenter
    assert "April Merdjan" in body  # commenter


def test_detail_route_shows_approve_and_reject_forms(fake_inbox, admin_inbox_app):
    with patch("app.main._check_admin", return_value=None), \
         patch("app.rhodes_inbox._supabase_client", return_value=None):
        client = TestClient(admin_inbox_app)
        resp = client.get("/admin/rhodes-inbox/2026-04-28_2360240064471306")
    body = resp.text
    assert "approve" in body.lower()
    assert "reject" in body.lower()


def test_detail_route_404_on_unknown_slug(fake_inbox, admin_inbox_app):
    with patch("app.main._check_admin", return_value=None):
        client = TestClient(admin_inbox_app)
        resp = client.get("/admin/rhodes-inbox/2026-04-29_doesnotexist000")
    assert resp.status_code == 404
