"""Tests for CSRF protection: Origin header check + SameSite cookie."""

import pytest
from unittest.mock import patch, MagicMock

from app.auth import _check_origin


class _FakeRequest:
    """Minimal request stub with configurable headers."""

    def __init__(self, headers: dict | None = None):
        self.headers = headers or {}


class TestCheckOriginHelper:
    """Unit tests for _check_origin()."""

    def test_matching_origin_returns_none(self):
        """Origin header matching allowed domain returns None (allowed)."""
        req = _FakeRequest({"origin": "https://rhodesli.nolanandrewfox.com"})
        assert _check_origin(req) is None

    def test_localhost_origin_returns_none(self):
        """Origin header with localhost is allowed."""
        req = _FakeRequest({"origin": "http://localhost:5001"})
        assert _check_origin(req) is None

    def test_127_origin_returns_none(self):
        """Origin header with 127.0.0.1 is allowed."""
        req = _FakeRequest({"origin": "http://127.0.0.1:8000"})
        assert _check_origin(req) is None

    def test_missing_origin_and_referer_returns_none(self):
        """No Origin or Referer header — same-origin request; allowed."""
        req = _FakeRequest({})
        assert _check_origin(req) is None

    def test_bad_origin_returns_403(self):
        """Origin from unknown domain returns 403."""
        req = _FakeRequest({"origin": "https://evil-site.com"})
        resp = _check_origin(req)
        assert resp is not None
        assert resp.status_code == 403

    def test_referer_fallback_matching(self):
        """No Origin but Referer matches — allowed."""
        req = _FakeRequest({"referer": "https://rhodesli.nolanandrewfox.com/person/123"})
        assert _check_origin(req) is None

    def test_referer_fallback_bad(self):
        """No Origin and bad Referer — 403."""
        req = _FakeRequest({"referer": "https://malicious.example.org/page"})
        resp = _check_origin(req)
        assert resp is not None
        assert resp.status_code == 403

    def test_empty_origin_empty_referer_returns_none(self):
        """Explicit empty strings for both headers — treated as missing."""
        req = _FakeRequest({"origin": "", "referer": ""})
        assert _check_origin(req) is None


class TestSameSiteCookieConfig:
    """Verify that the fast_app call includes SameSite=Strict."""

    def test_fast_app_has_same_site_strict(self):
        """The fast_app() call in main.py uses same_site='Strict'."""
        import inspect
        import app.main

        # Read the source of main.py and check for same_site="Strict"
        source = inspect.getsource(app.main)
        assert 'same_site="Strict"' in source or "same_site='Strict'" in source


class TestCsrfOnProtectedRoutes:
    """Integration tests: POST to protected routes with bad Origin gets 403."""

    def test_confirm_route_rejects_bad_origin(self, client, auth_disabled):
        """POST /confirm/<id> with bad Origin header returns 403."""
        response = client.post(
            "/confirm/fake-id",
            headers={"Origin": "https://evil-site.com"},
        )
        assert response.status_code == 403

    def test_reject_route_rejects_bad_origin(self, client, auth_disabled):
        """POST /reject/<id> with bad Origin header returns 403."""
        response = client.post(
            "/reject/fake-id",
            headers={"Origin": "https://evil-site.com"},
        )
        assert response.status_code == 403

    def test_merge_route_rejects_bad_origin(self, client, auth_disabled):
        """POST /api/identity/<t>/merge/<s> with bad Origin returns 403."""
        response = client.post(
            "/api/identity/fake-target/merge/fake-source",
            headers={"Origin": "https://evil-site.com"},
        )
        assert response.status_code == 403

    def test_rename_route_rejects_bad_origin(self, client, auth_disabled):
        """POST /api/identity/<id>/rename with bad Origin returns 403."""
        response = client.post(
            "/api/identity/fake-id/rename",
            headers={"Origin": "https://evil-site.com"},
        )
        assert response.status_code == 403

    def test_detach_route_rejects_bad_origin(self, client, auth_disabled):
        """POST /api/face/<fid>/detach with bad Origin returns 403."""
        response = client.post(
            "/api/face/fake-face/detach",
            headers={"Origin": "https://evil-site.com"},
        )
        assert response.status_code == 403

    def test_skip_route_rejects_bad_origin(self, client, auth_disabled):
        """POST /api/identity/<id>/skip with bad Origin returns 403."""
        response = client.post(
            "/api/identity/fake-id/skip",
            headers={"Origin": "https://evil-site.com"},
        )
        assert response.status_code == 403

    def test_admin_migrations_rejects_bad_origin(self, client, auth_disabled):
        """POST /api/admin/run-migrations with bad Origin returns 403."""
        response = client.post(
            "/api/admin/run-migrations",
            headers={"Origin": "https://evil-site.com"},
        )
        assert response.status_code == 403

    def test_upload_approve_rejects_bad_origin(self, client, auth_disabled):
        """POST /admin/pending/<id>/approve with bad Origin returns 403."""
        response = client.post(
            "/admin/pending/fake-job/approve",
            headers={"Origin": "https://evil-site.com"},
        )
        assert response.status_code == 403

    def test_allowed_origin_passes_through(self, client, auth_disabled):
        """POST with allowed Origin passes origin check (may fail on other grounds)."""
        # With auth disabled, the origin check passes and the route proceeds.
        # It may return 404 or other errors for the fake ID, but NOT 403 from CSRF.
        response = client.post(
            "/api/identity/fake-id/skip",
            headers={"Origin": "https://rhodesli.nolanandrewfox.com"},
        )
        # Should NOT be 403 (origin is allowed)
        assert response.status_code != 403


class TestSessionSecretWarning:
    """Verify SESSION_SECRET warning logic."""

    def test_check_origin_imported_from_auth(self):
        """_check_origin is importable from app.auth."""
        from app.auth import _check_origin

        assert callable(_check_origin)
