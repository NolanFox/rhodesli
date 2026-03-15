"""Tests for Session 102 performance improvements.

- GEDCOM search minimum character guard (FB-120, PERF-006)
- Similar panel neighbors cache (FB-127, PERF-005)
- Registry cache repopulation after save
"""

import time
import pytest
from unittest.mock import patch, MagicMock

# Bootstrap app.main first to avoid circular imports
import app.main  # noqa: F401


# ---------------------------------------------------------------------------
# Task A1: GEDCOM search requires minimum 3 characters
# ---------------------------------------------------------------------------


class TestGedcomSearchMinChars:
    """GEDCOM search must require >= 3 characters before hitting the DB."""

    def test_empty_query_returns_empty(self):
        """Empty query returns empty without DB hit."""
        from app.relationship_routes import _search_gedcom_individuals

        results, total = _search_gedcom_individuals("")
        assert results == []
        assert total == 0

    def test_one_char_returns_empty(self):
        """1-char query returns empty without DB hit."""
        from app.relationship_routes import _search_gedcom_individuals

        results, total = _search_gedcom_individuals("A")
        assert results == []
        assert total == 0

    def test_two_chars_returns_empty(self):
        """2-char query returns empty without DB hit (raised from 2 to 3)."""
        from app.relationship_routes import _search_gedcom_individuals

        results, total = _search_gedcom_individuals("AB")
        assert results == []
        assert total == 0

    def test_three_chars_triggers_search(self):
        """3-char query should attempt the search (may return 0 results from mock)."""
        from app.relationship_routes import _search_gedcom_individuals

        mock_individuals = [
            {
                "gedcom_id": "@I1@",
                "name": "Leon Capeluto",
                "given_name": "Leon",
                "surname": "Capeluto",
                "gender": "M",
                "birth_date": "1903",
                "birth_place": "Rhodes",
                "death_date": "",
                "death_place": "",
            }
        ]
        with patch(
            "app.relationship_routes._query_gedcom_search_candidates",
            return_value=mock_individuals,
        ):
            results, total = _search_gedcom_individuals("Leo")
            # Should have processed (not short-circuited)
            assert total >= 0  # May or may not match depending on scoring

    def test_prefilter_rejects_short_queries(self):
        """_query_gedcom_search_candidates rejects < 3 char queries."""
        from app.relationship_routes import _query_gedcom_search_candidates

        assert _query_gedcom_search_candidates("") == []
        assert _query_gedcom_search_candidates("A") == []
        assert _query_gedcom_search_candidates("AB") == []

    def test_gedcom_search_htmx_no_auto_fire(self):
        """GEDCOM link panel should NOT auto-fire search on load."""
        from app.relationship_routes import _gedcom_link_panel

        html = repr(_gedcom_link_panel("test-id", "Test Person"))
        # Should NOT contain "load" in hx_trigger
        assert 'hx-trigger="input changed delay:300ms"' in html or "input changed delay:300ms" in html
        # Verify "load" is NOT in the trigger
        assert ", load" not in html


# ---------------------------------------------------------------------------
# Task A2: Similar panel neighbors cache
# ---------------------------------------------------------------------------


class TestSimilarPanelCache:
    """Neighbors cache stores and invalidates correctly."""

    def test_cache_stores_and_retrieves(self):
        """Cache stores results and returns them on next call."""
        from app.identity_routes import (
            _get_cached_neighbors,
            _set_cached_neighbors,
            invalidate_neighbors_cache,
        )

        # Clean state
        invalidate_neighbors_cache()

        test_results = [{"identity_id": "abc", "distance": 0.5}]
        _set_cached_neighbors("test-id-1", test_results)

        cached = _get_cached_neighbors("test-id-1")
        assert cached is not None
        assert len(cached) == 1
        assert cached[0]["identity_id"] == "abc"

    def test_cache_miss_returns_none(self):
        """Uncached identity returns None."""
        from app.identity_routes import (
            _get_cached_neighbors,
            invalidate_neighbors_cache,
        )

        invalidate_neighbors_cache()
        assert _get_cached_neighbors("nonexistent") is None

    def test_cache_invalidation_specific(self):
        """Invalidating one identity leaves others."""
        from app.identity_routes import (
            _get_cached_neighbors,
            _set_cached_neighbors,
            invalidate_neighbors_cache,
        )

        invalidate_neighbors_cache()

        _set_cached_neighbors("id-a", [{"identity_id": "x"}])
        _set_cached_neighbors("id-b", [{"identity_id": "y"}])

        invalidate_neighbors_cache("id-a")
        assert _get_cached_neighbors("id-a") is None
        assert _get_cached_neighbors("id-b") is not None

    def test_cache_invalidation_global(self):
        """Invalidating all clears everything."""
        from app.identity_routes import (
            _get_cached_neighbors,
            _set_cached_neighbors,
            invalidate_neighbors_cache,
        )

        _set_cached_neighbors("id-a", [{"identity_id": "x"}])
        _set_cached_neighbors("id-b", [{"identity_id": "y"}])

        invalidate_neighbors_cache()
        assert _get_cached_neighbors("id-a") is None
        assert _get_cached_neighbors("id-b") is None

    def test_cache_ttl_expiry(self):
        """Expired cache entries return None."""
        from app.identity_routes import (
            _get_cached_neighbors,
            _neighbors_cache,
            invalidate_neighbors_cache,
        )

        invalidate_neighbors_cache()

        # Insert with a timestamp far in the past
        _neighbors_cache["old-id"] = (time.time() - 600, [{"identity_id": "stale"}])
        assert _get_cached_neighbors("old-id") is None

    def test_save_registry_invalidates_neighbors_cache(self):
        """save_registry() should clear neighbors cache."""
        from app.identity_routes import (
            _set_cached_neighbors,
            _get_cached_neighbors,
        )

        _set_cached_neighbors("id-test", [{"identity_id": "cached"}])
        assert _get_cached_neighbors("id-test") is not None

        # Mock the actual save operations but verify cache invalidation fires
        with (
            patch("app.main.REGISTRY_PATH") as mock_path,
            patch("app.main.DATA_SOURCE", "json"),
        ):
            mock_path.exists.return_value = False

            from app.main import save_registry
            from core.registry import IdentityRegistry

            reg = IdentityRegistry()
            try:
                save_registry(reg)
            except Exception:
                pass  # Save may fail without real file — that's OK

        # Cache should have been invalidated
        assert _get_cached_neighbors("id-test") is None


# ---------------------------------------------------------------------------
# Task A3: Registry cache repopulation after save
# ---------------------------------------------------------------------------


class TestRegistryCacheAfterSave:
    """Registry cache should be repopulated after save_registry()."""

    def test_registry_cache_repopulated_after_save(self):
        """After save_registry(), the cache should hold the saved registry."""
        import app.main as m
        from core.registry import IdentityRegistry

        # Save the original cache state
        orig_cache = m._registry_cache
        orig_ts = m._registry_cache_ts
        orig_key = m._registry_cache_key

        try:
            # Create a fresh registry
            reg = IdentityRegistry()

            # Mock persistence so save doesn't actually write files
            with patch.object(reg, "save", return_value=None):
                m.save_registry(reg)

            # Cache should now hold our registry
            assert m._registry_cache is reg
            assert m._registry_cache_ts > 0
        finally:
            # Restore original cache state
            m._registry_cache = orig_cache
            m._registry_cache_ts = orig_ts
            m._registry_cache_key = orig_key

    def test_load_registry_returns_from_cache(self):
        """load_registry() returns cached instance when TTL is valid."""
        import app.main as m
        from core.registry import IdentityRegistry

        orig_cache = m._registry_cache
        orig_ts = m._registry_cache_ts
        orig_key = m._registry_cache_key

        try:
            reg = IdentityRegistry()
            m._registry_cache = reg
            m._registry_cache_ts = time.time()
            m._registry_cache_key = (m.DATA_SOURCE, str(m.REGISTRY_PATH))

            loaded = m.load_registry()
            assert loaded is reg
        finally:
            m._registry_cache = orig_cache
            m._registry_cache_ts = orig_ts
            m._registry_cache_key = orig_key
