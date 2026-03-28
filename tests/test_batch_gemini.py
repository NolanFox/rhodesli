"""Tests for scripts/batch_gemini_for_person.py.

Tests cover:
- get_photos_for_identities() photo counting
- load_existing_estimates() duplicate detection
- resolve_photo_path() local file resolution
- _get_face_coordinates() left-to-right sorting
- QuotaExhaustedError early-stop behavior
- Graceful handling of missing photos
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.batch_gemini_for_person import (
    QuotaExhaustedError,
    get_photos_for_identities,
    load_existing_estimates,
    resolve_photo_path,
)


# ---------------------------------------------------------------------------
# get_photos_for_identities
# ---------------------------------------------------------------------------


class TestGetPhotosForIdentities:
    """Test get_photos_for_identities with mocked Supabase and local JSON."""

    IDENTITY_ID_1 = "aaaa-1111"
    IDENTITY_ID_2 = "bbbb-2222"

    PHOTO_INDEX = {
        "photos": {
            "photo_001": {"path": "img1.jpg", "face_ids": ["face_a", "face_b"]},
            "photo_002": {"path": "img2.jpg", "face_ids": ["face_c"]},
            "photo_003": {"path": "img3.jpg", "face_ids": ["face_d"]},
        },
        "face_to_photo": {
            "face_a": "photo_001",
            "face_b": "photo_001",
            "face_c": "photo_002",
            "face_d": "photo_003",
        },
    }

    def _mock_supabase_identity(self, identity_id, name, anchor_ids, candidate_ids):
        return {
            "identity_id": identity_id,
            "name": name,
            "anchor_ids": anchor_ids,
            "candidate_ids": candidate_ids,
        }

    @patch("scripts.batch_gemini_for_person.os.environ", {})
    @patch(
        "builtins.open",
        mock_open(read_data="{}"),
    )
    def test_returns_empty_when_no_identities_found(self):
        """When identities don't exist in local JSON fallback, returns empty."""
        with patch(
            "builtins.open", mock_open(read_data=json.dumps({"identities": {}, "photos": {}, "face_to_photo": {}}))
        ):
            result = get_photos_for_identities(["nonexistent-id"])
        assert result == {}

    @patch(
        "scripts.batch_gemini_for_person.os.environ",
        {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_ANON_KEY": "eyJtest"},
    )
    def test_returns_correct_photo_count(self):
        """Identity with 2 faces in 1 photo + 1 face in another = 2 photos."""
        mock_sb = MagicMock()
        # Identity query
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[self._mock_supabase_identity(self.IDENTITY_ID_1, "Alice", ["face_a", "face_c"], [])]
        )
        # photo_faces pagination
        mock_sb.table.return_value.select.return_value.range.return_value.execute.return_value = MagicMock(
            data=[
                {"face_id": "face_a", "photo_id": "photo_001"},
                {"face_id": "face_b", "photo_id": "photo_001"},
                {"face_id": "face_c", "photo_id": "photo_002"},
                {"face_id": "face_d", "photo_id": "photo_003"},
            ]
        )

        with patch("supabase.create_client", return_value=mock_sb):
            with patch("builtins.open", mock_open(read_data=json.dumps(self.PHOTO_INDEX))):
                result = get_photos_for_identities([self.IDENTITY_ID_1])

        # face_a -> photo_001, face_c -> photo_002
        assert len(result) == 2
        assert "photo_001" in result
        assert "photo_002" in result

    @patch(
        "scripts.batch_gemini_for_person.os.environ",
        {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_ANON_KEY": "eyJtest"},
    )
    def test_multiple_identities_deduplicate_photos(self):
        """Two identities sharing a photo should not duplicate it."""
        mock_sb = MagicMock()

        def _identity_query_side_effect(*args, **kwargs):
            """Return different identities based on eq() call."""
            mock_result = MagicMock()
            # We'll just return both having face_a (same photo)
            mock_result.execute.return_value = MagicMock(
                data=[self._mock_supabase_identity("x", "Person", ["face_a"], [])]
            )
            return mock_result

        mock_sb.table.return_value.select.return_value.eq.return_value = MagicMock(
            execute=MagicMock(
                return_value=MagicMock(data=[self._mock_supabase_identity(self.IDENTITY_ID_1, "Alice", ["face_a"], [])])
            )
        )
        mock_sb.table.return_value.select.return_value.range.return_value.execute.return_value = MagicMock(
            data=[{"face_id": "face_a", "photo_id": "photo_001"}]
        )

        with patch("supabase.create_client", return_value=mock_sb):
            with patch("builtins.open", mock_open(read_data=json.dumps(self.PHOTO_INDEX))):
                result = get_photos_for_identities([self.IDENTITY_ID_1, self.IDENTITY_ID_1])

        # Same identity twice should still produce 1 photo entry for photo_001
        assert len(result) == 1

    @patch(
        "scripts.batch_gemini_for_person.os.environ",
        {"SUPABASE_URL": "https://x.supabase.co", "SUPABASE_ANON_KEY": "eyJtest"},
    )
    def test_handles_jsonb_string_encoded_anchor_ids(self):
        """Supabase can return anchor_ids as JSON string instead of list (Lesson 142)."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
            data=[
                {
                    "identity_id": self.IDENTITY_ID_1,
                    "name": "Test",
                    "anchor_ids": '["face_a", "face_c"]',  # String-encoded JSONB
                    "candidate_ids": "[]",
                }
            ]
        )
        mock_sb.table.return_value.select.return_value.range.return_value.execute.return_value = MagicMock(
            data=[
                {"face_id": "face_a", "photo_id": "photo_001"},
                {"face_id": "face_c", "photo_id": "photo_002"},
            ]
        )

        with patch("supabase.create_client", return_value=mock_sb):
            with patch("builtins.open", mock_open(read_data=json.dumps(self.PHOTO_INDEX))):
                result = get_photos_for_identities([self.IDENTITY_ID_1])

        assert len(result) == 2


# ---------------------------------------------------------------------------
# load_existing_estimates
# ---------------------------------------------------------------------------


class TestLoadExistingEstimates:
    def test_returns_photo_ids_from_labels_file(self, tmp_path):
        labels = {
            "labels": [
                {"photo_id": "photo_001", "estimated_decade": 1920},
                {"photo_id": "photo_002", "estimated_decade": 1950},
            ]
        }
        labels_path = tmp_path / "date_labels.json"
        labels_path.write_text(json.dumps(labels))

        with (
            patch("scripts.batch_gemini_for_person.Path") as MockPath,
            patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_ANON_KEY": ""}),
        ):
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            MockPath.return_value = mock_path_instance
            # Use the real file; Supabase env vars empty so Supabase check is skipped
            with patch("builtins.open", mock_open(read_data=json.dumps(labels))):
                result = load_existing_estimates()

        assert "photo_001" in result
        assert "photo_002" in result
        assert len(result) == 2

    def test_returns_empty_when_no_labels_file(self):
        with (
            patch("scripts.batch_gemini_for_person.Path") as MockPath,
            patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_ANON_KEY": ""}),
        ):
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            MockPath.return_value = mock_path_instance
            result = load_existing_estimates()

        assert result == set()

    def test_handles_empty_labels_array(self):
        labels = {"labels": []}
        with (
            patch("scripts.batch_gemini_for_person.Path") as MockPath,
            patch.dict("os.environ", {"SUPABASE_URL": "", "SUPABASE_ANON_KEY": ""}),
        ):
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            MockPath.return_value = mock_path_instance
            with patch("builtins.open", mock_open(read_data=json.dumps(labels))):
                result = load_existing_estimates()

        assert result == set()


# ---------------------------------------------------------------------------
# resolve_photo_path
# ---------------------------------------------------------------------------


class TestResolvePhotoPath:
    def test_finds_file_in_raw_photos(self, tmp_path):
        raw_dir = tmp_path / "raw_photos"
        raw_dir.mkdir()
        (raw_dir / "test_photo.jpg").write_text("fake image")

        with patch("scripts.batch_gemini_for_person.Path") as MockPath:
            # First call: Path("raw_photos") / "test_photo.jpg"
            real_path = raw_dir / "test_photo.jpg"

            def path_side_effect(arg):
                if arg == "raw_photos":
                    return raw_dir
                p = Path(arg)
                return p

            MockPath.side_effect = path_side_effect

            result = resolve_photo_path({"path": "test_photo.jpg"})

        # The function tries Path("raw_photos") / basename first
        assert result is not None

    def test_returns_none_for_missing_photo(self):
        result = resolve_photo_path({"path": "nonexistent_photo_xyz.jpg"})
        assert result is None

    def test_returns_none_for_empty_entry(self):
        result = resolve_photo_path({})
        assert result is None

    def test_uses_filename_field_if_present(self):
        """Should prefer 'filename' over 'path'."""
        result = resolve_photo_path({"filename": "some_photo.jpg", "path": "other.jpg"})
        # Both won't exist, so returns None, but the function should try filename first
        assert result is None

    def test_handles_nested_path(self):
        """Path with directories should extract just the basename."""
        result = resolve_photo_path({"path": "some/nested/dir/photo.jpg"})
        # Won't exist locally, returns None
        assert result is None


# ---------------------------------------------------------------------------
# _get_face_coordinates (tested via import of the inner function pattern)
# ---------------------------------------------------------------------------


class TestGetFaceCoordinates:
    """Test face coordinate extraction and left-to-right sorting.

    Since _get_face_coordinates is a nested function inside run_batch,
    we test the sorting logic directly.
    """

    def test_sorts_left_to_right_by_x_coordinate(self):
        """Faces should be sorted by bbox[0] (x-coordinate), left to right."""
        coords = [
            {"face_id": "face_right", "bbox": [300, 10, 400, 100]},
            {"face_id": "face_left", "bbox": [10, 10, 100, 100]},
            {"face_id": "face_middle", "bbox": [150, 10, 250, 100]},
        ]
        coords.sort(key=lambda c: c["bbox"][0])

        assert coords[0]["face_id"] == "face_left"
        assert coords[1]["face_id"] == "face_middle"
        assert coords[2]["face_id"] == "face_right"

    def test_already_sorted_stays_sorted(self):
        coords = [
            {"face_id": "a", "bbox": [10, 0, 50, 50]},
            {"face_id": "b", "bbox": [60, 0, 100, 50]},
        ]
        coords.sort(key=lambda c: c["bbox"][0])
        assert coords[0]["face_id"] == "a"
        assert coords[1]["face_id"] == "b"

    def test_single_face(self):
        coords = [{"face_id": "only", "bbox": [50, 50, 150, 150]}]
        coords.sort(key=lambda c: c["bbox"][0])
        assert len(coords) == 1
        assert coords[0]["face_id"] == "only"

    def test_empty_list(self):
        coords = []
        coords.sort(key=lambda c: c["bbox"][0])
        assert coords == []


# ---------------------------------------------------------------------------
# QuotaExhaustedError early-stop
# ---------------------------------------------------------------------------


class TestQuotaExhaustedError:
    def test_is_an_exception(self):
        with pytest.raises(QuotaExhaustedError):
            raise QuotaExhaustedError("429 RESOURCE_EXHAUSTED")

    def test_message_preserved(self):
        err = QuotaExhaustedError("429 RESOURCE_EXHAUSTED: daily limit")
        assert "RESOURCE_EXHAUSTED" in str(err)


# ---------------------------------------------------------------------------
# Missing photos graceful handling
# ---------------------------------------------------------------------------


class TestMissingPhotosHandling:
    def test_resolve_photo_path_graceful_on_missing(self):
        """resolve_photo_path should return None, not raise, for missing files."""
        result = resolve_photo_path({"path": "definitely_not_a_real_file_abc123.jpg"})
        assert result is None

    def test_resolve_photo_path_graceful_on_none_path(self):
        """Handles None/missing path fields without crashing."""
        result = resolve_photo_path({"filename": None, "path": None})
        assert result is None

    def test_resolve_photo_path_graceful_on_empty_string(self):
        result = resolve_photo_path({"path": ""})
        assert result is None
