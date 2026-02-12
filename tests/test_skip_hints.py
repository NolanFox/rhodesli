"""
Tests for skip hints (ML suggestions for skipped identities) and
confidence gap (relative identity ranking in neighbor results).
"""

import numpy as np
import pytest

from core.photo_registry import PhotoRegistry
from core.registry import IdentityRegistry, IdentityState


class TestConfidenceGap:
    """Test that confidence_gap is computed in neighbor results."""

    def test_confidence_gap_in_results(self):
        """find_nearest_neighbors should include confidence_gap for each result."""
        from core.neighbors import find_nearest_neighbors

        # face_data is a dict: {face_id: {"mu": np.ndarray}}
        face_data = {
            "face_a": {"mu": np.random.randn(512).astype(np.float32)},
            "face_b": {"mu": np.random.randn(512).astype(np.float32)},
            "face_c": {"mu": np.random.randn(512).astype(np.float32)},
        }

        photo_reg = PhotoRegistry()
        photo_reg.register_face("photo_a", "a.jpg", "face_a")
        photo_reg.register_face("photo_b", "b.jpg", "face_b")
        photo_reg.register_face("photo_c", "c.jpg", "face_c")

        identity_reg = IdentityRegistry()
        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"], user_source="test",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b"], user_source="test",
            state=IdentityState.PROPOSED,
        )
        id_c = identity_reg.create_identity(
            anchor_ids=["face_c"], user_source="test",
            state=IdentityState.PROPOSED,
        )

        results = find_nearest_neighbors(id_a, identity_reg, photo_reg, face_data, limit=5)

        assert len(results) >= 1
        # Every result should have confidence_gap
        for r in results:
            assert "confidence_gap" in r
            assert isinstance(r["confidence_gap"], float)

    def test_single_candidate_gets_max_gap(self):
        """When there's only one candidate, confidence_gap should be 100%."""
        from core.neighbors import find_nearest_neighbors

        face_data = {
            "face_a": {"mu": np.random.randn(512).astype(np.float32)},
            "face_b": {"mu": np.random.randn(512).astype(np.float32)},
        }

        photo_reg = PhotoRegistry()
        photo_reg.register_face("photo_a", "a.jpg", "face_a")
        photo_reg.register_face("photo_b", "b.jpg", "face_b")

        identity_reg = IdentityRegistry()
        id_a = identity_reg.create_identity(
            anchor_ids=["face_a"], user_source="test",
            state=IdentityState.CONFIRMED,
        )
        id_b = identity_reg.create_identity(
            anchor_ids=["face_b"], user_source="test",
            state=IdentityState.PROPOSED,
        )

        results = find_nearest_neighbors(id_a, identity_reg, photo_reg, face_data, limit=5)

        assert len(results) == 1
        assert results[0]["confidence_gap"] == 100.0


class TestSkipHintsEndpoint:
    """Test the /api/identity/{id}/skip-hints endpoint."""

    def test_skip_hints_returns_html(self, client, auth_disabled):
        """Skip hints endpoint should return HTML content."""
        from app.main import load_registry
        registry = load_registry()
        identities = registry.list_identities()

        if not identities:
            pytest.skip("No identities available")

        identity_id = identities[0]["identity_id"]
        response = client.get(f"/api/identity/{identity_id}/skip-hints")

        # Should return 200 regardless (graceful fallback)
        assert response.status_code == 200

    def test_skip_hints_not_found_returns_empty(self, client, auth_disabled):
        """Skip hints for nonexistent identity returns empty span."""
        response = client.get("/api/identity/nonexistent-id/skip-hints")
        assert response.status_code == 200
        # Should be empty (graceful fallback)

    def test_skipped_section_has_hint_containers(self, client, auth_disabled):
        """Skipped section should have lazy-load containers for ML hints."""
        response = client.get("/?section=skipped")
        assert response.status_code == 200
        # If there are skipped items, they should have hint containers
        content = response.text
        if "skip-hint-" in content:
            assert "hx-get" in content or "hx_get" in content


class TestAISuggestionsCompareButton:
    """Regression: AI suggestions Compare button must open the compare modal, not swap into sidebar."""

    def test_skip_hints_compare_targets_modal(self, client, auth_disabled):
        """Compare button in AI suggestions targets #compare-modal-content, not #neighbors-{id}."""
        from app.main import load_registry
        registry = load_registry()
        identities = registry.list_identities()

        if not identities:
            pytest.skip("No identities available")

        identity_id = identities[0]["identity_id"]
        response = client.get(f"/api/identity/{identity_id}/skip-hints")

        if response.status_code == 200 and "Compare" in response.text:
            html = response.text
            # Compare button must target the modal, not the sidebar
            assert '#compare-modal-content' in html, \
                "Compare button should target #compare-modal-content"
            assert f'#neighbors-{identity_id}' not in html or 'Compare' not in html.split(f'#neighbors-{identity_id}')[0], \
                "Compare button should NOT target #neighbors-{identity_id}"


class TestSkipHintsThumbnailResolution:
    """Test that skip-hints resolves face thumbnails via enriched anchor_face_ids."""

    def test_skip_hints_enriches_face_ids(self, client, auth_disabled, monkeypatch):
        """Skip hints should enrich neighbor results with anchor_face_ids for thumbnail resolution."""
        from unittest.mock import MagicMock

        from app import main as app_main

        # Create a minimal registry with one identity that has anchors
        mock_registry = MagicMock()
        mock_registry.get_identity.return_value = {
            "identity_id": "target-id",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face_a"],
        }
        mock_registry.get_anchor_face_ids.return_value = ["face_x", "face_y"]
        mock_registry.get_candidate_face_ids.return_value = ["face_z"]
        monkeypatch.setattr(app_main, "load_registry", lambda: mock_registry)

        # Mock find_nearest_neighbors to return a result WITHOUT face IDs
        mock_neighbors = [
            {
                "identity_id": "neighbor-1",
                "name": "Neighbor Person",
                "distance": 0.85,
                "face_count": 2,
                "can_merge": True,
                "confidence_gap": 100.0,
            }
        ]

        monkeypatch.setattr(
            "core.neighbors.find_nearest_neighbors",
            lambda *a, **kw: mock_neighbors,
        )

        # Mock face data and photo registry
        monkeypatch.setattr(app_main, "get_face_data", lambda: {})
        monkeypatch.setattr(app_main, "load_photo_registry", lambda: MagicMock())

        response = client.get("/api/identity/target-id/skip-hints")
        assert response.status_code == 200

        # The enrichment should have been called
        mock_registry.get_anchor_face_ids.assert_called_with("neighbor-1")
        mock_registry.get_candidate_face_ids.assert_called_with("neighbor-1")


class TestVariableSuggestionCount:
    """Test that skip-hints adapts suggestion count based on confidence."""

    def test_strong_match_shows_up_to_3(self, client, auth_disabled, monkeypatch):
        """When best match is strong (< HIGH threshold), show up to 3 suggestions."""
        from unittest.mock import MagicMock
        from app import main as app_main

        mock_registry = MagicMock()
        mock_registry.get_identity.return_value = {
            "identity_id": "target-id", "name": "Test", "state": "CONFIRMED",
            "anchor_ids": ["face_a"],
        }
        mock_registry.get_anchor_face_ids.return_value = ["face_x"]
        mock_registry.get_candidate_face_ids.return_value = []
        monkeypatch.setattr(app_main, "load_registry", lambda: mock_registry)

        # 5 neighbors with strong top match (dist=0.80 < HIGH=1.05)
        mock_neighbors = [
            {"identity_id": f"n-{i}", "name": f"N{i}", "distance": 0.80 + i * 0.05,
             "face_count": 1, "can_merge": True, "confidence_gap": 10.0}
            for i in range(5)
        ]
        monkeypatch.setattr("core.neighbors.find_nearest_neighbors", lambda *a, **kw: mock_neighbors)
        monkeypatch.setattr(app_main, "get_face_data", lambda: {})
        monkeypatch.setattr(app_main, "load_photo_registry", lambda: MagicMock())

        response = client.get("/api/identity/target-id/skip-hints")
        assert response.status_code == 200
        # Should show 3 suggestions (strong match)
        html = response.text
        assert html.count("Compare") == 3

    def test_weak_match_shows_only_1(self, client, auth_disabled, monkeypatch):
        """When best match is weak (> LOW threshold), show only 1 suggestion."""
        from unittest.mock import MagicMock
        from app import main as app_main

        mock_registry = MagicMock()
        mock_registry.get_identity.return_value = {
            "identity_id": "target-id", "name": "Test", "state": "CONFIRMED",
            "anchor_ids": ["face_a"],
        }
        mock_registry.get_anchor_face_ids.return_value = ["face_x"]
        mock_registry.get_candidate_face_ids.return_value = []
        monkeypatch.setattr(app_main, "load_registry", lambda: mock_registry)

        # 5 neighbors with weak top match (dist=1.30 > LOW=1.25)
        mock_neighbors = [
            {"identity_id": f"n-{i}", "name": f"N{i}", "distance": 1.30 + i * 0.05,
             "face_count": 1, "can_merge": True, "confidence_gap": 10.0}
            for i in range(5)
        ]
        monkeypatch.setattr("core.neighbors.find_nearest_neighbors", lambda *a, **kw: mock_neighbors)
        monkeypatch.setattr(app_main, "get_face_data", lambda: {})
        monkeypatch.setattr(app_main, "load_photo_registry", lambda: MagicMock())

        response = client.get("/api/identity/target-id/skip-hints")
        assert response.status_code == 200
        # Should show only 1 suggestion (weak match)
        html = response.text
        assert html.count("Compare") == 1


class TestNeighborCardConfidenceGap:
    """Test that neighbor cards display the confidence gap."""

    def test_neighbor_card_renders_gap(self):
        """neighbor_card should render confidence_gap when present."""
        from fasthtml.common import to_xml

        from app.main import neighbor_card

        neighbor = {
            "identity_id": "test-id-123",
            "name": "Leon Capeluto",
            "distance": 0.85,
            "percentile": 0.1,
            "confidence_gap": 15.3,
            "can_merge": True,
            "face_count": 3,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
        }

        card = neighbor_card(neighbor, "target-id", set())
        html = to_xml(card)

        # The gap indicator should appear
        assert "+15.3% gap" in html
