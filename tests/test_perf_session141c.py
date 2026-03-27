"""Tests for Session 141 Track C performance quick wins.

C1: heapq.nsmallest replaces sorted()[:10] in focus mode
C2: Parallel cold start Supabase fetches
"""

import heapq
import random
from pathlib import Path


class TestHeapqFocusSort:
    """C1: heapq.nsmallest produces same results as sorted()[:N]."""

    def test_heapq_matches_sorted_simple(self):
        """heapq.nsmallest gives same ordering as sorted()[:N] for simple keys."""
        items = list(range(100))
        random.shuffle(items)
        assert heapq.nsmallest(10, items) == sorted(items)[:10]

    def test_heapq_matches_sorted_with_key(self):
        """heapq.nsmallest matches sorted()[:N] with a key function."""
        items = [{"distance": random.uniform(0.5, 2.0), "name": f"person_{i}"} for i in range(200)]
        key_fn = lambda x: x["distance"]
        result_heap = heapq.nsmallest(10, items, key=key_fn)
        result_sort = sorted(items, key=key_fn)[:10]
        assert result_heap == result_sort

    def test_heapq_matches_sorted_with_tuple_key(self):
        """heapq.nsmallest matches sorted()[:N] with tuple key (like _focus_sort_key)."""
        items = []
        for i in range(150):
            items.append(
                {
                    "tier": random.randint(0, 5),
                    "distance": random.uniform(0.5, 2.0),
                    "quality": random.uniform(0.0, 1.0),
                    "face_count": random.randint(1, 10),
                }
            )
        key_fn = lambda x: (x["tier"], x["distance"], -x["quality"], -x["face_count"])
        result_heap = heapq.nsmallest(10, items, key=key_fn)
        result_sort = sorted(items, key=key_fn)[:10]
        assert result_heap == result_sort

    def test_heapq_with_fewer_items_than_n(self):
        """heapq.nsmallest handles case where list has fewer than N items."""
        items = [3, 1, 2]
        assert heapq.nsmallest(10, items) == sorted(items)

    def test_heapq_with_empty_list(self):
        """heapq.nsmallest handles empty input."""
        assert heapq.nsmallest(10, []) == []

    def test_main_py_uses_heapq_nsmallest(self):
        """app/main.py uses heapq.nsmallest instead of sorted()[:10] for focus sort."""
        source = Path("app/main.py").read_text()
        assert "import heapq" in source
        assert "heapq.nsmallest(10, to_review, key=_focus_sort_key)" in source
        # Ensure old pattern is gone
        assert "sorted(to_review, key=_focus_sort_key)[:10]" not in source


class TestParallelColdStart:
    """C2: Parallel cold start cache warming."""

    def test_prewarm_uses_thread_pool(self):
        """_prewarm_caches uses ThreadPoolExecutor for parallel UI cache warming."""
        source = Path("app/main.py").read_text()
        # Find the _prewarm_caches function
        idx = source.index("def _prewarm_caches():")
        # Get the function body (up to the next unindented line after the thread start)
        end_idx = source.index("threading.Thread(target=_prewarm_caches", idx)
        prewarm_body = source[idx:end_idx]
        assert "ThreadPoolExecutor" in prewarm_body
        assert "as_completed" in prewarm_body

    def test_prewarm_runs_all_three_caches(self):
        """_prewarm_caches runs _build_caches, _load_date_labels, and get_crop_files."""
        source = Path("app/main.py").read_text()
        idx = source.index("def _prewarm_caches():")
        end_idx = source.index("threading.Thread(target=_prewarm_caches", idx)
        prewarm_body = source[idx:end_idx]
        assert "_build_caches" in prewarm_body
        assert "_load_date_labels" in prewarm_body
        assert "get_crop_files" in prewarm_body

    def test_prewarm_handles_individual_failures(self):
        """Individual cache task failures don't prevent other tasks from completing."""
        source = Path("app/main.py").read_text()
        idx = source.index("def _prewarm_caches():")
        end_idx = source.index("threading.Thread(target=_prewarm_caches", idx)
        prewarm_body = source[idx:end_idx]
        # Each future result is wrapped in try/except
        assert "future.result()" in prewarm_body
        assert 'logging.warning(f"UI cache prewarm' in prewarm_body

    def test_parallel_warmup_functional(self):
        """ThreadPoolExecutor correctly runs multiple callables in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []

        def task_a():
            results.append("a")

        def task_b():
            results.append("b")

        def task_c():
            results.append("c")

        tasks = {"a": task_a, "b": task_b, "c": task_c}
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(futures):
                future.result()

        assert sorted(results) == ["a", "b", "c"]

    def test_parallel_warmup_one_failure_doesnt_block_others(self):
        """If one cache task fails, others still complete."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []

        def task_ok():
            results.append("ok")

        def task_fail():
            raise RuntimeError("simulated failure")

        tasks = {"ok1": task_ok, "fail": task_fail, "ok2": task_ok}
        errors = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    errors.append(str(e))

        assert len(results) == 2  # Both ok tasks completed
        assert len(errors) == 1  # One failure captured
        assert "simulated failure" in errors[0]
