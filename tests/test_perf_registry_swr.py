"""Tests for Session 125 PERF #1: Registry stale-while-revalidate."""

import threading
import time
from unittest.mock import patch, MagicMock


class TestRegistrySWR:
    """Registry SWR: serve stale, refresh in background."""

    def _reset_cache(self, main_mod):
        main_mod._registry_cache = None
        main_mod._registry_cache_ts = 0.0
        main_mod._registry_cache_key = None

    def test_fresh_cache_returns_immediately(self):
        """Within TTL, cache is returned without any load call."""
        import app.main as main_mod

        fake_registry = MagicMock()
        fake_registry._identities = {}
        main_mod._registry_cache = fake_registry
        main_mod._registry_cache_ts = time.time()  # Just set
        main_mod._registry_cache_key = (main_mod.DATA_SOURCE, str(main_mod.REGISTRY_PATH))

        with patch.object(main_mod.IdentityRegistry, "load_from_postgres") as mock_load:
            result = main_mod.load_registry()
            assert result is fake_registry
            mock_load.assert_not_called()

        self._reset_cache(main_mod)

    def test_stale_cache_returns_stale_and_spawns_refresh(self):
        """When TTL expired but cache exists, return stale and start refresh thread."""
        import app.main as main_mod

        fake_registry = MagicMock()
        fake_registry._identities = {}
        main_mod._registry_cache = fake_registry
        main_mod._registry_cache_ts = time.time() - 999  # Expired long ago
        main_mod._registry_cache_key = (main_mod.DATA_SOURCE, str(main_mod.REGISTRY_PATH))

        threads_started = []
        original_thread = threading.Thread

        def track_thread(*args, **kwargs):
            t = original_thread(*args, **kwargs)
            threads_started.append(t)
            return t

        with patch("app.main._registry_threading.Thread", side_effect=track_thread):
            result = main_mod.load_registry()
            assert result is fake_registry  # Stale returned immediately
            assert len(threads_started) == 1  # Background refresh spawned

        self._reset_cache(main_mod)

    def test_cold_start_blocks(self):
        """With no cache, load_registry blocks until data is available."""
        import app.main as main_mod

        self._reset_cache(main_mod)

        fresh_registry = MagicMock()
        fresh_registry._identities = {"a": {}}

        with patch.object(
            main_mod.IdentityRegistry,
            "load_from_postgres",
            return_value=fresh_registry,
        ):
            with patch.object(main_mod, "DATA_SOURCE", "postgres"):
                result = main_mod.load_registry()
                assert result is fresh_registry
                assert main_mod._registry_cache is fresh_registry

        self._reset_cache(main_mod)

    def test_refresh_lock_prevents_thundering_herd(self):
        """Only one background refresh runs at a time."""
        import app.main as main_mod

        # Acquire lock manually to simulate in-progress refresh
        main_mod._registry_refresh_lock.acquire()

        try:
            call_count = 0
            original_load = main_mod.IdentityRegistry.load_from_postgres

            def counting_load():
                nonlocal call_count
                call_count += 1
                return MagicMock(_identities={})

            cache_key = (main_mod.DATA_SOURCE, str(main_mod.REGISTRY_PATH))
            with patch.object(
                main_mod.IdentityRegistry,
                "load_from_postgres",
                side_effect=counting_load,
            ):
                # This should return immediately since lock is held
                main_mod._background_registry_refresh(cache_key)
                assert call_count == 0  # Skipped because lock held
        finally:
            main_mod._registry_refresh_lock.release()

        self._reset_cache(main_mod)

    def test_invalidate_clears_refresh_state(self):
        """_invalidate_all_caches clears registry cache."""
        import app.main as main_mod

        main_mod._registry_cache = MagicMock()
        main_mod._registry_cache_ts = time.time()
        main_mod._invalidate_all_caches()
        assert main_mod._registry_cache is None
        assert main_mod._registry_cache_ts == 0.0
