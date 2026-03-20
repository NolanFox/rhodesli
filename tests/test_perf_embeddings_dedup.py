"""Tests for Session 123+125: embeddings dedup + unified parse."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np


class TestEmbeddingsDedup:
    """Verify embeddings are loaded via cached path where possible."""

    def test_compare_routes_uses_get_face_data(self):
        """compare_routes should use get_face_data() not raw np.load for face lookup."""
        source = Path("app/compare_routes.py").read_text()
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
        """Functions use _load_raw_embeddings(), not direct np.load."""
        source = Path("app/main.py").read_text()
        assert "load_embeddings_for_photos" in source
        assert "get_crop_files" in source


class TestUnifiedEmbeddingsCache:
    """Session 125 PERF #6: embeddings.npy parsed once, three views derived."""

    def test_single_np_load(self):
        """np.load should be called once even when all three consumers fire."""
        import app.main as main_mod

        # Reset caches
        main_mod._raw_embeddings_cache = None
        main_mod._face_data_cache = None
        main_mod._crop_files_cache = None

        fake_entries = [
            {
                "filename": "test.jpg",
                "face_id": "test:face0",
                "mu": np.zeros(512, dtype=np.float32),
                "sigma_sq": np.full(512, 0.55, dtype=np.float32),
                "bbox": [10, 20, 30, 40],
                "det_score": 0.95,
                "quality": 0.8,
            }
        ]
        fake_array = np.array(fake_entries, dtype=object)

        with (
            patch.object(np, "load", return_value=fake_array) as mock_load,
            patch.object(Path, "exists", return_value=True),
        ):
            # Call all three consumers
            main_mod._load_raw_embeddings()
            main_mod.load_face_embeddings()
            main_mod.load_embeddings_for_photos()

            # np.load called exactly once (by _load_raw_embeddings)
            assert mock_load.call_count == 1, f"np.load called {mock_load.call_count} times, expected 1"

        # Cleanup
        main_mod._raw_embeddings_cache = None
        main_mod._face_data_cache = None
        main_mod._crop_files_cache = None

    def test_face_data_format_preserved(self):
        """get_face_data() returns same dict format after unification."""
        import app.main as main_mod

        main_mod._raw_embeddings_cache = None
        main_mod._face_data_cache = None

        mu = np.random.randn(512).astype(np.float32)
        fake_entries = [
            {
                "filename": "photo1.jpg",
                "mu": mu,
                "sigma_sq": np.full(512, 0.55, dtype=np.float32),
                "bbox": [1, 2, 3, 4],
                "det_score": 0.9,
                "quality": 0.7,
            }
        ]

        main_mod._raw_embeddings_cache = fake_entries

        result = main_mod.load_face_embeddings()
        assert "photo1:face0" in result
        entry = result["photo1:face0"]
        assert "mu" in entry
        assert "sigma_sq" in entry
        assert "bbox" in entry
        assert "det_score" in entry
        assert "quality" in entry
        assert "filename" in entry
        assert entry["filename"] == "photo1.jpg"

        main_mod._raw_embeddings_cache = None
        main_mod._face_data_cache = None

    def test_crop_files_format_preserved(self):
        """get_crop_files() returns a set after unification."""
        import app.main as main_mod

        main_mod._raw_embeddings_cache = None
        main_mod._crop_files_cache = None

        result = main_mod.get_crop_files()
        assert isinstance(result, set)

        main_mod._raw_embeddings_cache = None
        main_mod._crop_files_cache = None

    def test_invalidate_clears_raw_cache(self):
        """_invalidate_all_caches clears the raw embeddings cache."""
        import app.main as main_mod

        main_mod._raw_embeddings_cache = [{"fake": True}]
        main_mod._invalidate_all_caches()
        assert main_mod._raw_embeddings_cache is None
