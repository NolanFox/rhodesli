"""Tests for P0 triage fixes: FB-168, FB-150, FB-169."""

import pytest
from unittest.mock import patch, MagicMock
from fasthtml.common import to_xml


class TestFB168TagAssignment:
    """FB-168: Tag search click doesn't assign identity to face.

    Root cause: When get_photo_id_for_face returns None (common for Fox Family
    photos not in embeddings cache), the tag handler returned a bare toast that
    replaced the entire photo viewer — appearing as "nothing happens."
    """

    def test_tag_fallback_uses_photo_registry(self, client, auth_disabled):
        """When face-to-photo cache misses, fall back to photo_registry."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.load_photo_registry") as mock_photo_reg,
            patch("app.main.save_registry"),
            patch("app.main.get_identity_for_face") as mock_get_id,
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.photo_view_content") as mock_pvc,
            patch("app.main._invalidate_discovery_cache"),
        ):
            from fasthtml.common import Div

            source = {"identity_id": "source-id", "name": "Unidentified Person 999"}
            mock_get_id.return_value = source

            registry = MagicMock()
            registry.get_identity.return_value = {"identity_id": "target-id", "name": "Esther Burd Fox"}
            registry.merge_identities.return_value = {
                "success": True,
                "faces_merged": 1,
                "source_id": "source-id",
                "target_id": "target-id",
                "direction_swapped": False,
            }
            mock_reg.return_value = registry

            # Photo registry has the face-to-photo mapping
            photo_reg = MagicMock()
            photo_reg.get_photo_for_face.return_value = "inbox_photo_123"
            mock_photo_reg.return_value = photo_reg

            mock_pvc.return_value = (Div("Updated photo", id="test-photo"),)

            resp = client.post(
                "/api/face/tag?face_id=inbox_test_face&target_id=target-id",
                headers={"HX-Request": "true"},
            )

            assert resp.status_code == 200
            # Should re-render photo view (not just a toast)
            assert "Updated photo" in resp.text
            assert "Tagged as Esther Burd Fox" in resp.text
            # photo_view_content should have been called
            mock_pvc.assert_called_once()

    def test_tag_no_photo_retargets_toast(self, client, auth_disabled):
        """When neither cache nor registry has the photo, toast goes to toast-container."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.load_photo_registry") as mock_photo_reg,
            patch("app.main.save_registry"),
            patch("app.main.get_identity_for_face") as mock_get_id,
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main._invalidate_discovery_cache"),
        ):
            source = {"identity_id": "source-id", "name": "Unidentified Person 999"}
            mock_get_id.return_value = source

            registry = MagicMock()
            registry.get_identity.return_value = {"identity_id": "target-id", "name": "Esther"}
            registry.merge_identities.return_value = {
                "success": True,
                "faces_merged": 1,
                "source_id": "source-id",
                "target_id": "target-id",
                "direction_swapped": False,
            }
            mock_reg.return_value = registry

            # Photo registry also can't find it
            photo_reg = MagicMock()
            photo_reg.get_photo_for_face.return_value = None
            mock_photo_reg.return_value = photo_reg

            resp = client.post(
                "/api/face/tag?face_id=unknown_face&target_id=target-id",
                headers={"HX-Request": "true"},
            )

            assert resp.status_code == 200
            assert "Tagged as Esther" in resp.text
            # Must retarget to toast container (not replace photo viewer)
            assert resp.headers.get("HX-Retarget") == "#toast-container"
            assert resp.headers.get("HX-Reswap") == "beforeend"

    def test_tag_community_prefix_works(self, client, auth_disabled):
        """Tag works through /c/fox-family/ community prefix."""
        fox_community = {
            "id": "fox-uuid",
            "slug": "fox-family",
            "name": "Fox Family Archive",
        }
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.load_photo_registry") as mock_photo_reg,
            patch("app.main.save_registry"),
            patch("app.main.get_identity_for_face") as mock_get_id,
            patch("app.main.get_photo_id_for_face", return_value="test-photo"),
            patch("app.main.photo_view_content") as mock_pvc,
            patch("app.main._invalidate_discovery_cache"),
            patch("app.supabase_data.get_community_by_slug", return_value=fox_community),
        ):
            from fasthtml.common import Div

            source = {"identity_id": "source-id", "name": "Unidentified Person 999"}
            mock_get_id.return_value = source

            registry = MagicMock()
            registry.get_identity.return_value = {"identity_id": "target-id", "name": "Albert Fox"}
            registry.merge_identities.return_value = {
                "success": True,
                "faces_merged": 1,
                "source_id": "source-id",
                "target_id": "target-id",
                "direction_swapped": False,
            }
            mock_reg.return_value = registry
            mock_photo_reg.return_value = MagicMock()
            mock_pvc.return_value = (Div("Photo updated", id="photo-content"),)

            resp = client.post(
                "/c/fox-family/api/face/tag?face_id=inbox_123&target_id=target-id",
                headers={"HX-Request": "true"},
            )

            assert resp.status_code == 200
            assert "Photo updated" in resp.text
            assert "Tagged as Albert Fox" in resp.text


class TestFB150SpeedLoopNavigation:
    """FB-150: Speed Loop suggestion thumbnails not clickable.

    Suggestion thumbnails and names must link to the person page so admins
    can inspect the match before deciding to merge.
    """

    def test_suggestion_thumbnails_are_clickable(self):
        """Suggestion thumbnail links to person page."""
        from app.cluster_review_routes import _speed_run_enrichment_panel

        identity_data = {
            "name": "Unidentified Person 100",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a"],
            "candidate_ids": [],
            "negative_ids": [],
        }

        with (
            patch("app.cluster_review_routes._get_crop_url_for_face", return_value="/crop/test.jpg"),
            patch("app.cluster_review_routes._best_face_id", return_value="face-a"),
            patch("app.cluster_review_routes._identity_face_ids", return_value=["face-a"]),
            patch("app.cluster_review_routes._get_confirmed_identity_suggestions") as mock_sug,
            patch("app.cluster_review_routes._main_mod") as mock_main,
        ):
            mock_main.community_url_prefix.return_value = "/c/fox-family"
            mock_main._cross_community_badge.return_value = None

            mock_sug.return_value = [
                {
                    "identity_id": "sug-id-1",
                    "name": "Roland Fox",
                    "face_count": 8,
                    "best_face_id": "sug-face-1",
                },
            ]

            result = _speed_run_enrichment_panel("test-id", identity_data, 0, "fox-family")
            html = to_xml(result)

            # Suggestion thumbnail should be wrapped in a link to person page
            assert "/c/fox-family/person/sug-id-1" in html
            assert 'target="_blank"' in html
            assert "Roland Fox" in html

    def test_suggestion_name_is_clickable(self):
        """Suggestion name also links to person page."""
        from app.cluster_review_routes import _speed_run_enrichment_panel

        identity_data = {
            "name": "Unidentified Person 200",
            "state": "CONFIRMED",
            "anchor_ids": ["face-b"],
            "candidate_ids": [],
            "negative_ids": [],
        }

        with (
            patch("app.cluster_review_routes._get_crop_url_for_face", return_value="/crop/test.jpg"),
            patch("app.cluster_review_routes._best_face_id", return_value="face-b"),
            patch("app.cluster_review_routes._identity_face_ids", return_value=["face-b"]),
            patch("app.cluster_review_routes._get_confirmed_identity_suggestions") as mock_sug,
            patch("app.cluster_review_routes._main_mod") as mock_main,
        ):
            mock_main.community_url_prefix.return_value = ""
            mock_main._cross_community_badge.return_value = None

            mock_sug.return_value = [
                {
                    "identity_id": "sug-id-2",
                    "name": "Charles Fox",
                    "face_count": 15,
                    "best_face_id": "sug-face-2",
                },
            ]

            result = _speed_run_enrichment_panel("test-id", identity_data, 0, "rhodes")
            html = to_xml(result)

            # Name should link to person page
            assert "/person/sug-id-2" in html
            assert "Charles Fox" in html
            # Merge button still exists
            assert "Merge" in html


class TestFB169FaceLabelDisplay:
    """FB-169: Esther Burd Fox face label shows 'Unidentified'.

    Root cause: FB-168 — the tag merge never completed because the toast
    replaced the photo viewer. With FB-168 fixed, this resolves itself.
    This test verifies the face label rendering logic is correct.
    """

    def test_confirmed_face_shows_name_not_unidentified(self):
        """A face in a CONFIRMED identity shows the person's name."""
        from app.main import photo_view_content, to_xml

        with (
            patch("app.main.get_photo_metadata") as mock_meta,
            patch("app.main.get_photo_dimensions", return_value=(800, 600)),
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face") as mock_get_id,
        ):
            mock_meta.return_value = {
                "filename": "test.jpg",
                "faces": [{"face_id": "face-esther", "bbox": [10, 10, 100, 100]}],
            }
            mock_get_id.return_value = {
                "identity_id": "esther-id",
                "name": "Esther Burd Fox",
                "state": "CONFIRMED",
                "anchor_ids": ["face-esther"],
                "candidate_ids": [],
                "negative_ids": [],
            }
            mock_reg.return_value = MagicMock()

            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

            # Should show real name, not "Unidentified"
            assert "Esther Burd Fox" in html
            # Should have confirmed styling (emerald border)
            assert "border-emerald-500" in html

    def test_unidentified_face_shows_unidentified_label(self):
        """An INBOX face with auto-generated name shows 'Unidentified'."""
        from app.main import photo_view_content, to_xml

        with (
            patch("app.main.get_photo_metadata") as mock_meta,
            patch("app.main.get_photo_dimensions", return_value=(800, 600)),
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face") as mock_get_id,
        ):
            mock_meta.return_value = {
                "filename": "test.jpg",
                "faces": [{"face_id": "face-unknown", "bbox": [10, 10, 100, 100]}],
            }
            mock_get_id.return_value = {
                "identity_id": "unknown-id",
                "name": "Unidentified Person 4066",
                "state": "INBOX",
                "anchor_ids": ["face-unknown"],
                "candidate_ids": [],
                "negative_ids": [],
            }
            mock_reg.return_value = MagicMock()

            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

            # Should have dashed border (unidentified styling)
            assert "border-dashed" in html
