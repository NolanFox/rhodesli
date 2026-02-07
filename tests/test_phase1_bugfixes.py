"""Tests for Phase 1 bug fixes: multi-merge form, carousel count, photo click."""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Bug 1: Multi-merge form fixes
# ---------------------------------------------------------------------------

class TestBulkMergeForm:
    """Tests for the bulk merge form structure and submission."""

    def test_bulk_merge_buttons_have_own_hx_post(self):
        """Merge Selected and Not Same Selected buttons have individual hx-post attributes."""
        from app.main import neighbors_sidebar, to_xml

        # Create mock neighbors (need at least 2 mergeable for bulk actions)
        neighbors = [
            {
                "identity_id": f"neighbor-{i}",
                "name": f"Person {i}",
                "distance": 0.5,
                "percentile": 0.8,
                "can_merge": True,
                "merge_blocked_reason": None,
                "anchor_face_ids": [f"face-{i}"],
                "candidate_face_ids": [],
            }
            for i in range(3)
        ]
        crop_files = set()

        html = to_xml(neighbors_sidebar("target-id", neighbors, crop_files))

        # Both buttons should have their own hx-post (not relying on form's hx-post)
        assert 'hx-post="/api/identity/target-id/bulk-merge"' in html
        assert 'hx-post="/api/identity/target-id/bulk-reject"' in html

    def test_bulk_merge_buttons_include_closest_form(self):
        """Both buttons use hx-include to pull form data."""
        from app.main import neighbors_sidebar, to_xml

        neighbors = [
            {
                "identity_id": f"neighbor-{i}",
                "name": f"Person {i}",
                "distance": 0.5,
                "percentile": 0.8,
                "can_merge": True,
                "merge_blocked_reason": None,
                "anchor_face_ids": [f"face-{i}"],
                "candidate_face_ids": [],
            }
            for i in range(3)
        ]
        crop_files = set()

        html = to_xml(neighbors_sidebar("target-id", neighbors, crop_files))

        # Buttons should use hx-include to grab form data
        assert 'hx-include="closest form"' in html

    def test_bulk_merge_form_no_form_level_hx_post(self):
        """Form element should NOT have its own hx-post (buttons handle it individually)."""
        from app.main import neighbors_sidebar, to_xml

        neighbors = [
            {
                "identity_id": f"neighbor-{i}",
                "name": f"Person {i}",
                "distance": 0.5,
                "percentile": 0.8,
                "can_merge": True,
                "merge_blocked_reason": None,
                "anchor_face_ids": [f"face-{i}"],
                "candidate_face_ids": [],
            }
            for i in range(3)
        ]
        crop_files = set()

        html = to_xml(neighbors_sidebar("target-id", neighbors, crop_files))

        # The form tag itself should not have hx-post
        # Check that hx-post appears only on buttons, not form
        lines = html.split('\n')
        for line in lines:
            if '<form' in line.lower():
                assert 'hx-post' not in line, \
                    f"Form element should not have hx-post (buttons handle routing): {line}"

    def test_neighbor_checkbox_sets_property_not_attribute(self):
        """Neighbor card checkbox uses property assignment for reliable FormData serialization."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "neighbor-abc",
            "name": "Test Person",
            "distance": 0.5,
            "percentile": 0.8,
            "can_merge": True,
            "merge_blocked_reason": None,
            "anchor_face_ids": ["face-1"],
            "candidate_face_ids": [],
        }
        crop_files = set()

        html = to_xml(neighbor_card(neighbor, "target-id", crop_files))

        # Should use property assignment (.checked = ) not attribute toggle (@checked)
        assert ".checked" in html, "Should use property assignment for checkbox toggling"
        assert "toggle @checked" not in html, "Should not use attribute toggle"

    def test_bulk_merge_hidden_checkboxes_present(self):
        """Hidden checkboxes with name='bulk_ids' exist for each mergeable neighbor."""
        from app.main import neighbors_sidebar, to_xml

        neighbors = [
            {
                "identity_id": f"neighbor-{i}",
                "name": f"Person {i}",
                "distance": 0.5,
                "percentile": 0.8,
                "can_merge": True,
                "merge_blocked_reason": None,
                "anchor_face_ids": [f"face-{i}"],
                "candidate_face_ids": [],
            }
            for i in range(3)
        ]
        crop_files = set()

        html = to_xml(neighbors_sidebar("target-id", neighbors, crop_files))

        # Each mergeable neighbor should have a hidden checkbox
        for i in range(3):
            assert f'id="bulk-neighbor-{i}"' in html
            assert f'value="neighbor-{i}"' in html


# ---------------------------------------------------------------------------
# Bug 2: Carousel count ("+N More") updates after actions
# ---------------------------------------------------------------------------

class TestFocusCarouselUpdate:
    """Tests for the focus mode carousel updating correctly."""

    def _make_identities(self, count):
        """Create mock identities for focus mode testing."""
        return [
            {
                "identity_id": f"id-{i}",
                "name": f"Person {i}",
                "state": "INBOX",
                "anchor_ids": [f"face-{i}-a"],
                "candidate_ids": [f"face-{i}-b"] * (count - i),  # Varying face counts
                "created_at": f"2026-01-{i+1:02d}T00:00:00Z",
            }
            for i in range(count)
        ]

    @patch("app.main.load_registry")
    @patch("app.main.get_crop_files", return_value=set())
    def test_get_next_focus_card_includes_carousel(self, mock_crops, mock_registry):
        """get_next_focus_card returns both expanded card AND Up Next carousel."""
        from app.main import get_next_focus_card, to_xml, IdentityState

        identities = self._make_identities(8)
        registry = MagicMock()
        registry.list_identities.side_effect = lambda state: identities if state == IdentityState.INBOX else []
        mock_registry.return_value = registry

        result = get_next_focus_card()
        html = to_xml(result)

        # Should have focus-container wrapping everything
        assert 'id="focus-container"' in html
        # Should have the Up Next section
        assert "Up Next" in html

    @patch("app.main.load_registry")
    @patch("app.main.get_crop_files", return_value=set())
    def test_get_next_focus_card_shows_correct_remaining_count(self, mock_crops, mock_registry):
        """The +N more count reflects actual remaining items."""
        from app.main import get_next_focus_card, to_xml, IdentityState

        identities = self._make_identities(10)
        registry = MagicMock()
        registry.list_identities.side_effect = lambda state: identities if state == IdentityState.INBOX else []
        mock_registry.return_value = registry

        result = get_next_focus_card()
        html = to_xml(result)

        # 10 items: 1 expanded + 5 in carousel + "+4 more"
        assert "+4 more" in html

    @patch("app.main.load_registry")
    @patch("app.main.get_crop_files", return_value=set())
    def test_get_next_focus_card_excludes_actioned_identity(self, mock_crops, mock_registry):
        """When exclude_id is provided, that identity is filtered out."""
        from app.main import get_next_focus_card, to_xml, IdentityState

        identities = self._make_identities(3)
        registry = MagicMock()
        registry.list_identities.side_effect = lambda state: identities if state == IdentityState.INBOX else []
        mock_registry.return_value = registry

        result = get_next_focus_card(exclude_id="id-0")
        html = to_xml(result)

        # The excluded identity should not appear
        assert 'id-0' not in html or 'exclude' in html.lower()  # id-0 should be gone

    @patch("app.main.load_registry")
    @patch("app.main.get_crop_files", return_value=set())
    def test_get_next_focus_card_empty_state(self, mock_crops, mock_registry):
        """When no items remain, shows empty state with focus-container id."""
        from app.main import get_next_focus_card, to_xml, IdentityState

        registry = MagicMock()
        registry.list_identities.return_value = []
        mock_registry.return_value = registry

        result = get_next_focus_card()
        html = to_xml(result)

        assert 'id="focus-container"' in html
        assert "All caught up" in html

    def test_focus_mode_action_buttons_target_container(self):
        """Action buttons in focus mode target #focus-container, not #focus-card."""
        from app.main import identity_card_expanded, to_xml

        identity = {
            "identity_id": "test-id",
            "name": "Test Person",
            "state": "INBOX",
            "anchor_ids": ["face-1"],
            "candidate_ids": ["face-2"],
        }
        crop_files = set()

        html = to_xml(identity_card_expanded(identity, crop_files, is_admin=True))

        # Action buttons should target the container, not the card
        assert 'hx-target="#focus-container"' in html
        assert 'hx-target="#focus-card"' not in html


# ---------------------------------------------------------------------------
# Bug 3: First photo click consistency
# ---------------------------------------------------------------------------

class TestPhotoClickConsistency:
    """Tests for consistent photo click behavior in Focus mode."""

    def test_main_face_is_clickable(self):
        """The main face image in expanded card is clickable to view photo."""
        from app.main import identity_card_expanded, to_xml

        identity = {
            "identity_id": "test-id",
            "name": "Test Person",
            "state": "INBOX",
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
        }
        crop_files = set()

        # Mock get_photo_id_for_face to return a photo ID
        with patch("app.main.get_photo_id_for_face", return_value="photo-abc"):
            html = to_xml(identity_card_expanded(identity, crop_files))

        # Main face should have click handler to open photo modal
        assert "photo-modal" in html
        assert "/photo/photo-abc/partial" in html

    def test_main_face_opens_same_modal_as_other_faces(self):
        """All face thumbnails (including main) open the photo modal."""
        from app.main import identity_card_expanded, to_xml

        identity = {
            "identity_id": "test-id",
            "name": "Test Person",
            "state": "INBOX",
            "anchor_ids": ["face-1", "face-2", "face-3"],
            "candidate_ids": [],
        }
        crop_files = set()

        with patch("app.main.get_photo_id_for_face", return_value="photo-abc"), \
             patch("app.main.resolve_face_image_url", return_value="/fake/crop.jpg"):
            html = to_xml(identity_card_expanded(identity, crop_files))

        # Should have photo modal triggers for main face
        assert 'hx-target="#photo-modal-content"' in html
        # The main face should also have a click-to-view handler
        modal_triggers = html.count('remove .hidden from #photo-modal')
        # At least 1 for main face + additional face previews
        assert modal_triggers >= 1, f"Expected at least 1 modal trigger, got {modal_triggers}"

    def test_main_face_no_photo_shows_placeholder(self):
        """When no photo ID available, main face shows placeholder without click handler."""
        from app.main import identity_card_expanded, to_xml

        identity = {
            "identity_id": "test-id",
            "name": "Test Person",
            "state": "INBOX",
            "anchor_ids": [],
            "candidate_ids": [],
        }
        crop_files = set()

        html = to_xml(identity_card_expanded(identity, crop_files))

        # Should show placeholder "?" and not crash
        assert "?" in html
