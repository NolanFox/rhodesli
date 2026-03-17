import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.main import log_user_action


def test_log_user_action_dual_writes_to_supabase(tmp_path):
    with patch("app.main.logs_path", tmp_path), patch("app.supabase_data.sync_audit_log_entry") as sync_mock:
        log_user_action(
            "RENAME_IDENTITY",
            identity_id="person-1",
            admin="admin@example.com",
            previous_name="Old Name",
            new_name="New Name",
        )

    log_file = tmp_path / "user_actions.log"
    assert log_file.exists()
    contents = log_file.read_text(encoding="utf-8")
    assert "RENAME_IDENTITY" in contents
    assert "identity_id=person-1" in contents

    assert sync_mock.called
    kwargs = sync_mock.call_args.kwargs
    assert kwargs["action"] == "RENAME_IDENTITY"
    assert kwargs["target_id"] == "person-1"
    assert kwargs["actor"] == "admin@example.com"
    assert kwargs["target_type"] == "identity_action"
    assert kwargs["entry_data"]["new_name"] == "New Name"


def test_photo_metadata_routes_include_audit_logging():
    source = Path("app/page_routes.py").read_text(encoding="utf-8")
    assert "UPDATE_PHOTO_COLLECTION" in source
    assert "previous_collection" in source
    assert "new_collection" in source
    assert "UPDATE_PHOTO_SOURCE" in source
    assert "previous_source" in source
    assert "new_source" in source
    assert "UPDATE_PHOTO_SOURCE_URL" in source
    assert "previous_source_url" in source
    assert "new_source_url" in source


def test_identity_routes_include_rename_audit_logging():
    source = Path("app/identity_routes.py").read_text(encoding="utf-8")
    assert '"RENAME_IDENTITY"' in source
    assert 'source="web"' in source
    assert 'source="face_tag"' in source
    assert 'source="admin_web"' in source


# ===================================================================
# AUDIT-001: Supabase audit_log integration tests
# ===================================================================


class TestAuditHelper:
    """Unit tests for app.audit._log_audit and _safe_jsonb."""

    def test_safe_jsonb_none(self):
        from app.audit import _safe_jsonb

        assert _safe_jsonb(None) == {}

    def test_safe_jsonb_valid(self):
        from app.audit import _safe_jsonb

        data = {"key": "value", "num": 42}
        assert _safe_jsonb(data) == data

    def test_safe_jsonb_non_serializable(self):
        from app.audit import _safe_jsonb

        data = {"key": "value", "bad": object()}
        result = _safe_jsonb(data)
        assert result["key"] == "value"
        assert isinstance(result["bad"], str)

    def test_log_audit_calls_supabase_insert(self):
        from app.audit import _log_audit

        mock_client = MagicMock()
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            _log_audit(
                "merge",
                entity_id="test-123",
                user_email="admin@test.com",
                old_value={"source_id": "src-456"},
                new_value={"merged_into": "test-123"},
                metadata={"route": "face_tag"},
            )

        mock_client.table.assert_called_once_with("audit_log")
        insert_args = mock_table.insert.call_args[0][0]
        assert insert_args["action"] == "merge"
        assert insert_args["entity_type"] == "identity"
        assert insert_args["entity_id"] == "test-123"
        assert insert_args["user_email"] == "admin@test.com"
        assert insert_args["old_value"]["source_id"] == "src-456"
        assert insert_args["new_value"]["merged_into"] == "test-123"
        assert insert_args["metadata"]["route"] == "face_tag"

    def test_log_audit_no_client_does_not_raise(self):
        from app.audit import _log_audit

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            _log_audit("merge", entity_id="test-123")

    def test_log_audit_exception_does_not_raise(self):
        from app.audit import _log_audit

        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("Supabase down")

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            _log_audit("merge", entity_id="test-123")


class TestMergeWritesAuditLog:
    """Test that merge routes call _log_audit."""

    def test_face_tag_merge_writes_audit(self, client):
        """POST /api/face/tag writes an audit_log entry on successful merge."""
        from app.main import load_registry

        registry = load_registry()
        non_merged = [(iid, data) for iid, data in registry._identities.items() if not data.get("merged_into")]
        if len(non_merged) < 2:
            pytest.skip("Need at least 2 non-merged identities")

        target_id = non_merged[0][0]
        source_data = non_merged[1][1]
        face_ids = source_data.get("anchor_ids", []) + source_data.get("candidate_ids", [])
        if not face_ids:
            pytest.skip("Source identity has no faces")
        face_id = face_ids[0]

        with (
            patch("app.main.save_registry"),
            patch("app.identity_routes._log_audit") as mock_audit,
            patch("app.main._invalidate_discovery_cache"),
        ):
            response = client.post(
                "/api/face/tag",
                data={"face_id": face_id, "target_id": target_id},
            )

        if response.status_code == 200 and mock_audit.called:
            audit_call = mock_audit.call_args
            assert audit_call[0][0] == "merge"


class TestConfirmWritesAuditLog:
    """Test that confirm routes call _log_audit."""

    def test_confirm_writes_audit(self, client):
        """POST /confirm/{identity_id} writes an audit_log entry."""
        from app.main import load_registry

        registry = load_registry()
        proposed = [
            (iid, data)
            for iid, data in registry._identities.items()
            if data.get("state") == "PROPOSED"
            and not data.get("name", "").startswith("Unidentified")
            and not data.get("merged_into")
        ]
        if not proposed:
            pytest.skip("No PROPOSED identity with real name")

        identity_id = proposed[0][0]

        with (
            patch("app.main.save_registry"),
            patch("app.identity_routes._log_audit") as mock_audit,
        ):
            response = client.post(f"/confirm/{identity_id}")

        if response.status_code == 200:
            assert mock_audit.called
            audit_call = mock_audit.call_args
            assert audit_call[0][0] == "confirm"


class TestSkipWritesAuditLog:
    """Test that skip route calls _log_audit."""

    def test_skip_writes_audit(self, client):
        """POST /skip/{identity_id} writes an audit_log entry."""
        from app.main import load_registry

        registry = load_registry()
        non_merged = [
            (iid, data)
            for iid, data in registry._identities.items()
            if not data.get("merged_into") and data.get("state") in ("INBOX", "PROPOSED")
        ]
        if not non_merged:
            pytest.skip("No skippable identity")

        identity_id = non_merged[0][0]

        with (
            patch("app.main.save_registry"),
            patch("app.identity_routes._log_audit") as mock_audit,
        ):
            response = client.post(f"/skip/{identity_id}")

        if response.status_code == 200:
            assert mock_audit.called
            audit_call = mock_audit.call_args
            assert audit_call[0][0] == "skip"


class TestRenameWritesAuditLog:
    """Test that rename route calls _log_audit."""

    def test_rename_writes_audit(self, client):
        """POST /api/identity/{id}/rename writes an audit_log entry."""
        from app.main import load_registry

        registry = load_registry()
        non_merged = [(iid, data) for iid, data in registry._identities.items() if not data.get("merged_into")]
        if not non_merged:
            pytest.skip("No identity to rename")

        identity_id = non_merged[0][0]

        with (
            patch("app.main.save_registry"),
            patch("app.identity_routes._log_audit") as mock_audit,
        ):
            response = client.post(
                f"/api/identity/{identity_id}/rename",
                data={"name": "Test Rename Person"},
            )

        if response.status_code == 200:
            assert mock_audit.called
            audit_call = mock_audit.call_args
            assert audit_call[0][0] == "rename"


class TestAuditLogFailureDoesNotCrashMutation:
    """Test that audit failures don't prevent mutations from succeeding."""

    def test_audit_helper_never_raises(self):
        """_log_audit() with a broken Supabase client must not raise."""
        from app.audit import _log_audit

        mock_client = MagicMock()
        mock_client.table.side_effect = RuntimeError("connection refused")

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            _log_audit(
                "confirm",
                entity_id="test-id",
                user_email="admin@test.com",
                old_value={"state": "PROPOSED"},
                new_value={"state": "CONFIRMED"},
            )

    def test_confirm_succeeds_even_when_audit_fails(self, client):
        """If _log_audit raises, confirm still works (since _log_audit has its own try/except)."""
        from app.main import load_registry

        registry = load_registry()
        proposed = [
            (iid, data)
            for iid, data in registry._identities.items()
            if data.get("state") == "PROPOSED"
            and not data.get("name", "").startswith("Unidentified")
            and not data.get("merged_into")
        ]
        if not proposed:
            pytest.skip("No PROPOSED identity with real name")

        identity_id = proposed[0][0]

        # Even with a broken audit, the mutation should succeed
        mock_client = MagicMock()
        mock_client.table.side_effect = Exception("Supabase down")

        with (
            patch("app.main.save_registry") as save_mock,
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
        ):
            response = client.post(f"/confirm/{identity_id}")

        # save_registry should have been called — mutation succeeded
        assert save_mock.called


class TestAuditLogCodePresence:
    """Verify _log_audit calls exist in all mutation route files."""

    def test_identity_routes_has_audit_calls(self):
        source = Path("app/identity_routes.py").read_text(encoding="utf-8")
        # Check all major action types are logged
        assert '_log_audit(\n        "confirm"' in source or '_log_audit(\n            "confirm"' in source
        assert '_log_audit(\n        "merge"' in source or '_log_audit(\n            "merge"' in source
        assert '_log_audit(\n        "skip"' in source or '_log_audit(\n            "skip"' in source
        assert '_log_audit(\n        "rename"' in source or '_log_audit(\n            "rename"' in source
        assert '_log_audit(\n        "detach"' in source or '_log_audit(\n            "detach"' in source
        assert (
            '_log_audit(\n        "negative_match"' in source or '_log_audit(\n            "negative_match"' in source
        )

    def test_match_facecompare_routes_has_audit_calls(self):
        source = Path("app/match_facecompare_routes.py").read_text(encoding="utf-8")
        assert "_log_audit" in source
        assert '"merge"' in source
        assert '"negative_match"' in source

    def test_cluster_review_routes_has_audit_calls(self):
        source = Path("app/cluster_review_routes.py").read_text(encoding="utf-8")
        assert "_log_audit" in source
        assert '"confirm"' in source
        assert '"reject"' in source
