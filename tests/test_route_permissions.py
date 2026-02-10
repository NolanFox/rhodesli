"""Permission boundary tests for critical admin data-modification routes.

Each route is tested with the full permission matrix:
1. Anonymous user (auth enabled, no user) -> 401
2. Regular (non-admin) user -> 403
3. Admin user -> success (200, or domain error like 404/409)

Additionally, auth-disabled mode is tested for all routes to ensure
they pass through (no 401/403).

Routes tested (priority order):
- POST /confirm/{identity_id}
- POST /reject/{identity_id}
- POST /api/identity/{target_id}/merge/{source_id}
- POST /api/identity/{identity_id}/undo-merge
- POST /api/face/{face_id}/detach
- POST /api/identity/{identity_id}/rename
- POST /api/identity/{id}/skip
- POST /identity/{identity_id}/reset
- POST /api/identity/{identity_id}/bulk-merge
- POST /api/identity/{identity_id}/bulk-reject
- POST /api/photo/{photo_id}/collection
- POST /api/identity/{identity_id}/metadata
- POST /api/photo/{photo_id}/metadata
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.auth import User
from core.registry import IdentityRegistry, IdentityState
from core.photo_registry import PhotoRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def auth_enabled():
    with patch("app.main.is_auth_enabled", return_value=True), \
         patch("app.auth.is_auth_enabled", return_value=True):
        yield


@pytest.fixture
def auth_disabled():
    with patch("app.main.is_auth_enabled", return_value=False), \
         patch("app.auth.is_auth_enabled", return_value=False):
        yield


@pytest.fixture
def no_user(auth_enabled):
    with patch("app.main.get_current_user", return_value=None):
        yield


@pytest.fixture
def regular_user(auth_enabled):
    user = User(id="test-user-1", email="user@example.com", is_admin=False, role="viewer")
    with patch("app.main.get_current_user", return_value=user):
        yield user


@pytest.fixture
def admin_user(auth_enabled):
    user = User(id="test-admin-1", email="admin@rhodesli.test", is_admin=True, role="admin")
    with patch("app.main.get_current_user", return_value=user):
        yield user


@pytest.fixture
def mock_registry():
    """Create a real IdentityRegistry with test data for admin success tests."""
    reg = IdentityRegistry()
    target_id = reg.create_identity(
        anchor_ids=["face_a"],
        user_source="test",
        name="Alice Test",
        state=IdentityState.CONFIRMED,
    )
    source_id = reg.create_identity(
        anchor_ids=["face_b"],
        user_source="test",
        name="Bob Test",
        state=IdentityState.PROPOSED,
    )
    inbox_id = reg.create_identity(
        anchor_ids=["face_c"],
        user_source="test",
        state=IdentityState.INBOX,
    )
    return reg, target_id, source_id, inbox_id


@pytest.fixture
def mock_photo_registry():
    """Create a PhotoRegistry with test data."""
    photo_reg = PhotoRegistry()
    photo_reg.register_face("photo_1", "/path/photo_1.jpg", "face_a")
    photo_reg.register_face("photo_2", "/path/photo_2.jpg", "face_b")
    photo_reg.register_face("photo_3", "/path/photo_3.jpg", "face_c")
    return photo_reg


HTMX_HEADERS = {"HX-Request": "true"}


# ===========================================================================
# POST /confirm/{identity_id}
# ===========================================================================

class TestConfirmPermissions:
    """POST /confirm/{identity_id} — admin-only identity confirmation."""

    def test_confirm_rejects_anonymous(self, client, no_user):
        resp = client.post("/confirm/fake-id", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_confirm_rejects_non_admin(self, client, regular_user):
        resp = client.post("/confirm/fake-id", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_confirm_allows_admin(self, client, admin_user, mock_registry, mock_photo_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(f"/confirm/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)

    def test_confirm_passes_when_auth_disabled(self, client, auth_disabled, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(f"/confirm/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /reject/{identity_id}
# ===========================================================================

class TestRejectPermissions:
    """POST /reject/{identity_id} — admin-only identity rejection."""

    def test_reject_rejects_anonymous(self, client, no_user):
        resp = client.post("/reject/fake-id", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_reject_rejects_non_admin(self, client, regular_user):
        resp = client.post("/reject/fake-id", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_reject_allows_admin(self, client, admin_user, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(f"/reject/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)

    def test_reject_passes_when_auth_disabled(self, client, auth_disabled, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(f"/reject/{source_id}", headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /api/identity/{target_id}/merge/{source_id}
# ===========================================================================

class TestMergePermissions:
    """POST /api/identity/{target_id}/merge/{source_id} — admin-only merge."""

    def test_merge_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/identity/tgt/merge/src", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_merge_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/identity/tgt/merge/src", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_merge_allows_admin(self, client, admin_user, mock_registry, mock_photo_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.load_photo_registry", return_value=mock_photo_registry), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(
                f"/api/identity/{target_id}/merge/{source_id}",
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)

    def test_merge_passes_when_auth_disabled(self, client, auth_disabled, mock_registry, mock_photo_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.load_photo_registry", return_value=mock_photo_registry), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(
                f"/api/identity/{target_id}/merge/{source_id}",
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /api/identity/{identity_id}/undo-merge
# ===========================================================================

class TestUndoMergePermissions:
    """POST /api/identity/{identity_id}/undo-merge — admin-only undo."""

    def test_undo_merge_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/identity/fake-id/undo-merge", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_undo_merge_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/identity/fake-id/undo-merge", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_undo_merge_allows_admin(self, client, admin_user, mock_registry, mock_photo_registry):
        """Admin can call undo-merge; gets domain error (no merge history) not auth error."""
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"):
            resp = client.post(
                f"/api/identity/{target_id}/undo-merge",
                headers=HTMX_HEADERS)
            # 409 = no merge history (domain error), not an auth error
            assert resp.status_code not in (401, 403)
            assert resp.status_code == 409  # "Nothing to undo"


# ===========================================================================
# POST /api/face/{face_id}/detach
# ===========================================================================

class TestDetachPermissions:
    """POST /api/face/{face_id}/detach — admin-only face detach."""

    def test_detach_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/face/image_001:face0/detach", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_detach_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/face/image_001:face0/detach", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_detach_allows_admin_face_not_found(self, client, admin_user):
        """Admin can call detach; gets 404 (face not found) not auth error."""
        reg = IdentityRegistry()
        with patch("app.main.load_registry", return_value=reg):
            resp = client.post(
                "/api/face/nonexistent_face/detach",
                headers=HTMX_HEADERS)
            assert resp.status_code == 404

    def test_detach_passes_when_auth_disabled(self, client, auth_disabled):
        reg = IdentityRegistry()
        with patch("app.main.load_registry", return_value=reg):
            resp = client.post(
                "/api/face/nonexistent_face/detach",
                headers=HTMX_HEADERS)
            # 404 = face not found (domain error, not auth)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /api/identity/{identity_id}/rename
# ===========================================================================

class TestRenamePermissions:
    """POST /api/identity/{identity_id}/rename — admin-only rename."""

    def test_rename_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/identity/fake-id/rename", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_rename_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/identity/fake-id/rename", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_rename_allows_admin(self, client, admin_user, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"):
            resp = client.post(
                f"/api/identity/{target_id}/rename",
                data={"name": "New Name"},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)
            assert resp.status_code == 200

    def test_rename_passes_when_auth_disabled(self, client, auth_disabled, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"):
            resp = client.post(
                f"/api/identity/{target_id}/rename",
                data={"name": "New Name"},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /api/identity/{id}/skip (instrumentation)
# ===========================================================================

class TestSkipInstrumentationPermissions:
    """POST /api/identity/{id}/skip — admin-only skip logging."""

    def test_skip_instrumentation_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/identity/fake-id/skip", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_skip_instrumentation_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/identity/fake-id/skip", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_skip_instrumentation_allows_admin(self, client, admin_user):
        with patch("app.main.get_event_recorder") as mock_recorder:
            mock_recorder.return_value.record = MagicMock()
            resp = client.post(
                "/api/identity/test-id/skip",
                headers=HTMX_HEADERS)
            assert resp.status_code == 200

    def test_skip_instrumentation_passes_when_auth_disabled(self, client, auth_disabled):
        with patch("app.main.get_event_recorder") as mock_recorder:
            mock_recorder.return_value.record = MagicMock()
            resp = client.post(
                "/api/identity/test-id/skip",
                headers=HTMX_HEADERS)
            assert resp.status_code == 200


# ===========================================================================
# POST /identity/{identity_id}/skip (inbox skip)
# ===========================================================================

class TestIdentitySkipPermissions:
    """POST /identity/{identity_id}/skip — admin-only skip from review."""

    def test_identity_skip_rejects_anonymous(self, client, no_user):
        resp = client.post("/identity/fake-id/skip", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_identity_skip_rejects_non_admin(self, client, regular_user):
        resp = client.post("/identity/fake-id/skip", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_identity_skip_allows_admin(self, client, admin_user, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(
                f"/identity/{inbox_id}/skip",
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)

    def test_identity_skip_passes_when_auth_disabled(self, client, auth_disabled, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(
                f"/identity/{inbox_id}/skip",
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /identity/{identity_id}/reset
# ===========================================================================

class TestResetPermissions:
    """POST /identity/{identity_id}/reset — admin-only reset to Inbox."""

    def test_reset_rejects_anonymous(self, client, no_user):
        resp = client.post("/identity/fake-id/reset", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_reset_rejects_non_admin(self, client, regular_user):
        resp = client.post("/identity/fake-id/reset", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_reset_allows_admin(self, client, admin_user, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        # Skip the proposed identity first so we can reset it
        reg.skip_identity(source_id, user_source="test")
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(
                f"/identity/{source_id}/reset",
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)

    def test_reset_passes_when_auth_disabled(self, client, auth_disabled, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        reg.skip_identity(source_id, user_source="test")
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=[]):
            resp = client.post(
                f"/identity/{source_id}/reset",
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /api/identity/{identity_id}/bulk-merge
# ===========================================================================

class TestBulkMergePermissions:
    """POST /api/identity/{identity_id}/bulk-merge — admin-only bulk merge."""

    def test_bulk_merge_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/identity/fake-id/bulk-merge", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_bulk_merge_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/identity/fake-id/bulk-merge", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_bulk_merge_allows_admin_no_ids(self, client, admin_user):
        """Admin can call bulk-merge; with no IDs, gets warning toast not auth error."""
        resp = client.post(
            "/api/identity/fake-id/bulk-merge",
            headers=HTMX_HEADERS)
        assert resp.status_code not in (401, 403)

    def test_bulk_merge_allows_admin_with_ids(self, client, admin_user, mock_registry, mock_photo_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"), \
             patch("app.main.load_photo_registry", return_value=mock_photo_registry):
            resp = client.post(
                f"/api/identity/{target_id}/bulk-merge",
                data={"bulk_ids": source_id},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)

    def test_bulk_merge_passes_when_auth_disabled(self, client, auth_disabled):
        resp = client.post(
            "/api/identity/fake-id/bulk-merge",
            headers=HTMX_HEADERS)
        assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /api/identity/{identity_id}/bulk-reject
# ===========================================================================

class TestBulkRejectPermissions:
    """POST /api/identity/{identity_id}/bulk-reject — admin-only bulk reject."""

    def test_bulk_reject_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/identity/fake-id/bulk-reject", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_bulk_reject_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/identity/fake-id/bulk-reject", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_bulk_reject_allows_admin_no_ids(self, client, admin_user):
        """Admin can call bulk-reject; with no IDs, gets warning toast not auth error."""
        resp = client.post(
            "/api/identity/fake-id/bulk-reject",
            headers=HTMX_HEADERS)
        assert resp.status_code not in (401, 403)

    def test_bulk_reject_allows_admin_with_ids(self, client, admin_user, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"):
            resp = client.post(
                f"/api/identity/{target_id}/bulk-reject",
                data={"bulk_ids": source_id},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)

    def test_bulk_reject_passes_when_auth_disabled(self, client, auth_disabled):
        resp = client.post(
            "/api/identity/fake-id/bulk-reject",
            headers=HTMX_HEADERS)
        assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /api/photo/{photo_id}/collection
# ===========================================================================

class TestPhotoCollectionPermissions:
    """POST /api/photo/{photo_id}/collection — admin-only collection reassignment."""

    def test_collection_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/photo/fake-id/collection", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_collection_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/photo/fake-id/collection", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_collection_allows_admin(self, client, admin_user, mock_photo_registry):
        with patch("app.main.load_photo_registry", return_value=mock_photo_registry), \
             patch("app.main.save_photo_registry"):
            # Use a known photo_id from the mock
            resp = client.post(
                "/api/photo/photo_1/collection",
                data={"source": "Test Collection"},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)

    def test_collection_passes_when_auth_disabled(self, client, auth_disabled, mock_photo_registry):
        with patch("app.main.load_photo_registry", return_value=mock_photo_registry), \
             patch("app.main.save_photo_registry"):
            resp = client.post(
                "/api/photo/photo_1/collection",
                data={"source": "Test Collection"},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /api/identity/{identity_id}/metadata
# ===========================================================================

class TestIdentityMetadataPermissions:
    """POST /api/identity/{identity_id}/metadata — admin-only metadata update."""

    def test_identity_metadata_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/identity/fake-id/metadata", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_identity_metadata_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/identity/fake-id/metadata", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_identity_metadata_allows_admin(self, client, admin_user, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"):
            resp = client.post(
                f"/api/identity/{target_id}/metadata",
                data={"birth_year": "1920", "birth_place": "Rhodes"},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)
            assert resp.status_code == 200

    def test_identity_metadata_passes_when_auth_disabled(self, client, auth_disabled, mock_registry):
        reg, target_id, source_id, inbox_id = mock_registry
        with patch("app.main.load_registry", return_value=reg), \
             patch("app.main.save_registry"):
            resp = client.post(
                f"/api/identity/{target_id}/metadata",
                data={"birth_year": "1920"},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# POST /api/photo/{photo_id}/metadata
# ===========================================================================

class TestPhotoMetadataPermissions:
    """POST /api/photo/{photo_id}/metadata — admin-only photo metadata update."""

    def test_photo_metadata_rejects_anonymous(self, client, no_user):
        resp = client.post("/api/photo/fake-id/metadata", headers=HTMX_HEADERS)
        assert resp.status_code == 401

    def test_photo_metadata_rejects_non_admin(self, client, regular_user):
        resp = client.post("/api/photo/fake-id/metadata", headers=HTMX_HEADERS)
        assert resp.status_code == 403

    def test_photo_metadata_allows_admin(self, client, admin_user, mock_photo_registry):
        with patch("app.main.load_photo_registry", return_value=mock_photo_registry), \
             patch("app.main.save_photo_registry"):
            resp = client.post(
                "/api/photo/photo_1/metadata",
                data={"date_taken": "1935", "location": "Rhodes, Greece"},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)

    def test_photo_metadata_passes_when_auth_disabled(self, client, auth_disabled, mock_photo_registry):
        with patch("app.main.load_photo_registry", return_value=mock_photo_registry), \
             patch("app.main.save_photo_registry"):
            resp = client.post(
                "/api/photo/photo_1/metadata",
                data={"date_taken": "1935"},
                headers=HTMX_HEADERS)
            assert resp.status_code not in (401, 403)


# ===========================================================================
# Cross-cutting: 401 responses have empty body (HTMX compatibility)
# ===========================================================================

class TestAnonymous401EmptyBody:
    """All 401 responses must have empty body so HTMX beforeSwap can intercept."""

    ADMIN_ROUTES = [
        "/confirm/test-id",
        "/reject/test-id",
        "/api/identity/tgt/merge/src",
        "/api/identity/test-id/undo-merge",
        "/api/face/test_face/detach",
        "/api/identity/test-id/rename",
        "/api/identity/test-id/skip",
        "/identity/test-id/skip",
        "/identity/test-id/reset",
        "/api/identity/test-id/bulk-merge",
        "/api/identity/test-id/bulk-reject",
        "/api/photo/test-id/collection",
        "/api/identity/test-id/metadata",
        "/api/photo/test-id/metadata",
    ]

    def test_anonymous_401_empty_body(self, client, no_user):
        """401 responses must have empty body for HTMX beforeSwap handler."""
        for route in self.ADMIN_ROUTES:
            resp = client.post(route, headers=HTMX_HEADERS, follow_redirects=False)
            assert resp.status_code == 401, f"{route} returned {resp.status_code}, expected 401"
            assert resp.text.strip() == "", f"{route} returned non-empty body on 401: {resp.text[:100]}"


# ===========================================================================
# Cross-cutting: 403 responses include permission toast
# ===========================================================================

class TestNonAdmin403Toast:
    """All 403 responses should include a permission-denied toast."""

    ADMIN_ROUTES = [
        "/confirm/test-id",
        "/reject/test-id",
        "/api/identity/tgt/merge/src",
        "/api/identity/test-id/undo-merge",
        "/api/face/test_face/detach",
        "/api/identity/test-id/rename",
        "/api/identity/test-id/skip",
        "/identity/test-id/skip",
        "/identity/test-id/reset",
        "/api/identity/test-id/bulk-merge",
        "/api/identity/test-id/bulk-reject",
        "/api/photo/test-id/collection",
        "/api/identity/test-id/metadata",
        "/api/photo/test-id/metadata",
    ]

    def test_non_admin_403_has_toast(self, client, regular_user):
        """403 responses include permission-denied messaging."""
        for route in self.ADMIN_ROUTES:
            resp = client.post(route, headers=HTMX_HEADERS, follow_redirects=False)
            assert resp.status_code == 403, f"{route} returned {resp.status_code}, expected 403"
            body = resp.text.lower()
            assert "permission" in body or "toast" in body, \
                f"{route} 403 response missing permission toast: {resp.text[:200]}"


# ===========================================================================
# Cross-cutting: No 303 redirects from admin routes (HTMX regression guard)
# ===========================================================================

class TestNo303Redirects:
    """Admin routes NEVER return 303 redirect — HTMX would silently follow it."""

    ADMIN_ROUTES = [
        "/confirm/test-id",
        "/reject/test-id",
        "/api/identity/tgt/merge/src",
        "/api/identity/test-id/undo-merge",
        "/api/face/test_face/detach",
        "/api/identity/test-id/rename",
        "/api/identity/test-id/skip",
        "/identity/test-id/skip",
        "/identity/test-id/reset",
        "/api/identity/test-id/bulk-merge",
        "/api/identity/test-id/bulk-reject",
        "/api/photo/test-id/collection",
        "/api/identity/test-id/metadata",
        "/api/photo/test-id/metadata",
    ]

    def test_anonymous_never_gets_303(self, client, no_user):
        for route in self.ADMIN_ROUTES:
            resp = client.post(route, headers=HTMX_HEADERS, follow_redirects=False)
            assert resp.status_code != 303, \
                f"{route} returned 303 redirect for anonymous — MUST use 401"

    def test_non_admin_never_gets_303(self, client, regular_user):
        for route in self.ADMIN_ROUTES:
            resp = client.post(route, headers=HTMX_HEADERS, follow_redirects=False)
            assert resp.status_code != 303, \
                f"{route} returned 303 redirect for non-admin — MUST use 403"
