"""Permission matrix tests: route x auth_state -> expected_status.

Tests the full matrix of:
- Public routes (anyone can access)
- Login-required routes (authenticated users)
- Admin-only routes (admin users only)

Against auth states:
- Auth disabled (all access)
- Auth enabled, no user (anonymous)
- Auth enabled, regular user
- Auth enabled, admin user
"""

import pytest
from unittest.mock import patch

from app.auth import User


# ---------------------------------------------------------------------------
# Route lists for matrix testing
# ---------------------------------------------------------------------------

# Routes that should ALWAYS return 200 (public, no auth needed)
PUBLIC_GET_ROUTES = [
    "/",
    "/health",
]

# Admin-only POST routes (all use _check_admin)
# Using dummy IDs — the 401/403 check happens before any data lookup
ADMIN_POST_ROUTES = [
    "/confirm/test-id-123",
    "/reject/test-id-123",
    "/api/identity/src-id/reject/tgt-id",
    "/api/identity/src-id/unreject/tgt-id",
    "/api/identity/tgt-id/merge/src-id",
    "/api/identity/test-id-123/rename",
    "/api/face/image_001:face0/detach",
    "/api/identity/test-id-123/skip",
    "/inbox/test-id-123/review",
    "/inbox/test-id-123/confirm",
    "/inbox/test-id-123/reject",
    "/identity/test-id-123/skip",
    "/identity/test-id-123/reset",
]

# Login-required POST routes (use _check_login)
LOGIN_POST_ROUTES = [
    # POST /upload requires login but also needs multipart form data
    # Tested separately below
]


class TestPublicRoutesAlwaysAccessible:
    """Public GET routes should return 200 regardless of auth state."""

    def test_public_routes_with_auth_disabled(self, client, auth_disabled):
        """Public routes work when auth is disabled."""
        for route in PUBLIC_GET_ROUTES:
            response = client.get(route)
            assert response.status_code == 200, f"{route} returned {response.status_code}"

    def test_public_routes_with_auth_enabled_no_user(self, client, auth_enabled, no_user):
        """Public routes work for anonymous users."""
        for route in PUBLIC_GET_ROUTES:
            response = client.get(route)
            assert response.status_code == 200, f"{route} returned {response.status_code}"

    def test_public_routes_with_auth_enabled_regular_user(self, client, auth_enabled, regular_user):
        """Public routes work for logged-in users."""
        for route in PUBLIC_GET_ROUTES:
            response = client.get(route)
            assert response.status_code == 200, f"{route} returned {response.status_code}"


class TestAdminRoutesAuthDisabled:
    """When auth is disabled, admin routes should succeed (not block)."""

    def test_admin_routes_pass_through_when_auth_disabled(self, client, auth_disabled):
        """Admin POST routes don't block when auth is disabled.

        They may return 404 (identity not found) or other errors,
        but NOT 401 or 403.
        """
        for route in ADMIN_POST_ROUTES:
            response = client.post(route, follow_redirects=False)
            assert response.status_code not in (401, 403), \
                f"{route} returned {response.status_code} with auth disabled — should pass through"


class TestAdminRoutesAnonymous:
    """When auth is enabled and user is anonymous, admin routes return 401."""

    def test_admin_routes_return_401_for_anonymous(self, client, auth_enabled, no_user):
        """Anonymous users get 401 on admin POST routes."""
        for route in ADMIN_POST_ROUTES:
            response = client.post(route, follow_redirects=False)
            assert response.status_code == 401, \
                f"{route} returned {response.status_code}, expected 401"

    def test_admin_routes_never_return_303_redirect(self, client, auth_enabled, no_user):
        """Admin POST routes NEVER return 303 redirect (HTMX would follow it).

        This is a critical regression guard: HTMX silently follows 303
        redirects and swaps the redirect target's HTML into the element,
        which breaks the page. Admin routes must return 401 so the
        htmx:beforeSwap handler can show the login modal.
        """
        for route in ADMIN_POST_ROUTES:
            response = client.post(route, follow_redirects=False)
            assert response.status_code != 303, \
                f"{route} returned 303 redirect — MUST use 401 for HTMX compatibility"


class TestAdminRoutesRegularUser:
    """When auth is enabled and user is non-admin, admin routes return 403."""

    def test_admin_routes_return_403_for_non_admin(self, client, auth_enabled, regular_user):
        """Non-admin users get 403 on admin POST routes."""
        for route in ADMIN_POST_ROUTES:
            response = client.post(route, follow_redirects=False)
            assert response.status_code == 403, \
                f"{route} returned {response.status_code}, expected 403"


class TestAdminRoutesAdminUser:
    """When auth is enabled and user is admin, admin routes proceed."""

    def test_admin_routes_pass_for_admin(self, client, auth_enabled, admin_user):
        """Admin users get past the auth check (may hit 404 for missing data)."""
        for route in ADMIN_POST_ROUTES:
            response = client.post(route, follow_redirects=False)
            # Should NOT be 401 or 403 — admin passes the auth check
            # May be 404 (identity not found), 409, 423, etc.
            assert response.status_code not in (401, 403), \
                f"{route} returned {response.status_code} for admin — auth check should pass"


class TestUploadRoutePermissions:
    """Upload route has login-required permission."""

    def test_upload_get_redirects_when_auth_enabled_no_user(self, client, auth_enabled, no_user):
        """GET /upload redirects to login when not authenticated."""
        response = client.get("/upload", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    def test_upload_get_accessible_when_auth_disabled(self, client, auth_disabled):
        """GET /upload is accessible when auth is disabled."""
        response = client.get("/upload")
        assert response.status_code == 200

    def test_upload_get_accessible_when_logged_in(self, client, auth_enabled, regular_user):
        """GET /upload is accessible for logged-in users."""
        response = client.get("/upload")
        assert response.status_code == 200

    def test_upload_post_rejects_anonymous_users(self, client, auth_enabled, no_user):
        """POST /upload rejects anonymous users.

        FastHTML validates required params (files) before calling the handler,
        so a bare POST returns 400. With proper multipart data, the handler
        returns 401 via _check_login. Either way, the upload is blocked.
        """
        response = client.post("/upload", follow_redirects=False)
        assert response.status_code in (400, 401), \
            f"Expected 400 or 401, got {response.status_code}"


class TestHtmxAuthBehavior:
    """HTMX-specific auth behavior tests."""

    def test_admin_route_returns_empty_body_on_401(self, client, auth_enabled, no_user):
        """401 responses should have empty body (not a redirect page).

        The htmx:beforeSwap handler checks for 401 and shows the login
        modal. If the response had content, HTMX might try to swap it.
        """
        response = client.post("/confirm/test-id-123", follow_redirects=False)
        assert response.status_code == 401
        assert response.text == "" or len(response.text.strip()) == 0

    def test_admin_route_returns_toast_on_403(self, client, auth_enabled, regular_user):
        """403 responses include a permission-denied toast."""
        response = client.post("/confirm/test-id-123", follow_redirects=False)
        assert response.status_code == 403
        assert "permission" in response.text.lower() or "toast" in response.text.lower()
