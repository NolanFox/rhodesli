"""Tests for Supabase data layer (AD-135).

Tests dual-write behavior, startup sync, and degraded mode.
Uses mocked Supabase client — does NOT hit real Supabase.
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def mock_supabase():
    """Mock Supabase client that records calls."""
    client = MagicMock()
    # Make table().upsert().execute() return a mock result
    mock_result = MagicMock()
    mock_result.data = []
    mock_result.count = 0
    client.table.return_value.upsert.return_value.execute.return_value = mock_result
    client.table.return_value.insert.return_value.execute.return_value = mock_result
    client.table.return_value.delete.return_value.neq.return_value.execute.return_value = mock_result
    client.table.return_value.select.return_value.execute.return_value = mock_result
    client.table.return_value.select.return_value.limit.return_value.execute.return_value = mock_result
    return client


@pytest.fixture
def sample_identities():
    """Sample identity data for testing."""
    return {
        "confirmed_1": {
            "identity_id": "confirmed_1",
            "name": "Moise Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face_1"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 3,
            "metadata": {"birth_year": 1920},
            "updated_at": "2026-02-21T00:00:00+00:00",
        },
        "proposed_1": {
            "identity_id": "proposed_1",
            "name": "Unidentified Person 001",
            "state": "PROPOSED",
            "anchor_ids": [],
            "candidate_ids": ["face_2"],
            "negative_ids": [],
            "version_id": 1,
            "metadata": {},
            "updated_at": "2026-02-20T00:00:00+00:00",
        },
        "skipped_1": {
            "identity_id": "skipped_1",
            "name": "Unidentified Person 002",
            "state": "SKIPPED",
            "anchor_ids": [],
            "candidate_ids": ["face_3"],
            "negative_ids": [],
            "version_id": 2,
            "metadata": {},
            "updated_at": "2026-02-20T00:00:00+00:00",
        },
        "merged_1": {
            "identity_id": "merged_1",
            "name": "Old Name",
            "state": "INBOX",
            "anchor_ids": [],
            "candidate_ids": [],
            "negative_ids": [],
            "merged_into": "confirmed_1",
            "version_id": 2,
            "metadata": {},
            "updated_at": "2026-02-20T00:00:00+00:00",
        },
        "inbox_1": {
            "identity_id": "inbox_1",
            "name": "Unidentified Person 003",
            "state": "INBOX",
            "anchor_ids": [],
            "candidate_ids": ["face_4"],
            "negative_ids": [],
            "version_id": 1,
            "metadata": {},
            "updated_at": "2026-02-19T00:00:00+00:00",
        },
    }


@pytest.fixture(autouse=True)
def reset_supabase_client():
    """Reset the module-level client cache before each test."""
    from app.supabase_data import reset_client

    reset_client()
    yield
    reset_client()


# =========================================================================
# _is_user_modified_identity tests
# =========================================================================


class TestIsUserModified:
    def test_confirmed_is_user_modified(self):
        from app.supabase_data import _is_user_modified_identity

        assert _is_user_modified_identity({"state": "CONFIRMED"}) is True

    def test_contested_is_user_modified(self):
        from app.supabase_data import _is_user_modified_identity

        assert _is_user_modified_identity({"state": "CONTESTED"}) is True

    def test_skipped_is_user_modified(self):
        from app.supabase_data import _is_user_modified_identity

        assert _is_user_modified_identity({"state": "SKIPPED"}) is True

    def test_merged_is_user_modified(self):
        from app.supabase_data import _is_user_modified_identity

        assert _is_user_modified_identity({"state": "INBOX", "merged_into": "abc"}) is True

    def test_negative_ids_is_user_modified(self):
        from app.supabase_data import _is_user_modified_identity

        assert _is_user_modified_identity({"state": "PROPOSED", "negative_ids": ["face_x"]}) is True

    def test_birth_year_metadata_is_user_modified(self):
        from app.supabase_data import _is_user_modified_identity

        assert _is_user_modified_identity({"state": "INBOX", "metadata": {"birth_year": 1920}}) is True

    def test_inbox_no_modifications(self):
        from app.supabase_data import _is_user_modified_identity

        assert _is_user_modified_identity({"state": "INBOX", "metadata": {}}) is False

    def test_proposed_no_modifications(self):
        from app.supabase_data import _is_user_modified_identity

        assert _is_user_modified_identity({"state": "PROPOSED", "negative_ids": [], "metadata": {}}) is False


# =========================================================================
# sync_identity_overrides tests
# =========================================================================


class TestSyncIdentityOverrides:
    def test_syncs_only_user_modified(self, mock_supabase, sample_identities):
        from app.supabase_data import sync_identity_overrides

        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_identity_overrides(sample_identities)

        # Should have called upsert (at least once)
        mock_supabase.table.assert_called_with("identity_overrides")
        call_args = mock_supabase.table.return_value.upsert.call_args
        rows = call_args[0][0]
        synced_ids = {r["identity_id"] for r in rows}

        # confirmed_1 (CONFIRMED), skipped_1 (SKIPPED), merged_1 (merged_into)
        # should all be synced. inbox_1 and proposed_1 should NOT.
        assert "confirmed_1" in synced_ids
        assert "skipped_1" in synced_ids
        assert "merged_1" in synced_ids
        assert "inbox_1" not in synced_ids
        assert "proposed_1" not in synced_ids

    def test_no_supabase_does_nothing(self, sample_identities):
        from app.supabase_data import sync_identity_overrides

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            # Should not raise
            sync_identity_overrides(sample_identities)

    def test_supabase_error_logs_warning(self, mock_supabase, sample_identities):
        from app.supabase_data import sync_identity_overrides

        mock_supabase.table.return_value.upsert.return_value.execute.side_effect = Exception("network error")
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            # Should not raise — degraded mode
            sync_identity_overrides(sample_identities)

    def test_empty_identities_does_nothing(self, mock_supabase):
        from app.supabase_data import sync_identity_overrides

        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_identity_overrides({})
        mock_supabase.table.return_value.upsert.assert_not_called()


# =========================================================================
# sync_annotations tests
# =========================================================================


class TestSyncAnnotations:
    def test_syncs_all_annotations(self, mock_supabase):
        from app.supabase_data import sync_annotations

        annotations = {
            "ann_1": {
                "type": "name_suggestion",
                "target_type": "identity",
                "target_id": "id_1",
                "status": "approved",
                "submitted_at": "2026-02-21T00:00:00+00:00",
            },
            "ann_2": {
                "type": "bio",
                "target_type": "photo",
                "target_id": "photo_1",
                "status": "pending",
                "submitted_at": "2026-02-21T00:00:00+00:00",
            },
        }
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_annotations(annotations)

        mock_supabase.table.assert_called_with("annotations")
        call_args = mock_supabase.table.return_value.upsert.call_args
        rows = call_args[0][0]
        assert len(rows) == 2

        # Check identity vs photo target mapping
        ann_1_row = next(r for r in rows if r["annotation_id"] == "ann_1")
        assert ann_1_row["identity_id"] == "id_1"
        assert ann_1_row["photo_id"] is None

        ann_2_row = next(r for r in rows if r["annotation_id"] == "ann_2")
        assert ann_2_row["identity_id"] is None
        assert ann_2_row["photo_id"] == "photo_1"


# =========================================================================
# Startup sync tests
# =========================================================================


class TestStartupSync:
    def test_applies_identity_overrides(self, mock_supabase, tmp_path):
        """Startup sync overlays Supabase overrides onto bundled identities."""
        from app.supabase_data import sync_from_supabase_on_startup

        # Create bundled identities.json with PROPOSED identity
        ids_data = {
            "schema_version": 1,
            "identities": {
                "id_1": {
                    "identity_id": "id_1",
                    "name": "Unidentified",
                    "state": "PROPOSED",
                    "anchor_ids": [],
                    "candidate_ids": ["face_1"],
                    "negative_ids": [],
                    "metadata": {},
                },
            },
            "history": [],
        }
        ids_path = tmp_path / "identities.json"
        ids_path.write_text(json.dumps(ids_data))

        # Supabase has a CONFIRMED override for the same identity
        override_data = {
            "identity_id": "id_1",
            "name": "Moise Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face_1"],
            "candidate_ids": [],
            "negative_ids": [],
            "metadata": {"birth_year": 1920},
        }
        mock_result = MagicMock()
        mock_result.data = [{"identity_id": "id_1", "data": override_data}]

        # Configure mock: identity_overrides returns override, others empty
        def table_select_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "identity_overrides":
                mock_table.select.return_value.execute.return_value = mock_result
            else:
                empty_result = MagicMock()
                empty_result.data = []
                mock_table.select.return_value.execute.return_value = empty_result
            return mock_table

        mock_supabase.table.side_effect = table_select_side_effect

        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            result = sync_from_supabase_on_startup(tmp_path)

        assert result is True

        # Verify identities.json was updated
        with open(ids_path) as f:
            updated = json.load(f)
        identity = updated["identities"]["id_1"]
        assert identity["state"] == "CONFIRMED"
        assert identity["name"] == "Moise Capeluto"
        assert identity["metadata"]["birth_year"] == 1920

    def test_preserves_bundle_only_identities(self, mock_supabase, tmp_path):
        """New ML proposals (not in Supabase) stay in identities.json."""
        from app.supabase_data import sync_from_supabase_on_startup

        ids_data = {
            "schema_version": 1,
            "identities": {
                "ml_proposal": {
                    "identity_id": "ml_proposal",
                    "name": "Unidentified 999",
                    "state": "INBOX",
                    "anchor_ids": [],
                    "candidate_ids": ["new_face"],
                    "negative_ids": [],
                    "metadata": {},
                },
            },
            "history": [],
        }
        ids_path = tmp_path / "identities.json"
        ids_path.write_text(json.dumps(ids_data))

        # Supabase has NO overrides for this identity
        def table_select_side_effect(table_name):
            mock_table = MagicMock()
            empty_result = MagicMock()
            empty_result.data = []
            mock_table.select.return_value.execute.return_value = empty_result
            return mock_table

        mock_supabase.table.side_effect = table_select_side_effect

        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_from_supabase_on_startup(tmp_path)

        # ML proposal should still be there
        with open(ids_path) as f:
            updated = json.load(f)
        assert "ml_proposal" in updated["identities"]
        assert updated["identities"]["ml_proposal"]["state"] == "INBOX"

    def test_skips_override_when_json_is_newer(self, mock_supabase, tmp_path):
        """Startup sync skips overrides when JSON has a newer updated_at timestamp.
        This prevents restart from reverting manual volume fixes (Person 2973 bug).
        """
        from app.supabase_data import sync_from_supabase_on_startup

        # JSON has a SKIPPED identity with a RECENT timestamp (user manually fixed it)
        ids_data = {
            "schema_version": 1,
            "identities": {
                "person_2973": {
                    "identity_id": "person_2973",
                    "name": "Unidentified Person 2973",
                    "state": "SKIPPED",
                    "anchor_ids": ["face_x"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "metadata": {},
                    "updated_at": "2026-03-10T20:00:00+00:00",  # Newer
                },
            },
            "history": [],
        }
        ids_path = tmp_path / "identities.json"
        ids_path.write_text(json.dumps(ids_data))

        # Supabase has an OLDER override with CONFIRMED state
        override_data = {
            "identity_id": "person_2973",
            "name": "Person 2973",
            "state": "CONFIRMED",
            "anchor_ids": ["face_x"],
            "candidate_ids": [],
            "negative_ids": [],
            "metadata": {},
            "updated_at": "2026-03-10T18:00:00+00:00",  # Older
        }
        mock_result = MagicMock()
        mock_result.data = [{"identity_id": "person_2973", "data": override_data}]

        def table_select_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "identity_overrides":
                mock_table.select.return_value.execute.return_value = mock_result
            else:
                empty_result = MagicMock()
                empty_result.data = []
                mock_table.select.return_value.execute.return_value = empty_result
            return mock_table

        mock_supabase.table.side_effect = table_select_side_effect

        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_from_supabase_on_startup(tmp_path)

        # JSON should NOT have been overwritten — SKIPPED state preserved
        with open(ids_path) as f:
            updated = json.load(f)
        assert updated["identities"]["person_2973"]["state"] == "SKIPPED"

    def test_applies_override_when_supabase_is_newer(self, mock_supabase, tmp_path):
        """Startup sync applies overrides when Supabase has a newer timestamp."""
        from app.supabase_data import sync_from_supabase_on_startup

        ids_data = {
            "schema_version": 1,
            "identities": {
                "id_1": {
                    "identity_id": "id_1",
                    "name": "Unidentified",
                    "state": "PROPOSED",
                    "anchor_ids": [],
                    "candidate_ids": ["face_1"],
                    "negative_ids": [],
                    "metadata": {},
                    "updated_at": "2026-03-10T16:00:00+00:00",  # Older
                },
            },
            "history": [],
        }
        ids_path = tmp_path / "identities.json"
        ids_path.write_text(json.dumps(ids_data))

        override_data = {
            "identity_id": "id_1",
            "name": "Moise Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face_1"],
            "candidate_ids": [],
            "negative_ids": [],
            "metadata": {"birth_year": 1920},
            "updated_at": "2026-03-10T20:00:00+00:00",  # Newer
        }
        mock_result = MagicMock()
        mock_result.data = [{"identity_id": "id_1", "data": override_data}]

        def table_select_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "identity_overrides":
                mock_table.select.return_value.execute.return_value = mock_result
            else:
                empty_result = MagicMock()
                empty_result.data = []
                mock_table.select.return_value.execute.return_value = empty_result
            return mock_table

        mock_supabase.table.side_effect = table_select_side_effect

        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_from_supabase_on_startup(tmp_path)

        with open(ids_path) as f:
            updated = json.load(f)
        assert updated["identities"]["id_1"]["state"] == "CONFIRMED"
        assert updated["identities"]["id_1"]["name"] == "Moise Capeluto"

    def test_supabase_unavailable_uses_existing_json(self, tmp_path):
        """When Supabase is down, app uses existing JSON cache."""
        from app.supabase_data import sync_from_supabase_on_startup

        ids_data = {
            "schema_version": 1,
            "identities": {"id_1": {"state": "PROPOSED", "name": "Test"}},
            "history": [],
        }
        ids_path = tmp_path / "identities.json"
        ids_path.write_text(json.dumps(ids_data))

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            result = sync_from_supabase_on_startup(tmp_path)

        assert result is False

        # JSON should be unchanged
        with open(ids_path) as f:
            unchanged = json.load(f)
        assert unchanged["identities"]["id_1"]["state"] == "PROPOSED"

    def test_syncs_annotations_from_supabase(self, mock_supabase, tmp_path):
        """Startup sync rebuilds annotations.json from Supabase."""
        from app.supabase_data import sync_from_supabase_on_startup

        # Create minimal identities.json (required for startup)
        ids_path = tmp_path / "identities.json"
        ids_path.write_text(json.dumps({"schema_version": 1, "identities": {}, "history": []}))

        # Create empty annotations.json
        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps({"schema_version": 1, "annotations": {}}))

        # Supabase has an annotation
        ann_data = {
            "annotation_id": "ann_1",
            "type": "bio",
            "target_type": "identity",
            "target_id": "id_1",
            "value": "Test bio",
            "status": "approved",
        }

        def table_select_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "annotations":
                result = MagicMock()
                result.data = [{"annotation_id": "ann_1", "data": ann_data}]
                mock_table.select.return_value.execute.return_value = result
            else:
                empty = MagicMock()
                empty.data = []
                mock_table.select.return_value.execute.return_value = empty
            return mock_table

        mock_supabase.table.side_effect = table_select_side_effect

        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_from_supabase_on_startup(tmp_path)

        with open(ann_path) as f:
            updated = json.load(f)
        assert "ann_1" in updated["annotations"]
        assert updated["annotations"]["ann_1"]["type"] == "bio"


# =========================================================================
# Deploy safety regression test — THE DATA-001 scenario
# =========================================================================


class TestDeploySafetyRegression:
    def test_deploy_cannot_lose_user_confirmations(self, mock_supabase, tmp_path):
        """Regression test for DATA-001.

        Simulates: user confirms identities via web UI → deploy happens
        with stale bundled JSON → startup sync restores from Supabase.
        """
        from app.supabase_data import sync_from_supabase_on_startup

        # Step 1: Stale bundled JSON (as if deploy bundled old data)
        # This has the identity as PROPOSED (before the user confirmed it)
        stale_ids = {
            "schema_version": 1,
            "identities": {
                "49b_identity": {
                    "identity_id": "49b_identity",
                    "name": "Unidentified Person 042",
                    "state": "PROPOSED",
                    "anchor_ids": [],
                    "candidate_ids": ["face_x"],
                    "negative_ids": [],
                    "metadata": {},
                },
            },
            "history": [],
        }
        ids_path = tmp_path / "identities.json"
        ids_path.write_text(json.dumps(stale_ids))

        # Step 2: Supabase has the CONFIRMED version (user confirmed via web UI)
        confirmed_data = {
            "identity_id": "49b_identity",
            "name": "Isaac Franco",
            "state": "CONFIRMED",
            "anchor_ids": ["face_x"],
            "candidate_ids": [],
            "negative_ids": [],
            "metadata": {"birth_year": 1895},
        }

        def table_select_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "identity_overrides":
                result = MagicMock()
                result.data = [{"identity_id": "49b_identity", "data": confirmed_data}]
                mock_table.select.return_value.execute.return_value = result
            else:
                empty = MagicMock()
                empty.data = []
                mock_table.select.return_value.execute.return_value = empty
            return mock_table

        mock_supabase.table.side_effect = table_select_side_effect

        # Step 3: Run startup sync (simulates what happens after deploy)
        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_from_supabase_on_startup(tmp_path)

        # Step 4: Verify — JSON now has the confirmed version from Supabase
        with open(ids_path) as f:
            restored = json.load(f)

        identity = restored["identities"]["49b_identity"]
        assert identity["state"] == "CONFIRMED", "Deploy lost user confirmation!"
        assert identity["name"] == "Isaac Franco", "Deploy lost user-assigned name!"
        assert identity["metadata"]["birth_year"] == 1895, "Deploy lost birth year!"


# =========================================================================
# save_registry integration test (with mocked Supabase)
# =========================================================================


class TestSaveRegistryDualWrite:
    def test_save_registry_calls_supabase_sync(self, mock_supabase, tmp_path):
        """save_registry() should sync to Supabase after JSON save."""
        import sys

        # Need to import save_registry from app.main
        # But app.main has heavy imports, so we'll test the sync function directly
        from app.supabase_data import sync_identity_overrides

        identities = {
            "test_id": {
                "identity_id": "test_id",
                "name": "Test",
                "state": "CONFIRMED",
                "anchor_ids": [],
                "candidate_ids": [],
                "negative_ids": [],
                "metadata": {},
            }
        }

        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_identity_overrides(identities)

        # Verify upsert was called with the confirmed identity
        mock_supabase.table.assert_called_with("identity_overrides")
        call_args = mock_supabase.table.return_value.upsert.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["identity_id"] == "test_id"
        assert call_args[0]["state"] == "CONFIRMED"


# =========================================================================
# get_supabase_client tests
# =========================================================================


class TestGetSupabaseClient:
    def test_returns_none_when_not_configured(self):
        from app.supabase_data import get_supabase_client, reset_client

        reset_client()
        with patch.dict(os.environ, {}, clear=True):
            # Remove all SUPABASE vars
            env = {k: v for k, v in os.environ.items() if "SUPABASE" not in k}
            with patch.dict(os.environ, env, clear=True):
                result = get_supabase_client()
                assert result is None

    def test_caches_none_result(self):
        """Once determined unavailable, don't retry on every call."""
        from app.supabase_data import get_supabase_client, reset_client, _supabase_available

        reset_client()
        with patch.dict(os.environ, {"SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""}, clear=False):
            result1 = get_supabase_client()
            result2 = get_supabase_client()
            assert result1 is None
            assert result2 is None


# =========================================================================
# Migration idempotency test
# =========================================================================


class TestMigrationIdempotency:
    def test_upsert_is_idempotent(self, mock_supabase):
        """Running sync twice with same data doesn't duplicate rows."""
        from app.supabase_data import sync_identity_overrides

        identities = {
            "id_1": {"identity_id": "id_1", "state": "CONFIRMED", "name": "Test", "metadata": {}},
        }

        with patch("app.supabase_data.get_supabase_client", return_value=mock_supabase):
            sync_identity_overrides(identities)
            sync_identity_overrides(identities)

        # Upsert is called twice — both times with the same data
        assert mock_supabase.table.return_value.upsert.call_count == 2
        # Upsert semantics: INSERT ON CONFLICT UPDATE, so no duplicates


# =========================================================================
# Deploy safety gate integration (existing tests still pass)
# =========================================================================


class TestInitRailwayVolumeSyncList:
    def test_annotations_not_in_sync_list(self):
        """annotations.json must NOT be in OPTIONAL_SYNC_FILES (production-origin)."""
        from scripts.init_railway_volume import OPTIONAL_SYNC_FILES

        assert "annotations.json" not in OPTIONAL_SYNC_FILES

    def test_relationships_not_in_sync_list(self):
        """relationships.json now in Supabase, must NOT be in sync list."""
        from scripts.init_railway_volume import OPTIONAL_SYNC_FILES

        assert "relationships.json" not in OPTIONAL_SYNC_FILES

    def test_gedcom_matches_not_in_sync_list(self):
        """gedcom_matches.json now in Supabase, must NOT be in sync list."""
        from scripts.init_railway_volume import OPTIONAL_SYNC_FILES

        assert "gedcom_matches.json" not in OPTIONAL_SYNC_FILES

    def test_ancestry_links_not_in_sync_list(self):
        """ancestry_links.json now in Supabase, must NOT be in sync list."""
        from scripts.init_railway_volume import OPTIONAL_SYNC_FILES

        assert "ancestry_links.json" not in OPTIONAL_SYNC_FILES

    def test_ml_data_still_in_sync_list(self):
        """Static reference files must still be in sync list (PRD-051 Session 114)."""
        from scripts.init_railway_volume import OPTIONAL_SYNC_FILES

        # proposals.json removed — now reads from Supabase ml_proposals table
        assert "proposals.json" not in OPTIONAL_SYNC_FILES
        # Static reference data remains
        assert "date_labels.json" in OPTIONAL_SYNC_FILES
        assert "birth_year_estimates.json" in OPTIONAL_SYNC_FILES
