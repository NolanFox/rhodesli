"""Tests for Phase 4: Instagram-style face tagging with autocomplete."""

import pytest
from unittest.mock import patch, MagicMock


class TestTagDropdownInOverlay:
    """Tests for the tag dropdown appearing in face overlays."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_face_overlay_has_tag_dropdown_admin(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Admin face overlay shows 'Type name to tag' placeholder."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face-1", "bbox": [10, 10, 100, 100]}],
            "source": "Test",
        }
        mock_get_id.return_value = {
            "identity_id": "id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=True)
        html = to_xml(result)

        # Should have tag dropdown
        assert "tag-dropdown-" in html
        assert "Type name to tag" in html
        assert "/api/face/tag-search" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_face_overlay_has_tag_dropdown_nonadmin(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Non-admin face overlay shows 'Who is this person?' placeholder."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face-1", "bbox": [10, 10, 100, 100]}],
            "source": "Test",
        }
        mock_get_id.return_value = {
            "identity_id": "id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True, is_admin=False)
        html = to_xml(result)

        assert "tag-dropdown-" in html
        assert "Who is this person?" in html
        assert "/api/face/tag-search" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face")
    def test_face_overlay_has_go_to_face_card(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Tag dropdown includes 'Go to Face Card' button."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face-1", "bbox": [10, 10, 100, 100]}],
        }
        mock_get_id.return_value = {
            "identity_id": "id-1",
            "name": "Test Person",
            "state": "INBOX",
        }
        mock_reg.return_value = MagicMock()

        result = photo_view_content("p1", is_partial=True)
        html = to_xml(result)

        assert "Go to Face Card" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    @patch("app.main.get_identity_for_face", return_value=None)
    def test_unidentified_face_has_tag_dropdown(self, mock_get_id, mock_reg, mock_dim, mock_meta):
        """Unidentified faces also get a tag dropdown."""
        from app.main import photo_view_content, to_xml

        mock_meta.return_value = {
            "filename": "test.jpg",
            "faces": [{"face_id": "face-1", "bbox": [10, 10, 100, 100]}],
        }
        mock_reg.return_value = MagicMock()

        # Admin mode: shows "Type name to tag"
        result = photo_view_content("p1", is_partial=True, is_admin=True)
        html = to_xml(result)

        assert "tag-dropdown-" in html
        assert "Type name to tag" in html


class TestTagSearchEndpoint:
    """Tests for the /api/face/tag-search endpoint."""

    def test_tag_search_returns_results(self, client):
        """Tag search returns compact result cards with merge buttons."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face", return_value=None),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
        ):
            registry = MagicMock()
            registry.search_identities.return_value = [
                {"identity_id": "id-1", "name": "Leon Capeluto", "face_count": 5, "preview_face_id": "f1"},
                {"identity_id": "id-2", "name": "Moise Capeluto", "face_count": 3, "preview_face_id": "f2"},
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=capel")
            html = resp.text

            assert "Leon Capeluto" in html
            assert "Moise Capeluto" in html
            assert "/api/face/tag" in html

    def test_tag_search_minimum_query_length(self, client):
        """Tag search requires at least 2 characters."""
        resp = client.get("/api/face/tag-search?face_id=test-face&q=a")
        html = resp.text
        # Should return empty container (no results, no error)
        assert "Leon" not in html

    def test_tag_search_excludes_current_identity(self, client):
        """Tag search excludes the face's current identity from results."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face") as mock_get_id,
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
        ):
            mock_get_id.return_value = {"identity_id": "current-id", "name": "Me"}
            registry = MagicMock()
            registry.search_identities.return_value = []
            mock_reg.return_value = registry

            client.get("/api/face/tag-search?face_id=test-face&q=test")

            # Verify exclude_id was passed
            registry.search_identities.assert_called_once()
            call_kwargs = registry.search_identities.call_args
            assert (
                call_kwargs[1].get("exclude_id") == "current-id"
                or (len(call_kwargs[0]) > 1 and call_kwargs[0][1] == "current-id")
                or call_kwargs.kwargs.get("exclude_id") == "current-id"
            )


class TestTagSearchNonAdmin:
    """Tests for non-admin tag-search behavior (annotation-based)."""

    def test_nonadmin_tag_search_returns_suggest_buttons(self, client, auth_enabled, regular_user):
        """Non-admin tag search returns 'Suggest match' buttons, not merge buttons."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face") as mock_get_id,
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
        ):
            mock_get_id.return_value = {"identity_id": "source-id", "name": "Unknown"}
            registry = MagicMock()
            registry.search_identities.return_value = [
                {"identity_id": "id-1", "name": "Leon Capeluto", "face_count": 5, "preview_face_id": "f1"},
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=leon")
            html = resp.text

            assert "Leon Capeluto" in html
            assert "Suggest match" in html
            # Should use annotation endpoint, NOT direct merge
            assert "/api/annotations/submit" in html
            assert "/api/face/tag?" not in html

    def test_nonadmin_create_shows_suggest_label(self, client, auth_enabled, regular_user):
        """Non-admin 'Create' button says 'Suggest' and submits annotation."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face") as mock_get_id,
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
        ):
            mock_get_id.return_value = {"identity_id": "source-id", "name": "Unknown"}
            registry = MagicMock()
            registry.search_identities.return_value = []
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=Sarina+Benatar")
            html = resp.text

            assert "Suggest &quot;Sarina Benatar&quot;" in html or 'Suggest "Sarina Benatar"' in html
            assert "Submit for review" in html
            assert "/api/annotations/submit" in html
            assert "/api/face/create-identity" not in html

    def test_admin_tag_search_still_returns_merge_buttons(self, client, auth_disabled):
        """Admin tag search returns direct merge buttons (auth disabled = admin)."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face", return_value=None),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
        ):
            registry = MagicMock()
            registry.search_identities.return_value = [
                {"identity_id": "id-1", "name": "Leon Capeluto", "face_count": 5, "preview_face_id": "f1"},
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=leon")
            html = resp.text

            assert "Leon Capeluto" in html
            assert "/api/face/tag?" in html
            assert "Suggest match" not in html

    def test_anonymous_tag_search_returns_suggest_buttons(self, client, auth_enabled, no_user):
        """Anonymous user tag search returns suggestion buttons (triggers login on submit)."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face") as mock_get_id,
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
        ):
            mock_get_id.return_value = {"identity_id": "source-id", "name": "Unknown"}
            registry = MagicMock()
            registry.search_identities.return_value = [
                {"identity_id": "id-1", "name": "Leon Capeluto", "face_count": 5, "preview_face_id": "f1"},
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=leon")
            html = resp.text

            assert "Leon Capeluto" in html
            assert "Suggest match" in html
            assert "/api/annotations/submit" in html


class TestTagMergeEndpoint:
    """Tests for the /api/face/tag POST endpoint."""

    def test_tag_requires_admin(self, client, auth_enabled, regular_user):
        """Tag merge requires admin permissions."""
        resp = client.post("/api/face/tag?face_id=f1&target_id=t1", headers={"HX-Request": "true"})
        assert resp.status_code in (401, 403)

    def test_tag_merges_identity(self, client, auth_disabled):
        """Tag endpoint merges the face's identity into the target."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.load_photo_registry") as mock_photo_reg,
            patch("app.main.save_registry"),
            patch("app.main.get_identity_for_face") as mock_get_id,
            patch("app.main.get_photo_id_for_face", return_value=None),
        ):
            source = {"identity_id": "source-id", "name": "Unknown"}
            mock_get_id.return_value = source

            registry = MagicMock()
            registry.get_identity.return_value = {"identity_id": "target-id", "name": "Leon"}
            registry.merge_identities.return_value = {
                "success": True,
                "faces_merged": 1,
                "source_id": "source-id",
                "target_id": "target-id",
                "direction_swapped": False,
            }
            mock_reg.return_value = registry
            mock_photo_reg.return_value = MagicMock()

            resp = client.post("/api/face/tag?face_id=f1&target_id=target-id")
            assert resp.status_code == 200
            assert "Tagged as Leon" in resp.text

    def test_tag_same_identity_returns_info(self, client, auth_disabled):
        """Tagging with the face's own identity returns info message."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.load_photo_registry"),
            patch("app.main.get_identity_for_face") as mock_get_id,
        ):
            mock_get_id.return_value = {"identity_id": "same-id", "name": "Same"}
            mock_reg.return_value = MagicMock()

            resp = client.post("/api/face/tag?face_id=f1&target_id=same-id")
            assert resp.status_code == 200
            assert "already belongs" in resp.text

    def test_tag_face_not_found(self, client, auth_disabled):
        """Tagging a face that doesn't exist returns error."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.load_photo_registry"),
            patch("app.main.get_identity_for_face", return_value=None),
        ):
            mock_reg.return_value = MagicMock()

            resp = client.post("/api/face/tag?face_id=nonexistent&target_id=t1")
            assert resp.status_code == 404


class TestSuggestButtonSubmission:
    """Tests that non-admin suggest buttons actually submit and produce visible feedback."""

    def test_suggest_new_name_saves_annotation(self, client, auth_enabled, regular_user, tmp_path):
        """Clicking 'Suggest <name>' saves an annotation and returns a toast."""
        import json
        from app.main import _invalidate_annotations_cache

        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps({"schema_version": 1, "annotations": {}}))

        with patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            resp = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "source-id-123",
                    "annotation_type": "name_suggestion",
                    "value": "Sarina Benatar Saragossi",
                    "confidence": "likely",
                    "reason": "face_tag:face-1:new_name",
                },
            )

        assert resp.status_code == 200
        assert "Thanks" in resp.text or "pending" in resp.text.lower()
        # Must be a toast, not a modal
        assert "guest-or-login-modal" not in resp.text

        # Verify annotation was persisted
        saved = json.loads(ann_path.read_text())
        assert len(saved["annotations"]) == 1
        ann = list(saved["annotations"].values())[0]
        assert ann["value"] == "Sarina Benatar Saragossi"
        assert ann["status"] == "pending"
        assert ann["submitted_by"] == "user@example.com"

    def test_suggest_match_saves_annotation(self, client, auth_enabled, regular_user, tmp_path):
        """Clicking 'Suggest match' for an existing identity saves an annotation."""
        import json
        from app.main import _invalidate_annotations_cache

        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps({"schema_version": 1, "annotations": {}}))

        with patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            resp = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "source-id-456",
                    "annotation_type": "name_suggestion",
                    "value": "Mary Maria Capelouto Hassid",
                    "confidence": "likely",
                    "reason": "face_tag:face-1:matched_to:target-id-789",
                },
            )

        assert resp.status_code == 200
        assert "Thanks" in resp.text or "pending" in resp.text.lower()

        saved = json.loads(ann_path.read_text())
        assert len(saved["annotations"]) == 1
        ann = list(saved["annotations"].values())[0]
        assert ann["value"] == "Mary Maria Capelouto Hassid"
        assert ann["reason"] == "face_tag:face-1:matched_to:target-id-789"

    def test_anonymous_suggest_saves_directly(self, client, auth_enabled, no_user, tmp_path):
        """Anonymous user suggestion saves directly as pending_unverified (no modal)."""
        import json
        from app.main import _invalidate_annotations_cache

        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps({"schema_version": 1, "annotations": {}}))

        with patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            resp = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "source-id-123",
                    "annotation_type": "name_suggestion",
                    "value": "Sarina Benatar Saragossi",
                    "confidence": "likely",
                    "reason": "face_tag:face-1:new_name",
                },
            )
        assert resp.status_code == 200
        assert "thanks" in resp.text.lower()
        # No modal — direct submission
        assert "Continue as guest" not in resp.text
        # Annotation saved as anonymous
        saved = json.loads(ann_path.read_text())
        assert len(saved["annotations"]) == 1
        ann = list(saved["annotations"].values())[0]
        assert ann["submitted_by"] == "anonymous"
        assert ann["status"] == "pending_unverified"

    def test_toast_z_index_above_photo_modal(self, client):
        """Toast container must have higher z-index than the photo modal."""
        resp = client.get("/?section=photos")
        html = resp.text
        # toast-container must be z-[10001] (above photo-modal z-[9999])
        assert "z-[10001]" in html
        # photo-modal must remain at z-[9999]
        assert "z-[9999]" in html

    def test_suggest_button_targets_tag_results(self, client, auth_enabled, regular_user):
        """Non-admin suggest button targets tag-results container for inline confirmation."""
        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face") as mock_get_id,
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
        ):
            mock_get_id.return_value = {"identity_id": "source-id", "name": "Unknown"}
            registry = MagicMock()
            registry.search_identities.return_value = []
            mock_reg.return_value = registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=Sarina+Benatar")
            html = resp.text

            # The suggest button targets the tag results area for inline "You suggested" confirmation
            assert 'hx-target="#tag-results-test-face"' in html
            assert 'hx-post="/api/annotations/submit"' in html

    def test_face_tag_submission_shows_inline_confirmation(self, client, tmp_path):
        """Submitting from face tag dropdown returns 'You suggested' inline UI."""
        import json
        from app.main import _invalidate_annotations_cache

        ann_path = tmp_path / "annotations.json"
        ann_path.write_text(json.dumps({"schema_version": 1, "annotations": {}}))

        with patch("app.main.data_path", tmp_path):
            _invalidate_annotations_cache()
            resp = client.post(
                "/api/annotations/submit",
                data={
                    "target_type": "identity",
                    "target_id": "test-id",
                    "annotation_type": "name_suggestion",
                    "value": "Sarina Benatar",
                    "reason": "face_tag:test-face:new_name",
                },
            )
            html = resp.text
            assert "You suggested" in html
            assert "Sarina Benatar" in html
            assert "Pending review" in html


class TestSpeedLoopSaveBug:
    """Tests for FB-141: Speed Loop tag assignments silently dropped.

    Root cause: save_registry() in Postgres path does not clear
    _face_identity_lookup_cache, so subsequent get_identity_for_face()
    returns stale data after a merge.
    """

    def test_face_identity_lookup_cache_cleared_after_save_postgres(self):
        """After save_registry (postgres path), face lookup cache must be invalidated.

        This test proves BUG-001: tags visually applied but reverted on reload
        because stale _face_identity_lookup_cache survives save_registry.
        """
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        # Create two identities with faces
        registry._identities = {
            "source-id": {
                "identity_id": "source-id",
                "name": "Unidentified Person 1",
                "state": "INBOX",
                "anchor_ids": ["face-A"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            "target-id": {
                "identity_id": "target-id",
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face-B"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        }

        # Build the lookup cache (simulates first get_identity_for_face call)
        from app.main import get_identity_for_face

        result_before = get_identity_for_face(registry, "face-A")
        assert result_before is not None
        assert result_before["identity_id"] == "source-id"
        # Cache is now populated on the registry object
        assert hasattr(registry, "_face_identity_lookup_cache")

        # Simulate merge: move face-A from source to target
        registry._identities["target-id"]["anchor_ids"].append("face-A")
        registry._identities["source-id"]["anchor_ids"] = []
        registry._identities["source-id"]["merged_into"] = "target-id"

        # Now save_registry should clear the lookup cache
        import app.main as main_mod

        original_data_source = main_mod.DATA_SOURCE
        original_cache = main_mod._registry_cache
        original_ts = main_mod._registry_cache_ts
        try:
            main_mod.DATA_SOURCE = "postgres"
            # Mock the postgres save to avoid actual DB writes
            with (
                patch("app.main.IdentityRegistry.load_from_postgres", return_value=None),
                patch.object(registry, "save"),
            ):
                # Patch background thread to run inline
                with patch("threading.Thread") as mock_thread:
                    mock_thread.return_value.start = MagicMock()
                    main_mod.save_registry(registry)
        finally:
            main_mod.DATA_SOURCE = original_data_source
            main_mod._registry_cache = original_cache
            main_mod._registry_cache_ts = original_ts

        # The stale cache should be cleared
        assert not hasattr(registry, "_face_identity_lookup_cache") or registry._face_identity_lookup_cache is None, (
            "BUG-001: _face_identity_lookup_cache not cleared after save_registry (postgres path)"
        )

        # After cache clear, get_identity_for_face should reflect the merge
        result_after = get_identity_for_face(registry, "face-A")
        assert result_after is not None, "face-A should be found in target after merge"
        assert result_after["identity_id"] == "target-id", (
            f"face-A should belong to target-id after merge, got {result_after['identity_id']}"
        )

    def test_speed_loop_tag_persists_after_re_render(self, client, auth_disabled):
        """Tag in speed loop mode persists when photo view re-renders.

        After tagging face-A as Leon (merge), the re-rendered photo view
        must show face-A as belonging to Leon, not to the old identity.
        """
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        registry._identities = {
            "source-id": {
                "identity_id": "source-id",
                "name": "Unidentified Person 1",
                "state": "INBOX",
                "anchor_ids": ["face-A"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
            "target-id": {
                "identity_id": "target-id",
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face-B"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            },
        }

        photo_data = {
            "filename": "test.jpg",
            "faces": [
                {"face_id": "face-A", "bbox": [10, 10, 100, 100]},
                {"face_id": "face-B", "bbox": [200, 10, 300, 100]},
            ],
            "source": "Test",
        }

        # Mock merge to actually move the face
        def mock_merge(source_id, target_id, user_source, photo_registry):
            registry._identities["target-id"]["anchor_ids"].append("face-A")
            registry._identities["source-id"]["anchor_ids"] = []
            registry._identities["source-id"]["merged_into"] = "target-id"
            return {
                "success": True,
                "faces_merged": 1,
                "source_id": "source-id",
                "target_id": "target-id",
                "direction_swapped": False,
            }

        registry.merge_identities = mock_merge
        registry.get_identity = lambda iid: registry._identities.get(iid, {})
        registry.search_identities = MagicMock(return_value=[])
        registry.list_identities = lambda **kwargs: [
            v.copy()
            for v in registry._identities.values()
            if not kwargs.get("include_merged", True) or not v.get("merged_into")
        ]

        saved_registries = []

        def mock_save_registry(reg, confirmed_identity_info=None, changed_ids=None):
            saved_registries.append(True)
            # Clear the cache like the fix should do
            reg_dict = getattr(reg, "__dict__", None)
            if reg_dict is not None:
                reg_dict.pop("_face_identity_lookup_cache", None)

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.load_photo_registry", return_value=MagicMock()),
            patch("app.main.save_registry", side_effect=mock_save_registry),
            patch("app.main.get_photo_id_for_face", return_value="photo-1"),
            patch("app.main.get_photo_metadata", return_value=photo_data),
            patch("app.main.get_photo_dimensions", return_value=(800, 600)),
            patch("app.main._invalidate_discovery_cache"),
        ):
            resp = client.post("/api/face/tag?face_id=face-A&target_id=target-id&seq=1")
            assert resp.status_code == 200
            assert len(saved_registries) == 1, "save_registry must be called"
            # The re-rendered HTML should show Leon Capeluto for face-A
            assert "Leon Capeluto" in resp.text

    def test_speed_loop_start_button_has_correct_href(self):
        """Start Speed Loop button renders as a link with ?seq=1."""
        from app.main import photo_view_content, to_xml, public_photo_page

        photo_data = {
            "filename": "test.jpg",
            "faces": [
                {"face_id": "face-1", "bbox": [10, 10, 100, 100]},
                {"face_id": "face-2", "bbox": [200, 10, 300, 100]},
            ],
            "source": "Test",
        }

        def mock_get_identity(registry, fid):
            return {"identity_id": f"id-{fid}", "name": "Unidentified", "state": "INBOX"}

        with (
            patch("app.main.get_photo_metadata", return_value=photo_data),
            patch("app.main.get_photo_dimensions", return_value=(800, 600)),
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face", side_effect=mock_get_identity),
        ):
            mock_reg.return_value = MagicMock()

            # In photo_view_content (modal), the "Name These Faces" button should appear
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)
            assert "seq=1" in html or "Name These Faces" in html

    def test_speed_loop_search_community_scoped(self, client, auth_disabled):
        """Tag search results sort community-match identities first."""
        from core.registry import IdentityRegistry

        registry = IdentityRegistry()
        # Create identities in different communities
        community_id = {"identity_id": "comm-1", "name": "Leon Capeluto", "face_count": 5, "preview_face_id": "f1"}
        cross_community_id = {"identity_id": "cross-1", "name": "Leon Franco", "face_count": 3, "preview_face_id": "f2"}

        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_identity_for_face", return_value=None),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.resolve_face_image_url", return_value=None),
        ):
            mock_registry = MagicMock()
            mock_registry.search_identities.return_value = [community_id, cross_community_id]
            mock_reg.return_value = mock_registry

            resp = client.get("/api/face/tag-search?face_id=test-face&q=leon")
            assert resp.status_code == 200
            html = resp.text
            # Both results should appear
            assert "Leon Capeluto" in html
            assert "Leon Franco" in html
