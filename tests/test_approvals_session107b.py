"""
Tests for Session 107b approvals improvements.

Covers:
- Fix 1: Submission timestamp on approval cards
- Fix 2: Auto-confirm checkbox on approve
- Fix 3: annotation_id in rename history
- Fix 4: Person page name provenance
"""

import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Fix 1: Submission timestamp rendering
# ============================================================================


class TestSubmissionTimestamp:
    """Approval cards should show submission timestamps."""

    def test_format_submitted_at_returns_relative_time(self):
        """_format_submitted_at returns a relative time string."""
        # Import via app.main to avoid circular import
        import app.main  # noqa: F401 — triggers admin_routes import
        from app.admin_routes import _format_submitted_at

        # Recent timestamp should return something like "Xm ago" or "Xh ago"
        ts = datetime.now(timezone.utc).isoformat()
        result = _format_submitted_at(ts)
        assert result  # Should return non-empty string
        assert "ago" in result or "just now" in result

    def test_format_submitted_at_empty_string(self):
        """Empty timestamp returns empty string."""
        import app.main  # noqa: F401
        from app.admin_routes import _format_submitted_at

        assert _format_submitted_at("") == ""

    def test_approval_card_contains_submitted_at_render(self):
        """Approval card rendering code includes submitted_at formatting."""
        import app.main  # noqa: F401
        import app.admin_routes as ar

        source = inspect.getsource(ar)
        assert "_format_submitted_at" in source
        assert "submitted_at" in source


# ============================================================================
# Fix 2: Auto-confirm checkbox
# ============================================================================


class TestAutoConfirmCheckbox:
    """Approving a name suggestion can auto-confirm the identity."""

    def test_approval_page_includes_auto_confirm_checkbox(self):
        """Approval card rendering includes auto-confirm checkbox."""
        import app.main  # noqa: F401
        import app.admin_routes as ar

        source = inspect.getsource(ar)
        assert "auto-confirm-" in source
        assert "Also confirm this person" in source

    def test_approve_handler_accepts_auto_confirm(self):
        """Approve handler accepts **kwargs for checkbox data."""
        import app.main  # noqa: F401
        import app.admin_routes as ar

        source = inspect.getsource(ar)
        assert "auto_confirm_on_approve" in source
        assert "confirm_identity" in source


# ============================================================================
# Fix 3: annotation_id in rename history
# ============================================================================


class TestAnnotationIdInHistory:
    """rename_identity stores annotation_id in event metadata."""

    def test_rename_identity_accepts_annotation_id(self):
        """rename_identity accepts optional annotation_id parameter."""
        from core.registry import IdentityRegistry

        sig = inspect.signature(IdentityRegistry.rename_identity)
        params = list(sig.parameters.keys())
        assert "annotation_id" in params

    @patch("core.registry.sync_identity_history_event", create=True)
    def test_rename_with_annotation_id_records_in_metadata(self, mock_sync):
        """Renaming with annotation_id stores it in the history event."""
        from core.registry import IdentityRegistry

        reg = IdentityRegistry()
        reg._identities = {
            "test-id": {
                "identity_id": "test-id",
                "name": "Old Name",
                "state": "INBOX",
                "anchor_ids": [],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        reg.rename_identity("test-id", "New Name", user_source="test", annotation_id="ann-123")

        # History events go to reg._history, not identity["history"]
        assert len(reg._history) >= 1
        rename_event = [e for e in reg._history if e["action"] == "rename"]
        assert len(rename_event) == 1
        assert rename_event[0]["metadata"]["annotation_id"] == "ann-123"

    @patch("core.registry.sync_identity_history_event", create=True)
    def test_rename_without_annotation_id_no_annotation_key(self, mock_sync):
        """Renaming without annotation_id doesn't add the key."""
        from core.registry import IdentityRegistry

        reg = IdentityRegistry()
        reg._identities = {
            "test-id": {
                "identity_id": "test-id",
                "name": "Old Name",
                "state": "INBOX",
                "anchor_ids": [],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        }
        reg.rename_identity("test-id", "New Name", user_source="test")

        rename_event = [e for e in reg._history if e["action"] == "rename"]
        assert len(rename_event) == 1
        assert "annotation_id" not in rename_event[0]["metadata"]


# ============================================================================
# Fix 4: Person page name provenance
# ============================================================================


class TestNameProvenance:
    """Person page shows where the name came from."""

    def test_name_provenance_function_exists(self):
        """_name_provenance_line function exists in person_routes."""
        from app.person_routes import _name_provenance_line

        assert callable(_name_provenance_line)

    @patch("app.person_routes._main_mod._load_annotations")
    def test_name_provenance_shows_approved_suggestion(self, mock_load):
        """Shows provenance for approved name suggestions."""
        from app.person_routes import _name_provenance_line

        mock_load.return_value = {
            "annotations": {
                "ann-1": {
                    "target_id": "person-123",
                    "type": "name_suggestion",
                    "status": "approved",
                    "submitted_by": "claude@example.com",
                    "submitted_at": "2026-03-15T10:00:00+00:00",
                    "reviewed_by": "admin@example.com",
                    "reviewed_at": "2026-03-16T12:00:00+00:00",
                    "value": "John Smith",
                }
            }
        }

        result = _name_provenance_line("person-123", is_admin=True)
        assert result is not None
        # Convert to string for assertion
        from fasthtml.common import to_xml

        html = to_xml(result)
        assert "claude@example.com" in html
        assert "admin@example.com" in html

    @patch("app.person_routes._main_mod._load_annotations")
    def test_name_provenance_hidden_for_non_admin(self, mock_load):
        """Non-admins don't see provenance."""
        from app.person_routes import _name_provenance_line

        result = _name_provenance_line("person-123", is_admin=False)
        assert result is None

    @patch("app.person_routes._main_mod._load_annotations")
    def test_name_provenance_none_for_no_approved_annotations(self, mock_load):
        """Returns None when no approved name suggestions exist."""
        from app.person_routes import _name_provenance_line

        mock_load.return_value = {"annotations": {}}

        result = _name_provenance_line("person-123", is_admin=True)
        assert result is None
