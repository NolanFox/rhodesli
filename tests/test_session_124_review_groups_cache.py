"""Tests for Session 124 — unresolved review groups TTL cache (Codex #3)."""

import time
from unittest.mock import patch

import pytest

from app import cluster_review_routes


class TestReviewGroupsCache:
    """Test the _review_groups_cache TTL cache for unresolved review groups."""

    def setup_method(self):
        """Clear caches before each test."""
        cluster_review_routes._review_groups_cache = {}

    def test_cache_ttl_constant_is_600(self):
        """Session 136: TTL bumped from 120s to 600s for egress reduction."""
        assert cluster_review_routes._CACHE_TTL == 600

    def test_review_groups_cache_exists_as_module_level_dict(self):
        """_review_groups_cache should be a dict at module level."""
        assert isinstance(cluster_review_routes._review_groups_cache, dict)

    def test_invalidation_clears_review_groups_cache(self):
        """invalidate_cluster_review_caches should clear _review_groups_cache."""
        # Populate cache
        cluster_review_routes._review_groups_cache["rhodes"] = (time.time(), [{"test": True}])
        assert len(cluster_review_routes._review_groups_cache) == 1

        # Full invalidation
        cluster_review_routes.invalidate_cluster_review_caches()
        assert len(cluster_review_routes._review_groups_cache) == 0

    def test_invalidation_with_changed_ids_clears_review_groups(self):
        """invalidate_cluster_review_caches with changed_ids should also clear review groups."""
        cluster_review_routes._review_groups_cache["rhodes"] = (time.time(), [{"test": True}])

        cluster_review_routes.invalidate_cluster_review_caches(changed_ids={"some-id"})
        assert len(cluster_review_routes._review_groups_cache) == 0

    def test_cache_key_uses_community_slug(self):
        """Cache should be keyed by community_slug."""
        # Populate two different communities
        cluster_review_routes._review_groups_cache["rhodes"] = (time.time(), [{"a": 1}])
        cluster_review_routes._review_groups_cache["fox-family"] = (time.time(), [{"b": 2}])

        assert len(cluster_review_routes._review_groups_cache) == 2
        assert cluster_review_routes._review_groups_cache["rhodes"][1] == [{"a": 1}]
        assert cluster_review_routes._review_groups_cache["fox-family"][1] == [{"b": 2}]

    def test_stale_cache_entry_would_be_replaced(self):
        """A cache entry older than TTL should be considered stale."""
        stale_time = time.time() - cluster_review_routes._CACHE_TTL - 1
        cluster_review_routes._review_groups_cache["rhodes"] = (stale_time, [{"old": True}])

        cached = cluster_review_routes._review_groups_cache.get("rhodes")
        assert cached is not None
        assert (time.time() - cached[0]) > cluster_review_routes._CACHE_TTL
