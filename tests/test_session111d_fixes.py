"""
Tests for Session 111d — Feedback Fix Sprint.

FB-069: Performance — targeted Supabase writes via changed_ids.
FB-070: CI test fix (separate commit).
"""

import pytest
from unittest.mock import patch, MagicMock

from core.registry import IdentityRegistry, IdentityState
from core.photo_registry import PhotoRegistry
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

    def test_merged_identity_appears_in_search(self):
        """Searching for a merged identity's name should return it."""
        reg, target_id, source_id = self._make_registry_with_merged()
        results = reg.search_identities("3053")
        ids = [r["identity_id"] for r in results]
        assert source_id in ids

    def test_merged_identity_has_merged_into_name(self):
        """Merged identity result should include merged_into_name."""
        reg, target_id, source_id = self._make_registry_with_merged()
        results = reg.search_identities("3053")
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
        results = reg.search_identities("3053")
        ids = [r["identity_id"] for r in results]
        assert "other-003" in ids
        assert source_id in ids
        # Non-merged should come before merged
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
        results = reg.search_identities("3053")
        merged_result = next(r for r in results if r["identity_id"] == source_id)
        assert merged_result["merged_into_name"] == "Unknown"
