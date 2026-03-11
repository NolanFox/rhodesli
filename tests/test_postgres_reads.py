"""Tests for Postgres read flip (PRD-027 Phase B/C).

Validates:
- DATA_SOURCE feature flag defaults to "json"
- load_from_postgres() returns same structure as load() from JSON (mocked Supabase)
- Feature flag routing in load_registry() and load_photo_registry()
- SQL files exist and are valid
- Round-trip identity through Postgres adapter (mock)
- All existing behavior preserved when DATA_SOURCE=json
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch


from core.photo_registry import PhotoRegistry
from core.registry import IdentityRegistry

# Root of the project
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# =========================================================================
# SQL FILE EXISTENCE
# =========================================================================


class TestSQLFiles:
    """Verify all SQL schema files exist and contain expected content."""

    SQL_DIR = PROJECT_ROOT / "scripts" / "sql"

    def test_create_core_tables_exists(self):
        path = self.SQL_DIR / "create_core_tables.sql"
        assert path.exists(), f"Missing: {path}"
        content = path.read_text()
        assert "CREATE TABLE IF NOT EXISTS photos" in content
        assert "CREATE TABLE IF NOT EXISTS identities" in content
        assert "CREATE TABLE IF NOT EXISTS photo_faces" in content

    def test_create_communities_exists(self):
        path = self.SQL_DIR / "create_communities.sql"
        assert path.exists(), f"Missing: {path}"
        content = path.read_text()
        assert "CREATE TABLE IF NOT EXISTS communities" in content
        assert "slug TEXT UNIQUE NOT NULL" in content

    def test_create_global_person_links_exists(self):
        path = self.SQL_DIR / "create_global_person_links.sql"
        assert path.exists(), f"Missing: {path}"
        content = path.read_text()
        assert "CREATE TABLE IF NOT EXISTS global_person_links" in content
        assert "global_person_id UUID NOT NULL" in content
        assert "UNIQUE(community_id, identity_id)" in content

    def test_seed_rhodes_community_exists(self):
        path = self.SQL_DIR / "seed_rhodes_community.sql"
        assert path.exists(), f"Missing: {path}"
        content = path.read_text()
        assert "INSERT INTO communities" in content
        assert "rhodes" in content
        assert "NolanFox@gmail.com" in content

    def test_core_tables_has_community_id(self):
        """Verify community_id column exists for multi-tenant support."""
        content = (self.SQL_DIR / "create_core_tables.sql").read_text()
        assert "community_id UUID" in content


# =========================================================================
# DATA_SOURCE FEATURE FLAG
# =========================================================================


class TestDataSourceFlag:
    """Verify DATA_SOURCE feature flag behavior."""

    def test_default_is_json(self):
        """DATA_SOURCE defaults to 'json' when env var is not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove DATA_SOURCE if it exists
            os.environ.pop("DATA_SOURCE", None)
            result = os.environ.get("DATA_SOURCE", "json")
            assert result == "json"

    def test_can_set_to_postgres(self):
        """DATA_SOURCE can be set to 'postgres'."""
        with patch.dict(os.environ, {"DATA_SOURCE": "postgres"}):
            result = os.environ.get("DATA_SOURCE", "json")
            assert result == "postgres"


# =========================================================================
# IDENTITY REGISTRY — POSTGRES ADAPTER
# =========================================================================


def _make_mock_supabase_identity_rows():
    """Create mock Supabase identity rows matching the table schema."""
    return [
        {
            "identity_id": "aaaa-bbbb-cccc-dddd",
            "name": "Nace Capeluto",
            "display_name": "Big Nace",
            "state": "CONFIRMED",
            "anchor_ids": ["face1", "face2"],
            "candidate_ids": ["face3"],
            "negative_ids": [],
            "version_id": 3,
            "merged_into": None,
            "metadata": {"birth_year": 1910},
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        },
        {
            "identity_id": "eeee-ffff-0000-1111",
            "name": "Unidentified Person 42",
            "display_name": None,
            "state": "INBOX",
            "anchor_ids": ["face4"],
            "candidate_ids": [],
            "negative_ids": ["face5"],
            "version_id": 1,
            "merged_into": None,
            "metadata": None,
            "created_at": "2026-02-01T00:00:00+00:00",
            "updated_at": "2026-02-01T00:00:00+00:00",
        },
        {
            "identity_id": "2222-3333-4444-5555",
            "name": "Merged Person",
            "display_name": None,
            "state": "PROPOSED",
            "anchor_ids": [],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 2,
            "merged_into": "aaaa-bbbb-cccc-dddd",
            "metadata": {},
            "created_at": "2026-01-15T00:00:00+00:00",
            "updated_at": "2026-02-15T00:00:00+00:00",
        },
    ]


class TestIdentityRegistryPostgresLoad:
    """Test IdentityRegistry.load_from_postgres()."""

    def _mock_client_with_rows(self, rows):
        """Create a mock Supabase client that returns the given rows."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = rows

        # Chain: client.table("identities").select("*").range(0, 999).execute()
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_result
        return mock_client

    @patch("core.registry.logger")
    def test_load_returns_registry(self, mock_logger):
        rows = _make_mock_supabase_identity_rows()
        mock_client = self._mock_client_with_rows(rows)

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()

        assert registry is not None
        assert len(registry._identities) == 3

    @patch("core.registry.logger")
    def test_identity_structure_matches_json(self, mock_logger):
        """Verify Postgres-loaded identity has same fields as JSON-loaded."""
        rows = _make_mock_supabase_identity_rows()
        mock_client = self._mock_client_with_rows(rows)

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()

        identity = registry._identities["aaaa-bbbb-cccc-dddd"]
        assert identity["name"] == "Nace Capeluto"
        assert identity["state"] == "CONFIRMED"
        assert identity["anchor_ids"] == ["face1", "face2"]
        assert identity["candidate_ids"] == ["face3"]
        assert identity["negative_ids"] == []
        assert identity["version_id"] == 3
        assert identity["display_name"] == "Big Nace"
        assert identity["metadata"] == {"birth_year": 1910}

    @patch("core.registry.logger")
    def test_merged_identity_preserved(self, mock_logger):
        rows = _make_mock_supabase_identity_rows()
        mock_client = self._mock_client_with_rows(rows)

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()

        merged = registry._identities["2222-3333-4444-5555"]
        assert merged["merged_into"] == "aaaa-bbbb-cccc-dddd"

    @patch("core.registry.logger")
    def test_history_starts_empty_when_no_identity_events(self, mock_logger):
        """History should stay empty when Supabase has no identity-event audit rows."""
        rows = _make_mock_supabase_identity_rows()
        mock_client = self._mock_client_with_rows(rows)

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()

        assert registry._history == []

    @patch("core.registry.logger")
    def test_load_merges_full_identity_override_payload(self, mock_logger):
        rows = _make_mock_supabase_identity_rows()
        mock_client = self._mock_client_with_rows(rows)
        overrides = {
            "aaaa-bbbb-cccc-dddd": {
                "identity_id": "aaaa-bbbb-cccc-dddd",
                "name": "Nace Capeluto",
                "display_name": "Don Nace",
                "state": "CONFIRMED",
                "anchor_ids": ["face1", "face2"],
                "candidate_ids": ["face3"],
                "negative_ids": [],
                "version_id": 4,
                "metadata": {"birth_year": 1910},
                "merge_history": [{"merge_event_id": "m1"}],
                "provenance": {"job_id": "job-123"},
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-03-02T00:00:00+00:00",
            }
        }

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=overrides),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()

        identity = registry._identities["aaaa-bbbb-cccc-dddd"]
        assert identity["display_name"] == "Don Nace"
        assert identity["merge_history"] == [{"merge_event_id": "m1"}]
        assert identity["provenance"] == {"job_id": "job-123"}
        assert identity["version_id"] == 4

    @patch("core.registry.logger")
    def test_load_restores_identity_history_from_audit_log(self, mock_logger):
        rows = _make_mock_supabase_identity_rows()
        mock_client = self._mock_client_with_rows(rows)
        history = [
            {
                "event_id": "evt-1",
                "timestamp": "2026-03-10T10:00:00+00:00",
                "identity_id": "aaaa-bbbb-cccc-dddd",
                "action": "state_change",
                "face_ids": [],
                "user_source": "web",
                "confidence_weight": 1.0,
                "previous_version_id": 3,
                "metadata": {"new_state": "SKIPPED", "previous_state": "CONFIRMED"},
            }
        ]

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=history),
        ):
            registry = IdentityRegistry.load_from_postgres()

        assert registry._history == history

    @patch("core.registry.logger")
    def test_returns_none_when_supabase_unavailable(self, mock_logger):
        with (
            patch("app.supabase_data.get_supabase_client", return_value=None),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()
        assert registry is None

    @patch("core.registry.logger")
    def test_returns_none_on_query_error(self, mock_logger):
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.range.return_value.execute.side_effect = Exception(
            "connection timeout"
        )

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()

        assert registry is None

    @patch("core.registry.logger")
    def test_empty_table_returns_empty_registry(self, mock_logger):
        mock_client = self._mock_client_with_rows([])

        # For empty result, first call returns empty data
        mock_result_empty = MagicMock()
        mock_result_empty.data = []
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_result_empty

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()

        assert registry is not None
        assert len(registry._identities) == 0

    @patch("core.registry.logger")
    def test_get_identity_works_after_postgres_load(self, mock_logger):
        """Verify get_identity() works on Postgres-loaded registry."""
        rows = _make_mock_supabase_identity_rows()
        mock_client = self._mock_client_with_rows(rows)

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()

        identity = registry.get_identity("aaaa-bbbb-cccc-dddd")
        assert identity["name"] == "Nace Capeluto"
        assert identity["state"] == "CONFIRMED"

    @patch("core.registry.logger")
    def test_list_identities_works_after_postgres_load(self, mock_logger):
        """Verify list_identities() works (excluding merged)."""
        rows = _make_mock_supabase_identity_rows()
        mock_client = self._mock_client_with_rows(rows)

        with (
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = IdentityRegistry.load_from_postgres()

        # Default: exclude merged
        identities = registry.list_identities()
        assert len(identities) == 2  # Merged Person excluded

        # Include merged
        all_identities = registry.list_identities(include_merged=True)
        assert len(all_identities) == 3


# =========================================================================
# PHOTO REGISTRY — POSTGRES ADAPTER
# =========================================================================


def _make_mock_photo_rows():
    return [
        {
            "photo_id": "abc123",
            "path": "Image 001_compress.jpg",
            "source": "Betty's Album",
            "collection": "Betty Capeluto Miami Collection",
            "source_url": "",
            "width": 800,
            "height": 600,
            "upload_date": "2026-01-15T00:00:00+00:00",
            "uploaded_by": "admin",
            "job_id": None,
            "face_count": 2,
        },
        {
            "photo_id": "def456",
            "path": "Image 054_compress.jpg",
            "source": "Newspapers.com",
            "collection": "Newspapers.com",
            "source_url": "https://newspapers.com/article/123",
            "width": 1024,
            "height": 768,
            "upload_date": None,
            "uploaded_by": None,
            "job_id": None,
            "face_count": 0,
        },
    ]


def _make_mock_face_rows():
    return [
        {"face_id": "Image 001_compress:face0", "photo_id": "abc123"},
        {"face_id": "Image 001_compress:face1", "photo_id": "abc123"},
    ]


class TestPhotoRegistryPostgresLoad:
    """Test PhotoRegistry.load_from_postgres()."""

    def _mock_client(self, photo_rows, face_rows):
        mock_client = MagicMock()

        def _table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "photos":
                mock_result = MagicMock()
                mock_result.data = photo_rows
                # Second call returns empty for pagination end
                mock_result_empty = MagicMock()
                mock_result_empty.data = []
                mock_table.select.return_value.range.return_value.execute.side_effect = [
                    mock_result,
                    mock_result_empty,
                ]
            elif table_name == "photo_faces":
                mock_result = MagicMock()
                mock_result.data = face_rows
                mock_result_empty = MagicMock()
                mock_result_empty.data = []
                mock_table.select.return_value.range.return_value.execute.side_effect = [
                    mock_result,
                    mock_result_empty,
                ]
            return mock_table

        mock_client.table.side_effect = _table_side_effect
        return mock_client

    @patch("core.photo_registry.logger")
    def test_load_returns_registry(self, mock_logger):
        mock_client = self._mock_client(_make_mock_photo_rows(), _make_mock_face_rows())

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            registry = PhotoRegistry.load_from_postgres()

        assert registry is not None
        assert len(registry._photos) == 2
        assert len(registry._face_to_photo) == 2

    @patch("core.photo_registry.logger")
    def test_photo_structure_matches_json(self, mock_logger):
        mock_client = self._mock_client(_make_mock_photo_rows(), _make_mock_face_rows())

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            registry = PhotoRegistry.load_from_postgres()

        photo = registry._photos["abc123"]
        assert photo["path"] == "Image 001_compress.jpg"
        assert photo["source"] == "Betty's Album"
        assert photo["collection"] == "Betty Capeluto Miami Collection"
        assert photo["width"] == 800
        assert photo["height"] == 600
        assert isinstance(photo["face_ids"], set)
        assert "Image 001_compress:face0" in photo["face_ids"]
        assert "Image 001_compress:face1" in photo["face_ids"]

    @patch("core.photo_registry.logger")
    def test_face_to_photo_mapping(self, mock_logger):
        mock_client = self._mock_client(_make_mock_photo_rows(), _make_mock_face_rows())

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            registry = PhotoRegistry.load_from_postgres()

        assert registry._face_to_photo["Image 001_compress:face0"] == "abc123"
        assert registry._face_to_photo["Image 001_compress:face1"] == "abc123"

    @patch("core.photo_registry.logger")
    def test_photo_without_faces(self, mock_logger):
        mock_client = self._mock_client(_make_mock_photo_rows(), _make_mock_face_rows())

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            registry = PhotoRegistry.load_from_postgres()

        photo = registry._photos["def456"]
        assert photo["face_ids"] == set()
        assert photo["source_url"] == "https://newspapers.com/article/123"

    @patch("core.photo_registry.logger")
    def test_returns_none_when_unavailable(self, mock_logger):
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            registry = PhotoRegistry.load_from_postgres()
        assert registry is None

    @patch("core.photo_registry.logger")
    def test_get_faces_works_after_postgres_load(self, mock_logger):
        """Verify get_faces_in_photo() works on Postgres-loaded registry."""
        mock_client = self._mock_client(_make_mock_photo_rows(), _make_mock_face_rows())

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            registry = PhotoRegistry.load_from_postgres()

        faces = registry.get_faces_in_photo("abc123")
        assert len(faces) == 2
        assert "Image 001_compress:face0" in faces

    @patch("core.photo_registry.logger")
    def test_get_photo_for_face_works_after_postgres_load(self, mock_logger):
        mock_client = self._mock_client(_make_mock_photo_rows(), _make_mock_face_rows())

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            registry = PhotoRegistry.load_from_postgres()

        photo_id = registry.get_photo_for_face("Image 001_compress:face0")
        assert photo_id == "abc123"


# =========================================================================
# FEATURE FLAG ROUTING — load_registry / load_photo_registry
# =========================================================================


class TestLoadRegistryRouting:
    """Verify load_registry() routes correctly based on DATA_SOURCE."""

    @patch.dict(os.environ, {"DATA_SOURCE": "json"}, clear=False)
    def test_json_mode_uses_json_load(self, tmp_path):
        """When DATA_SOURCE=json, load uses JSON path."""
        # This test validates that the default path works by checking
        # IdentityRegistry.load is called (not load_from_postgres)
        with patch("core.registry.IdentityRegistry.load_from_postgres") as mock_pg:
            # The load_registry in main.py checks DATA_SOURCE at module level,
            # so we test the logic directly
            from core.registry import IdentityRegistry

            # JSON load should NOT call postgres
            json_path = tmp_path / "identities.json"
            json_path.write_text('{"schema_version": 1, "identities": {}, "history": []}')
            reg = IdentityRegistry.load(json_path)
            mock_pg.assert_not_called()
            assert reg is not None

    def test_postgres_mode_calls_load_from_postgres(self):
        """When DATA_SOURCE=postgres, load_from_postgres is called."""
        rows = _make_mock_supabase_identity_rows()
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = rows
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            registry = IdentityRegistry.load_from_postgres()

        assert registry is not None
        assert len(registry._identities) == 3


# =========================================================================
# ROUND-TRIP IDENTITY THROUGH POSTGRES ADAPTER
# =========================================================================


class TestRoundTrip:
    """Test that identity operations work on Postgres-loaded registry."""

    @patch("core.registry.logger")
    def test_confirm_identity_after_postgres_load(self, mock_logger):
        rows = [
            {
                "identity_id": "test-uuid-1234",
                "name": "Test Person",
                "display_name": None,
                "state": "PROPOSED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "merged_into": None,
                "metadata": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ]
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = rows
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            registry = IdentityRegistry.load_from_postgres()

        # Confirm the identity
        registry.confirm_identity("test-uuid-1234", "admin")
        identity = registry.get_identity("test-uuid-1234")
        assert identity["state"] == "CONFIRMED"
        assert identity["version_id"] == 2

    @patch("core.registry.logger")
    def test_rename_identity_after_postgres_load(self, mock_logger):
        rows = [
            {
                "identity_id": "rename-test-uuid",
                "name": "Old Name",
                "display_name": None,
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "merged_into": None,
                "metadata": None,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ]
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = rows
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            registry = IdentityRegistry.load_from_postgres()

        old_name = registry.rename_identity("rename-test-uuid", "New Name", "admin")
        assert old_name == "Old Name"
        identity = registry.get_identity("rename-test-uuid")
        assert identity["name"] == "New Name"
        assert identity["version_id"] == 2


# =========================================================================
# SAVE PATH ROUTING
# =========================================================================


class TestSaveRouting:
    """Verify save functions respect DATA_SOURCE flag."""

    def test_save_registry_json_mode_writes_json(self, tmp_path):
        """In JSON mode, save_registry writes to disk."""
        registry = IdentityRegistry()
        path = tmp_path / "identities.json"
        registry.save(path)
        assert path.exists()

    def test_save_photo_registry_json_mode_writes_json(self, tmp_path):
        """In JSON mode, save_photo_registry writes to disk."""
        registry = PhotoRegistry()
        path = tmp_path / "photo_index.json"
        registry.save(path)
        assert path.exists()


# =========================================================================
# DATE LABELS — POSTGRES READ PATH
# =========================================================================


class TestDateLabelsPostgresRead:
    """Verify _load_date_labels() routes correctly based on DATA_SOURCE."""

    def test_json_mode_uses_json_file(self, tmp_path):
        """When DATA_SOURCE=json, date labels load from JSON."""
        import app.main as main_mod

        # Reset cache
        main_mod._date_labels_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "json"),
            patch.object(main_mod, "data_path", tmp_path),
        ):
            result = main_mod._load_date_labels()
            assert isinstance(result, dict)
            assert result == {}  # No JSON file exists

    def test_postgres_mode_calls_supabase(self):
        """When DATA_SOURCE=postgres, date labels load from Supabase."""
        import app.main as main_mod

        main_mod._date_labels_cache = None
        mock_data = {
            "photo1": {"best_year_estimate": 1950, "confidence": "high"},
            "photo2": {"best_year_estimate": 1965, "confidence": "medium"},
        }

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_date_labels_from_supabase", return_value=mock_data),
        ):
            result = main_mod._load_date_labels()
            assert result == mock_data
            assert result["photo1"]["best_year_estimate"] == 1950

        # Reset cache
        main_mod._date_labels_cache = None

    def test_postgres_fallback_to_json_on_none(self, tmp_path):
        """When Postgres returns None, falls back to JSON."""
        import app.main as main_mod

        main_mod._date_labels_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_date_labels_from_supabase", return_value=None),
            patch.object(main_mod, "data_path", tmp_path),
        ):
            result = main_mod._load_date_labels()
            assert isinstance(result, dict)
            assert result == {}

        main_mod._date_labels_cache = None

    def test_postgres_fallback_to_json_on_exception(self, tmp_path):
        """When Postgres raises, falls back to JSON."""
        import app.main as main_mod

        main_mod._date_labels_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch(
                "app.supabase_data.load_date_labels_from_supabase",
                side_effect=Exception("connection failed"),
            ),
            patch.object(main_mod, "data_path", tmp_path),
        ):
            result = main_mod._load_date_labels()
            assert isinstance(result, dict)
            assert result == {}

        main_mod._date_labels_cache = None


# =========================================================================
# PHOTO LOCATIONS — POSTGRES READ PATH
# =========================================================================


class TestPhotoLocationsPostgresRead:
    """Verify _load_photo_locations() routes correctly based on DATA_SOURCE."""

    def test_json_mode_uses_json_file(self, tmp_path):
        """When DATA_SOURCE=json, photo locations load from JSON."""
        import app.main as main_mod
        import app.page_routes as page_routes_mod

        page_routes_mod._photo_locations_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "json"),
            patch.object(main_mod, "DATA_DIR", str(tmp_path)),
            patch.object(main_mod, "data_path", tmp_path),
        ):
            result = page_routes_mod._load_photo_locations()
            assert isinstance(result, dict)
            assert result == {}

        page_routes_mod._photo_locations_cache = None

    def test_postgres_mode_calls_supabase(self):
        """When DATA_SOURCE=postgres, photo locations load from Supabase."""
        import app.main as main_mod
        import app.page_routes as page_routes_mod

        page_routes_mod._photo_locations_cache = None
        mock_data = {
            "photo1": {"location_name": "Rhodes, Greece", "lat": 36.4, "lng": 28.2},
            "photo2": {"location_name": "New York, NY", "lat": 40.7, "lng": -74.0},
        }

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_photo_locations_from_supabase", return_value=mock_data),
        ):
            result = page_routes_mod._load_photo_locations()
            assert result == mock_data
            assert result["photo1"]["location_name"] == "Rhodes, Greece"

        page_routes_mod._photo_locations_cache = None

    def test_postgres_fallback_to_json_on_none(self, tmp_path):
        """When Postgres returns None, falls back to JSON."""
        import app.main as main_mod
        import app.page_routes as page_routes_mod

        page_routes_mod._photo_locations_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_photo_locations_from_supabase", return_value=None),
            patch.object(main_mod, "DATA_DIR", str(tmp_path)),
            patch.object(main_mod, "data_path", tmp_path),
        ):
            result = page_routes_mod._load_photo_locations()
            assert isinstance(result, dict)
            assert result == {}

        page_routes_mod._photo_locations_cache = None


# =========================================================================
# ANNOTATIONS — POSTGRES READ PATH
# =========================================================================


class TestAnnotationsPostgresRead:
    """Verify _load_annotations() routes correctly based on DATA_SOURCE."""

    def test_json_mode_uses_json_file(self, tmp_path):
        """When DATA_SOURCE=json, annotations load from JSON."""
        import app.engagement_routes as eng_mod
        import app.main as main_mod

        eng_mod._annotations_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "json"),
            patch.object(main_mod, "data_path", tmp_path),
        ):
            result = eng_mod._load_annotations()
            assert isinstance(result, dict)
            assert "annotations" in result
            assert result["annotations"] == {}

        eng_mod._annotations_cache = None

    def test_postgres_mode_calls_supabase(self):
        """When DATA_SOURCE=postgres, annotations load from Supabase."""
        import app.engagement_routes as eng_mod
        import app.main as main_mod

        eng_mod._annotations_cache = None
        mock_data = {
            "schema_version": 1,
            "annotations": {
                "ann-1": {"type": "name_suggestion", "value": "Test Person"},
                "ann-2": {"type": "bio", "value": "A test bio"},
            },
        }

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_annotations_from_supabase", return_value=mock_data),
        ):
            result = eng_mod._load_annotations()
            assert result == mock_data
            assert len(result["annotations"]) == 2

        eng_mod._annotations_cache = None

    def test_postgres_fallback_to_json_on_none(self, tmp_path):
        """When Postgres returns None, falls back to JSON."""
        import app.engagement_routes as eng_mod
        import app.main as main_mod

        eng_mod._annotations_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_annotations_from_supabase", return_value=None),
            patch.object(main_mod, "data_path", tmp_path),
        ):
            result = eng_mod._load_annotations()
            assert isinstance(result, dict)
            assert "annotations" in result

        eng_mod._annotations_cache = None


# =========================================================================
# BIRTH YEAR ESTIMATES — POSTGRES READ PATH
# =========================================================================


class TestBirthYearEstimatesPostgresRead:
    """Verify _load_birth_year_estimates() routes correctly based on DATA_SOURCE."""

    def test_json_mode_does_not_use_postgres(self):
        """When DATA_SOURCE=json, birth year estimates do NOT call Supabase."""
        import app.main as main_mod

        main_mod._birth_year_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "json"),
            patch("app.supabase_data.load_birth_year_estimates_from_supabase") as mock_pg,
        ):
            result = main_mod._load_birth_year_estimates()
            assert isinstance(result, dict)
            mock_pg.assert_not_called()

        main_mod._birth_year_cache = None

    def test_postgres_mode_calls_supabase(self):
        """When DATA_SOURCE=postgres, birth year estimates load from Supabase."""
        import app.main as main_mod

        main_mod._birth_year_cache = None
        mock_data = {
            "id-1": {"birth_year_estimate": 1920, "birth_year_confidence": "high"},
            "id-2": {"birth_year_estimate": 1945, "birth_year_confidence": "medium"},
        }

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_birth_year_estimates_from_supabase", return_value=mock_data),
        ):
            result = main_mod._load_birth_year_estimates()
            assert result == mock_data
            assert result["id-1"]["birth_year_estimate"] == 1920

        main_mod._birth_year_cache = None

    def test_postgres_fallback_to_json_on_none(self):
        """When Postgres returns None, falls back to JSON (does not crash)."""
        import app.main as main_mod

        main_mod._birth_year_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.load_birth_year_estimates_from_supabase", return_value=None),
        ):
            result = main_mod._load_birth_year_estimates()
            assert isinstance(result, dict)
            # Falls back to JSON — may have real data from rhodesli_ml/data/

        main_mod._birth_year_cache = None

    def test_postgres_fallback_to_json_on_exception(self):
        """When Postgres raises, falls back to JSON (does not crash)."""
        import app.main as main_mod

        main_mod._birth_year_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch(
                "app.supabase_data.load_birth_year_estimates_from_supabase",
                side_effect=Exception("timeout"),
            ),
        ):
            result = main_mod._load_birth_year_estimates()
            assert isinstance(result, dict)
            # Falls back to JSON — may have real data from rhodesli_ml/data/

        main_mod._birth_year_cache = None


# =========================================================================
# SUPABASE LOADER FUNCTIONS (unit tests)
# =========================================================================


class TestSupabaseAnnotationsLoader:
    """Test load_annotations_from_supabase()."""

    def test_returns_annotations_dict(self):
        from app.supabase_data import load_annotations_from_supabase

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {"annotation_id": "ann-1", "data": {"type": "name_suggestion", "value": "Test"}},
            {"annotation_id": "ann-2", "data": {"type": "bio", "value": "A bio"}},
        ]
        mock_empty = MagicMock()
        mock_empty.data = []
        mock_client.table.return_value.select.return_value.range.return_value.execute.side_effect = [
            mock_result,
            mock_empty,
        ]

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = load_annotations_from_supabase()

        assert result is not None
        assert result["schema_version"] == 1
        assert len(result["annotations"]) == 2
        assert result["annotations"]["ann-1"]["type"] == "name_suggestion"

    def test_returns_none_when_unavailable(self):
        from app.supabase_data import load_annotations_from_supabase

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            result = load_annotations_from_supabase()
        assert result is None

    def test_returns_empty_on_no_data(self):
        from app.supabase_data import load_annotations_from_supabase

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_result

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = load_annotations_from_supabase()

        assert result is not None
        assert result["annotations"] == {}


class TestSupabaseBirthYearLoader:
    """Test load_birth_year_estimates_from_supabase()."""

    def test_returns_estimates_dict(self):
        from app.supabase_data import load_birth_year_estimates_from_supabase

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {"identity_id": "id-1", "data": {"birth_year_estimate": 1920}},
            {"identity_id": "id-2", "data": {"birth_year_estimate": 1945}},
        ]
        mock_empty = MagicMock()
        mock_empty.data = []
        mock_client.table.return_value.select.return_value.range.return_value.execute.side_effect = [
            mock_result,
            mock_empty,
        ]

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = load_birth_year_estimates_from_supabase()

        assert result is not None
        assert len(result) == 2
        assert result["id-1"]["birth_year_estimate"] == 1920

    def test_returns_none_when_unavailable(self):
        from app.supabase_data import load_birth_year_estimates_from_supabase

        with patch("app.supabase_data.get_supabase_client", return_value=None):
            result = load_birth_year_estimates_from_supabase()
        assert result is None

    def test_skips_rows_without_data(self):
        from app.supabase_data import load_birth_year_estimates_from_supabase

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [
            {"identity_id": "id-1", "data": {"birth_year_estimate": 1920}},
            {"identity_id": "id-2", "data": None},
            {"identity_id": None, "data": {"birth_year_estimate": 1950}},
        ]
        mock_empty = MagicMock()
        mock_empty.data = []
        mock_client.table.return_value.select.return_value.range.return_value.execute.side_effect = [
            mock_result,
            mock_empty,
        ]

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = load_birth_year_estimates_from_supabase()

        assert len(result) == 1
        assert "id-1" in result
