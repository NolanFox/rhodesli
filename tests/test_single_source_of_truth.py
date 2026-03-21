"""Tests for PRD-051 Phase 1: Single Source of Truth.

Session 112: Eliminate JSON read paths for identities and photos.
Supabase is the only read source when DATA_SOURCE=postgres (new default).
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from core.registry import IdentityRegistry
from core.photo_registry import PhotoRegistry


# Helper to make mock Supabase rows
def _make_mock_supabase_identity_rows():
    return [
        {
            "identity_id": "aaaa-bbbb-cccc-dddd",
            "name": "Test Person",
            "display_name": None,
            "state": "CONFIRMED",
            "anchor_ids": ["face1", "face2"],
            "candidate_ids": ["face3"],
            "negative_ids": [],
            "version_id": 3,
            "merged_into": None,
            "metadata": {},
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        }
    ]


def _mock_supabase_client_with_rows(rows):
    mock_client = MagicMock()
    mock_result = MagicMock()
    mock_result.data = rows
    mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_result
    return mock_client


# =========================================================================
# Phase 1: load_registry() — Supabase only
# =========================================================================


class TestLoadRegistrySingleSource:
    """Verify load_registry() reads from Supabase, not JSON."""

    def test_load_registry_reads_from_supabase(self):
        """When DATA_SOURCE=postgres, load_registry() uses Supabase, not JSON."""
        rows = _make_mock_supabase_identity_rows()
        mock_client = _mock_supabase_client_with_rows(rows)

        import app.main as main_mod

        # Clear cache
        main_mod._registry_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("app.supabase_data.get_supabase_client", return_value=mock_client),
            patch("app.supabase_data.load_identity_overrides_from_supabase", return_value=None),
            patch("app.supabase_data.load_identity_history_from_supabase", return_value=None),
        ):
            registry = main_mod.load_registry()

        assert registry is not None
        assert "aaaa-bbbb-cccc-dddd" in registry._identities
        assert registry._identities["aaaa-bbbb-cccc-dddd"]["name"] == "Test Person"

    def test_load_registry_raises_on_supabase_failure(self):
        """When DATA_SOURCE=postgres and Supabase fails, error propagates — no silent JSON fallback."""
        import app.main as main_mod

        # Clear cache
        main_mod._registry_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("core.registry.IdentityRegistry.load_from_postgres", side_effect=Exception("Supabase down")),
        ):
            with pytest.raises(Exception, match="Supabase down"):
                main_mod.load_registry()

    def test_load_registry_raises_on_none_return(self):
        """When Supabase returns None (unavailable), raise error — don't fallback to JSON."""
        import app.main as main_mod

        # Clear cache
        main_mod._registry_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("core.registry.IdentityRegistry.load_from_postgres", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="Supabase.*unavailable"):
                main_mod.load_registry()

    def test_load_registry_json_fallback_still_works(self):
        """When DATA_SOURCE=json (rollback), JSON path still works."""
        import app.main as main_mod

        # Clear cache
        main_mod._registry_cache = None

        mock_registry = IdentityRegistry()
        mock_registry._identities = {"test-id": {"name": "JSON Person", "state": "INBOX"}}

        with (
            patch.object(main_mod, "DATA_SOURCE", "json"),
            patch.object(main_mod, "REGISTRY_PATH", Path("/tmp/test_identities.json")),
            patch("pathlib.Path.exists", return_value=True),
            patch("core.registry.IdentityRegistry.load", return_value=mock_registry),
        ):
            registry = main_mod.load_registry()

        assert registry._identities["test-id"]["name"] == "JSON Person"

    def test_load_registry_cache_works(self):
        """TTL cache returns cached registry without hitting Supabase."""
        import app.main as main_mod
        import time

        cached_registry = IdentityRegistry()
        cached_registry._identities = {"cached": {"name": "Cached"}}

        main_mod._registry_cache = cached_registry
        main_mod._registry_cache_ts = time.time()  # Fresh
        main_mod._registry_cache_key = ("postgres", str(main_mod.REGISTRY_PATH))

        with patch.object(main_mod, "DATA_SOURCE", "postgres"):
            result = main_mod.load_registry()

        assert result is cached_registry
        # Clean up
        main_mod._registry_cache = None


class TestSaveRegistryPreservesInvalidation:
    """Verify save_registry() preserves smart cache invalidation from Session 111f."""

    def test_save_registry_writes_to_supabase(self):
        """When DATA_SOURCE=postgres, save_registry() writes to Supabase.
        Session 129: sync_identity_overrides removed — caused stale data overwrites."""
        import app.main as main_mod

        registry = IdentityRegistry()
        registry._identities = {"id1": {"name": "Test", "state": "CONFIRMED"}}
        registry._history = []

        mock_shadow = MagicMock()

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch.object(registry, "save"),  # Mock JSON save
            patch("app.supabase_data.shadow_write_identities_batch", mock_shadow),
            patch("app.identity_routes.invalidate_neighbors_cache", MagicMock()),
            patch("app.cluster_review_routes.invalidate_cluster_review_caches", MagicMock()),
        ):
            result = main_mod.save_registry(registry, changed_ids={"id1"})

        assert result is True
        mock_shadow.assert_called_once()

    def test_save_registry_surgical_invalidation_preserved(self):
        """Smart cache invalidation from Session 111f is called with changed_ids."""
        import app.main as main_mod

        registry = IdentityRegistry()
        registry._identities = {"id1": {"name": "Test", "state": "CONFIRMED"}}
        registry._history = []

        mock_neighbors = MagicMock()
        mock_cluster = MagicMock()

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch.object(registry, "save"),
            patch("app.supabase_data.shadow_write_identities_batch", MagicMock()),
            patch("app.supabase_data.sync_identity_overrides", MagicMock()),
            patch("app.identity_routes.invalidate_neighbors_cache", mock_neighbors),
            patch("app.cluster_review_routes.invalidate_cluster_review_caches", mock_cluster),
        ):
            main_mod.save_registry(registry, changed_ids={"id1"})

        # Surgical invalidation: called with identity_id, not full flush
        mock_neighbors.assert_called_once_with(identity_id="id1")
        mock_cluster.assert_called_once_with(changed_ids={"id1"})


class TestPerfCacheWithSupabaseRegistry:
    """Verify perf_cache.py works after Supabase-only load_registry."""

    def test_perf_cache_builds_matrix(self):
        """get_confirmed_distances() builds matrix from Supabase-loaded registry."""
        import numpy as np
        from app.perf_cache import get_confirmed_distances, mark_confirmed_dirty, _lock

        # Create a mock registry with confirmed identity
        mock_registry = IdentityRegistry()
        mock_registry._identities = {
            "confirmed-1": {
                "name": "Test Person",
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
                "merged_into": None,
            }
        }

        # Create mock face_data with embedding
        mock_face_data = {
            "face1": {
                "embeddings": np.random.randn(512).tolist(),
            }
        }

        mark_confirmed_dirty()

        with (
            patch("app.main.load_registry", return_value=mock_registry),
            patch("app.main.get_face_data", return_value=mock_face_data),
        ):
            results = get_confirmed_distances(np.random.randn(512))

        assert len(results) == 1
        assert results[0]["identity_id"] == "confirmed-1"
        assert "distance" in results[0]


# =========================================================================
# Phase 2: Photo read path — Supabase only
# =========================================================================


class TestLoadPhotoRegistrySingleSource:
    """Verify load_photo_registry() reads from Supabase, not JSON."""

    def test_load_photo_registry_reads_from_supabase(self):
        """When DATA_SOURCE=postgres, uses Supabase not JSON."""
        import app.main as main_mod

        main_mod._photo_registry_cache = None

        mock_registry = PhotoRegistry()
        mock_registry._photos = {"photo1": {"path": "raw_photos/test.jpg", "face_ids": ["f1"]}}

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("core.photo_registry.PhotoRegistry.load_from_postgres", return_value=mock_registry),
        ):
            result = main_mod.load_photo_registry()

        assert result is mock_registry
        assert "photo1" in result._photos
        # Clean up
        main_mod._photo_registry_cache = None

    def test_load_photo_registry_raises_on_failure(self):
        """When Supabase fails in postgres mode, error propagates."""
        import app.main as main_mod

        main_mod._photo_registry_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("core.photo_registry.PhotoRegistry.load_from_postgres", side_effect=Exception("DB error")),
        ):
            with pytest.raises(Exception, match="DB error"):
                main_mod.load_photo_registry()

        # Clean up
        main_mod._photo_registry_cache = None

    def test_load_photo_registry_raises_on_none(self):
        """When Supabase returns None, raise — don't fallback to JSON."""
        import app.main as main_mod

        main_mod._photo_registry_cache = None

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch("core.photo_registry.PhotoRegistry.load_from_postgres", return_value=None),
        ):
            with pytest.raises(RuntimeError, match="Supabase.*unavailable"):
                main_mod.load_photo_registry()

        main_mod._photo_registry_cache = None


class TestBuildCachesNoJSON:
    """Verify _build_caches() does not read photo_index.json."""

    def test_build_caches_does_not_read_json(self):
        """_build_caches() must not call json.load on photo_index.json."""
        import app.main as main_mod

        # Reset caches
        main_mod._photo_cache = None
        main_mod._face_to_photo_cache = None
        main_mod._photo_id_aliases = None

        mock_registry = PhotoRegistry()
        mock_registry._photos = {
            "photo1": {
                "path": "raw_photos/test.jpg",
                "face_ids": ["face1"],
                "source": "Test Collection",
                "collection": "Test",
                "source_url": "",
                "width": 800,
                "height": 600,
            }
        }
        mock_registry._face_to_photo = {"face1": "photo1"}

        original_open = open

        def guarded_open(path, *args, **kwargs):
            path_str = str(path)
            if "photo_index.json" in path_str:
                raise AssertionError(f"_build_caches() should NOT read photo_index.json, but opened: {path_str}")
            return original_open(path, *args, **kwargs)

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch.object(main_mod, "load_photo_registry", return_value=mock_registry),
            patch.object(main_mod, "load_embeddings_for_photos", return_value={}),
            patch("builtins.open", side_effect=guarded_open),
        ):
            main_mod._build_caches()

        # Verify caches were built
        assert main_mod._photo_cache is not None
        assert main_mod._face_to_photo_cache is not None

        # Clean up
        main_mod._photo_cache = None
        main_mod._face_to_photo_cache = None
        main_mod._photo_id_aliases = None


class TestPhotoDimensionsFromSupabase:
    """Verify _load_photo_dimensions_cache uses Supabase not JSON."""

    def test_photo_dimensions_from_registry(self):
        """When DATA_SOURCE=postgres, dimensions come from registry only."""
        import app.main as main_mod

        main_mod._photo_dimensions_cache = None

        mock_registry = PhotoRegistry()
        mock_registry._photos = {
            "photo1": {
                "path": "raw_photos/test_photo.jpg",
                "width": 1024,
                "height": 768,
            }
        }

        with (
            patch.object(main_mod, "DATA_SOURCE", "postgres"),
            patch.object(main_mod, "load_photo_registry", return_value=mock_registry),
        ):
            cache = main_mod._load_photo_dimensions_cache()

        assert cache.get("test_photo.jpg") == (1024, 768)

        # Clean up
        main_mod._photo_dimensions_cache = None


# =========================================================================
# DATA_SOURCE default
# =========================================================================


class TestDataSourceDefault:
    """Verify DATA_SOURCE defaults to postgres (Session 112 change)."""

    def test_default_is_postgres(self):
        """After Session 112 (PRD-051), DATA_SOURCE defaults to 'postgres'."""
        # Verify the default in the source code directly
        import ast
        from pathlib import Path

        main_py = Path(__file__).parent.parent / "app" / "main.py"
        source = main_py.read_text()
        # Find the DATA_SOURCE assignment line
        for line in source.split("\n"):
            if "DATA_SOURCE" in line and "os.environ.get" in line and "= os.environ.get" in line:
                # Should contain default "postgres"
                assert '"postgres"' in line, f"DATA_SOURCE default must be 'postgres' (PRD-051), found: {line.strip()}"
                break
        else:
            pytest.fail("Could not find DATA_SOURCE = os.environ.get(...) line in app/main.py")
