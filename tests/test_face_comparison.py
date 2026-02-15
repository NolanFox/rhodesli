"""
Unit tests for the Face Comparison Tool.

Tests the /compare route, /api/compare endpoint, find_similar_faces() function,
navigation integration, and graceful degradation.
"""

import json
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---- Core Algorithm: find_similar_faces() ----


class TestFindSimilarFaces:
    """Tests for core.neighbors.find_similar_faces()."""

    def test_returns_sorted_results(self):
        """Results are sorted by distance (closest first)."""
        from core.neighbors import find_similar_faces

        # Create test embeddings
        query = np.random.randn(512).astype(np.float32)
        face_data = {
            "face_a": {"mu": query + np.random.randn(512) * 0.1},  # Close
            "face_b": {"mu": query + np.random.randn(512) * 2.0},  # Far
            "face_c": {"mu": query + np.random.randn(512) * 0.5},  # Medium
        }

        results = find_similar_faces(query, face_data, limit=3)
        assert len(results) == 3
        # Distances should be sorted ascending
        distances = [r["distance"] for r in results]
        assert distances == sorted(distances)

    def test_excludes_specified_faces(self):
        """Excluded face_ids are not in results."""
        from core.neighbors import find_similar_faces

        query = np.random.randn(512).astype(np.float32)
        face_data = {
            "face_a": {"mu": query},
            "face_b": {"mu": query + np.random.randn(512) * 0.1},
        }

        results = find_similar_faces(query, face_data, exclude_face_ids={"face_a"})
        face_ids = [r["face_id"] for r in results]
        assert "face_a" not in face_ids
        assert "face_b" in face_ids

    def test_respects_limit(self):
        """Returns at most `limit` results."""
        from core.neighbors import find_similar_faces

        query = np.random.randn(512).astype(np.float32)
        face_data = {f"face_{i}": {"mu": np.random.randn(512)} for i in range(50)}

        results = find_similar_faces(query, face_data, limit=5)
        assert len(results) == 5

    def test_includes_confidence_tiers(self):
        """Each result has a confidence tier."""
        from core.neighbors import find_similar_faces

        query = np.zeros(512, dtype=np.float32)
        face_data = {"face_a": {"mu": np.zeros(512, dtype=np.float32) + 0.01}}

        results = find_similar_faces(query, face_data)
        assert len(results) == 1
        assert results[0]["confidence"] in ("VERY HIGH", "HIGH", "MODERATE", "LOW")

    def test_empty_face_data_returns_empty(self):
        """Empty face_data returns empty results."""
        from core.neighbors import find_similar_faces

        query = np.random.randn(512).astype(np.float32)
        results = find_similar_faces(query, {})
        assert results == []

    def test_none_query_returns_empty(self):
        """None query embedding returns empty results."""
        from core.neighbors import find_similar_faces

        results = find_similar_faces(None, {"face_a": {"mu": np.random.randn(512)}})
        assert results == []

    def test_enriches_with_identity_info(self):
        """When registry provided, results include identity names."""
        from core.neighbors import find_similar_faces

        query = np.random.randn(512).astype(np.float32)
        face_data = {"face_a": {"mu": query + np.random.randn(512) * 0.1}}

        # Mock registry
        registry = MagicMock()
        registry.list_identities.return_value = [
            {
                "identity_id": "id_1",
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face_a"],
                "candidate_ids": [],
            }
        ]

        results = find_similar_faces(query, face_data, registry=registry)
        assert len(results) == 1
        assert results[0]["identity_name"] == "Leon Capeluto"
        assert results[0]["state"] == "CONFIRMED"
        assert results[0]["identity_id"] == "id_1"


# ---- Compare Route ----


class TestCompareRoute:
    """Tests for the /compare page."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from starlette.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_compare_returns_200(self):
        """GET /compare returns 200."""
        resp = self.client.get("/compare")
        assert resp.status_code == 200

    def test_compare_has_face_selector(self):
        """Compare page has face selector grid."""
        resp = self.client.get("/compare")
        assert "face-selector" in resp.text

    def test_compare_has_upload_area(self):
        """Compare page has upload area."""
        resp = self.client.get("/compare")
        assert "upload-area" in resp.text

    def test_compare_has_search_input(self):
        """Compare page has face search input."""
        resp = self.client.get("/compare")
        assert "face-search" in resp.text

    def test_compare_has_nav_links(self):
        """Compare page has all navigation links."""
        resp = self.client.get("/compare")
        assert "/photos" in resp.text
        assert "/people" in resp.text
        assert "/timeline" in resp.text
        assert "Compare" in resp.text

    def test_compare_with_invalid_face_id(self):
        """Compare with non-existent face_id returns 200 with no results."""
        resp = self.client.get("/compare?face_id=nonexistent")
        assert resp.status_code == 200

    def test_compare_has_og_tags(self):
        """Compare page has Open Graph meta tags."""
        resp = self.client.get("/compare")
        assert "og:title" in resp.text


# ---- API Compare Endpoint ----


class TestApiCompare:
    """Tests for /api/compare endpoint."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from starlette.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_api_compare_no_face_id(self):
        """/api/compare without face_id returns message."""
        resp = self.client.get("/api/compare")
        assert resp.status_code == 200
        assert "No face selected" in resp.text

    def test_api_compare_invalid_face_id(self):
        """/api/compare with invalid face_id returns error."""
        resp = self.client.get("/api/compare?face_id=nonexistent_face")
        assert resp.status_code == 200
        assert "not found" in resp.text.lower()


# ---- Navigation Integration ----


class TestCompareNavigation:
    """Tests that /compare link appears in all main navigation."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        from starlette.testclient import TestClient
        from app.main import app
        self.client = TestClient(app)

    def test_landing_page_has_compare_link(self):
        """Landing page includes Compare link."""
        resp = self.client.get("/")
        assert "/compare" in resp.text

    def test_photos_page_has_compare_link(self):
        """/photos page includes Compare link."""
        resp = self.client.get("/photos")
        assert "/compare" in resp.text

    def test_people_page_has_compare_link(self):
        """/people page includes Compare link."""
        resp = self.client.get("/people")
        assert "/compare" in resp.text

    def test_timeline_page_has_compare_link(self):
        """/timeline page includes Compare link."""
        resp = self.client.get("/timeline")
        assert "/compare" in resp.text
