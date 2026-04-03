"""Tests for identity suggestion UI panel and review endpoints (PRD-059 Phase 4)."""

import json
from unittest.mock import MagicMock, patch

import pytest


# --- Signal bar rendering ---


class TestRenderSignalBar:
    def test_high_score_green_bar(self):
        from app.person_routes import _render_signal_bar

        result = _render_signal_bar("Family Cluster", 0.85, "Albert Fox")
        html = repr(result)
        assert "Family Cluster" in html
        assert "0.85" in html
        assert "bg-emerald-500" in html

    def test_medium_score_amber_bar(self):
        from app.person_routes import _render_signal_bar

        result = _render_signal_bar("Co-occurrence", 0.50, "3 shared photos")
        html = repr(result)
        assert "bg-amber-500" in html
        assert "0.50" in html

    def test_low_score_slate_bar(self):
        from app.person_routes import _render_signal_bar

        result = _render_signal_bar("Testimony", 0.10)
        html = repr(result)
        assert "bg-slate-500" in html


# --- Evidence panel rendering ---


SAMPLE_SUGGESTION = {
    "id": "suggestion-uuid-1",
    "target_identity_id": "test-id",
    "suggested_name": "Unidentified Person 42",
    "confidence": 0.72,
    "evidence_json": {
        "family_cluster": {"score": 0.8, "closest_member": "Albert Fox", "raw_distance": 0.95},
        "co_occurrence": {"score": 0.6, "shared_photos_with_family": 5},
        "age_trajectory": {"score": 0.5, "reason": "not_yet_implemented"},
        "gedcom_match": {"score": 0.5, "reason": "not_yet_implemented"},
        "testimony": {"score": 0.0, "entries": []},
        "provenance": {"score": 0.0, "labels": []},
    },
    "family_id": "fox",
    "status": "PENDING",
}


class TestRenderIdentitySuggestionPanel:
    @patch("app.person_routes._load_identity_suggestions")
    def test_no_suggestions_returns_none(self, mock_load):
        from app.person_routes import _render_identity_suggestion_panel

        mock_load.return_value = []
        result = _render_identity_suggestion_panel("test-id", "/c/rhodes")
        assert result is None

    @patch("app.person_routes._load_identity_suggestions")
    def test_renders_panel_with_suggestion(self, mock_load):
        from app.person_routes import _render_identity_suggestion_panel

        mock_load.return_value = [SAMPLE_SUGGESTION]
        result = _render_identity_suggestion_panel("test-id", "/c/rhodes")
        assert result is not None
        html = repr(result)
        assert "identity-suggestion-test-id" in html
        assert "Identity Inference" in html
        assert "Strong" in html  # confidence 0.72 >= 0.7
        assert "Family Cluster" in html
        assert "Co-occurrence" in html
        assert "Accept" in html
        assert "Dismiss" in html
        assert "Needs More Evidence" in html
        assert "suggestion-uuid-1" in html

    @patch("app.person_routes._load_identity_suggestions")
    def test_moderate_confidence_label(self, mock_load):
        from app.person_routes import _render_identity_suggestion_panel

        mock_load.return_value = [
            {**SAMPLE_SUGGESTION, "id": "s-2", "confidence": 0.45}
        ]
        result = _render_identity_suggestion_panel("test-id", "")
        html = repr(result)
        assert "Moderate" in html

    @patch("app.person_routes._load_identity_suggestions")
    def test_weak_confidence_label(self, mock_load):
        from app.person_routes import _render_identity_suggestion_panel

        mock_load.return_value = [
            {**SAMPLE_SUGGESTION, "id": "s-3", "confidence": 0.2}
        ]
        result = _render_identity_suggestion_panel("test-id", "")
        html = repr(result)
        assert "Weak" in html

    @patch("app.person_routes._load_identity_suggestions")
    def test_accept_button_posts_to_correct_url(self, mock_load):
        from app.person_routes import _render_identity_suggestion_panel

        mock_load.return_value = [SAMPLE_SUGGESTION]
        result = _render_identity_suggestion_panel("test-id", "/c/fox-family")
        html = repr(result)
        assert "/c/fox-family/api/ml-review/identity/test-id/accept" in html

    @patch("app.person_routes._load_identity_suggestions")
    def test_panel_includes_all_signal_labels(self, mock_load):
        from app.person_routes import _render_identity_suggestion_panel

        mock_load.return_value = [SAMPLE_SUGGESTION]
        result = _render_identity_suggestion_panel("test-id", "")
        html = repr(result)
        for signal in ["Family Cluster", "Co-occurrence", "Age Trajectory", "GEDCOM Match", "Testimony", "Provenance"]:
            assert signal in html, f"Missing signal label: {signal}"


# --- Helper function tests ---


class TestUpdateSuggestionStatus:
    @patch("app.supabase_data.get_supabase_client")
    def test_returns_false_when_no_client(self, mock_get_sb):
        from app.admin_routes import _update_suggestion_status

        mock_get_sb.return_value = None
        result = _update_suggestion_status("test-id", "REJECTED", reason="not a match")
        assert result is False

    @patch("app.supabase_data.get_supabase_client")
    def test_updates_status_on_success(self, mock_get_sb):
        from app.admin_routes import _update_suggestion_status

        mock_sb = MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"id": "test"}]
        mock_get_sb.return_value = mock_sb
        result = _update_suggestion_status("sug-1", "ACCEPTED", reviewed_by="admin@test.com")
        assert result is True
        mock_sb.table.assert_called_with("identity_suggestions")


class TestLoadSuggestionById:
    @patch("app.supabase_data.get_supabase_client")
    def test_returns_none_when_no_client(self, mock_get_sb):
        from app.admin_routes import _load_suggestion_by_id

        mock_get_sb.return_value = None
        result = _load_suggestion_by_id("test-id")
        assert result is None

    @patch("app.supabase_data.get_supabase_client")
    def test_returns_suggestion_on_success(self, mock_get_sb):
        from app.admin_routes import _load_suggestion_by_id

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "sug-1", "status": "PENDING", "confidence": 0.8}
        ]
        mock_get_sb.return_value = mock_sb
        result = _load_suggestion_by_id("sug-1")
        assert result is not None
        assert result["status"] == "PENDING"


# --- CSRF on reset ---


class TestResetEndpointCSRF:
    def test_reset_has_check_origin(self):
        """Verify _check_origin is called in the reset endpoint."""
        import inspect

        from app import identity_routes

        source = inspect.getsource(identity_routes)
        # Find the reset handler
        reset_idx = source.index('@rt("/identity/{identity_id}/reset")')
        reset_section = source[reset_idx:]
        # Get just this function
        next_rt = reset_section.find("@rt(", 10)
        if next_rt > 0:
            reset_section = reset_section[:next_rt]
        assert "_check_origin" in reset_section, (
            "Reset endpoint must call _check_origin for CSRF protection"
        )


# --- Batch script placeholder fix ---


class TestBatchScriptSuggestedName:
    def test_no_placeholder_in_suggested_name(self):
        """Verify compute_identity_suggestions doesn't generate placeholder names."""
        from pathlib import Path

        script_path = Path(__file__).resolve().parent.parent / "scripts" / "compute_identity_suggestions.py"
        source = script_path.read_text()
        assert "Fox family member (score:" not in source, (
            "Batch script must not use placeholder suggested_name"
        )
