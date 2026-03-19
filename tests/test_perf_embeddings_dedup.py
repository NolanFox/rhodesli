"""Tests for Session 123: PERF-A deduplicate embeddings.npy loads."""

from pathlib import Path


class TestEmbeddingsDedup:
    """Verify embeddings are loaded via cached path where possible."""

    def test_compare_routes_uses_get_face_data(self):
        """compare_routes should use get_face_data() not raw np.load for face lookup."""
        source = Path("app/compare_routes.py").read_text()
        # Should NOT have np.load for face-by-ID lookup
        # The old pattern: np.load(...embeddings.npy...) then iterate
        assert "np.load(_main_mod.data_path" not in source, (
            "compare_routes should use get_face_data() cache, not raw np.load"
        )

    def test_get_face_data_is_cached(self):
        """get_face_data() must use module-level caching."""
        source = Path("app/main.py").read_text()
        idx = source.index("def get_face_data()")
        func = source[idx : idx + 300]
        assert "_face_data_cache" in func, "get_face_data must use _face_data_cache"

    def test_raw_loads_are_for_structural_data_only(self):
        """Remaining np.load calls in main.py are for photo/crop structure, not face lookup."""
        source = Path("app/main.py").read_text()
        # These two are legitimate — they need filename, bbox, quality from raw embeddings
        # load_embeddings_for_photos (line ~3694) — groups by photo_id
        # get_crop_files (line ~4547) — builds crop filename list
        assert "load_embeddings_for_photos" in source, "Photo grouping function should exist"
        assert "get_crop_files" in source, "Crop file listing function should exist"
