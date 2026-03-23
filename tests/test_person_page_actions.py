"""
Tests for person page action fixes (Session 110).

FB-019: Individual merge button on person page
FB-021: Override button (swapped IDs + person page targeting)
FB-017: Confirm on person page returns status, not full card
FB-020: Merge keeps Similar panel open (from_person_page)
FB-016/FB-024: Loading indicators present
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient
from fasthtml.common import to_xml

from core.registry import IdentityRegistry, IdentityState
from core.photo_registry import PhotoRegistry


@pytest.fixture
def person_page_registries():
    """Create registries with two identities for person page testing."""
    photo_reg = PhotoRegistry()
    photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_a")
    photo_reg.register_face("photo_2", "/path/photo_2.jpg", "face_b")

    identity_reg = IdentityRegistry()
    target_id = identity_reg.create_identity(
        anchor_ids=["face_a"],
        user_source="test",
        name="James Fields",
        state=IdentityState.CONFIRMED,
    )
    source_id = identity_reg.create_identity(
        anchor_ids=["face_b"],
        user_source="test",
        name="Unidentified Person 001",
    )
    return identity_reg, photo_reg, target_id, source_id


class TestMergeFromPersonPage:
    """FB-019/FB-020: Merge works on person page and returns neighbor-targeted response."""

    def test_merge_from_person_page_returns_merged_indicator(self, person_page_registries):
        """When from_person_page=true, merge returns a merged indicator, not identity_card."""
        identity_reg, photo_reg, target_id, source_id = person_page_registries

        with (
            patch("app.main.load_registry", return_value=identity_reg),
            patch("app.main.save_registry"),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
            from app.main import app

            client = TestClient(app)
            response = client.post(
                f"/api/identity/{target_id}/merge/{source_id}?from_person_page=true",
                headers={"HX-Request": "true"},
            )

        assert response.status_code == 200
        html = response.text
        # Should contain merged indicator, not a full identity card
        assert "Merged" in html
        # Should NOT contain the full identity card (which has face gallery etc.)
        assert "identity-card" not in html
        # Should still have toast
        assert "Merged" in html

    def test_merge_without_person_page_returns_identity_card(self, person_page_registries):
        """Normal merge (not from person page) still returns identity_card."""
        identity_reg, photo_reg, target_id, source_id = person_page_registries

        with (
            patch("app.main.load_registry", return_value=identity_reg),
            patch("app.main.save_registry"),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
            from app.main import app

            client = TestClient(app)
            response = client.post(
                f"/api/identity/{target_id}/merge/{source_id}",
                headers={"HX-Request": "true"},
            )

        assert response.status_code == 200
        # Normal merge should return identity card content
        assert "James Fields" in response.text


class TestOverrideButton:
    """FB-021: Override button uses correct merge direction."""

    def test_override_button_correct_merge_direction(self, person_page_registries):
        """Override button in neighbor_card should merge neighbor INTO target, not reverse."""
        from app.main import neighbor_card

        identity_reg, photo_reg, target_id, source_id = person_page_registries

        neighbor = {
            "identity_id": source_id,
            "name": "Unidentified Person 001",
            "distance": 0.87,
            "can_merge": False,
            "merge_blocked_reason": "co_occurrence",
            "merge_blocked_reason_display": "Appear together in photo.jpg",
            "face_count": 1,
            "co_occurrence": 1,
            "anchor_face_ids": ["face_b"],
            "candidate_face_ids": [],
        }

        card = neighbor_card(
            neighbor,
            target_id,
            set(),
            target_name="James Fields",
            from_person_page=True,
        )
        html = to_xml(card)

        # FB-008: Override button now uses hx-get to load preview panel
        # Preview endpoint URL should have correct merge direction (TARGET/preview/SOURCE)
        assert f"/api/identity/{target_id}/co-occurrence-preview/{source_id}" in html
        # Should NOT have the IDs reversed
        assert f"/api/identity/{source_id}/co-occurrence-preview/{target_id}" not in html
        # Should include from_person_page in preview params
        assert "from_person_page=true" in html
        # Preview container div should exist
        assert f'id="override-preview-{source_id}"' in html


class TestConfirmFromPersonPage:
    """FB-017: Confirm on person page returns status badge, not full identity card."""

    def test_confirm_from_person_page_returns_status(self, person_page_registries):
        """When from_person_page=true, confirm returns status badge."""
        identity_reg, photo_reg, target_id, source_id = person_page_registries

        # Create an INBOX identity to confirm
        inbox_id = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
            name="Test Person",
            state=IdentityState.INBOX,
        )

        with (
            patch("app.main.load_registry", return_value=identity_reg),
            patch("app.main.save_registry"),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
            from app.main import app

            client = TestClient(app)
            response = client.post(
                f"/inbox/{inbox_id}/confirm?from_person_page=true",
                headers={"HX-Request": "true"},
            )

        assert response.status_code == 200
        html = response.text
        # Should contain CONFIRMED badge
        assert "CONFIRMED" in html
        # Should have the person-admin-actions id for proper swap targeting
        assert "person-admin-actions" in html
        # Should NOT contain identity card (gallery, face thumbnails, etc.)
        assert "identity-card" not in html

    def test_confirm_without_person_page_returns_card(self, person_page_registries):
        """Normal confirm still returns full identity card."""
        identity_reg, photo_reg, target_id, source_id = person_page_registries

        # Make target PROPOSED so it can be confirmed
        identity_reg._identities[target_id]["state"] = IdentityState.PROPOSED.value

        with (
            patch("app.main.load_registry", return_value=identity_reg),
            patch("app.main.save_registry"),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
            from app.main import app

            client = TestClient(app)
            response = client.post(
                f"/confirm/{target_id}",
                headers={"HX-Request": "true"},
            )

        assert response.status_code == 200
        # Normal confirm should return something substantive
        assert "James Fields" in response.text


class TestNeighborCardPersonPageTargeting:
    """FB-019: Merge button targets #neighbor-{id} on person page."""

    def test_merge_button_targets_neighbor_on_person_page(self, person_page_registries):
        """On person page, merge button targets the neighbor card itself."""
        from app.main import neighbor_card

        identity_reg, photo_reg, target_id, source_id = person_page_registries

        neighbor = {
            "identity_id": source_id,
            "name": "Similar Person",
            "distance": 0.95,
            "can_merge": True,
            "face_count": 1,
            "co_occurrence": 0,
            "anchor_face_ids": ["face_b"],
            "candidate_face_ids": [],
        }

        card = neighbor_card(
            neighbor,
            target_id,
            set(),
            target_name="James Fields",
            from_person_page=True,
        )
        html = to_xml(card)

        # Should target #neighbor-{source_id} on person page
        assert f'hx-target="#neighbor-{source_id}"' in html
        # Should NOT target #identity-{target_id} (doesn't exist on person page)
        assert f'hx-target="#identity-{target_id}"' not in html
        # Should include from_person_page in URL
        assert "from_person_page=true" in html

    def test_merge_button_targets_identity_in_browse_mode(self, person_page_registries):
        """In normal browse mode, merge button targets the identity card."""
        from app.main import neighbor_card

        identity_reg, photo_reg, target_id, source_id = person_page_registries

        neighbor = {
            "identity_id": source_id,
            "name": "Similar Person",
            "distance": 0.95,
            "can_merge": True,
            "face_count": 1,
            "co_occurrence": 0,
            "anchor_face_ids": ["face_b"],
            "candidate_face_ids": [],
        }

        card = neighbor_card(
            neighbor,
            target_id,
            set(),
            target_name="James Fields",
            from_person_page=False,
        )
        html = to_xml(card)

        # Should target #identity-{target_id} in browse mode
        assert f'hx-target="#identity-{target_id}"' in html
        # Should NOT include from_person_page
        assert "from_person_page" not in html


class TestLoadingIndicators:
    """FB-016/FB-024: Loading indicators on slow-action buttons."""

    def test_merge_button_has_loading_indicator(self, person_page_registries):
        """Merge button has hx-disabled-elt for loading state."""
        from app.main import neighbor_card

        identity_reg, photo_reg, target_id, source_id = person_page_registries

        neighbor = {
            "identity_id": source_id,
            "name": "Similar Person",
            "distance": 0.95,
            "can_merge": True,
            "face_count": 1,
            "co_occurrence": 0,
            "anchor_face_ids": ["face_b"],
            "candidate_face_ids": [],
        }

        card = neighbor_card(neighbor, target_id, set(), target_name="James Fields")
        html = to_xml(card)

        assert "hx-disabled-elt" in html
        assert "disabled:opacity-50" in html
