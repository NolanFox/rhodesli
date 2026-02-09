"""Tests for Phase 2: Photo navigation with keyboard arrows and lightbox prev/next."""

import pytest
from unittest.mock import patch, MagicMock


class TestPhotoNavUrl:
    """Tests for the _photo_nav_url helper function."""

    def test_first_photo_has_next_only(self):
        """First photo in collection has next_id but no prev_id."""
        from app.main import _photo_nav_url
        photos = [{"photo_id": f"p{i}"} for i in range(5)]
        url = _photo_nav_url("p0", 0, photos, 5)
        assert "prev_id" not in url
        assert "next_id=p1" in url
        assert "nav_idx=0" in url
        assert "nav_total=5" in url

    def test_last_photo_has_prev_only(self):
        """Last photo in collection has prev_id but no next_id."""
        from app.main import _photo_nav_url
        photos = [{"photo_id": f"p{i}"} for i in range(5)]
        url = _photo_nav_url("p4", 4, photos, 5)
        assert "prev_id=p3" in url
        assert "next_id" not in url

    def test_middle_photo_has_both(self):
        """Middle photo has both prev_id and next_id."""
        from app.main import _photo_nav_url
        photos = [{"photo_id": f"p{i}"} for i in range(5)]
        url = _photo_nav_url("p2", 2, photos, 5)
        assert "prev_id=p1" in url
        assert "next_id=p3" in url
        assert "nav_idx=2" in url

    def test_single_photo_has_no_nav(self):
        """Single photo in collection has no prev/next."""
        from app.main import _photo_nav_url
        photos = [{"photo_id": "p0"}]
        url = _photo_nav_url("p0", 0, photos, 1)
        assert "prev_id" not in url
        assert "next_id" not in url


class TestPhotoViewNavigation:
    """Tests for navigation elements in photo_view_content."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_nav_buttons_rendered_with_context(self, mock_reg, mock_dim, mock_meta):
        """Prev/next buttons appear when navigation context is provided."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test Collection",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        # Prev button
        assert 'id="photo-nav-prev"' in html
        assert "/photo/p0/partial" in html
        # Next button
        assert 'id="photo-nav-next"' in html
        assert "/photo/p2/partial" in html
        # Counter
        assert "2 / 5" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_no_nav_without_context(self, mock_reg, mock_dim, mock_meta):
        """No navigation buttons when no context provided."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test Collection",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True)
        html = to_xml(result)

        assert 'id="photo-nav-prev"' not in html
        assert 'id="photo-nav-next"' not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_nav_buttons_have_data_action(self, mock_reg, mock_dim, mock_meta):
        """Nav buttons have data-action attributes for global event delegation."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=3
        )
        html = to_xml(result)

        # Buttons carry data-action for the global delegation handler
        assert 'data-action="photo-nav-prev"' in html
        assert 'data-action="photo-nav-next"' in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_first_photo_no_prev_button(self, mock_reg, mock_dim, mock_meta):
        """First photo has next but no prev button."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p0", is_partial=True,
            next_id="p1",
            nav_idx=0, nav_total=3
        )
        html = to_xml(result)

        assert 'id="photo-nav-prev"' not in html
        assert 'id="photo-nav-next"' in html
        assert "1 / 3" in html


class TestPhotoModalEscape:
    """Tests for photo modal keyboard handling."""

    def test_photo_modal_has_escape_handler(self):
        """Photo modal has Escape key handler."""
        from app.main import photo_modal, to_xml

        html = to_xml(photo_modal())
        assert "Escape" in html
        assert 'tabindex="-1"' in html


class TestArrowButtonsUseEventDelegation:
    """Regression: arrow buttons must use data-action for event delegation (BUG-001)."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_prev_button_has_data_action_and_index(self, mock_reg, mock_dim, mock_meta):
        """Prev button uses data-action and data-nav-idx for delegation."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        assert 'data-action="photo-nav-prev"' in html
        assert 'data-nav-idx="0"' in html  # nav_idx - 1 = 0

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_next_button_has_data_action_and_index(self, mock_reg, mock_dim, mock_meta):
        """Next button uses data-action and data-nav-idx for delegation."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=5
        )
        html = to_xml(result)

        assert 'data-action="photo-nav-next"' in html
        assert 'data-nav-idx="2"' in html  # nav_idx + 1 = 2

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_no_inline_onclick_on_arrows(self, mock_reg, mock_dim, mock_meta):
        """Arrow buttons must NOT use inline onclick (dies on HTMX swap)."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p1", is_partial=True,
            prev_id="p0", next_id="p2",
            nav_idx=1, nav_total=3
        )
        html = to_xml(result)

        # No inline onclick that calls photoNavTo — delegation handles it
        assert 'onclick="if(typeof photoNavTo' not in html


class TestIdentityBasedNavigation:
    """Tests for identity-context photo navigation (face card clicks)."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face")
    def test_identity_id_computes_nav_buttons(self, mock_face_photo, mock_reg, mock_dim, mock_meta):
        """When identity_id is provided, prev/next computed from identity's photos."""
        from app.main import photo_view_content, to_xml

        # Identity has 3 faces in 3 different photos
        mock_identity = {
            "identity_id": "id1",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["f1", "f2", "f3"],
            "candidate_ids": [],
        }
        mock_reg_inst = MagicMock()
        mock_reg_inst.get_identity.return_value = mock_identity
        mock_reg.return_value = mock_reg_inst

        # Map faces to photos
        mock_face_photo.side_effect = lambda fid: {"f1": "p1", "f2": "p2", "f3": "p3"}.get(fid)

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [],
            "source": "Test",
        }

        # View middle photo with identity context
        result = photo_view_content("p2", is_partial=True, identity_id="id1")
        html = to_xml(result)

        # Should have both prev and next buttons
        assert 'id="photo-nav-prev"' in html
        assert 'id="photo-nav-next"' in html
        # Counter should show 2 / 3
        assert "2 / 3" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face")
    def test_identity_nav_first_photo_no_prev(self, mock_face_photo, mock_reg, mock_dim, mock_meta):
        """First photo in identity's list has next but no prev."""
        from app.main import photo_view_content, to_xml

        mock_identity = {
            "identity_id": "id1",
            "name": "Test",
            "state": "CONFIRMED",
            "anchor_ids": ["f1", "f2"],
            "candidate_ids": [],
        }
        mock_reg_inst = MagicMock()
        mock_reg_inst.get_identity.return_value = mock_identity
        mock_reg.return_value = mock_reg_inst
        mock_face_photo.side_effect = lambda fid: {"f1": "p1", "f2": "p2"}.get(fid)
        mock_meta.return_value = {"filename": "test.jpg", "faces": [], "source": "Test"}

        result = photo_view_content("p1", is_partial=True, identity_id="id1")
        html = to_xml(result)

        assert 'id="photo-nav-prev"' not in html
        assert 'id="photo-nav-next"' in html
        assert "1 / 2" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face")
    def test_identity_nav_carries_identity_id_on_buttons(self, mock_face_photo, mock_reg, mock_dim, mock_meta):
        """Nav button URLs include identity_id for continuity."""
        from app.main import photo_view_content, to_xml

        mock_identity = {
            "identity_id": "id1",
            "name": "Test",
            "state": "CONFIRMED",
            "anchor_ids": ["f1", "f2", "f3"],
            "candidate_ids": [],
        }
        mock_reg_inst = MagicMock()
        mock_reg_inst.get_identity.return_value = mock_identity
        mock_reg.return_value = mock_reg_inst
        mock_face_photo.side_effect = lambda fid: {"f1": "p1", "f2": "p2", "f3": "p3"}.get(fid)
        mock_meta.return_value = {"filename": "test.jpg", "faces": [], "source": "Test"}

        result = photo_view_content("p2", is_partial=True, identity_id="id1")
        html = to_xml(result)

        # Both nav button URLs should include identity_id
        assert "identity_id=id1" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face")
    def test_identity_nav_deduplicates_photos(self, mock_face_photo, mock_reg, mock_dim, mock_meta):
        """Multiple faces in same photo should not create duplicate nav entries."""
        from app.main import photo_view_content, to_xml

        mock_identity = {
            "identity_id": "id1",
            "name": "Test",
            "state": "CONFIRMED",
            "anchor_ids": ["f1", "f2", "f3"],
            "candidate_ids": [],
        }
        mock_reg_inst = MagicMock()
        mock_reg_inst.get_identity.return_value = mock_identity
        mock_reg.return_value = mock_reg_inst
        # f1 and f2 in same photo, f3 in different photo
        mock_face_photo.side_effect = lambda fid: {"f1": "p1", "f2": "p1", "f3": "p2"}.get(fid)
        mock_meta.return_value = {"filename": "test.jpg", "faces": [], "source": "Test"}

        result = photo_view_content("p1", is_partial=True, identity_id="id1")
        html = to_xml(result)

        # Should show 1 / 2 (two unique photos), not 1 / 3
        assert "1 / 2" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face")
    def test_identity_nav_single_photo_no_arrows(self, mock_face_photo, mock_reg, mock_dim, mock_meta):
        """Identity with one unique photo shows no nav arrows."""
        from app.main import photo_view_content, to_xml

        mock_identity = {
            "identity_id": "id1",
            "name": "Test",
            "state": "CONFIRMED",
            "anchor_ids": ["f1"],
            "candidate_ids": [],
        }
        mock_reg_inst = MagicMock()
        mock_reg_inst.get_identity.return_value = mock_identity
        mock_reg.return_value = mock_reg_inst
        mock_face_photo.side_effect = lambda fid: {"f1": "p1"}.get(fid)
        mock_meta.return_value = {"filename": "test.jpg", "faces": [], "source": "Test"}

        result = photo_view_content("p1", is_partial=True, identity_id="id1")
        html = to_xml(result)

        assert 'id="photo-nav-prev"' not in html
        assert 'id="photo-nav-next"' not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_explicit_nav_overrides_identity(self, mock_reg, mock_dim, mock_meta):
        """Explicit prev_id/next_id takes precedence over identity_id computation."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {"filename": "test.jpg", "faces": [], "source": "Test"}
        mock_reg.return_value = MagicMock()

        result = photo_view_content(
            "p2", is_partial=True,
            prev_id="p1", next_id="p3",
            nav_idx=1, nav_total=5,
            identity_id="id1"
        )
        html = to_xml(result)

        # Should use explicit nav, showing 2 / 5 not identity-computed values
        assert "2 / 5" in html


class TestConfirmedFaceClick:
    """Tests for confirmed face click behavior in photo view."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_confirmed_face_navigates_not_tags(self, mock_reg, mock_dim, mock_meta):
        """Clicking a confirmed face should navigate to identity card, not open tag dialog."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "f1", "bbox": [10, 10, 100, 100]}],
            "source": "Test",
        }
        mock_identity = {
            "identity_id": "id1",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["f1"],
            "candidate_ids": [],
            "negative_ids": [],
        }
        mock_reg_inst = MagicMock()
        mock_reg_inst.get_identity.return_value = mock_identity
        mock_reg_inst.get_all_identities.return_value = {"id1": mock_identity}
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=mock_identity):
            result = photo_view_content("p1", is_partial=True)
            html = to_xml(result)

        # Should have navigation to identity card
        assert "#identity-id1" in html
        # Should NOT have tag dropdown for this confirmed face
        # The dropdown still exists in DOM but the click handler navigates instead
        assert "go to url" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_unconfirmed_face_opens_tag_dialog(self, mock_reg, mock_dim, mock_meta):
        """Clicking an unconfirmed face should open the tag dropdown."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "f1", "bbox": [10, 10, 100, 100]}],
            "source": "Test",
        }
        mock_identity = {
            "identity_id": "id1",
            "name": "Unidentified Person 42",
            "state": "INBOX",
            "anchor_ids": [],
            "candidate_ids": ["f1"],
            "negative_ids": [],
        }
        mock_reg_inst = MagicMock()
        mock_reg_inst.get_identity.return_value = mock_identity
        mock_reg_inst.get_all_identities.return_value = {"id1": mock_identity}
        mock_reg.return_value = mock_reg_inst

        with patch("app.main.get_identity_for_face", return_value=mock_identity):
            result = photo_view_content("p1", is_partial=True)
            html = to_xml(result)

        # Should have tag dropdown toggle (not navigation)
        assert "toggle .hidden on" in html
        assert "Type name to tag" in html


class TestFaceCardIdentityContext:
    """Tests that face card clicks include identity_id for navigation."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_photo_id_for_face")
    @patch("app.main.resolve_face_image_url")
    @patch("app.main.get_crop_files", return_value=set())
    @patch("app.main.get_identity_for_face", return_value=None)
    @patch("app.main.photo_url", side_effect=lambda f: f"/photos/{f}")
    def test_face_detail_view_photo_has_identity_id(self, *mocks):
        """'View Photo' button in face detail card passes identity_id."""
        from app.main import face_card, to_xml

        html = to_xml(face_card(
            face_id="f1",
            crop_url="/crops/f1.jpg",
            quality=0.95,
            identity_id="id1",
            photo_id="p1",
        ))

        assert "identity_id=id1" in html


class TestPhotosGridNavScript:
    """Tests for the navigation script embedded in the photos grid."""

    @patch("app.main._build_caches")
    @patch("app.main._photo_cache", {
        "p1": {"filename": "a.jpg", "source": "Test", "faces": []},
        "p2": {"filename": "b.jpg", "source": "Test", "faces": []},
        "p3": {"filename": "c.jpg", "source": "Test", "faces": []},
    })
    @patch("app.main.get_identity_for_face", return_value=None)
    @patch("app.main.photo_url", side_effect=lambda f: f"/photos/{f}")
    def test_photos_section_includes_nav_script(self, mock_url, mock_id, mock_cache):
        """Photos section embeds JS with photo ID list for keyboard navigation."""
        from app.main import render_photos_section, to_xml

        registry = MagicMock()
        html = to_xml(render_photos_section(
            {"photos": 3}, registry, set()
        ))

        assert "window._photoNavIds" in html
        assert "photoNavTo" in html
        assert "ArrowLeft" in html
        assert "ArrowRight" in html
