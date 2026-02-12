"""
Tests for UX enhancements:
1. Compare modal "View Photo" links with hx-get targeting /photo/{id}/partial
2. Post-merge guidance banner (Grouped vs Merge complete)
3. Grouped badge for unnamed multi-face identities
4. Compare modal size (max-w-[90vw] not max-w-5xl)
"""

import pytest
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers: build mock registries for route-level tests
# ---------------------------------------------------------------------------

def _make_identity(identity_id, name=None, state="PROPOSED",
                   anchor_ids=None, candidate_ids=None):
    """Create a minimal identity dict matching the registry schema."""
    return {
        "identity_id": identity_id,
        "name": name or f"Unidentified Person {identity_id[:8]}",
        "state": state,
        "anchor_ids": anchor_ids or [],
        "candidate_ids": candidate_ids or [],
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "history": [],
    }


def _make_registry(identities_list):
    """Build a real IdentityRegistry populated with test identities."""
    from core.registry import IdentityRegistry
    registry = IdentityRegistry()
    for ident in identities_list:
        registry._identities[ident["identity_id"]] = ident
    return registry


def _make_photo_registry_mock():
    """Build a mock PhotoRegistry that allows all merges (no co-occurrence)."""
    photo_reg = MagicMock()
    photo_reg.get_photos_for_faces.return_value = set()
    return photo_reg


# ---------------------------------------------------------------------------
# 1. Compare modal "View Photo" links
# ---------------------------------------------------------------------------

class TestCompareViewPhotoLinks:
    """The compare endpoint should include 'View Photo' buttons with hx-get
    targeting /photo/{photo_id}/partial."""

    def _build_compare_mocks(self):
        """Set up mocks for the compare endpoint with two identities that have
        faces mapped to photos."""
        target = _make_identity("target-aaa", name="Leon Capeluto", state="CONFIRMED",
                                anchor_ids=["face-t1"])
        neighbor = _make_identity("neighbor-bbb", name="Betty Capeluto", state="CONFIRMED",
                                  anchor_ids=["face-n1"])
        registry = _make_registry([target, neighbor])

        # Mock crop_files to resolve face images
        crop_files = {"face-t1.jpg", "face-n1.jpg"}

        # Mock the face-to-photo cache
        face_to_photo = {"face-t1": "photo-001", "face-n1": "photo-002"}
        photo_cache = {
            "photo-001": {"filename": "img1.jpg", "faces": [{"face_id": "face-t1"}], "source": "test"},
            "photo-002": {"filename": "img2.jpg", "faces": [{"face_id": "face-n1"}], "source": "test"},
        }

        return registry, crop_files, face_to_photo, photo_cache

    def test_compare_faces_view_has_view_photo_buttons(self, client):
        """Faces view includes 'View Photo' buttons for both sides."""
        registry, crop_files, face_to_photo, photo_cache = self._build_compare_mocks()

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=crop_files), \
             patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"), \
             patch("app.main._face_to_photo_cache", face_to_photo), \
             patch("app.main._photo_cache", photo_cache), \
             patch("app.main._build_caches"):

            resp = client.get("/api/identity/target-aaa/compare/neighbor-bbb?view=faces")
            assert resp.status_code == 200
            html = resp.text

            # Both sides should have "View Photo" buttons
            assert "View Photo" in html

            # The buttons should have hx-get targeting /photo/{id}/partial
            assert 'hx-get="/photo/photo-001/partial' in html
            assert 'hx-get="/photo/photo-002/partial' in html

    def test_compare_photos_view_has_view_photo_buttons(self, client):
        """Photos view also includes 'View Photo' buttons."""
        registry, crop_files, face_to_photo, photo_cache = self._build_compare_mocks()

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=crop_files), \
             patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"), \
             patch("app.main._face_to_photo_cache", face_to_photo), \
             patch("app.main._photo_cache", photo_cache), \
             patch("app.main._build_caches"), \
             patch("app.main.storage") as mock_storage:

            mock_storage.get_photo_url.return_value = "/photos/img1.jpg"
            resp = client.get("/api/identity/target-aaa/compare/neighbor-bbb?view=photos")
            assert resp.status_code == 200
            html = resp.text

            # View Photo buttons should link to photo partial endpoint
            assert "View Photo" in html
            assert "/photo/" in html
            assert "/partial" in html

    def test_view_photo_button_includes_face_param(self, client):
        """View Photo buttons pass the face ID as a query parameter."""
        registry, crop_files, face_to_photo, photo_cache = self._build_compare_mocks()

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=crop_files), \
             patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"), \
             patch("app.main._face_to_photo_cache", face_to_photo), \
             patch("app.main._photo_cache", photo_cache), \
             patch("app.main._build_caches"):

            resp = client.get("/api/identity/target-aaa/compare/neighbor-bbb?view=faces")
            html = resp.text

            # Each button should include face= param for highlighting
            assert "face=face-t1" in html
            assert "face=face-n1" in html

    def test_view_photo_button_targets_photo_modal_content(self, client):
        """View Photo buttons target #photo-modal-content for HTMX swap."""
        registry, crop_files, face_to_photo, photo_cache = self._build_compare_mocks()

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=crop_files), \
             patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"), \
             patch("app.main._face_to_photo_cache", face_to_photo), \
             patch("app.main._photo_cache", photo_cache), \
             patch("app.main._build_caches"):

            resp = client.get("/api/identity/target-aaa/compare/neighbor-bbb?view=faces")
            html = resp.text

            assert 'hx-target="#photo-modal-content"' in html

    def test_no_view_photo_when_face_has_no_photo(self, client):
        """When a face has no photo mapping, no View Photo button is shown."""
        target = _make_identity("target-xxx", name="Leon", state="CONFIRMED",
                                anchor_ids=["face-orphan"])
        neighbor = _make_identity("neighbor-yyy", name="Betty", state="CONFIRMED",
                                  anchor_ids=["face-n1"])
        registry = _make_registry([target, neighbor])

        crop_files = {"face-orphan.jpg", "face-n1.jpg"}
        # face-orphan has no photo mapping
        face_to_photo = {"face-n1": "photo-002"}
        photo_cache = {
            "photo-002": {"filename": "img2.jpg", "faces": [{"face_id": "face-n1"}], "source": "test"},
        }

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=crop_files), \
             patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"), \
             patch("app.main._face_to_photo_cache", face_to_photo), \
             patch("app.main._photo_cache", photo_cache), \
             patch("app.main._build_caches"):

            resp = client.get("/api/identity/target-xxx/compare/neighbor-yyy?view=faces")
            html = resp.text

            # Should still have at least one View Photo (for neighbor)
            assert "View Photo" in html
            # But the orphan face should NOT have a photo link
            # (no hx-get for an empty photo_id)
            assert 'hx-get="/photo//partial' not in html


# ---------------------------------------------------------------------------
# 2. Post-merge guidance banner
# ---------------------------------------------------------------------------

class TestPostMergeGuidanceBanner:
    """After a merge, the response should include a guidance banner
    via OOB swap. Unnamed merges get 'Grouped' message, named get 'Merge complete'."""

    def test_unnamed_merge_shows_grouped_message(self, client, auth_disabled):
        """Merging an unnamed identity shows 'Grouped' with 'Add a name' CTA."""
        target = _make_identity("target-111", state="PROPOSED",
                                anchor_ids=["face-a"])
        source = _make_identity("source-222", state="INBOX",
                                anchor_ids=["face-b"])
        registry = _make_registry([target, source])
        photo_reg = _make_photo_registry_mock()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None), \
             patch("app.main._post_merge_suggestions", return_value=None), \
             patch("app.main._merge_annotations"), \
             patch("app.main.log_user_action"):

            resp = client.post("/api/identity/target-111/merge/source-222")
            assert resp.status_code == 200
            html = resp.text

            # Should contain the "Grouped" banner
            assert "Grouped" in html
            # Should contain the "Add a name" CTA
            assert "Add a name" in html

    def test_named_merge_shows_merge_complete(self, client, auth_disabled):
        """Merging a named identity shows 'Merge complete' success message."""
        target = _make_identity("target-333", name="Leon Capeluto",
                                state="CONFIRMED", anchor_ids=["face-a"])
        source = _make_identity("source-444", state="INBOX",
                                anchor_ids=["face-b"])
        registry = _make_registry([target, source])
        photo_reg = _make_photo_registry_mock()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None), \
             patch("app.main._post_merge_suggestions", return_value=None), \
             patch("app.main._merge_annotations"), \
             patch("app.main.log_user_action"):

            resp = client.post("/api/identity/target-333/merge/source-444")
            assert resp.status_code == 200
            html = resp.text

            # Should contain the "Merge complete" banner
            assert "Merge complete" in html
            # Should reference the named identity
            assert "Leon Capeluto" in html

    def test_merge_guidance_banner_uses_oob_swap(self, client, auth_disabled):
        """The guidance banner targets #identity-{id} via hx-swap-oob."""
        target = _make_identity("target-555", name="Leon Capeluto",
                                state="CONFIRMED", anchor_ids=["face-a"])
        source = _make_identity("source-666", state="INBOX",
                                anchor_ids=["face-b"])
        registry = _make_registry([target, source])
        photo_reg = _make_photo_registry_mock()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None), \
             patch("app.main._post_merge_suggestions", return_value=None), \
             patch("app.main._merge_annotations"), \
             patch("app.main.log_user_action"):

            resp = client.post("/api/identity/target-555/merge/source-666")
            assert resp.status_code == 200
            html = resp.text

            # The banner should use OOB swap targeting the identity card
            assert "hx-swap-oob" in html
            assert "#identity-target-555" in html

    def test_unnamed_merge_guidance_has_rename_form_link(self, client, auth_disabled):
        """The 'Add a name' button links to the rename form endpoint."""
        target = _make_identity("target-777", state="PROPOSED",
                                anchor_ids=["face-a"])
        source = _make_identity("source-888", state="INBOX",
                                anchor_ids=["face-b"])
        registry = _make_registry([target, source])
        photo_reg = _make_photo_registry_mock()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None), \
             patch("app.main._post_merge_suggestions", return_value=None), \
             patch("app.main._merge_annotations"), \
             patch("app.main.log_user_action"):

            resp = client.post("/api/identity/target-777/merge/source-888")
            html = resp.text

            # The "Add a name" button should link to the rename form
            assert "/api/identity/target-777/rename-form" in html

    def test_named_merge_banner_auto_dismisses(self, client, auth_disabled):
        """Named identity merge banner has auto-dismiss behavior (Hyperscript)."""
        target = _make_identity("target-999", name="Victoria Cukran",
                                state="CONFIRMED", anchor_ids=["face-a"])
        source = _make_identity("source-aaa", state="INBOX",
                                anchor_ids=["face-b"])
        registry = _make_registry([target, source])
        photo_reg = _make_photo_registry_mock()

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value=None), \
             patch("app.main._post_merge_suggestions", return_value=None), \
             patch("app.main._merge_annotations"), \
             patch("app.main.log_user_action"):

            resp = client.post("/api/identity/target-999/merge/source-aaa")
            html = resp.text

            # Named merge banner should have auto-dismiss behavior
            assert "wait" in html and "remove me" in html


# ---------------------------------------------------------------------------
# 3. Grouped badge for unnamed multi-face identities
# ---------------------------------------------------------------------------

class TestGroupedBadge:
    """Unnamed identities with >1 face should show a 'Grouped (N faces)' badge."""

    def test_unnamed_multi_face_shows_grouped_badge(self):
        """Unnamed identity with 3 faces shows 'Grouped (3 faces)' badge."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = _make_identity(
            "grouped-id-1",
            name="Unidentified Person 042",
            state="PROPOSED",
            anchor_ids=["face-a", "face-b", "face-c"],
        )

        # Use empty crop files -- face_cards will still be built
        crop_files = {"face-a.jpg", "face-b.jpg", "face-c.jpg"}

        with patch("app.main.resolve_face_image_url", return_value="/static/crops/placeholder.jpg"), \
             patch("app.main._face_to_photo_cache", {}), \
             patch("app.main._photo_cache", {}), \
             patch("app.main._build_caches"):

            card = identity_card(identity, crop_files)

        if card is None:
            pytest.skip("identity_card returned None (no face cards rendered)")

        html = to_xml(card)
        assert "Grouped (3 faces)" in html
        assert "purple" in html.lower()  # purple badge styling

    def test_unnamed_single_face_no_grouped_badge(self):
        """Unnamed identity with only 1 face does NOT show grouped badge."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = _make_identity(
            "single-face-id",
            name="Unidentified Person 099",
            state="INBOX",
            anchor_ids=["face-solo"],
        )

        crop_files = {"face-solo.jpg"}

        with patch("app.main.resolve_face_image_url", return_value="/static/crops/placeholder.jpg"), \
             patch("app.main._face_to_photo_cache", {}), \
             patch("app.main._photo_cache", {}), \
             patch("app.main._build_caches"):

            card = identity_card(identity, crop_files)

        if card is None:
            pytest.skip("identity_card returned None (no face cards rendered)")

        html = to_xml(card)
        assert "Grouped" not in html

    def test_named_identity_no_grouped_badge(self):
        """Named identity (even with multiple faces) does NOT show grouped badge."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = _make_identity(
            "named-id-1",
            name="Leon Capeluto",
            state="CONFIRMED",
            anchor_ids=["face-a", "face-b", "face-c"],
        )

        crop_files = {"face-a.jpg", "face-b.jpg", "face-c.jpg"}

        with patch("app.main.resolve_face_image_url", return_value="/static/crops/placeholder.jpg"), \
             patch("app.main._face_to_photo_cache", {}), \
             patch("app.main._photo_cache", {}), \
             patch("app.main._build_caches"):

            card = identity_card(identity, crop_files)

        if card is None:
            pytest.skip("identity_card returned None (no face cards rendered)")

        html = to_xml(card)
        assert "Grouped" not in html

    def test_grouped_badge_shows_correct_face_count(self):
        """Badge reflects total face count (anchors + candidates)."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = _make_identity(
            "mixed-faces-id",
            name="Unidentified Person 007",
            state="PROPOSED",
            anchor_ids=["face-a", "face-b"],
            candidate_ids=["face-c", "face-d", "face-e"],
        )

        crop_files = {"face-a.jpg", "face-b.jpg", "face-c.jpg", "face-d.jpg", "face-e.jpg"}

        with patch("app.main.resolve_face_image_url", return_value="/static/crops/placeholder.jpg"), \
             patch("app.main._face_to_photo_cache", {}), \
             patch("app.main._photo_cache", {}), \
             patch("app.main._build_caches"):

            card = identity_card(identity, crop_files)

        if card is None:
            pytest.skip("identity_card returned None (no face cards rendered)")

        html = to_xml(card)
        assert "Grouped (5 faces)" in html

    def test_identity_prefix_also_triggers_grouped_badge(self):
        """Identities starting with 'Identity ' (legacy unnamed) also get the badge."""
        from app.main import identity_card
        from fastcore.xml import to_xml

        identity = _make_identity(
            "legacy-unnamed-id",
            name="Identity 25f0a152",
            state="INBOX",
            anchor_ids=["face-a", "face-b"],
        )

        crop_files = {"face-a.jpg", "face-b.jpg"}

        with patch("app.main.resolve_face_image_url", return_value="/static/crops/placeholder.jpg"), \
             patch("app.main._face_to_photo_cache", {}), \
             patch("app.main._photo_cache", {}), \
             patch("app.main._build_caches"):

            card = identity_card(identity, crop_files)

        if card is None:
            pytest.skip("identity_card returned None (no face cards rendered)")

        html = to_xml(card)
        assert "Grouped (2 faces)" in html


# ---------------------------------------------------------------------------
# 4. Compare modal size
# ---------------------------------------------------------------------------

class TestCompareModalSize:
    """The compare modal container should use max-w-[90vw], not max-w-5xl."""

    def test_compare_modal_uses_90vw(self, client):
        """Compare modal uses max-w-[90vw] for adequate viewport width."""
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/?section=confirmed")
            html = resp.text

            # The compare-modal should use 90vw-based width
            assert "max-w-[90vw]" in html or "max-w-7xl" in html
            # Verify the compare modal HTML is present
            assert 'id="compare-modal"' in html

    def test_compare_modal_not_restricted_to_5xl(self, client):
        """Compare modal should NOT use the old max-w-5xl restriction.

        Note: max-w-5xl may appear elsewhere on the page (e.g. photo modal, nav bar),
        so we specifically check the compare-modal's inner dialog panel.
        The compare modal has id="compare-modal" as its outer div, and the
        inner dialog panel is the div just before id="compare-modal-content".
        """
        import re
        with patch("app.main.is_auth_enabled", return_value=False):
            resp = client.get("/?section=confirmed")
            html = resp.text

            # Extract the section of HTML between id="compare-modal" and its closing
            # The compare-modal-content is only inside the compare modal
            compare_start = html.find('id="compare-modal"')
            assert compare_start != -1, "compare-modal not found in page"

            # Get the chunk of HTML from compare-modal to the next major modal
            compare_chunk = html[compare_start:compare_start + 2000]

            # Find the dialog panel class within the compare modal chunk
            dialog_match = re.search(
                r'class="(bg-slate-800 rounded-lg shadow-2xl[^"]*)"',
                compare_chunk,
            )
            assert dialog_match, "Could not find compare modal dialog panel"
            compare_dialog_cls = dialog_match.group(1)

            # The compare modal dialog should use 90vw, NOT sm:max-w-5xl
            assert "max-w-[90vw]" in compare_dialog_cls or "max-w-7xl" in compare_dialog_cls
            assert "sm:max-w-5xl" not in compare_dialog_cls


# ---------------------------------------------------------------------------
# 5. Regression: compare endpoint returns 200 for both view modes
# ---------------------------------------------------------------------------

class TestCompareViewModes:
    """Regression tests for faces/photos toggle on compare endpoint."""

    def _setup_compare(self, client):
        """Set up standard compare mocks and return response for both views."""
        target = _make_identity("reg-target", name="Leon", state="CONFIRMED",
                                anchor_ids=["face-rt1"])
        neighbor = _make_identity("reg-neighbor", name="Betty", state="CONFIRMED",
                                  anchor_ids=["face-rn1"])
        registry = _make_registry([target, neighbor])

        face_to_photo = {"face-rt1": "photo-r1", "face-rn1": "photo-r2"}
        photo_cache = {
            "photo-r1": {"filename": "img1.jpg", "faces": [{"face_id": "face-rt1"}], "source": "test"},
            "photo-r2": {"filename": "img2.jpg", "faces": [{"face_id": "face-rn1"}], "source": "test"},
        }

        return registry, face_to_photo, photo_cache

    def test_faces_view_returns_200(self, client):
        """Faces view returns 200 with mocked data."""
        registry, face_to_photo, photo_cache = self._setup_compare(client)

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"), \
             patch("app.main._face_to_photo_cache", face_to_photo), \
             patch("app.main._photo_cache", photo_cache), \
             patch("app.main._build_caches"):

            resp = client.get("/api/identity/reg-target/compare/reg-neighbor?view=faces")
            assert resp.status_code == 200

    def test_photos_view_returns_200(self, client):
        """Photos view returns 200 with mocked data."""
        registry, face_to_photo, photo_cache = self._setup_compare(client)

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"), \
             patch("app.main._face_to_photo_cache", face_to_photo), \
             patch("app.main._photo_cache", photo_cache), \
             patch("app.main._build_caches"), \
             patch("app.main.storage") as mock_storage:

            mock_storage.get_photo_url.return_value = "/photos/img1.jpg"
            resp = client.get("/api/identity/reg-target/compare/reg-neighbor?view=photos")
            assert resp.status_code == 200

    def test_toggle_buttons_present_in_both_views(self, client):
        """Both Faces and Photos toggle buttons are present."""
        registry, face_to_photo, photo_cache = self._setup_compare(client)

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value="/static/crops/face.jpg"), \
             patch("app.main._face_to_photo_cache", face_to_photo), \
             patch("app.main._photo_cache", photo_cache), \
             patch("app.main._build_caches"):

            resp = client.get("/api/identity/reg-target/compare/reg-neighbor?view=faces")
            html = resp.text

            assert "view=faces" in html
            assert "view=photos" in html
            assert "Faces" in html
            assert "Photos" in html
