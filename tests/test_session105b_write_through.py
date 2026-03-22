"""Tests for Session 105b: Write-through architecture + photo_faces.

Tests:
1. shadow_write_photo_faces_batch works (strict/non-strict)
2. save_photo_registry writes photo_faces alongside photos
3. save_registry postgres path is synchronous (no threading)
4. Reconciliation script audit function
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest


class TestPhotoFacesBatch:
    """Verify shadow_write_photo_faces_batch function."""

    def test_writes_face_rows(self):
        """Writes face_id/photo_id rows to photo_faces table."""
        from app.supabase_data import shadow_write_photo_faces_batch

        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = shadow_write_photo_faces_batch(
                [
                    {"photo_id": "p1", "face_ids": ["f1", "f2"]},
                    {"photo_id": "p2", "face_ids": ["f3"]},
                ]
            )

        assert result == 3  # 3 face rows
        mock_client.table.assert_called_with("photo_faces")

    def test_strict_raises_on_failure(self):
        """strict=True re-raises exceptions."""
        from app.supabase_data import shadow_write_photo_faces_batch

        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.side_effect = Exception("DB error")

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            with pytest.raises(Exception, match="DB error"):
                shadow_write_photo_faces_batch([{"photo_id": "p1", "face_ids": ["f1"]}], strict=True)

    def test_non_strict_swallows(self):
        """strict=False (default) swallows exceptions."""
        from app.supabase_data import shadow_write_photo_faces_batch

        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.side_effect = Exception("DB error")

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = shadow_write_photo_faces_batch([{"photo_id": "p1", "face_ids": ["f1"]}])
            assert result == 0

    def test_no_client_strict_raises(self):
        """strict=True raises when no client."""
        from app.supabase_data import shadow_write_photo_faces_batch

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            with pytest.raises(ConnectionError):
                shadow_write_photo_faces_batch([{"photo_id": "p1", "face_ids": ["f1"]}], strict=True)

    def test_skips_empty_face_ids(self):
        """Photos with no face_ids are skipped."""
        from app.supabase_data import shadow_write_photo_faces_batch

        mock_client = MagicMock()
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = shadow_write_photo_faces_batch(
                [
                    {"photo_id": "p1", "face_ids": []},
                    {"photo_id": "p2"},  # missing face_ids key
                ]
            )

        assert result == 0
        # upsert should never be called since no rows
        mock_client.table.return_value.upsert.assert_not_called()


class TestSaveRegistrySynchronous:
    """Verify save_registry postgres path is synchronous."""

    def test_postgres_path_does_not_use_threading(self):
        """When DATA_SOURCE=postgres, save_registry calls batch write inline."""
        import app.main as main_mod

        mock_batch = MagicMock(return_value=1)
        mock_overrides = MagicMock()

        # Create a minimal registry mock
        mock_registry = MagicMock()
        mock_registry._identities = {"id1": {"name": "Test", "state": "CONFIRMED"}}

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch.object(main_mod, "REGISTRY_PATH", "/tmp/test_identities.json"),
            patch("app.supabase_data.shadow_write_identities_batch", mock_batch),
            patch("app.supabase_data.sync_identity_overrides", mock_overrides),
        ):
            main_mod.save_registry(mock_registry)

        # Verify batch write was called (synchronously — if it were threaded,
        # the mock wouldn't be called yet)
        mock_batch.assert_called_once()
        # Verify strict=True was passed
        args, kwargs = mock_batch.call_args
        assert kwargs.get("strict") is True or (len(args) > 1 and args[1] is True)

    def test_json_path_completes_without_error(self):
        """When DATA_SOURCE=json, save_registry completes without error.

        JSON backup runs in a background thread on a deepcopy (Session 131),
        so mock_registry.save won't be called on the original mock.
        """
        import app.main as main_mod

        mock_registry = MagicMock()
        mock_registry._identities = {"id1": {"name": "Test"}}

        with (
            patch.object(main_mod, "DATA_SOURCE", "json"),
            patch.object(main_mod, "REGISTRY_PATH", "/tmp/test_identities.json"),
        ):
            main_mod.save_registry(mock_registry)

        # No error means JSON path works correctly


class TestSavePhotoRegistryWriteThrough:
    """Verify save_photo_registry writes photo_faces."""

    def test_postgres_path_writes_photo_faces(self):
        """When DATA_SOURCE=postgres, photo_faces are written alongside photos."""
        import app.main as main_mod

        mock_photos_batch = MagicMock(return_value=1)
        mock_faces_batch = MagicMock(return_value=2)

        mock_registry = MagicMock()
        mock_registry._photos = {
            "p1": {"path": "test.jpg", "face_ids": ["f1", "f2"]},
        }

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch.object(main_mod, "data_path", MagicMock()),
            patch("app.supabase_data.shadow_write_photos_batch", mock_photos_batch),
            patch("app.supabase_data.shadow_write_photo_faces_batch", mock_faces_batch),
        ):
            main_mod.save_photo_registry(mock_registry)

        mock_photos_batch.assert_called_once()
        mock_faces_batch.assert_called_once()

    def test_always_writes_json_backup(self):
        """Both postgres and json paths write JSON."""
        import app.main as main_mod

        mock_registry = MagicMock()
        mock_registry._photos = {"p1": {"path": "test.jpg", "face_ids": []}}

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch.object(main_mod, "data_path", MagicMock()),
            patch("app.supabase_data.shadow_write_photos_batch", MagicMock()),
            patch("app.supabase_data.shadow_write_photo_faces_batch", MagicMock()),
        ):
            main_mod.save_photo_registry(mock_registry)

        # JSON save should always be called
        mock_registry.save.assert_called_once()


class TestReconcileAudit:
    """Verify reconciliation audit logic."""

    def test_audit_detects_stale_rows(self):
        """Audit correctly identifies rows in PG but not in JSON."""
        from scripts.reconcile_supabase import audit

        mock_client = MagicMock()

        # PG has 3 identities, JSON has 2
        def mock_table(name):
            mock = MagicMock()
            if name == "identities":
                mock.select.return_value.range.return_value.execute.return_value = MagicMock(
                    data=[{"identity_id": "a"}, {"identity_id": "b"}, {"identity_id": "c"}]
                )
            elif name == "photos":
                mock.select.return_value.range.return_value.execute.return_value = MagicMock(data=[])
            elif name == "photo_faces":
                mock.select.return_value.range.return_value.execute.return_value = MagicMock(data=[])
            return mock

        mock_client.table = mock_table

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # JSON has only a, b (not c)
            (tmp_path / "identities.json").write_text(json.dumps({"identities": {"a": {}, "b": {}}}))
            (tmp_path / "photo_index.json").write_text(json.dumps({"photos": {}, "face_to_photo": {}}))

            with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
                report = audit(tmp_path)

        assert report["stale_in_pg"]["identity_count"] == 1
        assert "c" in report["stale_in_pg"]["identities"]
        assert report["summary"]["synced"] is False
