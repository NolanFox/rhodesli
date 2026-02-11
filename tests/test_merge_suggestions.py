"""
Tests for contributor merge suggestions: role-aware buttons, suggest endpoint,
admin approval with merge execution.
"""

import json
import pytest
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


def _mock_user(role="contributor", email="contributor@test.com"):
    """Create a mock user with the given role."""
    from app.auth import User
    return User(id="test-123", email=email, is_admin=(role == "admin"), role=role)


def _get_two_identity_ids():
    """Get two identity IDs for testing."""
    from app.main import load_registry
    registry = load_registry()
    identities = registry.list_identities()
    ids = []
    for identity in identities:
        if identity.get("anchor_ids") or identity.get("candidate_ids"):
            ids.append(identity["identity_id"])
        if len(ids) >= 2:
            break
    return ids


class TestRoleAwareMergeButtons:
    """Merge buttons should show 'Suggest Merge' for contributors."""

    def test_get_user_role_returns_admin_when_auth_disabled(self, client):
        """When auth is disabled, _get_user_role returns 'admin'."""
        from app.main import _get_user_role
        with patch("app.main.is_auth_enabled", return_value=False):
            assert _get_user_role(None) == "admin"

    def test_get_user_role_returns_viewer_when_no_user(self, client):
        """When auth is enabled but no user, returns 'viewer'."""
        from app.main import _get_user_role
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            assert _get_user_role({}) == "viewer"

    def test_get_user_role_returns_contributor(self, client):
        """When auth enabled and user is contributor, returns 'contributor'."""
        from app.main import _get_user_role
        user = _mock_user("contributor")
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=user):
            assert _get_user_role({}) == "contributor"

    def test_neighbor_card_shows_merge_for_admin(self):
        """Admin users see 'Merge' button in neighbor cards."""
        from app.main import neighbor_card
        from fastcore.xml import to_xml
        neighbor = {
            "identity_id": "test-id",
            "name": "Test Person",
            "distance": 0.5,
            "percentile": 0.9,
            "confidence_gap": 10.0,
            "can_merge": True,
            "face_count": 1,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
            "state": "INBOX",
        }
        html = to_xml(neighbor_card(neighbor, "target-id", set(), user_role="admin"))
        assert "Merge" in html
        assert "Suggest Merge" not in html
        assert "/merge/" in html

    def test_neighbor_card_shows_suggest_merge_for_contributor(self):
        """Contributor users see 'Suggest Merge' button."""
        from app.main import neighbor_card
        from fastcore.xml import to_xml
        neighbor = {
            "identity_id": "test-id",
            "name": "Test Person",
            "distance": 0.5,
            "percentile": 0.9,
            "confidence_gap": 10.0,
            "can_merge": True,
            "face_count": 1,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
            "state": "INBOX",
        }
        html = to_xml(neighbor_card(neighbor, "target-id", set(), user_role="contributor"))
        assert "Suggest Merge" in html
        assert "/suggest-merge/" in html
        # Should use purple styling for contributor
        assert "bg-purple-600" in html

    def test_neighbor_card_blocked_unaffected_by_role(self):
        """Blocked merge shows same for all roles."""
        from app.main import neighbor_card
        from fastcore.xml import to_xml
        neighbor = {
            "identity_id": "test-id",
            "name": "Test Person",
            "distance": 0.5,
            "percentile": 0.9,
            "confidence_gap": 10.0,
            "can_merge": False,
            "face_count": 1,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
            "state": "INBOX",
            "merge_blocked_reason_display": "Co-occurrence",
        }
        html = to_xml(neighbor_card(neighbor, "target-id", set(), user_role="contributor"))
        assert "Blocked" in html
        assert "Suggest Merge" not in html


class TestSuggestMergeEndpoint:
    """Tests for POST /api/identity/{target}/suggest-merge/{source}."""

    def test_suggest_merge_requires_login(self, client):
        """Unauthenticated users get 401."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.post(
                "/api/identity/fake-target/suggest-merge/fake-source",
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 401

    def test_suggest_merge_rejects_viewer(self, client):
        """Viewers (not contributors) get 403."""
        viewer = _mock_user("viewer", "viewer@test.com")
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=viewer):
            response = client.post(
                "/api/identity/fake-target/suggest-merge/fake-source",
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 403

    def test_suggest_merge_creates_annotation(self, client):
        """Contributors can create merge suggestions."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        contributor = _mock_user("contributor")
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._save_annotations"):
            response = client.post(
                f"/api/identity/{ids[0]}/suggest-merge/{ids[1]}",
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            assert "suggestion" in response.text.lower() or "review" in response.text.lower()

    def test_suggest_merge_invalid_identity(self, client):
        """Suggesting merge with nonexistent identity returns 404."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.post(
                "/api/identity/nonexistent-a/suggest-merge/nonexistent-b",
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 404


class TestCreateMergeSuggestion:
    """Tests for the _create_merge_suggestion helper."""

    def test_creates_annotation_with_correct_type(self):
        """Merge suggestion creates annotation with type 'merge_suggestion'."""
        from app.main import _create_merge_suggestion, _load_annotations
        with patch("app.main._save_annotations") as mock_save:
            ann_id = _create_merge_suggestion(
                target_id="target-123",
                source_id="source-456",
                submitted_by="test@test.com",
                confidence="likely",
                reason="They look similar",
            )
            assert ann_id  # Non-empty
            # Check the saved data
            saved_data = mock_save.call_args[0][0]
            ann = saved_data["annotations"][ann_id]
            assert ann["type"] == "merge_suggestion"
            assert ann["status"] == "pending"
            assert ann["submitted_by"] == "test@test.com"
            assert ann["confidence"] == "likely"
            value = json.loads(ann["value"])
            assert value["source_id"] == "source-456"
            assert value["target_id"] == "target-123"


class TestMatchModeRoleAware:
    """Match mode buttons should be role-aware."""

    def test_match_mode_shows_same_person_for_admin(self, client):
        """Admin sees 'Same Person' button in match mode."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/api/match/next-pair")
            if response.status_code == 200 and "No more pairs" not in response.text:
                assert "Same Person" in response.text

    def test_match_mode_shows_suggest_same_for_contributor(self, client):
        """Contributor sees 'Suggest Same' button in match mode."""
        contributor = _mock_user("contributor")
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=contributor):
            response = client.get("/api/match/next-pair")
            if response.status_code == 200 and "No more pairs" not in response.text:
                assert "Suggest Same" in response.text
                assert "bg-purple-600" in response.text


class TestCompareViewRoleAware:
    """Compare view merge button should be role-aware."""

    def test_compare_shows_merge_for_admin(self, client):
        """Admin sees 'Merge' button in compare view."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            assert response.status_code == 200
            assert ">Merge<" in response.text

    def test_compare_shows_suggest_merge_for_contributor(self, client):
        """Contributor sees 'Suggest Merge' button in compare view."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        contributor = _mock_user("contributor")
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=contributor):
            response = client.get(f"/api/identity/{ids[0]}/compare/{ids[1]}")
            assert response.status_code == 200
            assert "Suggest Merge" in response.text


class TestAdminApprovalsMergeSuggestion:
    """Admin approvals page handles merge suggestions with face preview."""

    def test_approvals_page_loads(self, client):
        """Admin approvals page returns 200."""
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/admin/approvals")
            assert response.status_code == 200

    def test_merge_suggestion_shows_face_thumbnails(self, client):
        """Merge suggestions on approvals page show face comparison."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        # Create a merge suggestion with save mocked
        from app.main import _create_merge_suggestion, _invalidate_annotations_cache
        with patch("app.main._save_annotations"):
            ann_id = _create_merge_suggestion(
                target_id=ids[0], source_id=ids[1],
                submitted_by="test@test.com",
            )

        # The annotation is in the in-memory cache, so the approvals page will show it
        with patch("app.main.is_auth_enabled", return_value=False):
            response = client.get("/admin/approvals")
            assert response.status_code == 200
            assert "Merge Suggestion" in response.text
            assert "Execute Merge" in response.text
            assert "Compare" in response.text
        _invalidate_annotations_cache()

    def test_admin_can_execute_merge_suggestion(self, client):
        """Admin can approve a merge suggestion, which executes the merge."""
        ids = _get_two_identity_ids()
        if len(ids) < 2:
            pytest.skip("Need at least 2 identities with faces")

        from app.main import _create_merge_suggestion, _load_annotations, _invalidate_annotations_cache
        # Create suggestion with save mocked (stays in memory cache)
        with patch("app.main._save_annotations"):
            ann_id = _create_merge_suggestion(
                target_id=ids[0], source_id=ids[1],
                submitted_by="test@test.com",
            )

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._save_annotations"), \
             patch("app.main.save_registry"):
            response = client.post(
                f"/admin/approvals/{ann_id}/approve",
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            # Check annotation was marked approved (in-memory)
            annotations = _load_annotations()
            assert annotations["annotations"][ann_id]["status"] == "approved"
        _invalidate_annotations_cache()


class TestFocusMergeButton:
    """Merge button in Focus mode's Similar Identities panel must work."""

    def test_neighbor_card_merge_targets_browse_by_default(self):
        """Without from_focus, merge button targets #identity-{target_id}."""
        from app.main import neighbor_card
        from fastcore.xml import to_xml
        neighbor = {
            "identity_id": "nbr-id",
            "name": "Test Person",
            "distance": 0.5,
            "percentile": 0.9,
            "confidence_gap": 10.0,
            "can_merge": True,
            "face_count": 1,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
            "state": "INBOX",
        }
        html = to_xml(neighbor_card(neighbor, "target-id", set(), user_role="admin", from_focus=False))
        assert 'hx-target="#identity-target-id"' in html
        assert "from_focus" not in html

    def test_neighbor_card_merge_targets_focus_container(self):
        """With from_focus=True, merge button targets #focus-container."""
        from app.main import neighbor_card
        from fastcore.xml import to_xml
        neighbor = {
            "identity_id": "nbr-id",
            "name": "Test Person",
            "distance": 0.5,
            "percentile": 0.9,
            "confidence_gap": 10.0,
            "can_merge": True,
            "face_count": 1,
            "anchor_face_ids": [],
            "candidate_face_ids": [],
            "state": "INBOX",
        }
        html = to_xml(neighbor_card(neighbor, "target-id", set(), user_role="admin", from_focus=True))
        assert 'hx-target="#focus-container"' in html
        assert "from_focus=true" in html

    def test_focus_merge_advances_to_next(self):
        """After merge from focus mode, response contains next focus card."""
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
        # Create a third identity so there's something to advance to
        identity_reg.create_identity(
            anchor_ids=["face_c"],
            user_source="test",
            state=IdentityState.INBOX,
        )

        with patch("app.main.load_registry", return_value=identity_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_crop_files", return_value=set()):
            from app.main import app
            client = TestClient(app)
            response = client.post(
                f"/api/identity/{target_id}/merge/{source_id}?from_focus=true",
                headers={"HX-Request": "true"})

        assert response.status_code == 200
        # Focus mode response should have focus-container (next card)
        assert "focus-container" in response.text
        # Should NOT contain identity-{target_id} card (that's browse mode)
        assert f'id="identity-{target_id}"' not in response.text

    def test_browse_merge_returns_identity_card(self):
        """Without from_focus, merge returns browse-mode identity card."""
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

        with patch("app.main.load_registry", return_value=identity_reg), \
             patch("app.main.save_registry"), \
             patch("app.main.load_photo_registry", return_value=photo_reg), \
             patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main.get_crop_files", return_value=set()):
            from app.main import app
            client = TestClient(app)
            response = client.post(
                f"/api/identity/{target_id}/merge/{source_id}",
                headers={"HX-Request": "true"})

        assert response.status_code == 200
        # Browse mode response should have identity card
        assert f'id="identity-{target_id}"' in response.text
