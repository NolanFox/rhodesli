"""Tests for identity suggestion evidence panel on person page (PRD-059 Phase 4)."""

import json
from unittest.mock import MagicMock, patch

import pytest
from starlette.testclient import TestClient

from app.auth import User
from app.main import app, load_registry

ADMIN_USER = User(id="test-admin-1", email="admin@rhodesli.test", is_admin=True)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def registry_snapshot(monkeypatch):
    registry = load_registry()
    monkeypatch.setattr("app.main.load_registry", lambda: registry)
    return registry


@pytest.fixture
def person_admin(auth_enabled):
    """Mock admin user for person_routes (which imports get_current_user from app.auth)."""
    with (
        patch("app.main.get_current_user", return_value=ADMIN_USER),
        patch("app.person_routes.get_current_user", return_value=ADMIN_USER),
    ):
        yield ADMIN_USER


def _get_any_identity(registry):
    """Get any identity with at least one face for a valid person page."""
    for identity in registry.list_identities(state=None):
        if identity.get("anchor_ids") or identity.get("candidate_ids"):
            return identity
    # Fall back to any identity
    identities = registry.list_identities(state=None)
    return identities[0] if identities else None


MOCK_SUGGESTION = {
    "id": "test-suggestion-001",
    "target_identity_id": "test-person-id",
    "family_id": "fox",
    "suggested_name": "Fox family member (score: 0.45)",
    "confidence": 0.45,
    "status": "PENDING",
    "evidence_json": {
        "family_cluster": {"score": 0.82, "raw_distance": 1.18, "threshold": 1.35},
        "co_occurrence": {"score": 0.65, "shared_photos_with_family": 8},
        "age_trajectory": {"score": 0.50, "reason": "neutral"},
        "gedcom_match": {"score": 0.50, "reason": "partial"},
        "testimony": {"score": 0, "entries": []},
        "provenance": {"score": 0, "labels": []},
    },
}


def _mock_supabase_with_suggestion(person_id=None):
    """Create a mock Supabase client that returns a PENDING suggestion."""
    suggestion = dict(MOCK_SUGGESTION)
    if person_id:
        suggestion["target_identity_id"] = person_id

    mock_resp = MagicMock()
    mock_resp.data = [suggestion]

    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.execute.return_value = mock_resp

    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_query
    return mock_sb


def _mock_supabase_empty():
    """Create a mock Supabase client that returns no suggestions."""
    mock_resp = MagicMock()
    mock_resp.data = []

    mock_query = MagicMock()
    mock_query.select.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.execute.return_value = mock_resp

    mock_sb = MagicMock()
    mock_sb.table.return_value = mock_query
    return mock_sb


class TestIdentitySuggestionPanel:
    """Tests for the identity suggestion evidence panel on person page."""

    def test_panel_renders_for_admin_with_pending(self, client, registry_snapshot, person_admin):
        """Admin sees identity suggestion card when PENDING suggestion exists."""
        identity = _get_any_identity(registry_snapshot)
        if not identity:
            pytest.skip("No identities available")
        person_id = identity["identity_id"]

        mock_sb = _mock_supabase_with_suggestion(person_id)
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            response = client.get(f"/person/{person_id}")

        assert response.status_code == 200
        html = response.text
        assert 'data-testid="identity-suggestion-card"' in html
        assert "Identity Suggestion" in html
        assert "Fox family member" in html

    def test_panel_hidden_for_nonadmin(self, client, registry_snapshot, auth_enabled, no_user):
        """Non-admin (anonymous) users do not see the identity suggestion card."""
        identity = _get_any_identity(registry_snapshot)
        if not identity:
            pytest.skip("No identities available")
        person_id = identity["identity_id"]

        response = client.get(f"/person/{person_id}")
        assert response.status_code == 200
        assert 'data-testid="identity-suggestion-card"' not in response.text

    def test_panel_hidden_when_no_suggestions(self, client, registry_snapshot, person_admin):
        """Admin sees no card when there are no PENDING suggestions."""
        identity = _get_any_identity(registry_snapshot)
        if not identity:
            pytest.skip("No identities available")
        person_id = identity["identity_id"]

        mock_sb = _mock_supabase_empty()
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            response = client.get(f"/person/{person_id}")

        assert response.status_code == 200
        assert 'data-testid="identity-suggestion-card"' not in response.text

    def test_signal_bars_render_all_six(self):
        """All 6 signal display names appear in the rendered panel."""
        from app.person_routes import _build_identity_suggestion_panel

        panel = _build_identity_suggestion_panel(MOCK_SUGGESTION)
        html = repr(panel)

        expected_labels = [
            "Family Resemblance",
            "Co-occurrence",
            "Age Consistency",
            "GEDCOM Match",
            "Testimony",
            "Photo Source",
        ]
        for label in expected_labels:
            assert label in html, f"Missing signal label: {label}"

    def test_accept_button_has_correct_endpoint(self):
        """Accept button hx-post targets the correct API endpoint."""
        from app.person_routes import _build_identity_suggestion_panel

        panel = _build_identity_suggestion_panel(MOCK_SUGGESTION)
        html = repr(panel)

        assert "/api/identity-suggestion/test-suggestion-001/accept" in html
        assert "/api/identity-suggestion/test-suggestion-001/reject" in html
        assert "/api/identity-suggestion/test-suggestion-001/needs-more" in html

    def test_supabase_read_failure_graceful(self, client, registry_snapshot, person_admin):
        """Page loads without error when Supabase read fails."""
        identity = _get_any_identity(registry_snapshot)
        if not identity:
            pytest.skip("No identities available")
        person_id = identity["identity_id"]

        def _failing_table(name):
            if name == "identity_suggestions":
                raise Exception("Connection timeout")
            # Return a default MagicMock for other tables (e.g. communities middleware)
            m = MagicMock()
            m.select.return_value = m
            m.eq.return_value = m
            m.limit.return_value = m
            m.execute.return_value = MagicMock(data=[])
            return m

        mock_sb = MagicMock()
        mock_sb.table.side_effect = _failing_table
        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            response = client.get(f"/person/{person_id}")

        assert response.status_code == 200
        assert 'data-testid="identity-suggestion-card"' not in response.text
