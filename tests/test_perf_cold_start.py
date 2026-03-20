"""Tests for Session 125 PERF #4: Cold start optimization."""

import ast
from pathlib import Path


class TestColdStartOptimization:
    """Server starts without blocking on Supabase."""

    def test_supabase_health_in_prewarm_not_startup_body(self):
        """Supabase health check runs inside _prewarm_caches, not in startup_event body."""
        source = Path("app/main.py").read_text()

        # Find startup_event function
        startup_idx = source.index("async def startup_event():")
        # Find _prewarm_caches definition inside it
        prewarm_idx = source.index("def _prewarm_caches():", startup_idx)

        # The actual health check call (get_supabase_client) should be AFTER _prewarm_caches def
        health_check_idx = source.index("get_supabase_client", startup_idx)
        assert health_check_idx > prewarm_idx, (
            "Supabase health check should be inside _prewarm_caches, not in startup body"
        )

    def test_sync_in_prewarm_not_startup_body(self):
        """Supabase sync runs inside _prewarm_caches, not in startup_event body."""
        source = Path("app/main.py").read_text()

        startup_idx = source.index("async def startup_event():")
        prewarm_idx = source.index("def _prewarm_caches():", startup_idx)

        sync_idx = source.index("sync_from_supabase_on_startup", startup_idx)
        assert sync_idx > prewarm_idx, "Supabase sync should be inside _prewarm_caches, not in startup body"

    def test_startup_still_creates_directories(self):
        """Startup must still create required directories synchronously."""
        source = Path("app/main.py").read_text()

        startup_idx = source.index("async def startup_event():")
        prewarm_idx = source.index("def _prewarm_caches():", startup_idx)

        # mkdir should be BEFORE _prewarm_caches (synchronous in startup body)
        mkdir_idx = source.index("mkdir(parents=True", startup_idx)
        assert mkdir_idx < prewarm_idx, "Directory creation must be synchronous in startup body"

    def test_prewarm_thread_is_daemon(self):
        """Prewarm thread must be daemon so it doesn't block shutdown."""
        source = Path("app/main.py").read_text()
        assert (
            'daemon=True, name="cache-prewarm"' in source
            or "daemon=True" in source[source.index("cache-prewarm") - 100 : source.index("cache-prewarm")]
        )
