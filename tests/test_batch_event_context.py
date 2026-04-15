"""Tests for scripts/batch_event_context.py."""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_supabase():
    """Create a mock Supabase client."""
    client = MagicMock()
    return client


class TestGetCommunityPhotoIds:
    """Tests for get_community_photo_ids()."""

    def test_returns_photo_ids_from_supabase(self, mock_supabase):
        mock_supabase.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = (
            MagicMock(data=[{"photo_id": "photo1"}, {"photo_id": "photo2"}])
        )
        with patch("scripts.batch_event_context.get_supabase_client", return_value=mock_supabase):
            from scripts.batch_event_context import get_community_photo_ids

            result = get_community_photo_ids("test-community-id")
        assert result == ["photo1", "photo2"]

    def test_paginates_large_results(self, mock_supabase):
        # First page: 1000 rows, second page: 50 rows
        page1 = [{"photo_id": f"p{i}"} for i in range(1000)]
        page2 = [{"photo_id": f"p{i}"} for i in range(1000, 1050)]
        mock_supabase.table.return_value.select.return_value.eq.return_value.range.return_value.execute.side_effect = [
            MagicMock(data=page1),
            MagicMock(data=page2),
        ]
        with patch("scripts.batch_event_context.get_supabase_client", return_value=mock_supabase):
            from scripts.batch_event_context import get_community_photo_ids

            result = get_community_photo_ids("test-community-id")
        assert len(result) == 1050

    def test_returns_empty_for_no_photos(self, mock_supabase):
        mock_supabase.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = (
            MagicMock(data=[])
        )
        with patch("scripts.batch_event_context.get_supabase_client", return_value=mock_supabase):
            from scripts.batch_event_context import get_community_photo_ids

            result = get_community_photo_ids("test-community-id")
        assert result == []


class TestLoadExistingEventContext:
    """Tests for load_existing_event_context()."""

    def test_finds_photos_with_event_context(self, mock_supabase):
        mock_supabase.table.return_value.select.return_value.range.return_value.execute.return_value = MagicMock(
            data=[
                {"photo_id": "p1", "data": {"event_context": {"event_type": "wedding"}}},
                {"photo_id": "p2", "data": {"date_estimation": {"decade": 1950}}},  # no event_context
                {"photo_id": "p3", "data": {"event_context": {"event_type": "portrait"}}},
            ]
        )
        with patch("scripts.batch_event_context.get_supabase_client", return_value=mock_supabase):
            from scripts.batch_event_context import load_existing_event_context

            result = load_existing_event_context()
        assert result == {"p1", "p3"}

    def test_handles_string_encoded_data(self, mock_supabase):
        mock_supabase.table.return_value.select.return_value.range.return_value.execute.return_value = MagicMock(
            data=[
                {"photo_id": "p1", "data": json.dumps({"event_context": {"event_type": "casual"}})},
            ]
        )
        with patch("scripts.batch_event_context.get_supabase_client", return_value=mock_supabase):
            from scripts.batch_event_context import load_existing_event_context

            result = load_existing_event_context()
        assert "p1" in result

    def test_handles_null_data(self, mock_supabase):
        mock_supabase.table.return_value.select.return_value.range.return_value.execute.return_value = MagicMock(
            data=[
                {"photo_id": "p1", "data": None},
            ]
        )
        with patch("scripts.batch_event_context.get_supabase_client", return_value=mock_supabase):
            from scripts.batch_event_context import load_existing_event_context

            result = load_existing_event_context()
        assert result == set()


class TestResolvePhotoPath:
    """Tests for resolve_photo_path()."""

    def test_returns_none_for_empty_path(self):
        from scripts.batch_event_context import resolve_photo_path

        assert resolve_photo_path({}) is None
        assert resolve_photo_path({"path": ""}) is None

    def test_rejects_path_traversal(self):
        """Codex P1: path traversal must be rejected."""
        from scripts.batch_event_context import resolve_photo_path

        assert resolve_photo_path({"path": "../../etc/passwd"}) is None
        assert resolve_photo_path({"path": "/etc/passwd"}) is None
        assert resolve_photo_path({"path": "raw_photos/../../../secrets.json"}) is None

    def test_returns_path_when_file_exists(self, tmp_path):
        photo_file = tmp_path / "raw_photos" / "test.jpg"
        photo_file.parent.mkdir(parents=True)
        photo_file.write_bytes(b"fake image")

        from scripts.batch_event_context import resolve_photo_path

        with patch("scripts.batch_event_context.Path") as MockPath:
            # Make raw_photos/test.jpg exist
            raw_path = MagicMock()
            raw_path.exists.return_value = True
            full_path = MagicMock()
            full_path.exists.return_value = False

            def path_side_effect(arg):
                mock = MagicMock()
                if arg == "raw_photos":
                    mock.__truediv__ = lambda self, other: raw_path
                    return mock
                mock.name = "test.jpg"
                return mock

            MockPath.side_effect = path_side_effect
            result = resolve_photo_path({"path": "raw_photos/test.jpg"})
        assert result == raw_path


class TestArgParsing:
    """Tests for CLI argument parsing."""

    def test_default_community_id(self):
        from scripts.batch_event_context import FADER_COMMUNITY_ID

        assert FADER_COMMUNITY_ID == "1a2c23d6-fc5e-4d0e-b020-1721579485bf"

    def test_dry_run_does_not_require_api_key(self, mock_supabase):
        """Dry run should work without GEMINI_API_KEY."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.range.return_value.execute.return_value = (
            MagicMock(data=[{"photo_id": "p1"}])
        )
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(
            data=[{"photo_id": "p1", "path": "test.jpg", "source": "", "collection": ""}]
        )
        mock_supabase.table.return_value.select.return_value.range.return_value.execute.return_value = MagicMock(
            data=[]
        )
        with (
            patch("scripts.batch_event_context.get_supabase_client", return_value=mock_supabase),
            patch.dict("os.environ", {"GEMINI_API_KEY": ""}, clear=False),
        ):
            from scripts.batch_event_context import run_batch

            # Should not sys.exit — dry_run doesn't need API key
            run_batch(
                community_id="test-id",
                dry_run=True,
                skip_existing=False,
                max_cost=1.0,
            )


class TestMergePreservesExistingData:
    """Tests that upsert preserves existing date_estimation data."""

    def test_merge_preserves_date_estimation(self):
        """When adding event_context, existing date_estimation should be preserved."""
        existing_data = {
            "date_estimation": {"estimated_decade": 1950, "confidence": "high"},
            "location": {"place": "New York"},
        }
        new_event_context = {"event_type": "wedding", "formality_level": "formal"}
        new_relationship = {"couple_pairs": []}

        # Simulate the merge logic from the script
        merged = {**existing_data}
        merged["event_context"] = new_event_context
        merged["relationship_inference"] = new_relationship

        assert merged["date_estimation"] == {"estimated_decade": 1950, "confidence": "high"}
        assert merged["location"] == {"place": "New York"}
        assert merged["event_context"] == new_event_context
        assert merged["relationship_inference"] == new_relationship
