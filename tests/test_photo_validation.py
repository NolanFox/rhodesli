"""
Tests for photo entry schema validation (Rule #16).

Validates that incomplete photo entries are caught at write time,
not discovered in production.
"""

import json
from pathlib import Path

import pytest

from core.photo_registry import (
    REQUIRED_PHOTO_FIELDS,
    PhotoRegistry,
    validate_photo_entry,
)


class TestValidatePhotoEntry:
    """Unit tests for validate_photo_entry()."""

    def test_valid_entry_passes(self):
        """A complete photo entry raises no error."""
        entry = {"path": "img.jpg", "width": 800, "height": 600, "collection": "Album"}
        validate_photo_entry("p1", entry)  # should not raise

    def test_missing_field_raises(self):
        """Entry missing a required field raises ValueError with field name."""
        entry = {"path": "img.jpg", "width": 800, "height": 600}  # no collection
        with pytest.raises(ValueError, match="collection"):
            validate_photo_entry("p1", entry)

    def test_empty_field_raises(self):
        """Entry with empty-string required field raises ValueError."""
        entry = {"path": "", "width": 800, "height": 600, "collection": "Album"}
        with pytest.raises(ValueError, match="path"):
            validate_photo_entry("p1", entry)

    def test_zero_dimension_raises(self):
        """Entry with width=0 or height=0 raises ValueError."""
        entry = {"path": "img.jpg", "width": 0, "height": 600, "collection": "Album"}
        with pytest.raises(ValueError, match="width"):
            validate_photo_entry("p1", entry)


class TestSaveValidation:
    """Integration: PhotoRegistry.save() rejects incomplete entries."""

    def _make_registry(self, photo_data: dict) -> PhotoRegistry:
        reg = PhotoRegistry()
        reg._photos = {"p1": {"face_ids": set(), **photo_data}}
        reg._face_to_photo = {}
        return reg

    def test_save_rejects_incomplete_entry(self, tmp_path):
        """save() raises ValueError when a photo lacks required fields."""
        reg = self._make_registry({"path": "img.jpg", "width": 800})
        with pytest.raises(ValueError, match="missing required fields"):
            reg.save(tmp_path / "photo_index.json")

    def test_save_succeeds_with_complete_entries(self, tmp_path):
        """save() writes successfully when all entries are valid."""
        reg = self._make_registry({
            "path": "img.jpg", "width": 800, "height": 600, "collection": "Album",
        })
        out = tmp_path / "photo_index.json"
        reg.save(out)
        data = json.loads(out.read_text())
        assert "p1" in data["photos"]


class TestIntegrityCheckerPhotoCompleteness:
    """check_data_integrity catches incomplete photo entries."""

    def test_catches_missing_width(self, tmp_path):
        """Integrity checker flags photo missing width."""
        pi = {
            "photos": {"p1": {"path": "img.jpg", "collection": "Album"}},
            "face_to_photo": {},
        }
        (tmp_path / "photo_index.json").write_text(json.dumps(pi))
        (tmp_path / "identities.json").write_text('{"identities": {}}')

        import scripts.check_data_integrity as checker
        original_data_dir = checker.data_dir
        checker.data_dir = tmp_path
        checker.errors = []
        checker.warnings = []

        try:
            checker.check_photo_entry_completeness()
            assert any("INCOMPLETE PHOTO" in e for e in checker.errors)
            assert any("width" in e for e in checker.errors)
        finally:
            checker.data_dir = original_data_dir
