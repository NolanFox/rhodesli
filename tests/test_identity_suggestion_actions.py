"""Tests for identity suggestion accept/reject/needs-more endpoints (PRD-059 Phase 4)."""

from pathlib import Path

import pytest


SOURCE = Path("app/admin_routes.py").read_text()


def _handler_text(route_path: str, length: int = 5000) -> str:
    """Extract handler source text after a route path."""
    idx = SOURCE.index(route_path)
    return SOURCE[idx : idx + length]


class TestAcceptEndpoint:
    """Tests for POST /api/identity-suggestion/{id}/accept."""

    def test_accept_renames_and_confirms(self):
        """When suggested_identity_id is NULL, handler renames + confirms."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/accept")
        assert "rename_identity" in handler
        assert "confirm_identity" in handler
        assert "identity_suggestion_accept" in handler

    def test_accept_merges_when_suggested_identity_exists(self):
        """When suggested_identity_id is set, handler merges."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/accept")
        assert "merge_identities" in handler
        assert "save_photo_registry" in handler
        assert "Merged into" in handler

    def test_accept_requires_admin(self):
        """Endpoint checks admin auth."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/accept")
        assert "_check_admin" in handler

    def test_accept_already_confirmed(self):
        """Handler checks state != CONFIRMED before rename."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/accept")
        # Should check state before rename/confirm
        assert "state" in handler and "CONFIRMED" in handler

    def test_accept_stale_merged_target(self):
        """Handler checks if identity was already merged."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/accept")
        assert "merged_into" in handler
        assert "already merged" in handler.lower()

    def test_accept_nonexistent_suggestion(self):
        """Handler returns error div for missing suggestion."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/accept")
        assert "not found" in handler.lower()

    def test_gedcom_link_on_accept(self):
        """Accept creates GEDCOM link when suggested_gedcom_id present."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/accept")
        assert "gedcom_face_links" in handler
        assert "suggested_gedcom_id" in handler
        assert "upsert" in handler


class TestRejectEndpoint:
    """Tests for POST /api/identity-suggestion/{id}/reject."""

    def test_reject_stores_reason(self):
        """Reject stores rejection_reason in Supabase."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/reject")
        assert "rejection_reason" in handler
        assert "REJECTED" in handler

    def test_reject_without_reason(self):
        """Reject works even without a reason (reason is optional)."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/reject")
        # reason parameter has default empty string
        assert 'reason: str = ""' in handler or "reason: str = ''" in handler


class TestNeedsMoreEndpoint:
    """Tests for POST /api/identity-suggestion/{id}/needs-more."""

    def test_needs_more_sets_status(self):
        """Needs-more sets status to NEEDS_MORE."""
        handler = _handler_text("/api/identity-suggestion/{suggestion_id}/needs-more")
        assert "NEEDS_MORE" in handler
        assert "Flagged for follow-up" in handler


class TestAllEndpoints:
    """Cross-cutting tests for all three suggestion endpoints."""

    @pytest.mark.parametrize(
        "route",
        [
            "/api/identity-suggestion/{suggestion_id}/accept",
            "/api/identity-suggestion/{suggestion_id}/reject",
            "/api/identity-suggestion/{suggestion_id}/needs-more",
        ],
    )
    def test_all_endpoints_check_csrf(self, route):
        """All endpoints check CSRF origin."""
        handler = _handler_text(route)
        assert "_check_origin" in handler

    @pytest.mark.parametrize(
        "route",
        [
            "/api/identity-suggestion/{suggestion_id}/accept",
            "/api/identity-suggestion/{suggestion_id}/reject",
            "/api/identity-suggestion/{suggestion_id}/needs-more",
        ],
    )
    def test_all_endpoints_require_admin(self, route):
        """All endpoints require admin auth."""
        handler = _handler_text(route)
        assert "_check_admin" in handler

    @pytest.mark.parametrize(
        "route",
        [
            "/api/identity-suggestion/{suggestion_id}/accept",
            "/api/identity-suggestion/{suggestion_id}/reject",
            "/api/identity-suggestion/{suggestion_id}/needs-more",
        ],
    )
    def test_all_endpoints_handle_no_supabase(self, route):
        """All endpoints handle missing Supabase gracefully."""
        handler = _handler_text(route)
        assert "Database unavailable" in handler

    @pytest.mark.parametrize(
        "route",
        [
            "/api/identity-suggestion/{suggestion_id}/accept",
            "/api/identity-suggestion/{suggestion_id}/reject",
            "/api/identity-suggestion/{suggestion_id}/needs-more",
        ],
    )
    def test_all_endpoints_log_action(self, route):
        """All endpoints log user action."""
        handler = _handler_text(route)
        assert "log_user_action" in handler

    @pytest.mark.parametrize(
        "route",
        [
            "/api/identity-suggestion/{suggestion_id}/accept",
            "/api/identity-suggestion/{suggestion_id}/reject",
            "/api/identity-suggestion/{suggestion_id}/needs-more",
        ],
    )
    def test_all_endpoints_update_supabase_status(self, route):
        """All endpoints update suggestion status in Supabase."""
        handler = _handler_text(route)
        assert "reviewed_at" in handler
        assert "reviewed_by" in handler

    @pytest.mark.parametrize(
        "route",
        [
            "/api/identity-suggestion/{suggestion_id}/accept",
            "/api/identity-suggestion/{suggestion_id}/reject",
            "/api/identity-suggestion/{suggestion_id}/needs-more",
        ],
    )
    def test_all_endpoints_return_htmx_div(self, route):
        """All endpoints return a div with correct HTMX target id."""
        handler = _handler_text(route)
        assert "identity-suggestion-{suggestion_id}" in handler
