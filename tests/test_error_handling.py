"""
Tests for graceful error handling on corrupted data files.

Covers:
- IdentityRegistry.load() with corrupted JSON
- PhotoRegistry.load() with corrupted JSON
- IdentityRegistry.load() with missing required keys
- PhotoRegistry.load() with missing required keys
- load_registry() returns empty registry on corruption
- load_photo_registry() returns empty registry on corruption
- _load_annotations() returns default structure on corruption
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# IdentityRegistry.load() — corrupted JSON raises descriptive ValueError
# ---------------------------------------------------------------------------

class TestIdentityRegistryLoadErrors:
    """IdentityRegistry.load() error handling."""

    def test_corrupted_json_raises_value_error(self, tmp_path):
        """Corrupted JSON file raises ValueError with descriptive message."""
        from core.registry import IdentityRegistry

        bad_file = tmp_path / "identities.json"
        bad_file.write_text("{this is not valid json!!!")

        with pytest.raises(ValueError, match="corrupted"):
            IdentityRegistry.load(bad_file)

    def test_corrupted_json_chains_original_error(self, tmp_path):
        """The ValueError chains the original JSONDecodeError."""
        from core.registry import IdentityRegistry

        bad_file = tmp_path / "identities.json"
        bad_file.write_text("not json at all")

        with pytest.raises(ValueError) as exc_info:
            IdentityRegistry.load(bad_file)

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

    def test_empty_file_raises_value_error(self, tmp_path):
        """Empty file raises ValueError (json.load fails on empty input)."""
        from core.registry import IdentityRegistry

        bad_file = tmp_path / "identities.json"
        bad_file.write_text("")

        with pytest.raises(ValueError, match="corrupted"):
            IdentityRegistry.load(bad_file)

    def test_missing_identities_key_raises_value_error(self, tmp_path):
        """JSON with correct schema_version but missing 'identities' key raises ValueError."""
        from core.registry import IdentityRegistry

        bad_file = tmp_path / "identities.json"
        bad_file.write_text(json.dumps({
            "schema_version": 1,
            "history": [],
        }))

        with pytest.raises(ValueError, match="missing required key"):
            IdentityRegistry.load(bad_file)

    def test_missing_history_key_raises_value_error(self, tmp_path):
        """JSON with correct schema_version but missing 'history' key raises ValueError."""
        from core.registry import IdentityRegistry

        bad_file = tmp_path / "identities.json"
        bad_file.write_text(json.dumps({
            "schema_version": 1,
            "identities": {},
        }))

        with pytest.raises(ValueError, match="missing required key"):
            IdentityRegistry.load(bad_file)

    def test_valid_file_loads_successfully(self, tmp_path):
        """Sanity check: valid file still loads correctly."""
        from core.registry import IdentityRegistry

        good_file = tmp_path / "identities.json"
        good_file.write_text(json.dumps({
            "schema_version": 1,
            "identities": {},
            "history": [],
        }))

        registry = IdentityRegistry.load(good_file)
        assert registry is not None


# ---------------------------------------------------------------------------
# PhotoRegistry.load() — corrupted JSON raises descriptive ValueError
# ---------------------------------------------------------------------------

class TestPhotoRegistryLoadErrors:
    """PhotoRegistry.load() error handling."""

    def test_corrupted_json_raises_value_error(self, tmp_path):
        """Corrupted JSON file raises ValueError with descriptive message."""
        from core.photo_registry import PhotoRegistry

        bad_file = tmp_path / "photo_index.json"
        bad_file.write_text("{broken json content###")

        with pytest.raises(ValueError, match="corrupted"):
            PhotoRegistry.load(bad_file)

    def test_corrupted_json_chains_original_error(self, tmp_path):
        """The ValueError chains the original JSONDecodeError."""
        from core.photo_registry import PhotoRegistry

        bad_file = tmp_path / "photo_index.json"
        bad_file.write_text("totally not json")

        with pytest.raises(ValueError) as exc_info:
            PhotoRegistry.load(bad_file)

        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, json.JSONDecodeError)

    def test_empty_file_raises_value_error(self, tmp_path):
        """Empty file raises ValueError."""
        from core.photo_registry import PhotoRegistry

        bad_file = tmp_path / "photo_index.json"
        bad_file.write_text("")

        with pytest.raises(ValueError, match="corrupted"):
            PhotoRegistry.load(bad_file)

    def test_missing_photos_key_raises_value_error(self, tmp_path):
        """JSON with correct schema but missing 'photos' key raises ValueError."""
        from core.photo_registry import PhotoRegistry

        bad_file = tmp_path / "photo_index.json"
        bad_file.write_text(json.dumps({
            "schema_version": 1,
            "face_to_photo": {},
        }))

        with pytest.raises(ValueError, match="missing required key"):
            PhotoRegistry.load(bad_file)

    def test_missing_face_to_photo_key_raises_value_error(self, tmp_path):
        """JSON with correct schema but missing 'face_to_photo' key raises ValueError."""
        from core.photo_registry import PhotoRegistry

        bad_file = tmp_path / "photo_index.json"
        bad_file.write_text(json.dumps({
            "schema_version": 1,
            "photos": {},
        }))

        with pytest.raises(ValueError, match="missing required key"):
            PhotoRegistry.load(bad_file)

    def test_valid_file_loads_successfully(self, tmp_path):
        """Sanity check: valid file still loads correctly."""
        from core.photo_registry import PhotoRegistry

        good_file = tmp_path / "photo_index.json"
        good_file.write_text(json.dumps({
            "schema_version": 1,
            "photos": {},
            "face_to_photo": {},
        }))

        registry = PhotoRegistry.load(good_file)
        assert registry is not None


# ---------------------------------------------------------------------------
# app/main.py load_registry() — graceful degradation
# ---------------------------------------------------------------------------

class TestLoadRegistryGraceful:
    """load_registry() returns empty registry on corruption."""

    def test_corrupted_file_returns_empty_registry(self, tmp_path):
        """Corrupted identities.json returns empty IdentityRegistry, not crash."""
        import app.main as main_mod
        from core.registry import IdentityRegistry

        bad_file = tmp_path / "identities.json"
        bad_file.write_text("{corrupted!!!")

        original_path = main_mod.REGISTRY_PATH
        try:
            main_mod.REGISTRY_PATH = bad_file
            result = main_mod.load_registry()
            assert isinstance(result, IdentityRegistry)
            # Empty registry has no identities
            assert len(result._identities) == 0
        finally:
            main_mod.REGISTRY_PATH = original_path

    def test_missing_file_returns_empty_registry(self, tmp_path):
        """Missing file returns empty IdentityRegistry."""
        import app.main as main_mod
        from core.registry import IdentityRegistry

        missing_file = tmp_path / "nonexistent.json"

        original_path = main_mod.REGISTRY_PATH
        try:
            main_mod.REGISTRY_PATH = missing_file
            result = main_mod.load_registry()
            assert isinstance(result, IdentityRegistry)
            assert len(result._identities) == 0
        finally:
            main_mod.REGISTRY_PATH = original_path

    def test_valid_file_loads_normally(self, tmp_path):
        """Valid file loads normally (regression check)."""
        import app.main as main_mod
        from core.registry import IdentityRegistry

        good_file = tmp_path / "identities.json"
        good_file.write_text(json.dumps({
            "schema_version": 1,
            "identities": {"id1": {"name": "Test"}},
            "history": [],
        }))

        original_path = main_mod.REGISTRY_PATH
        try:
            main_mod.REGISTRY_PATH = good_file
            result = main_mod.load_registry()
            assert isinstance(result, IdentityRegistry)
            assert "id1" in result._identities
        finally:
            main_mod.REGISTRY_PATH = original_path


# ---------------------------------------------------------------------------
# app/main.py load_photo_registry() — graceful degradation
# ---------------------------------------------------------------------------

class TestLoadPhotoRegistryGraceful:
    """load_photo_registry() returns empty registry on corruption."""

    def test_corrupted_file_returns_empty_registry(self, tmp_path):
        """Corrupted photo_index.json returns empty PhotoRegistry, not crash."""
        import app.main as main_mod
        from core.photo_registry import PhotoRegistry

        bad_file = tmp_path / "photo_index.json"
        bad_file.write_text("{not valid json 123")

        # Reset cache so load_photo_registry() actually reads from disk
        original_cache = main_mod._photo_registry_cache
        main_mod._photo_registry_cache = None

        try:
            with patch.object(main_mod, "data_path", tmp_path):
                result = main_mod.load_photo_registry()
                assert isinstance(result, PhotoRegistry)
        finally:
            main_mod._photo_registry_cache = original_cache

    def test_missing_file_returns_empty_registry(self, tmp_path):
        """Missing file returns empty PhotoRegistry."""
        import app.main as main_mod
        from core.photo_registry import PhotoRegistry

        # tmp_path has no photo_index.json
        original_cache = main_mod._photo_registry_cache
        main_mod._photo_registry_cache = None

        try:
            with patch.object(main_mod, "data_path", tmp_path):
                result = main_mod.load_photo_registry()
                assert isinstance(result, PhotoRegistry)
        finally:
            main_mod._photo_registry_cache = original_cache

    def test_valid_file_loads_normally(self, tmp_path):
        """Valid file loads normally (regression check)."""
        import app.main as main_mod
        from core.photo_registry import PhotoRegistry

        good_file = tmp_path / "photo_index.json"
        good_file.write_text(json.dumps({
            "schema_version": 1,
            "photos": {
                "abc123": {
                    "path": "raw_photos/test.jpg",
                    "face_ids": ["face1"],
                    "source": "Test Collection",
                }
            },
            "face_to_photo": {"face1": "abc123"},
        }))

        original_cache = main_mod._photo_registry_cache
        main_mod._photo_registry_cache = None

        try:
            with patch.object(main_mod, "data_path", tmp_path):
                result = main_mod.load_photo_registry()
                assert isinstance(result, PhotoRegistry)
                assert result.get_photo_path("abc123") is not None
        finally:
            main_mod._photo_registry_cache = original_cache


# ---------------------------------------------------------------------------
# app/main.py _load_annotations() — graceful degradation
# ---------------------------------------------------------------------------

class TestLoadAnnotationsGraceful:
    """_load_annotations() returns default structure on corruption."""

    def test_corrupted_file_returns_default(self, tmp_path):
        """Corrupted annotations.json returns default structure."""
        import app.main as main_mod

        bad_file = tmp_path / "annotations.json"
        bad_file.write_text("{broken json!!")

        # Reset cache
        original_cache = main_mod._annotations_cache
        main_mod._annotations_cache = None

        try:
            with patch.object(main_mod, "data_path", tmp_path):
                result = main_mod._load_annotations()
                assert result == {"schema_version": 1, "annotations": {}}
        finally:
            main_mod._annotations_cache = original_cache

    def test_missing_file_returns_default(self, tmp_path):
        """Missing annotations.json returns default structure."""
        import app.main as main_mod

        # tmp_path has no annotations.json
        original_cache = main_mod._annotations_cache
        main_mod._annotations_cache = None

        try:
            with patch.object(main_mod, "data_path", tmp_path):
                result = main_mod._load_annotations()
                assert result == {"schema_version": 1, "annotations": {}}
        finally:
            main_mod._annotations_cache = original_cache

    def test_empty_file_returns_default(self, tmp_path):
        """Empty annotations.json returns default structure."""
        import app.main as main_mod

        empty_file = tmp_path / "annotations.json"
        empty_file.write_text("")

        original_cache = main_mod._annotations_cache
        main_mod._annotations_cache = None

        try:
            with patch.object(main_mod, "data_path", tmp_path):
                result = main_mod._load_annotations()
                assert result == {"schema_version": 1, "annotations": {}}
        finally:
            main_mod._annotations_cache = original_cache

    def test_valid_file_loads_normally(self, tmp_path):
        """Valid annotations file loads normally (regression check)."""
        import app.main as main_mod

        good_file = tmp_path / "annotations.json"
        good_file.write_text(json.dumps({
            "schema_version": 1,
            "annotations": {"ann1": {"text": "test annotation"}},
        }))

        original_cache = main_mod._annotations_cache
        main_mod._annotations_cache = None

        try:
            with patch.object(main_mod, "data_path", tmp_path):
                result = main_mod._load_annotations()
                assert result["annotations"]["ann1"]["text"] == "test annotation"
        finally:
            main_mod._annotations_cache = original_cache

    def test_cached_result_not_reloaded(self, tmp_path):
        """When cache is populated, file is not re-read (even if corrupted)."""
        import app.main as main_mod

        # Write corrupted file
        bad_file = tmp_path / "annotations.json"
        bad_file.write_text("{broken!!!")

        cached_data = {"schema_version": 1, "annotations": {"cached": True}}
        original_cache = main_mod._annotations_cache
        main_mod._annotations_cache = cached_data

        try:
            with patch.object(main_mod, "data_path", tmp_path):
                result = main_mod._load_annotations()
                # Should return cached data, not try to load corrupted file
                assert result["annotations"]["cached"] is True
        finally:
            main_mod._annotations_cache = original_cache
