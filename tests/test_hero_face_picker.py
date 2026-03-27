"""Tests for FB-007: Hero Face Picker (Session 141 Track B).

Tests cover:
- get_best_face_id returns primary_face_id when set on identity
- get_best_face_id falls back to quality when primary_face_id not set
- get_best_face_id falls back to quality when primary_face_id invalid
- set-primary-face endpoint works (mock save_registry)
- set-primary-face endpoint returns 401 for non-admin
- set-primary-face endpoint returns 400 for invalid face_id
- set-primary-face endpoint returns 404 for missing identity
- face_card renders primary indicator
- Supabase shadow write includes primary_face_id
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_session():
    return {"auth": "valid", "user_id": "admin-1", "user_email": "NolanFox@gmail.com"}


def _non_admin_session():
    return {"auth": "valid", "user_id": "user-1", "user_email": "guest@example.com"}


def _mock_registry(identities=None):
    """Build a mock IdentityRegistry with ._identities dict."""
    if identities is None:
        identities = {}
    reg = MagicMock()
    reg._identities = identities

    def _get_identity(iid):
        if iid not in identities:
            raise KeyError(f"Identity {iid} not found")
        return dict(identities[iid])

    reg.get_identity = _get_identity
    return reg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from app.main import app
    from starlette.testclient import TestClient

    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: get_best_face_id with primary_face_id
# ---------------------------------------------------------------------------


class TestGetBestFaceIdPrimary:
    def test_returns_primary_when_set_and_valid(self):
        """get_best_face_id returns primary_face_id when it exists in face list."""
        from app.main import get_best_face_id

        identity = {"primary_face_id": "face-b", "anchor_ids": ["face-a", "face-b"]}
        result = get_best_face_id(["face-a", "face-b"], identity=identity)
        assert result == "face-b"

    def test_falls_back_when_primary_not_set(self):
        """get_best_face_id falls back to quality when no primary_face_id."""
        from app.main import get_best_face_id

        identity = {"anchor_ids": ["face-a", "face-b"]}
        # Should not crash, should return some face
        result = get_best_face_id(["face-a", "face-b"], identity=identity)
        assert result in ("face-a", "face-b")

    def test_falls_back_when_primary_not_in_face_list(self):
        """get_best_face_id falls back when primary_face_id is not in the face list."""
        from app.main import get_best_face_id

        identity = {"primary_face_id": "face-c", "anchor_ids": ["face-a", "face-b"]}
        result = get_best_face_id(["face-a", "face-b"], identity=identity)
        assert result in ("face-a", "face-b")

    def test_works_without_identity_param(self):
        """get_best_face_id works normally when identity is not provided."""
        from app.main import get_best_face_id

        result = get_best_face_id(["face-a"])
        assert result == "face-a"

    def test_empty_face_list(self):
        """get_best_face_id returns None for empty list even with identity."""
        from app.main import get_best_face_id

        identity = {"primary_face_id": "face-a"}
        result = get_best_face_id([], identity=identity)
        assert result is None

    def test_primary_takes_precedence_over_quality(self):
        """primary_face_id should be returned even if another face has higher quality."""
        from app.main import get_best_face_id

        identity = {"primary_face_id": "face-low-quality"}
        # Even with multiple faces, primary wins
        result = get_best_face_id(
            ["face-high-quality", "face-low-quality"],
            identity=identity,
        )
        assert result == "face-low-quality"


# ---------------------------------------------------------------------------
# Tests: POST /api/identity/{id}/set-primary-face/{face_id}
# ---------------------------------------------------------------------------


class TestSetPrimaryFaceEndpoint:
    def test_set_primary_face_success(self, client):
        """Admin can set primary face and get success toast."""
        identity = {
            "identity_id": "test-id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a", "face-b"],
            "candidate_ids": [],
            "negative_ids": [],
        }
        reg = _mock_registry({"test-id-1": identity})

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.identity_routes._check_origin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main.save_registry"))
            stack.enter_context(patch("app.main.log_user_action"))

            resp = client.post(
                "/api/identity/test-id-1/set-primary-face/face-b",
                cookies=_admin_session(),
            )
            assert resp.status_code == 200
            assert "hero face" in resp.text.lower() or "primary" in resp.text.lower() or "Test Person" in resp.text

    def test_set_primary_face_updates_registry(self, client):
        """Setting primary face updates the internal identity dict."""
        identity = {
            "identity_id": "test-id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a", "face-b"],
            "candidate_ids": [],
            "negative_ids": [],
        }
        identities = {"test-id-1": identity}
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.identity_routes._check_origin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main.save_registry"))
            stack.enter_context(patch("app.main.log_user_action"))

            client.post(
                "/api/identity/test-id-1/set-primary-face/face-b",
                cookies=_admin_session(),
            )
            assert reg._identities["test-id-1"]["primary_face_id"] == "face-b"

    def test_set_primary_face_401_non_admin(self, client):
        """Non-admin gets 401 when trying to set primary face."""
        from starlette.responses import Response

        with patch("app.main._check_admin", return_value=Response("Unauthorized", status_code=401)):
            resp = client.post(
                "/api/identity/test-id-1/set-primary-face/face-a",
                cookies=_non_admin_session(),
            )
            assert resp.status_code == 401

    def test_set_primary_face_404_missing_identity(self, client):
        """404 when identity doesn't exist."""
        reg = _mock_registry({})

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.identity_routes._check_origin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))

            resp = client.post(
                "/api/identity/nonexistent/set-primary-face/face-a",
                cookies=_admin_session(),
            )
            assert resp.status_code == 404

    def test_set_primary_face_400_invalid_face(self, client):
        """400 when face_id doesn't belong to the identity."""
        identity = {
            "identity_id": "test-id-1",
            "name": "Test Person",
            "state": "CONFIRMED",
            "anchor_ids": ["face-a"],
            "candidate_ids": [],
            "negative_ids": [],
        }
        reg = _mock_registry({"test-id-1": identity})

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.identity_routes._check_origin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))

            resp = client.post(
                "/api/identity/test-id-1/set-primary-face/face-not-mine",
                cookies=_admin_session(),
            )
            assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests: face_card renders primary indicator
# ---------------------------------------------------------------------------


class TestFaceCardPrimaryIndicator:
    def test_face_card_shows_primary_badge_when_is_primary(self):
        """face_card with is_primary=True shows amber star indicator."""
        from app.components.cards import face_card

        card = face_card(
            face_id="face-a",
            crop_url="/static/crops/test.jpg",
            identity_id="test-id-1",
            is_primary=True,
            is_admin=True,
        )
        html = repr(card)
        # Should show "Primary" label (not a button since it's already primary)
        assert "Primary" in html
        # Should have amber ring on the image container
        assert "ring-amber" in html

    def test_face_card_shows_set_primary_button_when_not_primary(self):
        """face_card with is_primary=False shows 'Set as Primary' button for admin."""
        from app.components.cards import face_card

        card = face_card(
            face_id="face-a",
            crop_url="/static/crops/test.jpg",
            identity_id="test-id-1",
            is_primary=False,
            is_admin=True,
        )
        html = repr(card)
        # Should have a button with hx_post to set-primary-face
        assert "set-primary-face" in html
        assert "Primary" in html

    def test_face_card_no_primary_button_for_non_admin(self):
        """face_card for non-admin should not show primary button."""
        from app.components.cards import face_card

        card = face_card(
            face_id="face-a",
            crop_url="/static/crops/test.jpg",
            identity_id="test-id-1",
            is_primary=False,
            is_admin=False,
        )
        html = repr(card)
        assert "set-primary-face" not in html

    def test_face_card_no_primary_button_without_identity(self):
        """face_card without identity_id should not show primary button."""
        from app.components.cards import face_card

        card = face_card(
            face_id="face-a",
            crop_url="/static/crops/test.jpg",
            identity_id=None,
            is_primary=False,
            is_admin=True,
        )
        html = repr(card)
        assert "set-primary-face" not in html


# ---------------------------------------------------------------------------
# Tests: Supabase shadow write includes primary_face_id
# ---------------------------------------------------------------------------


class TestShadowWritePrimaryFaceId:
    def test_shadow_write_includes_primary_face_id(self):
        """shadow_write_identities_batch includes primary_face_id in upsert row."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            from app.supabase_data import shadow_write_identities_batch

            identities = [
                {
                    "identity_id": "test-id-1",
                    "name": "Test Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-a"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "primary_face_id": "face-a",
                }
            ]
            shadow_write_identities_batch(identities)

            # Check the upserted row includes primary_face_id
            upsert_call = mock_client.table.return_value.upsert
            assert upsert_call.called
            rows = upsert_call.call_args[0][0]
            assert any(row.get("primary_face_id") == "face-a" for row in rows)

    def test_shadow_write_omits_primary_face_id_when_none(self):
        """shadow_write_identities_batch omits primary_face_id when not set."""
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[])
        mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            from app.supabase_data import shadow_write_identities_batch

            identities = [
                {
                    "identity_id": "test-id-2",
                    "name": "Test Person 2",
                    "state": "INBOX",
                    "anchor_ids": [],
                    "candidate_ids": ["face-b"],
                    "negative_ids": [],
                    "version_id": 1,
                }
            ]
            shadow_write_identities_batch(identities)

            upsert_call = mock_client.table.return_value.upsert
            assert upsert_call.called
            rows = upsert_call.call_args[0][0]
            # Should NOT have primary_face_id key when not set
            assert all("primary_face_id" not in row for row in rows)
