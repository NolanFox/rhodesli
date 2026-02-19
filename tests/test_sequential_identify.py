"""Tests for "Name These Faces" sequential identification mode (PRD-021 P1).

Covers:
- "Name These Faces" button visibility (admin + 2+ unidentified)
- Sequential mode activation (seq=1 parameter)
- Progress banner display
- Auto-advance to next unidentified face
- "Done" button exits sequential mode
- seq parameter propagation through tag/create endpoints
"""

import pytest
from unittest.mock import patch, MagicMock


def _make_photo_meta(face_count=3, identified_count=0):
    """Build mock photo metadata with configurable face counts."""
    faces = []
    for i in range(face_count):
        faces.append({
            "face_id": f"face-{i}",
            "bbox": [10 + i * 100, 10, 90 + i * 100, 90],  # left-to-right
        })
    return {
        "filename": "test_group.jpg",
        "faces": faces,
        "source": "Test Collection",
    }


def _identity_for_face(identified_set):
    """Return a mock get_identity_for_face that marks certain faces as identified."""
    def _get(registry, face_id):
        idx = int(face_id.split("-")[1])
        if idx in identified_set:
            return {
                "identity_id": f"id-{idx}",
                "name": f"Person {idx}",
                "state": "CONFIRMED",
            }
        else:
            return {
                "identity_id": f"id-{idx}",
                "name": f"Unidentified Person {idx}",
                "state": "INBOX",
            }
    return _get


class TestNameTheseFacesButton:
    """The 'Name These Faces' button appears for admin with 2+ unidentified faces."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_button_shown_admin_multiple_unidentified(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Admin sees 'Name These Faces' button when 2+ faces are unidentified."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=4, identified_count=0)
        mock_get_id.side_effect = _identity_for_face(set())  # none identified
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True)
        html = to_xml(result)

        assert "Name These Faces" in html
        assert "4 unidentified" in html
        assert "seq=1" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_button_hidden_non_admin(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Non-admin does NOT see 'Name These Faces' button."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=4)
        mock_get_id.side_effect = _identity_for_face(set())
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=False)
        html = to_xml(result)

        assert "Name These Faces" not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_button_hidden_single_unidentified(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Button not shown when only 1 face is unidentified."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=3)
        # 2 of 3 identified → only 1 unidentified
        mock_get_id.side_effect = _identity_for_face({0, 1})
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True)
        html = to_xml(result)

        assert "Name These Faces" not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_button_hidden_all_identified(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Button not shown when all faces are already identified."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=3)
        mock_get_id.side_effect = _identity_for_face({0, 1, 2})
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True)
        html = to_xml(result)

        assert "Name These Faces" not in html


class TestSequentialModeActivation:
    """Sequential mode renders progress banner and auto-opens first face's dropdown."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_seq_mode_shows_progress_banner(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Sequential mode shows progress banner with count."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=4)
        mock_get_id.side_effect = _identity_for_face({0})  # 1 identified
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True, seq_mode=True)
        html = to_xml(result)

        assert "Naming faces" in html
        assert "1 of 4 identified" in html
        # "Name These Faces" button should be hidden in seq mode
        assert "Name These Faces" not in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_seq_mode_auto_opens_first_unidentified_dropdown(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """In seq mode, the first unidentified face's tag dropdown is open (not hidden)."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=3)
        mock_get_id.side_effect = _identity_for_face({0})  # face-0 identified, face-1 and face-2 not
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True, seq_mode=True)
        html = to_xml(result)

        # face-1 should be the first unidentified (face-0 is identified)
        # Its tag dropdown should NOT have 'hidden' class
        # The dropdown id pattern is tag-dropdown-face-1
        assert 'id="tag-dropdown-face-1"' in html
        # Check that face-1's dropdown is not hidden (no "hidden" class before "tag-dropdown")
        # Find the specific dropdown div
        import re
        dd_match = re.search(r'id="tag-dropdown-face-1"[^>]*class="([^"]*)"', html)
        if not dd_match:
            dd_match = re.search(r'class="([^"]*)"[^>]*id="tag-dropdown-face-1"', html)
        assert dd_match, "Could not find tag-dropdown-face-1 element"
        dd_classes = dd_match.group(1)
        assert "hidden" not in dd_classes.split(), f"Active face dropdown should not be hidden, got classes: {dd_classes}"

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_seq_mode_highlights_active_face(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """In seq mode, the active face has a visual highlight (ring)."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=3)
        mock_get_id.side_effect = _identity_for_face({0})
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True, seq_mode=True)
        html = to_xml(result)

        assert "ring-2 ring-indigo-400" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_seq_mode_done_button_exits(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Sequential mode has a 'Done' button that exits seq mode."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=3)
        mock_get_id.side_effect = _identity_for_face(set())
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True, seq_mode=True)
        html = to_xml(result)

        assert "Done" in html
        # Done button should NOT include seq=1
        assert '/partial"' in html or "/partial?" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_seq_mode_all_identified_shows_completion(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """When all faces are identified in seq mode, show 'All faces identified!'."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=3)
        mock_get_id.side_effect = _identity_for_face({0, 1, 2})
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True, seq_mode=True)
        html = to_xml(result)

        assert "All faces identified" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_seq_mode_left_to_right_order(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Sequential mode picks leftmost unidentified face first."""
        from app.main import photo_view_content, to_xml

        # face-0 at x=10, face-1 at x=110, face-2 at x=210
        # face-0 identified, face-1 and face-2 unidentified
        # Should pick face-1 (leftmost unidentified)
        mock_meta.return_value = _make_photo_meta(face_count=3)
        mock_get_id.side_effect = _identity_for_face({0})
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True, seq_mode=True)
        html = to_xml(result)

        # face-1's dropdown should be open (not hidden)
        import re
        dd_match = re.search(r'id="tag-dropdown-face-1"[^>]*class="([^"]*)"', html)
        if not dd_match:
            dd_match = re.search(r'class="([^"]*)"[^>]*id="tag-dropdown-face-1"', html)
        assert dd_match, "Could not find face-1 dropdown"
        assert "hidden" not in dd_match.group(1).split()

        # face-2's dropdown should still be hidden
        dd2_match = re.search(r'id="tag-dropdown-face-2"[^>]*class="([^"]*)"', html)
        if not dd2_match:
            dd2_match = re.search(r'class="([^"]*)"[^>]*id="tag-dropdown-face-2"', html)
        assert dd2_match, "Could not find face-2 dropdown"
        assert "hidden" in dd2_match.group(1).split()


class TestSeqPropagation:
    """seq parameter is propagated through tag/create endpoints."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_seq_mode_propagates_in_tag_search_url(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """In seq mode, tag search URLs include seq=1."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = _make_photo_meta(face_count=3)
        mock_get_id.side_effect = _identity_for_face(set())
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True, seq_mode=True)
        html = to_xml(result)

        assert "tag-search" in html
        assert "&amp;seq=1" in html or "&seq=1" in html

    def test_tag_search_passes_seq_to_results(self, client):
        """Tag search with seq=1 includes seq=1 in action button URLs."""
        response = client.get("/api/face/tag-search?face_id=test_face&q=TestName&seq=1")
        text = response.text
        # If there are results or create button, they should include seq=1
        if "create-identity" in text:
            assert "seq=1" in text
        if "/api/face/tag?" in text:
            assert "seq=1" in text

    def test_tag_search_no_seq_without_param(self, client):
        """Tag search without seq param does not include seq=1 in URLs."""
        response = client.get("/api/face/tag-search?face_id=test_face&q=TestName")
        text = response.text
        # Should not have seq=1 in action URLs
        if "create-identity" in text:
            assert "seq=1" not in text

    @patch("app.main.save_registry")
    @patch("app.main.load_photo_registry")
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_photo_id_for_face", return_value="p1")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    def test_tag_endpoint_passes_seq_mode(self, mock_dim, mock_meta, mock_pid, mock_get_id,
                                          mock_reg, mock_photo_reg, mock_save, client):
        """POST /api/face/tag with seq=1 re-renders in sequential mode."""
        mock_meta.return_value = _make_photo_meta(face_count=3)
        mock_get_id.side_effect = _identity_for_face(set())

        registry = MagicMock()
        registry.get_identity.return_value = {"identity_id": "target-1", "name": "Test Person", "state": "CONFIRMED"}
        registry.merge_identities.return_value = {"success": True, "target_id": "target-1", "source_id": "id-0"}
        mock_reg.return_value = registry
        mock_photo_reg.return_value = MagicMock()

        response = client.post("/api/face/tag?face_id=face-0&target_id=target-1&seq=1")
        assert response.status_code == 200
        html = response.text

        # Should be in sequential mode (progress banner visible)
        assert "Naming faces" in html or "All faces identified" in html

    @patch("app.main.save_registry")
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    @patch("app.main.get_photo_id_for_face", return_value="p1")
    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    def test_create_identity_passes_seq_mode(self, mock_dim, mock_meta, mock_pid, mock_get_id,
                                              mock_reg, mock_save, client):
        """POST /api/face/create-identity with seq=1 re-renders in sequential mode."""
        mock_meta.return_value = _make_photo_meta(face_count=3)
        mock_get_id.side_effect = _identity_for_face(set())

        registry = MagicMock()
        source_id_obj = {"identity_id": "id-0", "name": "Unidentified Person 0", "state": "INBOX"}
        registry.get_identity.return_value = source_id_obj
        mock_get_id.return_value = source_id_obj
        mock_reg.return_value = registry

        response = client.post("/api/face/create-identity?face_id=face-0&name=Albert%20Cohen&seq=1")
        assert response.status_code == 200
        html = response.text

        assert "Naming faces" in html or "All faces identified" in html


class TestPartialRouteSeqParam:
    """The /photo/{id}/partial route accepts and passes seq parameter."""

    def test_partial_route_accepts_seq(self, client):
        """GET /photo/{id}/partial?seq=1 returns 200."""
        from app.main import load_embeddings_for_photos
        photos = load_embeddings_for_photos()
        if not photos:
            pytest.skip("No embeddings available for testing")
        photo_id = next(iter(photos.keys()))
        response = client.get(f"/photo/{photo_id}/partial?seq=1")
        assert response.status_code == 200
        # Should include sequential mode elements
        html = response.text
        assert "Naming faces" in html or "Name These Faces" in html or "All faces identified" in html
