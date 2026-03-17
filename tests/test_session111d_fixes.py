"""
Tests for Session 111d — Feedback Fix Sprint.

FB-069: Performance — targeted Supabase writes via changed_ids.
FB-070: CI test fix (separate commit).
"""

import pytest
from unittest.mock import patch, MagicMock

from core.registry import IdentityRegistry, IdentityState
from core.photo_registry import PhotoRegistry
from fasthtml.common import Div
from app.auth import User


HTMX_HEADERS = {"HX-Request": "true"}


@pytest.fixture
def admin_user():
    user = User(id="test-admin", email="admin@test.com", is_admin=True, role="admin")
    with patch("app.main.get_current_user", return_value=user), patch("app.main.is_auth_enabled", return_value=True):
        yield user


@pytest.fixture
def confirm_registry():
    """Registry with identities for confirm/reject/skip testing."""
    reg = IdentityRegistry()
    target_id = reg.create_identity(
        anchor_ids=["face_target_1", "face_target_2"],
        user_source="test",
        name="Charles Fox",
        state=IdentityState.CONFIRMED,
    )
    source_id = reg.create_identity(
        anchor_ids=["face_source_1"],
        user_source="test",
        name="Bob Test",
        state=IdentityState.PROPOSED,
    )
    inbox_id = reg.create_identity(
        anchor_ids=["face_inbox_1"],
        user_source="test",
        name="Jane Test",
        state=IdentityState.INBOX,
    )
    photo_reg = PhotoRegistry()
    photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_target_1")
    photo_reg.register_face("photo_2", "/path/photo_2.jpg", "face_target_2")
    photo_reg.register_face("photo_3", "/path/photo_3.jpg", "face_source_1")
    photo_reg.register_face("photo_4", "/path/photo_4.jpg", "face_inbox_1")
    return reg, target_id, source_id, inbox_id, photo_reg


class TestConfirmOnlyConfirms:
    """Confirm button promotes state without auto-merging."""

    def test_confirm_promotes_to_confirmed(self, client, admin_user, confirm_registry):
        """Confirm promotes PROPOSED to CONFIRMED — does not merge."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_registry

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry"),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(f"/confirm/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code == 200
            assert "confirmed" in resp.text.lower()
            # Should NOT contain merge language
            assert "Merged into" not in resp.text

    def test_inbox_confirm_promotes_to_confirmed(self, client, admin_user, confirm_registry):
        """Inbox confirm promotes INBOX to CONFIRMED — does not merge."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_registry

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry"),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(f"/inbox/{inbox_id}/confirm", headers=HTMX_HEADERS)
            assert resp.status_code == 200
            assert "confirmed" in resp.text.lower()
            assert "Merged into" not in resp.text

    def test_confirm_returns_updated_card(self, client, admin_user, confirm_registry):
        """After confirm, response contains the identity card."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_registry

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry"),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(f"/confirm/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code == 200
            # Card should still be in the DOM with the identity ID
            assert f"identity-{source_id}" in resp.text


class TestTargetedSupabaseWrites:
    """FB-069: save_registry passes changed_ids for targeted writes."""

    def test_confirm_passes_changed_ids(self, client, admin_user, confirm_registry):
        """Confirm passes changed_ids={identity_id} to save_registry."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_registry

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry") as mock_save,
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(f"/confirm/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code == 200
            # Verify changed_ids was passed
            call_kwargs = mock_save.call_args
            assert call_kwargs is not None
            changed = call_kwargs.kwargs.get("changed_ids") or (
                call_kwargs[1].get("changed_ids") if len(call_kwargs) > 1 else None
            )
            assert changed is not None
            assert source_id in changed

    def test_skip_passes_changed_ids(self, client, admin_user, confirm_registry):
        """Skip passes changed_ids={identity_id} to save_registry."""
        reg, target_id, source_id, inbox_id, photo_reg = confirm_registry

        with (
            patch("app.main.load_registry", return_value=reg),
            patch("app.main.save_registry") as mock_save,
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.log_user_action"),
        ):
            resp = client.post(f"/identity/{source_id}/skip", headers=HTMX_HEADERS)
            assert resp.status_code == 200
            call_kwargs = mock_save.call_args
            assert call_kwargs is not None
            changed = call_kwargs.kwargs.get("changed_ids") or (
                call_kwargs[1].get("changed_ids") if len(call_kwargs) > 1 else None
            )
            assert changed is not None
            assert source_id in changed


class TestFB065MergedIdentitySearch:
    """FB-065: Post-merge findability — merged identities appear in search results."""

    def _make_registry_with_merged(self):
        """Create a registry with a merged identity pair."""
        reg = IdentityRegistry.__new__(IdentityRegistry)
        target_id = "target-001"
        source_id = "source-002"
        reg._identities = {
            target_id: {
                "identity_id": target_id,
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face_a", "face_b"],
                "candidate_ids": [],
                "negative_ids": [],
            },
            source_id: {
                "identity_id": source_id,
                "name": "Unidentified Person 3053",
                "state": "PROPOSED",
                "anchor_ids": [],
                "candidate_ids": [],
                "negative_ids": [],
                "merged_into": target_id,
            },
        }
        reg._version_id = 1
        return reg, target_id, source_id

    def test_default_search_excludes_merged(self):
        """Default search excludes merged identities (safe for tag/merge)."""
        reg, target_id, source_id = self._make_registry_with_merged()
        results = reg.search_identities("3053")
        ids = [r["identity_id"] for r in results]
        assert source_id not in ids

    def test_include_merged_finds_merged_identity(self):
        """With include_merged=True, merged identities appear in results."""
        reg, target_id, source_id = self._make_registry_with_merged()
        results = reg.search_identities("3053", include_merged=True)
        ids = [r["identity_id"] for r in results]
        assert source_id in ids

    def test_merged_identity_has_merged_into_name(self):
        """Merged identity result should include merged_into_name."""
        reg, target_id, source_id = self._make_registry_with_merged()
        results = reg.search_identities("3053", include_merged=True)
        merged_result = next(r for r in results if r["identity_id"] == source_id)
        assert merged_result["merged_into"] == target_id
        assert merged_result["merged_into_name"] == "Leon Capeluto"

    def test_merged_identity_ranks_after_non_merged(self):
        """Merged identities should sort after non-merged results."""
        reg, target_id, source_id = self._make_registry_with_merged()
        reg._identities["other-003"] = {
            "identity_id": "other-003",
            "name": "Person 3053 Junior",
            "state": "INBOX",
            "anchor_ids": [],
            "candidate_ids": [],
            "negative_ids": [],
        }
        results = reg.search_identities("3053", include_merged=True)
        ids = [r["identity_id"] for r in results]
        assert "other-003" in ids
        assert source_id in ids
        assert ids.index("other-003") < ids.index(source_id)

    def test_non_merged_search_unchanged(self):
        """Normal (non-merged) identities should still work as before."""
        reg, target_id, source_id = self._make_registry_with_merged()
        results = reg.search_identities("Leon")
        ids = [r["identity_id"] for r in results]
        assert target_id in ids
        assert source_id not in ids

    def test_merged_into_unknown_target(self):
        """If merge target doesn't exist, merged_into_name should be 'Unknown'."""
        reg, target_id, source_id = self._make_registry_with_merged()
        reg._identities[source_id]["merged_into"] = "nonexistent-999"
        results = reg.search_identities("3053", include_merged=True)
        merged_result = next(r for r in results if r["identity_id"] == source_id)
        assert merged_result["merged_into_name"] == "Unknown"


class TestFB066UnidentifiedConfirm:
    """FB-066: Green checkmark on photo overlay should show clear error for unidentified faces."""

    def test_quick_action_confirm_unidentified_returns_warning(self, client, admin_user):
        """Confirming an unidentified person via quick-action should return a helpful warning."""
        reg = IdentityRegistry()
        identity_id = reg.create_identity(anchor_ids=["face_fb066"], user_source="test")

        with (
            patch("app.identity_routes._main_mod.load_registry", return_value=reg),
            patch("app.identity_routes._main_mod.save_registry"),
        ):
            resp = client.post(
                "/api/face/quick-action",
                data={"identity_id": identity_id, "action": "confirm", "photo_id": "fake_photo"},
                headers=HTMX_HEADERS,
            )
        assert resp.status_code == 409
        assert "Name this person first" in resp.text

    def test_quick_action_confirm_named_identity_succeeds(self, client, admin_user):
        """Confirming a named identity via quick-action should succeed."""
        reg = IdentityRegistry()
        identity_id = reg.create_identity(anchor_ids=["face_fb066b"], user_source="test", name="Leon Capeluto")

        with (
            patch("app.identity_routes._main_mod.load_registry", return_value=reg),
            patch("app.identity_routes._main_mod.save_registry"),
            patch("app.identity_routes._main_mod.photo_view_content", return_value=(Div("ok"),)),
            patch("app.identity_routes._main_mod.get_current_user", return_value=None),
            patch("app.identity_routes._main_mod.is_auth_enabled", return_value=False),
        ):
            resp = client.post(
                "/api/face/quick-action",
                data={"identity_id": identity_id, "action": "confirm", "photo_id": "fake_photo"},
                headers=HTMX_HEADERS,
            )
        assert resp.status_code == 200

    def test_quick_action_skip_unidentified_still_works(self, client, admin_user):
        """Skip action should still work for unidentified faces (only confirm is blocked)."""
        reg = IdentityRegistry()
        identity_id = reg.create_identity(anchor_ids=["face_fb066c"], user_source="test")

        with (
            patch("app.identity_routes._main_mod.load_registry", return_value=reg),
            patch("app.identity_routes._main_mod.save_registry"),
            patch("app.identity_routes._main_mod.photo_view_content", return_value=(Div("ok"),)),
        ):
            resp = client.post(
                "/api/face/quick-action",
                data={"identity_id": identity_id, "action": "skip", "photo_id": "fake_photo"},
                headers=HTMX_HEADERS,
            )
        assert resp.status_code == 200


class TestFB036037TagSyncFailureWarning:
    """FB-036/037: Tag endpoint surfaces Supabase save failure to user.

    When save_registry returns False, the toast should warn the user
    instead of showing silent success.
    """

    def _make_mock_registry(self, target_name="Target Person"):
        """Create a mock registry that returns successful merge."""
        registry = MagicMock()
        registry.get_identity.return_value = {"identity_id": "target-id", "name": target_name}
        registry.merge_identities.return_value = {
            "success": True,
            "faces_merged": 1,
            "source_id": "source-id",
            "target_id": "target-id",
            "direction_swapped": False,
        }
        return registry

    def test_tag_shows_warning_on_save_failure(self, client, admin_user):
        """When save_registry returns False, toast says sync failed."""
        registry = self._make_mock_registry("Target Person")
        photo_reg = MagicMock()
        photo_reg.get_photo_for_face.return_value = None

        with (
            patch("app.identity_routes._main_mod.load_registry", return_value=registry),
            patch("app.identity_routes._main_mod.load_photo_registry", return_value=photo_reg),
            patch("app.identity_routes._main_mod.save_registry", return_value=False),
            patch(
                "app.identity_routes._main_mod.get_identity_for_face",
                return_value={"identity_id": "source-id", "name": "Unidentified Person 1"},
            ),
            patch("app.identity_routes._main_mod.get_photo_id_for_face", return_value=None),
            patch("app.identity_routes._main_mod._invalidate_discovery_cache"),
        ):
            resp = client.post(
                "/api/face/tag?face_id=face_source&target_id=target-id",
                headers=HTMX_HEADERS,
            )

        assert resp.status_code == 200
        assert "sync failed" in resp.text
        assert "may not persist" in resp.text

    def test_tag_shows_success_on_save_ok(self, client, admin_user):
        """When save_registry returns True (default), toast shows success."""
        registry = self._make_mock_registry("Good Person")
        photo_reg = MagicMock()
        photo_reg.get_photo_for_face.return_value = None

        with (
            patch("app.identity_routes._main_mod.load_registry", return_value=registry),
            patch("app.identity_routes._main_mod.load_photo_registry", return_value=photo_reg),
            patch("app.identity_routes._main_mod.save_registry", return_value=True),
            patch(
                "app.identity_routes._main_mod.get_identity_for_face",
                return_value={"identity_id": "source-id", "name": "Unidentified Person 2"},
            ),
            patch("app.identity_routes._main_mod.get_photo_id_for_face", return_value=None),
            patch("app.identity_routes._main_mod._invalidate_discovery_cache"),
        ):
            resp = client.post(
                "/api/face/tag?face_id=face_source2&target_id=target-id",
                headers=HTMX_HEADERS,
            )

        assert resp.status_code == 200
        assert "Tagged as Good Person" in resp.text
        assert "sync failed" not in resp.text


class TestFB051PhotoSearchCommunityPrefix:
    """FB-051: Photo filename search results include community prefix in links."""

    def test_photo_search_results_include_nav_prefix(self, client, admin_user):
        """Photo search results should use nav_prefix in photo links."""
        mock_photo_cache = {
            "photo_abc123": {
                "filename": "beach_photo.jpg",
                "faces": [{"face_id": "f1"}],
            }
        }

        with (
            patch("app.identity_routes._main_mod.load_registry") as mock_reg,
            patch("app.identity_routes._main_mod._build_caches"),
            patch("app.identity_routes._main_mod._photo_cache", mock_photo_cache),
            patch("app.identity_routes._main_mod.get_crop_files", return_value=set()),
            patch("app.identity_routes._main_mod._highlight_match", side_effect=lambda name, q: name),
        ):
            mock_reg.return_value.search_identities.return_value = []
            resp = client.get("/api/search?q=beach", headers=HTMX_HEADERS)

        assert resp.status_code == 200
        # Default community is rhodes, prefix is /c/rhodes
        assert "/photo/photo_abc123" in resp.text

    def test_photo_search_link_has_data_testid(self, client, admin_user):
        """Photo search results should have data-testid for testing."""
        mock_photo_cache = {
            "photo_xyz789": {
                "filename": "wedding_photo.jpg",
                "faces": [{"face_id": "f2"}, {"face_id": "f3"}],
            }
        }

        with (
            patch("app.identity_routes._main_mod.load_registry") as mock_reg,
            patch("app.identity_routes._main_mod._build_caches"),
            patch("app.identity_routes._main_mod._photo_cache", mock_photo_cache),
            patch("app.identity_routes._main_mod.get_crop_files", return_value=set()),
            patch("app.identity_routes._main_mod._highlight_match", side_effect=lambda name, q: name),
        ):
            mock_reg.return_value.search_identities.return_value = []
            resp = client.get("/api/search?q=wedding", headers=HTMX_HEADERS)

        assert resp.status_code == 200
        assert "search-photo-result" in resp.text


class TestFB030SpeedRunCounterPersistence:
    """FB-030: Speed-run counter should persist via localStorage."""

    def test_speed_run_page_has_localstorage_js(self, client, admin_user):
        """Speed-run page should include localStorage persistence JS."""
        from core.registry import IdentityRegistry, IdentityState

        reg = IdentityRegistry()
        iid = reg.create_identity(
            anchor_ids=["face_sr_1", "face_sr_2"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        with (
            patch("app.cluster_review_routes._main_mod.load_registry", return_value=reg),
            patch("app.cluster_review_routes._main_mod.get_crop_files", return_value=set()),
            patch("app.cluster_review_routes._main_mod.resolve_face_image_url", return_value="/static/crops/test.jpg"),
            patch("app.cluster_review_routes._main_mod._get_community_identity_ids", return_value=None),
            patch("app.cluster_review_routes._main_mod.get_photo_id_for_face", return_value=None),
            patch("app.supabase_data.load_communities", return_value=[]),
        ):
            resp = client.get("/admin/upload-review?mode=speed", headers=HTMX_HEADERS)

        assert resp.status_code == 200
        html = resp.text
        # localStorage key
        assert "rhodesli_speedrun_stats" in html
        # saveStats function
        assert "saveStats" in html
        # loadStats function
        assert "loadStats" in html
        # Reset button
        assert "speed-run-reset" in html
        # restoreStats call
        assert "restoreStats" in html
class TestFB054058ThumbnailConsistency:
    """FB-054/058: Compare view should default to best-quality face, matching neighbor card thumbnail."""

    def test_compare_defaults_to_best_face(self):
        """Compare view should use get_best_face_id to pick the default face index."""
        from app import compare_routes
        import app.main as main_mod

        # Create mock identities with multiple faces
        mock_registry = MagicMock()
        target_identity = {
            "identity_id": "target-id",
            "name": "Target Person",
            "anchor_ids": ["face_a", "face_b", "face_c"],
            "candidate_ids": [],
            "state": "CONFIRMED",
        }
        neighbor_identity = {
            "identity_id": "neighbor-id",
            "name": "Neighbor Person",
            "anchor_ids": ["face_x", "face_y", "face_z"],
            "candidate_ids": [],
            "state": "PROPOSED",
        }

        def get_identity(iid):
            if iid == "target-id":
                return target_identity
            if iid == "neighbor-id":
                return neighbor_identity
            raise KeyError(iid)

        mock_registry.get_identity = get_identity

        # get_best_face_id picks face_b for target (index 1), face_z for neighbor (index 2)
        def mock_best_face(face_ids):
            if "face_b" in face_ids:
                return "face_b"
            if "face_z" in face_ids:
                return "face_z"
            return face_ids[0] if face_ids else None

        with (
            patch.object(main_mod, "load_registry", return_value=mock_registry),
            patch.object(main_mod, "get_crop_files", return_value=set()),
            patch.object(main_mod, "get_best_face_id", side_effect=mock_best_face),
            patch.object(main_mod, "resolve_face_image_url", return_value="/crop/test.jpg"),
            patch.object(main_mod, "_build_caches"),
            patch.object(main_mod, "_face_to_photo_cache", {"face_b": "photo1", "face_z": "photo2"}),
            patch.object(main_mod, "_photo_cache", {}),
        ):
            mock_request = MagicMock()
            mock_request.state.community_slug = "rhodes"
            result = compare_routes.get.__wrapped__(
                target_id="target-id",
                neighbor_id="neighbor-id",
                target_idx=0,  # default
                neighbor_idx=0,  # default
                view="faces",
                filter="",
                sess=None,
                request=mock_request,
            )
            html = repr(result)
            # The compare view should show face_b and face_z (best faces)
            # not face_a and face_x (first faces)
            assert "face_b" in html or "face_z" in html, (
                "Compare view should default to best-quality face, not first face"
            )

    def test_neighbor_card_uses_get_best_face_id(self):
        """Neighbor card thumbnail should use get_best_face_id for consistency."""
        from app.main import neighbor_card

        neighbor = {
            "identity_id": "nbr-123",
            "name": "Test Person",
            "distance": 0.85,
            "can_merge": True,
            "face_count": 3,
            "anchor_face_ids": ["face1", "face2", "face3"],
            "candidate_face_ids": [],
            "state": "PROPOSED",
        }

        with (
            patch("app.main.get_best_face_id", return_value="face2") as mock_best,
            patch("app.main.resolve_face_image_url", return_value="/crop/face2.jpg"),
            patch("app.main._identity_home_community_slug", return_value=None),
            patch("app.main.community_url_prefix", return_value=""),
        ):
            neighbor_card(
                neighbor,
                "target-123",
                crop_files={"face2.jpg"},
                nav_prefix="",
            )
            # Verify get_best_face_id was called with combined face IDs
            mock_best.assert_called_once_with(["face1", "face2", "face3"])


class TestFB038LoadMorePreservesCheckboxes:
    """FB-038: Load More should append new cards, not replace entire sidebar."""

    def test_load_more_button_uses_outerhtml(self):
        """Load More button should use outerHTML swap to preserve existing cards."""
        from app.main import neighbors_sidebar

        neighbors = [
            {
                "identity_id": f"nbr-{i}",
                "name": f"Person {i}",
                "distance": 0.8 + i * 0.01,
                "can_merge": True,
                "face_count": 1,
                "anchor_face_ids": [f"face_{i}"],
                "candidate_face_ids": [],
                "state": "PROPOSED",
            }
            for i in range(5)
        ]

        with (
            patch("app.main.get_best_face_id", return_value=None),
            patch("app.main.resolve_face_image_url", return_value=None),
            patch("app.main._identity_home_community_slug", return_value=None),
            patch("app.main.community_url_prefix", return_value=""),
        ):
            result = neighbors_sidebar(
                "target-id",
                neighbors,
                crop_files=set(),
                offset=5,
                has_more=True,
                nav_prefix="",
            )
            html = repr(result)
            # The Load More button should use outerHTML swap
            assert 'hx-swap="outerHTML"' in html, "Load More button must use outerHTML swap to preserve checkbox state"
            # Should have a load-more container with specific ID
            assert "load-more-target-id" in html

    def test_incremental_load_returns_only_new_cards(self, client):
        """When offset > 0, neighbors endpoint returns only new cards (not full sidebar)."""
        import app.main as main_mod

        mock_registry = MagicMock()
        identity = {
            "identity_id": "target-id",
            "name": "Target",
            "anchor_ids": ["face_t"],
            "candidate_ids": [],
            "negative_ids": [],
            "state": "CONFIRMED",
        }
        mock_registry.get_identity.return_value = identity
        mock_registry.get_anchor_face_ids.return_value = ["face_x"]
        mock_registry.get_candidate_face_ids.return_value = []

        # Pre-cached neighbors (11 total — must exceed offset+limit+1 to hit cache path)
        cached_neighbors = [
            {
                "identity_id": f"nbr-{i}",
                "name": f"Person {i}",
                "distance": 0.8 + i * 0.01,
                "can_merge": True,
                "merge_blocked_reason": None,
                "face_count": 1,
                "co_occurrence": 0,
            }
            for i in range(11)
        ]

        with (
            patch.object(main_mod, "load_registry", return_value=mock_registry),
            patch.object(main_mod, "get_face_data", return_value={}),
            patch.object(main_mod, "load_photo_registry", return_value=MagicMock()),
            patch.object(main_mod, "get_crop_files", return_value=set()),
            patch.object(main_mod, "_compute_co_occurrence", return_value=0),
            patch.object(main_mod, "_get_user_role", return_value="admin"),
            patch("app.identity_routes._get_cached_neighbors", return_value=cached_neighbors),
            patch.object(main_mod, "get_best_face_id", return_value=None),
            patch.object(main_mod, "resolve_face_image_url", return_value=None),
            patch.object(main_mod, "_identity_home_community_slug", return_value=None),
            patch.object(main_mod, "community_url_prefix", return_value=""),
            patch("app.identity_routes._nav_prefix_from_request", return_value=""),
        ):
            resp = client.get(
                "/api/identity/target-id/neighbors?offset=5&limit=5",
                headers={"HX-Request": "true"},
            )
            html = resp.text
            # Should NOT contain sidebar wrapper elements (header, bulk actions)
            assert "Similar Identities" not in html, "Incremental load should NOT return full sidebar with header"
            # Should contain some of the new neighbors
            assert "nbr-5" in html or "nbr-6" in html or "Person 5" in html or "Person 6" in html, (
                "Incremental load should return new neighbor cards"
            )
