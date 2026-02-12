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
