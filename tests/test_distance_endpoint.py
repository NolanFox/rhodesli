"""Tests for FB-003: Async embedding distance computation in Manual Search.

Tests cover:
1. Distance endpoint returns correct structure for valid identities
2. Distance endpoint handles missing embeddings gracefully
3. Distance endpoint handles invalid identity IDs
4. Distance endpoint requires admin auth
5. search_result_card includes the scanner placeholder
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


class TestDistanceEndpoint:
    """Tests for GET /api/identity/{source_id}/distance/{target_id}."""

    def _make_registry_mock(self, identities=None):
        """Create a mock registry with given identities."""
        if identities is None:
            identities = {
                "id-source": {
                    "identity_id": "id-source",
                    "name": "Source Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-s1"],
                    "candidate_ids": [],
                },
                "id-target": {
                    "identity_id": "id-target",
                    "name": "Target Person",
                    "state": "PROPOSED",
                    "anchor_ids": ["face-t1"],
                    "candidate_ids": [],
                },
            }
        registry = MagicMock()

        def get_identity(iid):
            if iid not in identities:
                raise KeyError(f"Identity {iid} not found")
            return identities[iid]

        registry.get_identity = get_identity
        return registry

    @patch("core.confidence.compute_face_confidence")
    @patch("core.neighbors.get_identity_embeddings")
    @patch("app.identity_routes._main_mod")
    def test_distance_returns_match_percentage(self, mock_main, mock_get_embs, mock_conf):
        """Distance endpoint returns percentage and distance for valid identities."""
        from starlette.testclient import TestClient
        import app.main as main

        registry = self._make_registry_mock()
        mock_main.load_registry.return_value = registry
        mock_main._check_admin.return_value = None
        mock_main.get_face_data.return_value = {}

        mock_embs_source = np.random.randn(1, 512).astype(np.float32)
        mock_embs_target = np.random.randn(1, 512).astype(np.float32)

        mock_get_embs.side_effect = [
            (["face-s1"], mock_embs_source),
            (["face-t1"], mock_embs_target),
        ]
        mock_conf.return_value = {
            "confidence_pct": 72,
            "short_label": "High",
            "tier": "POSSIBLE MATCH",
            "label": "Strong match",
            "tier_color": "bg-blue-600",
            "dots": 4,
        }

        c = TestClient(main.app)
        resp = c.get("/api/identity/id-source/distance/id-target")

        assert resp.status_code == 200
        html = resp.text
        assert "72% match" in html
        assert "Dist:" in html
        assert "High" in html
        assert "distance-badge-reveal" in html

    @patch("core.neighbors.get_identity_embeddings")
    @patch("app.identity_routes._main_mod")
    def test_distance_no_embeddings(self, mock_main, mock_get_embs):
        """Distance endpoint returns 'No embedding' when no embeddings exist."""
        from starlette.testclient import TestClient
        import app.main as main

        registry = self._make_registry_mock()
        mock_main.load_registry.return_value = registry
        mock_main._check_admin.return_value = None
        mock_main.get_face_data.return_value = {}

        empty_embs = np.array([]).reshape(0, 512)

        mock_get_embs.side_effect = [
            ([], empty_embs),
            ([], empty_embs),
        ]

        c = TestClient(main.app)
        resp = c.get("/api/identity/id-source/distance/id-target")

        assert resp.status_code == 200
        assert "No embedding" in resp.text
        assert "distance-badge-reveal" in resp.text

    @patch("app.identity_routes._main_mod")
    def test_distance_invalid_identity(self, mock_main):
        """Distance endpoint returns hidden span for invalid identity IDs."""
        from starlette.testclient import TestClient
        import app.main as main

        registry = self._make_registry_mock()
        mock_main.load_registry.return_value = registry
        mock_main._check_admin.return_value = None

        c = TestClient(main.app)
        resp = c.get("/api/identity/id-source/distance/nonexistent-id")

        assert resp.status_code == 200
        assert "hidden" in resp.text

    @patch("app.identity_routes._main_mod")
    def test_distance_requires_admin(self, mock_main):
        """Distance endpoint returns hidden span when not admin."""
        from starlette.testclient import TestClient
        import app.main as main
        from starlette.responses import Response

        mock_main._check_admin.return_value = Response("Unauthorized", status_code=401)

        c = TestClient(main.app)
        resp = c.get("/api/identity/id-source/distance/id-target")

        assert resp.status_code == 200
        assert "hidden" in resp.text

    @patch("core.neighbors.get_identity_embeddings")
    @patch("app.identity_routes._main_mod")
    def test_distance_never_shows_zero_percent(self, mock_main, mock_get_embs):
        """Regression: distance endpoint must never show 0% match (FB-007b).

        The bug was using wrong dict keys ('calibrated_score' instead of
        'confidence_pct'), causing the percentage to default to 0.
        """
        from starlette.testclient import TestClient
        import app.main as main

        registry = self._make_registry_mock()
        mock_main.load_registry.return_value = registry
        mock_main._check_admin.return_value = None
        mock_main.get_face_data.return_value = {}

        # Create embeddings with a known distance (far apart = weak match)
        mock_embs_source = np.zeros((1, 512), dtype=np.float32)
        mock_embs_source[0, 0] = 1.0
        mock_embs_target = np.zeros((1, 512), dtype=np.float32)
        mock_embs_target[0, 1] = 1.0  # Distance ~1.41

        mock_get_embs.side_effect = [
            (["face-s1"], mock_embs_source),
            (["face-t1"], mock_embs_target),
        ]

        c = TestClient(main.app)
        resp = c.get("/api/identity/id-source/distance/id-target")

        assert resp.status_code == 200
        html = resp.text
        # Must show a real percentage, not 0%
        assert "0% match" not in html, "Distance endpoint showed 0% match — wrong dict key regression"
        assert "% match" in html, "Distance endpoint missing percentage display"


class TestSearchResultCardScanner:
    """search_result_card includes distance scanner placeholder."""

    def test_search_result_card_has_scanner(self):
        """search_result_card includes the HTMX distance scanner placeholder."""
        from app.main import search_result_card, to_xml

        result = {
            "identity_id": "result-001",
            "name": "Test Person",
            "face_count": 3,
            "preview_face_id": None,
        }
        html = to_xml(
            search_result_card(
                result,
                target_identity_id="target-001",
                crop_files=set(),
                nav_prefix="",
            )
        )

        assert "search-distance-scanner" in html
        assert "/api/identity/target-001/distance/result-001" in html
        assert 'hx-trigger="load"' in html

    def test_search_result_card_scanner_has_nav_prefix(self):
        """Scanner URL includes community nav_prefix."""
        from app.main import search_result_card, to_xml

        result = {
            "identity_id": "result-002",
            "name": "Another Person",
            "face_count": 1,
            "preview_face_id": None,
        }
        html = to_xml(
            search_result_card(
                result,
                target_identity_id="target-002",
                crop_files=set(),
                nav_prefix="/c/rhodes",
            )
        )

        assert "/c/rhodes/api/identity/target-002/distance/result-002" in html

    def test_search_result_card_still_shows_face_count(self):
        """Existing face count display is preserved alongside scanner."""
        from app.main import search_result_card, to_xml

        result = {
            "identity_id": "result-003",
            "name": "Person Three",
            "face_count": 5,
            "preview_face_id": None,
        }
        html = to_xml(
            search_result_card(
                result,
                target_identity_id="target-003",
                crop_files=set(),
                nav_prefix="",
            )
        )

        assert "5 faces" in html
        assert "search-distance-scanner" in html


class TestDistanceCSSAnimations:
    """CSS animations for distance scanner and reveal are present in app/main.py."""

    def _read_main_py(self):
        """Read app/main.py source to check for CSS."""
        from pathlib import Path

        main_path = Path(__file__).parent.parent / "app" / "main.py"
        return main_path.read_text()

    def test_distance_scan_animation_in_css(self):
        """The distance-scan keyframe animation is in app/main.py CSS."""
        source = self._read_main_py()
        assert "@keyframes distance-scan" in source
        assert ".search-distance-scanner" in source

    def test_distance_reveal_animation_in_css(self):
        """The distance-badge-reveal animation is in app/main.py CSS."""
        source = self._read_main_py()
        assert "@keyframes distance-reveal" in source
        assert ".distance-badge-reveal" in source
