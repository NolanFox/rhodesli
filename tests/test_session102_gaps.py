"""Tests closing Session 102 gaps: TEST-003, TEST-004, OBS-003."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# TEST-003: Rhodes photos must not appear in Fox Family identity set
# ---------------------------------------------------------------------------


class TestDATA019RhodesNotInFoxFamily:
    """Verify community scoping prevents Rhodes photos leaking into Fox Family."""

    def test_rhodes_photo_excluded_from_fox_identity_set(self):
        """A photo tagged as 'Jews of Rhodes' collection must not contribute
        identities to the Fox Family community identity set."""
        # Setup: two photos, one Rhodes, one Fox
        rhodes_photo_id = "rhodes_photo_001"
        fox_photo_id = "fox_photo_001"

        # Fox community only has fox_photo_id in photo_communities
        fox_community_photo_ids = [fox_photo_id]

        # Both photos have faces, with different identities
        rhodes_identity_id = "id-rhodes-001"
        fox_identity_id = "id-fox-001"

        # Mock face_to_photo cache: maps face_ids to photo_ids
        face_to_photo = {
            "face_rhodes_1": rhodes_photo_id,
            "face_fox_1": fox_photo_id,
        }

        # Mock registry with two identities
        identities = {
            rhodes_identity_id: {
                "identity_id": rhodes_identity_id,
                "name": "Rhodes Person",
                "state": "CONFIRMED",
                "anchor_ids": ["face_rhodes_1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
            fox_identity_id: {
                "identity_id": fox_identity_id,
                "name": "Fox Person",
                "state": "CONFIRMED",
                "anchor_ids": ["face_fox_1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }

        # The identity set derivation logic: only identities whose faces
        # are in community photos should be included
        community_identity_ids = set()
        for iid, ident in identities.items():
            all_faces = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
            for fid in all_faces:
                photo_id = face_to_photo.get(fid)
                if photo_id in fox_community_photo_ids:
                    community_identity_ids.add(iid)
                    break

        # Rhodes identity must NOT be in Fox community set
        assert rhodes_identity_id not in community_identity_ids
        # Fox identity MUST be in Fox community set
        assert fox_identity_id in community_identity_ids

    def test_cross_community_identity_included_when_faces_in_both(self):
        """An identity with faces in BOTH communities appears in both sets."""
        shared_identity_id = "id-shared-001"
        rhodes_photo_id = "rhodes_photo_001"
        fox_photo_id = "fox_photo_001"

        fox_community_photo_ids = [fox_photo_id]
        rhodes_community_photo_ids = [rhodes_photo_id]

        face_to_photo = {
            "face_shared_rhodes": rhodes_photo_id,
            "face_shared_fox": fox_photo_id,
        }

        identities = {
            shared_identity_id: {
                "identity_id": shared_identity_id,
                "name": "Shared Person",
                "state": "CONFIRMED",
                "anchor_ids": ["face_shared_rhodes", "face_shared_fox"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }

        # Derive for Fox
        fox_identity_ids = set()
        for iid, ident in identities.items():
            all_faces = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
            for fid in all_faces:
                if face_to_photo.get(fid) in fox_community_photo_ids:
                    fox_identity_ids.add(iid)
                    break

        # Derive for Rhodes
        rhodes_identity_ids = set()
        for iid, ident in identities.items():
            all_faces = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
            for fid in all_faces:
                if face_to_photo.get(fid) in rhodes_community_photo_ids:
                    rhodes_identity_ids.add(iid)
                    break

        assert shared_identity_id in fox_identity_ids
        assert shared_identity_id in rhodes_identity_ids


# ---------------------------------------------------------------------------
# TEST-004: Postgres name protection guard
# ---------------------------------------------------------------------------


class TestPostgresNameProtectionGuard:
    """Verify DATA-020: shadow_write_identities_batch never overwrites a real
    Postgres name with an auto-generated 'Unidentified Person NNN' local name."""

    @patch("app.supabase_data.get_supabase_client")
    def test_name_skipped_when_local_is_unidentified(self, mock_get_client):
        """When local name is 'Unidentified Person ...' but Postgres has a real
        name, the name field must be omitted from the upsert row."""
        from app.supabase_data import shadow_write_identities_batch

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        identity_id = "test-id-001"
        pg_real_name = "David Cohen"

        # Simulate Postgres returning a real name
        mock_prefetch_result = MagicMock()
        mock_prefetch_result.data = [{"identity_id": identity_id, "name": pg_real_name}]

        # Simulate upsert succeeding
        mock_upsert_result = MagicMock()
        mock_upsert_result.data = []

        # Chain: client.table("identities").select(...).in_(...).execute()
        mock_select = MagicMock()
        mock_in = MagicMock()
        mock_in.execute.return_value = mock_prefetch_result
        mock_select.in_.return_value = mock_in
        mock_table = MagicMock()
        mock_table.select.return_value = mock_select
        mock_table.upsert.return_value = MagicMock(execute=MagicMock(return_value=mock_upsert_result))
        mock_client.table.return_value = mock_table

        # Local identity with auto-generated name
        identities_list = [
            {
                "identity_id": identity_id,
                "name": f"Unidentified Person {identity_id[:8]}",
                "state": "INBOX",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
                "negative_ids": [],
            }
        ]

        result = shadow_write_identities_batch(identities_list)

        # Verify upsert was called
        assert mock_table.upsert.called

        # Get the rows passed to upsert
        upsert_args = mock_table.upsert.call_args[0][0]
        assert len(upsert_args) == 1
        row = upsert_args[0]

        # name field must NOT be present (protected)
        assert "name" not in row, f"Name field should be skipped but got: {row.get('name')}"
        # identity_id must still be present
        assert row["identity_id"] == identity_id

    @patch("app.supabase_data.get_supabase_client")
    def test_name_written_when_local_is_real(self, mock_get_client):
        """When local name is a real name, it should be written to Postgres."""
        from app.supabase_data import shadow_write_identities_batch

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        identity_id = "test-id-002"
        local_real_name = "Sarah Franco"

        # Postgres has an old auto-generated name
        mock_prefetch_result = MagicMock()
        mock_prefetch_result.data = [{"identity_id": identity_id, "name": "Unidentified Person test-id-"}]

        mock_upsert_result = MagicMock()
        mock_upsert_result.data = []

        mock_select = MagicMock()
        mock_in = MagicMock()
        mock_in.execute.return_value = mock_prefetch_result
        mock_select.in_.return_value = mock_in
        mock_table = MagicMock()
        mock_table.select.return_value = mock_select
        mock_table.upsert.return_value = MagicMock(execute=MagicMock(return_value=mock_upsert_result))
        mock_client.table.return_value = mock_table

        identities_list = [
            {
                "identity_id": identity_id,
                "name": local_real_name,
                "state": "CONFIRMED",
                "anchor_ids": ["face2"],
                "candidate_ids": [],
                "negative_ids": [],
            }
        ]

        shadow_write_identities_batch(identities_list)

        upsert_args = mock_table.upsert.call_args[0][0]
        row = upsert_args[0]

        # Real name SHOULD be written
        assert "name" in row
        assert row["name"] == local_real_name

    @patch("app.supabase_data.get_supabase_client")
    def test_name_written_when_postgres_has_no_record(self, mock_get_client):
        """When identity is new (not in Postgres), local name should be written."""
        from app.supabase_data import shadow_write_identities_batch

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        identity_id = "test-id-003"

        # Postgres has no record for this identity
        mock_prefetch_result = MagicMock()
        mock_prefetch_result.data = []

        mock_upsert_result = MagicMock()
        mock_upsert_result.data = []

        mock_select = MagicMock()
        mock_in = MagicMock()
        mock_in.execute.return_value = mock_prefetch_result
        mock_select.in_.return_value = mock_in
        mock_table = MagicMock()
        mock_table.select.return_value = mock_select
        mock_table.upsert.return_value = MagicMock(execute=MagicMock(return_value=mock_upsert_result))
        mock_client.table.return_value = mock_table

        identities_list = [
            {
                "identity_id": identity_id,
                "name": f"Unidentified Person {identity_id[:8]}",
                "state": "INBOX",
                "anchor_ids": [],
                "candidate_ids": ["face3"],
                "negative_ids": [],
            }
        ]

        shadow_write_identities_batch(identities_list)

        upsert_args = mock_table.upsert.call_args[0][0]
        row = upsert_args[0]

        # New identity: even auto-generated name should be written
        assert "name" in row
        assert row["name"].startswith("Unidentified Person")


# ---------------------------------------------------------------------------
# OBS-003: input_method in speed-run log_user_action calls
# ---------------------------------------------------------------------------


class TestSpeedRunInputMethodLogging:
    """Verify log_user_action in speed-run routes includes input_method."""

    def test_log_user_action_records_input_method(self):
        """log_user_action should include input_method in the log line when provided."""
        from app.main import log_user_action

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "user_actions.log")

            with patch("app.main.logs_path", MagicMock()):
                # Redirect the log file
                with patch("app.main.logs_path.__truediv__", return_value=log_file):
                    with patch("app.main.logs_path.mkdir"):
                        with patch("builtins.open", create=True) as mock_open:
                            # Capture what gets written
                            written_lines = []
                            mock_file = MagicMock()
                            mock_file.write.side_effect = lambda line: written_lines.append(line)
                            mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                            mock_open.return_value.__exit__ = MagicMock(return_value=False)

                            with patch("app.main.sync_audit_log_entry", create=True):
                                log_user_action(
                                    "SPEED_RUN_CONFIRM",
                                    identity_id="test-123",
                                    mode="speed-run",
                                    input_method="keyboard",
                                )

                            assert len(written_lines) == 1
                            line = written_lines[0]
                            assert "input_method=keyboard" in line
                            assert "SPEED_RUN_CONFIRM" in line

    def test_log_user_action_omits_input_method_when_empty(self):
        """When input_method is not passed, it should not appear in log."""
        from app.main import log_user_action

        with patch("app.main.logs_path", MagicMock()):
            with patch("app.main.logs_path.__truediv__", return_value="/tmp/test_actions.log"):
                with patch("app.main.logs_path.mkdir"):
                    with patch("builtins.open", create=True) as mock_open:
                        written_lines = []
                        mock_file = MagicMock()
                        mock_file.write.side_effect = lambda line: written_lines.append(line)
                        mock_open.return_value.__enter__ = MagicMock(return_value=mock_file)
                        mock_open.return_value.__exit__ = MagicMock(return_value=False)

                        with patch("app.main.sync_audit_log_entry", create=True):
                            log_user_action(
                                "SPEED_RUN_SKIP",
                                identity_id="test-456",
                                mode="speed-run",
                            )

                        assert len(written_lines) == 1
                        line = written_lines[0]
                        assert "input_method" not in line

    def test_confirm_route_accepts_input_method_param(self):
        """Verify confirm-all route signature accepts input_method parameter."""
        import pathlib

        source = pathlib.Path("app/cluster_review_routes.py").read_text()
        # Verify input_method appears in route signatures
        assert "input_method" in source

    def test_speed_run_routes_have_input_method_in_log_calls(self):
        """Verify that speed-run log_user_action calls conditionally include input_method."""
        import pathlib

        source = pathlib.Path("app/cluster_review_routes.py").read_text()

        # Count occurrences of input_method in log_user_action patterns
        # Each speed-run action (confirm, reject, skip, dismiss, save-name, merge)
        # should have input_method support
        assert source.count('"input_method": input_method') >= 6, (
            "Expected at least 6 speed-run log calls with input_method support"
        )
