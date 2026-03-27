"""Tests for Session 139 Track B: Focus Mode UX Fixes.

Tests cover:
- B1: Merge auto-advance in focus mode
- B2: Bulk-merge from_focus support
- B3: Edit in Admin deep link uses focus mode
"""

import re
import pytest
from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient


def _make_identity(identity_id, name=None, state="PROPOSED", anchor_ids=None, candidate_ids=None):
    """Helper: create a minimal identity dict."""
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
    }


def _make_registry(identities_list):
    """Helper: build a real IdentityRegistry populated with test identities."""
    from core.registry import IdentityRegistry

    registry = IdentityRegistry()
    for ident in identities_list:
        registry._identities[ident["identity_id"]] = ident
    return registry


def _make_photo_registry():
    """Helper: build a mock PhotoRegistry that allows all merges (no co-occurrence)."""
    photo_reg = MagicMock()
    photo_reg.get_photos_for_faces.return_value = set()
    return photo_reg


class TestMergeAutoAdvanceFocus:
    """B1: Verify merge auto-advance in focus mode."""

    def test_merge_with_from_focus_returns_focus_card(self):
        """POST merge with from_focus=true should return a focus-container card, not browse card."""
        from core.registry import IdentityRegistry, IdentityState
        from core.photo_registry import PhotoRegistry

        photo_reg = PhotoRegistry()
        photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_a")
        photo_reg.register_face("photo_2", "/path/photo_2.jpg", "face_b")
        photo_reg.register_face("photo_3", "/path/photo_3.jpg", "face_c")

        identity_reg = IdentityRegistry()
        target_id = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Alice",
            state=IdentityState.CONFIRMED,
        )
        source_id = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
        )
        # Third identity so there's something to advance to
        identity_reg.create_identity(
            anchor_ids=["face_c"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        with (
            patch("app.main.load_registry", return_value=identity_reg),
            patch("app.main.save_registry"),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_crop_files", return_value=set()),
        ):
            from app.main import app

            client = TestClient(app)
            response = client.post(
                f"/api/identity/{target_id}/merge/{source_id}?from_focus=true",
                headers={"HX-Request": "true"},
            )

        assert response.status_code == 200
        html = response.text
        # Should contain focus-container (next card via OOB)
        assert "focus-container" in html
        # Should contain toast via OOB swap
        assert "toast-container" in html
        # Should NOT contain the browse-mode identity card
        assert f'id="identity-{target_id}"' not in html

    def test_merge_without_from_focus_returns_browse_card(self):
        """POST merge without from_focus should return identity card (browse mode)."""
        from core.registry import IdentityRegistry, IdentityState
        from core.photo_registry import PhotoRegistry

        photo_reg = PhotoRegistry()
        photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_a")
        photo_reg.register_face("photo_2", "/path/photo_2.jpg", "face_b")

        identity_reg = IdentityRegistry()
        target_id = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Alice",
            state=IdentityState.CONFIRMED,
        )
        source_id = identity_reg.create_identity(
            anchor_ids=["face_b"],
            user_source="test",
        )

        with (
            patch("app.main.load_registry", return_value=identity_reg),
            patch("app.main.save_registry"),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_crop_files", return_value=set()),
        ):
            from app.main import app

            client = TestClient(app)
            response = client.post(
                f"/api/identity/{target_id}/merge/{source_id}",
                headers={"HX-Request": "true"},
            )

        assert response.status_code == 200
        html = response.text
        # Browse mode returns the identity card
        assert f"identity-{target_id}" in html
        # Should NOT have focus-container OOB swap
        assert 'id="focus-container"' not in html


class TestBulkMergeFromFocus:
    """B2: Bulk-merge endpoint from_focus support."""

    def test_bulk_merge_from_focus_returns_next_card(self):
        """POST bulk-merge with from_focus=true should advance to next focus card."""
        target_id = "aaaa-target-1111"
        source_id = "bbbb-source-2222"
        next_id = "cccc-next-3333"

        target = _make_identity(
            target_id,
            name="Leon Capeluto",
            state="CONFIRMED",
            anchor_ids=["face_t1"],
        )
        source = _make_identity(source_id, state="PROPOSED", anchor_ids=["face_s1"])
        next_ident = _make_identity(next_id, state="INBOX", anchor_ids=["face_n1"])

        registry = _make_registry([target, source, next_ident])
        photo_reg = _make_photo_registry()

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.save_registry"),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_crop_files", return_value=set()),
        ):
            from app.main import app

            client = TestClient(app)
            resp = client.post(
                f"/api/identity/{target_id}/bulk-merge?from_focus=true",
                data={"bulk_ids": source_id},
                headers={"HX-Request": "true"},
            )

        assert resp.status_code == 200
        html = resp.text
        # Should contain focus-container (next card)
        assert "focus-container" in html
        # Should contain toast via OOB swap
        assert "toast-container" in html

    def test_bulk_merge_without_from_focus_returns_toast_only(self):
        """POST bulk-merge without from_focus should return toast only."""
        target_id = "aaaa-target-1111"
        source_id = "bbbb-source-2222"

        target = _make_identity(
            target_id,
            name="Leon Capeluto",
            state="CONFIRMED",
            anchor_ids=["face_t1"],
        )
        source = _make_identity(source_id, state="PROPOSED", anchor_ids=["face_s1"])

        registry = _make_registry([target, source])
        photo_reg = _make_photo_registry()

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.save_registry"),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
            from app.main import app

            client = TestClient(app)
            resp = client.post(
                f"/api/identity/{target_id}/bulk-merge",
                data={"bulk_ids": source_id},
                headers={"HX-Request": "true"},
            )

        assert resp.status_code == 200
        html = resp.text
        # Should contain toast message
        assert "Merged 1 identities" in html
        # Should NOT contain focus-container
        assert 'id="focus-container"' not in html

    def test_bulk_merge_from_focus_skipped_section(self):
        """POST bulk-merge with from_focus=true&focus_section=skipped targets skipped container."""
        target_id = "aaaa-target-1111"
        source_id = "bbbb-source-2222"
        next_id = "cccc-next-3333"

        target = _make_identity(
            target_id,
            name="Leon Capeluto",
            state="CONFIRMED",
            anchor_ids=["face_t1"],
        )
        source = _make_identity(source_id, state="PROPOSED", anchor_ids=["face_s1"])
        next_ident = _make_identity(next_id, state="SKIPPED", anchor_ids=["face_n1"])

        registry = _make_registry([target, source, next_ident])
        photo_reg = _make_photo_registry()

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.save_registry"),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.is_auth_enabled", return_value=False),
            patch("app.main.get_crop_files", return_value=set()),
        ):
            from app.main import app

            client = TestClient(app)
            resp = client.post(
                f"/api/identity/{target_id}/bulk-merge?from_focus=true&focus_section=skipped",
                data={"bulk_ids": source_id},
                headers={"HX-Request": "true"},
            )

        assert resp.status_code == 200
        html = resp.text
        # Should target skipped-focus-container
        assert "skipped-focus-container" in html


class TestBulkMergeButtonFocusParams:
    """B2: Verify bulk merge button includes from_focus params in focus mode."""

    def test_neighbors_sidebar_bulk_merge_includes_focus_params(self):
        """When from_focus=True, bulk merge button URL should include from_focus."""
        from app.main import neighbors_sidebar

        neighbors = [
            {
                "identity_id": f"neighbor-{i}",
                "name": f"Person {i}",
                "distance": 0.8 + i * 0.01,
                "percentile": 0.9,
                "confidence_gap": 0.1,
                "can_merge": True,
                "face_count": 1,
                "co_occurrence": 0,
            }
            for i in range(3)
        ]

        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main._get_identities_with_proposals", return_value=set()),
        ):
            mock_reg.return_value = MagicMock()
            result = neighbors_sidebar(
                "target-id",
                neighbors,
                set(),
                from_focus=True,
                focus_section="",
            )

        html = str(result)
        # Bulk merge button should include from_focus
        assert "from_focus=true" in html
        # Bulk merge target should be focus-container, not neighbors target
        assert 'hx-target="#focus-container"' in html

    def test_neighbors_sidebar_bulk_merge_no_focus_in_browse(self):
        """When from_focus=False, bulk merge button should NOT include from_focus."""
        from app.main import neighbors_sidebar

        neighbors = [
            {
                "identity_id": f"neighbor-{i}",
                "name": f"Person {i}",
                "distance": 0.8 + i * 0.01,
                "percentile": 0.9,
                "confidence_gap": 0.1,
                "can_merge": True,
                "face_count": 1,
                "co_occurrence": 0,
            }
            for i in range(3)
        ]

        with (
            patch("app.main.load_registry") as mock_reg,
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main._get_identities_with_proposals", return_value=set()),
        ):
            mock_reg.return_value = MagicMock()
            result = neighbors_sidebar(
                "target-id",
                neighbors,
                set(),
                from_focus=False,
            )

        html = str(result)
        # Bulk merge URL should NOT include from_focus
        assert "bulk-merge" in html
        bulk_merge_urls = re.findall(r'bulk-merge[^"]*', html)
        for url in bulk_merge_urls:
            assert "from_focus" not in url


class TestEditInAdminLink:
    """B3: Edit in Admin deep link should use focus mode."""

    def test_person_page_edit_admin_uses_focus_view(self, client, auth_disabled):
        """Edit in Admin link on person page should use view=focus&current=."""
        from core.registry import IdentityRegistry, IdentityState
        from core.photo_registry import PhotoRegistry

        photo_reg = PhotoRegistry()
        photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_a")

        identity_reg = IdentityRegistry()
        person_id = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            name="Test Person",
            state=IdentityState.CONFIRMED,
        )

        with (
            patch("app.main.load_registry", return_value=identity_reg),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
            resp = client.get(f"/person/{person_id}")

        assert resp.status_code == 200
        html = resp.text

        # Should contain focus mode link, not browse mode with anchor
        assert "view=focus" in html
        assert f"current={person_id}" in html
        # Should NOT use old browse + anchor pattern
        assert f"view=browse#identity-{person_id}" not in html

    def test_edit_admin_link_uses_correct_section(self, client, auth_disabled):
        """Edit in Admin link should use section matching the identity state."""
        from core.registry import IdentityRegistry, IdentityState
        from core.photo_registry import PhotoRegistry

        photo_reg = PhotoRegistry()
        photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_a")

        identity_reg = IdentityRegistry()
        person_id = identity_reg.create_identity(
            anchor_ids=["face_a"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        with (
            patch("app.main.load_registry", return_value=identity_reg),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
            resp = client.get(f"/person/{person_id}")

        assert resp.status_code == 200
        html = resp.text
        # INBOX maps to section=to_review
        assert "section=to_review" in html
        assert f"view=focus&amp;current={person_id}" in html
