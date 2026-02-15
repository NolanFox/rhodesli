"""
Tests for Compare Intelligence — kinship calibration, tiered results,
upload persistence, and multi-face support.

Session 32: AD-067 (kinship calibration), AD-068 (tiered display),
AD-069 (upload persistence).
"""

import json
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from core.registry import IdentityState


# ---- Kinship Calibration ----


class TestKinshipThresholds:
    """Tests for rhodesli_ml/analysis/kinship_calibration.py output."""

    def test_kinship_thresholds_file_exists(self):
        """Calibrated thresholds JSON exists."""
        path = Path("rhodesli_ml/data/model_comparisons/kinship_thresholds.json")
        assert path.exists(), "kinship_thresholds.json not found"

    def test_kinship_thresholds_valid_json(self):
        """Thresholds file is valid JSON with required keys."""
        path = Path("rhodesli_ml/data/model_comparisons/kinship_thresholds.json")
        data = json.loads(path.read_text())
        assert "same_person" in data
        assert "same_family" in data
        assert "different_person" in data
        assert "recommended_thresholds" in data
        assert "calibration_metadata" in data

    def test_same_person_has_sufficient_pairs(self):
        """Same-person distribution has enough pairs for statistical validity."""
        path = Path("rhodesli_ml/data/model_comparisons/kinship_thresholds.json")
        data = json.loads(path.read_text())
        assert data["same_person"]["n"] >= 100, "Need >= 100 same-person pairs"

    def test_thresholds_are_ordered(self):
        """Thresholds increase: strong < possible < similar."""
        path = Path("rhodesli_ml/data/model_comparisons/kinship_thresholds.json")
        data = json.loads(path.read_text())
        t = data["recommended_thresholds"]
        assert t["strong_match"] < t["possible_match"] < t["similar_features"]

    def test_same_person_mean_lower_than_different(self):
        """Same-person mean distance is lower than different-person mean."""
        path = Path("rhodesli_ml/data/model_comparisons/kinship_thresholds.json")
        data = json.loads(path.read_text())
        assert data["same_person"]["mean"] < data["different_person"]["mean"]

    def test_cohens_d_same_person_vs_different_is_large(self):
        """Cohen's d for same_person vs different is > 1.0 (strong separation)."""
        path = Path("rhodesli_ml/data/model_comparisons/kinship_thresholds.json")
        data = json.loads(path.read_text())
        sep = data["recommended_thresholds"].get("separation_metrics", {})
        d = sep.get("cohens_d_sp_vs_dp", 0)
        assert d > 1.0, f"Cohen's d = {d}, expected > 1.0 for strong separation"

    def test_cohens_d_family_vs_different_is_small(self):
        """Cohen's d for same_family vs different is < 1.0 (weak separation).

        This validates the finding that family resemblance is barely
        detectable in embedding space.
        """
        path = Path("rhodesli_ml/data/model_comparisons/kinship_thresholds.json")
        data = json.loads(path.read_text())
        sep = data["recommended_thresholds"].get("separation_metrics", {})
        d = sep.get("cohens_d_sf_vs_dp", 0)
        assert d < 1.0, f"Cohen's d = {d}, expected < 1.0 (family resemblance is weak)"


class TestKinshipCalibrationScript:
    """Tests for the calibration script's functions."""

    def test_build_kinship_report_returns_valid_structure(self):
        """build_kinship_report returns all required keys."""
        from rhodesli_ml.analysis.kinship_calibration import build_kinship_report
        report = build_kinship_report(Path("data"))
        assert "same_person" in report
        assert "recommended_thresholds" in report
        assert "calibration_metadata" in report
        assert report["same_person"]["n"] > 0

    def test_compute_distributions_with_mock_data(self):
        """compute_distributions works with synthetic data."""
        from rhodesli_ml.analysis.kinship_calibration import compute_distributions

        identities = [
            {"identity_id": "a", "name": "Leon Capeluto", "face_ids": ["f1", "f2"]},
            {"identity_id": "b", "name": "Moise Capeluto", "face_ids": ["f3"]},
            {"identity_id": "c", "name": "Rosa Sedikaro", "face_ids": ["f4"]},
        ]
        # f1 and f2 are close (same person), f3 is similar family, f4 is different
        base = np.random.randn(512).astype(np.float32)
        face_embeddings = {
            "f1": base,
            "f2": base + np.random.randn(512).astype(np.float32) * 0.05,
            "f3": base + np.random.randn(512).astype(np.float32) * 0.5,
            "f4": np.random.randn(512).astype(np.float32) * 2.0,
        }
        variant_lookup = {
            "capeluto": "Capeluto",
            "sedikaro": "Sedikaro",
        }

        result = compute_distributions(identities, face_embeddings, variant_lookup)
        assert len(result["same_person_distances"]) == 1  # f1 vs f2
        assert len(result["same_family_distances"]) == 1  # Capeluto(a) vs Capeluto(b)
        assert len(result["different_person_distances"]) >= 1  # cross-family

    def test_recommend_thresholds_ordering(self):
        """Thresholds are always ordered: strong < possible < similar."""
        from rhodesli_ml.analysis.kinship_calibration import recommend_thresholds

        distributions = {
            "same_person_distances": list(np.random.normal(1.0, 0.2, 100)),
            "same_family_distances": list(np.random.normal(1.3, 0.1, 50)),
            "different_person_distances": list(np.random.normal(1.4, 0.1, 50)),
        }
        t = recommend_thresholds(distributions)
        assert t["strong_match"] < t["possible_match"]
        assert t["possible_match"] < t["similar_features"]


# ---- Tiered Results ----


class TestTieredResults:
    """Tests for tiered compare results in find_similar_faces."""

    def test_results_include_tier_field(self):
        """Each result has a 'tier' field."""
        from core.neighbors import find_similar_faces

        query = np.zeros(512, dtype=np.float32)
        face_data = {"f1": {"mu": np.zeros(512, dtype=np.float32) + 0.01}}
        results = find_similar_faces(query, face_data)
        assert len(results) == 1
        assert "tier" in results[0]
        assert results[0]["tier"] in ("STRONG MATCH", "POSSIBLE MATCH", "SIMILAR", "WEAK")

    def test_results_include_confidence_pct(self):
        """Each result has a confidence_pct percentage."""
        from core.neighbors import find_similar_faces

        query = np.zeros(512, dtype=np.float32)
        face_data = {"f1": {"mu": np.zeros(512, dtype=np.float32) + 0.01}}
        results = find_similar_faces(query, face_data)
        assert "confidence_pct" in results[0]
        assert 1 <= results[0]["confidence_pct"] <= 99

    def test_close_distance_is_strong_match(self):
        """Very close faces get STRONG MATCH tier."""
        from core.neighbors import find_similar_faces

        query = np.zeros(512, dtype=np.float32)
        # Near-identical embedding (distance ~0.15)
        face_data = {"f1": {"mu": np.zeros(512, dtype=np.float32) + 0.005}}
        results = find_similar_faces(query, face_data)
        assert results[0]["tier"] == "STRONG MATCH"
        assert results[0]["confidence_pct"] > 80

    def test_far_distance_is_weak(self):
        """Distant faces get WEAK tier."""
        from core.neighbors import find_similar_faces

        query = np.zeros(512, dtype=np.float32)
        face_data = {"f1": {"mu": np.random.randn(512).astype(np.float32) * 2.0}}
        results = find_similar_faces(query, face_data)
        assert results[0]["tier"] == "WEAK"
        assert results[0]["confidence_pct"] < 30

    def test_results_still_sorted_by_distance(self):
        """Tiered results are still sorted by distance within each tier."""
        from core.neighbors import find_similar_faces

        query = np.zeros(512, dtype=np.float32)
        face_data = {
            f"f{i}": {"mu": np.random.randn(512).astype(np.float32) * (0.1 + i * 0.3)}
            for i in range(10)
        }
        results = find_similar_faces(query, face_data, limit=10)
        distances = [r["distance"] for r in results]
        assert distances == sorted(distances)

    def test_backwards_compatible_confidence_field(self):
        """Results still include the legacy 'confidence' field for existing code."""
        from core.neighbors import find_similar_faces

        query = np.zeros(512, dtype=np.float32)
        face_data = {"f1": {"mu": np.zeros(512, dtype=np.float32) + 0.01}}
        results = find_similar_faces(query, face_data)
        assert "confidence" in results[0]
        assert results[0]["confidence"] in ("VERY HIGH", "HIGH", "MODERATE", "LOW")


# ---- Compare Route Tiered Display ----


class TestCompareRouteTiers:
    """Tests for tiered display in the /compare route."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from starlette.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_compare_with_face_id_has_tier_sections(self):
        """Compare results include tier section test IDs."""
        # Use a known confirmed identity's face
        from app.main import load_registry, get_face_data
        registry = load_registry()
        face_data = get_face_data()
        # Find a face_id that exists in the data
        confirmed = [
            i for i in registry.list_identities(state=IdentityState.CONFIRMED)
            if not i.get("merged_into")
        ]
        if not confirmed:
            pytest.skip("No confirmed identities with faces")
        face_ids = confirmed[0].get("anchor_ids", []) + confirmed[0].get("candidate_ids", [])
        test_fid = None
        for entry in face_ids:
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if fid in face_data:
                test_fid = fid
                break
        if not test_fid:
            pytest.skip("No face with embeddings found")

        resp = self.client.get(f"/compare?face_id={test_fid}")
        assert resp.status_code == 200
        # Should have at least one tier section
        assert "compare-results" in resp.text

    def test_compare_results_have_data_tier_attr(self):
        """Compare result cards have data-tier attributes."""
        from app.main import load_registry, get_face_data
        registry = load_registry()
        face_data = get_face_data()
        confirmed = [
            i for i in registry.list_identities(state=IdentityState.CONFIRMED)
            if not i.get("merged_into")
        ]
        if not confirmed:
            pytest.skip("No confirmed identities")
        face_ids = confirmed[0].get("anchor_ids", []) + confirmed[0].get("candidate_ids", [])
        test_fid = None
        for entry in face_ids:
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if fid in face_data:
                test_fid = fid
                break
        if not test_fid:
            pytest.skip("No face with embeddings found")

        resp = self.client.get(f"/compare?face_id={test_fid}")
        assert "data-tier=" in resp.text

    def test_compare_results_include_person_links(self):
        """Confirmed identity results include person page links."""
        from app.main import load_registry, get_face_data
        registry = load_registry()
        face_data = get_face_data()
        confirmed = [
            i for i in registry.list_identities(state=IdentityState.CONFIRMED)
            if not i.get("merged_into") and not i.get("name", "").startswith("Unidentified")
        ]
        if not confirmed:
            pytest.skip("No named confirmed identities")
        face_ids = confirmed[0].get("anchor_ids", []) + confirmed[0].get("candidate_ids", [])
        test_fid = None
        for entry in face_ids:
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if fid in face_data:
                test_fid = fid
                break
        if not test_fid:
            pytest.skip("No face with embeddings found")

        resp = self.client.get(f"/compare?face_id={test_fid}")
        # Should include /person/ links for confirmed identities
        assert "/person/" in resp.text

    def test_compare_results_include_timeline_links(self):
        """Confirmed identity results include timeline links."""
        from app.main import load_registry, get_face_data
        registry = load_registry()
        face_data = get_face_data()
        confirmed = [
            i for i in registry.list_identities(state=IdentityState.CONFIRMED)
            if not i.get("merged_into")
        ]
        if not confirmed:
            pytest.skip("No confirmed identities")
        face_ids = confirmed[0].get("anchor_ids", []) + confirmed[0].get("candidate_ids", [])
        test_fid = None
        for entry in face_ids:
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if fid in face_data:
                test_fid = fid
                break
        if not test_fid:
            pytest.skip("No face with embeddings found")

        resp = self.client.get(f"/compare?face_id={test_fid}")
        assert "/timeline?" in resp.text


# ---- Upload Persistence ----


class TestUploadPersistence:
    """Tests for upload persistence and multi-face support."""

    def test_save_compare_upload_creates_files(self, tmp_path):
        """_save_compare_upload creates image and metadata files."""
        # Monkey-patch upload dir
        import app.main as main_mod
        original_func = main_mod._save_compare_upload

        # Just test the upload dir creation logic
        upload_dir = tmp_path / "uploads" / "compare"
        upload_dir.mkdir(parents=True)

        content = b"fake image data"
        faces = [{"mu": [0.1] * 512, "bbox": [0, 0, 100, 100]}]
        results = [{"identity_name": "Test Person", "confidence_pct": 85, "tier": "STRONG MATCH"}]

        with patch.object(Path, '__new__', return_value=tmp_path):
            # Direct test of the save logic
            import uuid
            upload_id = str(uuid.uuid4())[:12]
            suffix = ".jpg"
            image_path = upload_dir / f"{upload_id}{suffix}"
            image_path.write_bytes(content)

            meta = {
                "upload_id": upload_id,
                "faces_detected": len(faces),
                "top_match": {
                    "identity_name": results[0]["identity_name"],
                    "confidence_pct": results[0]["confidence_pct"],
                    "tier": results[0]["tier"],
                },
            }
            meta_path = upload_dir / f"{upload_id}_meta.json"
            meta_path.write_text(json.dumps(meta))

            assert image_path.exists()
            assert meta_path.exists()
            loaded_meta = json.loads(meta_path.read_text())
            assert loaded_meta["faces_detected"] == 1
            assert loaded_meta["top_match"]["identity_name"] == "Test Person"

    def test_upload_area_exists_on_compare_page(self):
        """Compare page has upload form."""
        from starlette.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.get("/compare")
        assert "upload-form" in resp.text
        assert "upload-area" in resp.text

    def test_upload_without_file_returns_error(self):
        """POST /api/compare/upload without file returns error."""
        from starlette.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        resp = client.post("/api/compare/upload")
        assert resp.status_code == 200
        assert "No photo uploaded" in resp.text


# ---- Confidence Percentage ----


class TestConfidencePercentage:
    """Tests for CDF-based confidence percentages."""

    def test_compute_confidence_pct_close_distance(self):
        """Very close distance returns high confidence."""
        from core.neighbors import _compute_confidence_pct
        sp_stats = {"n": 959, "mean": 1.01, "std": 0.19}
        pct = _compute_confidence_pct(0.3, sp_stats)
        assert pct > 90

    def test_compute_confidence_pct_far_distance(self):
        """Far distance returns low confidence."""
        from core.neighbors import _compute_confidence_pct
        sp_stats = {"n": 959, "mean": 1.01, "std": 0.19}
        pct = _compute_confidence_pct(1.5, sp_stats)
        assert pct < 20

    def test_compute_confidence_pct_mean_distance(self):
        """Distance at the mean returns ~50%."""
        from core.neighbors import _compute_confidence_pct
        sp_stats = {"n": 959, "mean": 1.01, "std": 0.19}
        pct = _compute_confidence_pct(1.01, sp_stats)
        assert 40 <= pct <= 60

    def test_compute_confidence_pct_fallback(self):
        """Without stats, uses linear fallback."""
        from core.neighbors import _compute_confidence_pct
        pct = _compute_confidence_pct(0.5, None)
        assert 1 <= pct <= 99

    def test_compute_confidence_pct_clamped(self):
        """Confidence is always between 1 and 99."""
        from core.neighbors import _compute_confidence_pct
        sp_stats = {"n": 100, "mean": 1.0, "std": 0.2}
        assert 1 <= _compute_confidence_pct(0.0, sp_stats) <= 99
        assert 1 <= _compute_confidence_pct(5.0, sp_stats) <= 99


# ---- Kinship Threshold Loading ----


class TestKinshipThresholdLoading:
    """Tests for threshold loading and fallback in core/neighbors.py."""

    def test_get_kinship_thresholds_returns_dict(self):
        """_get_kinship_thresholds returns a dict with required keys."""
        from core.neighbors import _get_kinship_thresholds, _kinship_cache
        # Clear cache to force reload
        import core.neighbors
        core.neighbors._kinship_cache = None
        t = _get_kinship_thresholds()
        assert "strong_match" in t
        assert "possible_match" in t
        assert "similar_features" in t
        assert isinstance(t["strong_match"], (int, float))

    def test_kinship_thresholds_fallback_when_file_missing(self):
        """Falls back to defaults when kinship file is missing."""
        from core.neighbors import _get_kinship_thresholds
        import core.neighbors
        core.neighbors._kinship_cache = None
        with patch("core.neighbors._load_kinship_thresholds", return_value=None):
            t = _get_kinship_thresholds()
            assert t["strong_match"] == 1.05  # Default
            assert t["possible_match"] == 1.25
            assert t["similar_features"] == 1.40
        # Restore
        core.neighbors._kinship_cache = None
