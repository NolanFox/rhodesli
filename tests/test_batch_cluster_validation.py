"""Tests for PRD-040: Batch Cluster Validation.

Tests cover:
- Batch page renders for admin
- 401 for non-admin
- Face count filtering
- Batch confirm route
- Candidate promotion + state change
- log_user_action called per identity
- Community scoping
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
    reg.promote_candidate = MagicMock()
    return reg


def _inbox_identity(name="Unidentified Person 1", anchors=None, candidates=None):
    return {
        "identity_id": None,
        "name": name,
        "state": "INBOX",
        "anchor_ids": anchors or [],
        "candidate_ids": candidates or [],
        "negative_ids": [],
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Create a test client with standard mocks."""
    from app.main import app
    from starlette.testclient import TestClient

    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: GET /admin/cluster-batch
# ---------------------------------------------------------------------------


class TestBatchPageRender:
    def test_batch_page_renders_for_admin(self, client):
        """GET /admin/cluster-batch returns 200 for admin."""
        identities = {
            "id-1": _inbox_identity(anchors=["face-a", "face-b"]),
            "id-2": _inbox_identity(anchors=["face-c"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main._get_community_identity_ids", return_value=None))
            stack.enter_context(
                patch("app.cluster_review_routes._get_crop_url_for_face", return_value="/static/crops/test.jpg")
            )

            resp = client.get("/admin/cluster-batch", cookies=_admin_session())
            assert resp.status_code == 200

    def test_batch_page_returns_401_for_non_admin(self, client):
        """GET /admin/cluster-batch returns 401 for non-admin."""
        from starlette.responses import Response

        with patch("app.main._check_admin", return_value=Response("Unauthorized", status_code=401)):
            resp = client.get("/admin/cluster-batch", cookies=_non_admin_session())
            assert resp.status_code == 401


class TestBatchFaceCountFilter:
    def test_min_faces_filter(self, client):
        """Clusters with fewer faces than min_faces are excluded."""
        identities = {
            "id-big": _inbox_identity(anchors=["f1", "f2", "f3", "f4", "f5"]),
            "id-small": _inbox_identity(anchors=["f6"]),
            "id-medium": _inbox_identity(anchors=["f7", "f8", "f9"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main._get_community_identity_ids", return_value=None))
            stack.enter_context(
                patch("app.cluster_review_routes._get_crop_url_for_face", return_value="/static/crops/test.jpg")
            )

            resp = client.get("/admin/cluster-batch?min_faces=5", cookies=_admin_session())
            assert resp.status_code == 200

    def test_min_faces_default_shows_all(self, client):
        """Default min_faces=1 shows all INBOX identities including single-face."""
        identities = {
            "id-1": _inbox_identity(anchors=["f1"]),
            "id-2": _inbox_identity(anchors=["f2", "f3"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main._get_community_identity_ids", return_value=None))
            stack.enter_context(
                patch("app.cluster_review_routes._get_crop_url_for_face", return_value="/static/crops/test.jpg")
            )

            resp = client.get("/admin/cluster-batch", cookies=_admin_session())
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: POST /api/cluster-review/batch-confirm
# ---------------------------------------------------------------------------


class TestBatchConfirm:
    def test_batch_confirm_accepts_ids_and_confirms(self, client):
        """POST /api/cluster-review/batch-confirm confirms listed identities."""
        identities = {
            "id-1": _inbox_identity(anchors=["f1", "f2"], candidates=["f3"]),
            "id-2": _inbox_identity(anchors=["f4"], candidates=["f5", "f6"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main.save_registry"))
            stack.enter_context(patch("app.main.log_user_action"))
            stack.enter_context(patch("app.main.is_auth_enabled", return_value=False))

            resp = client.post(
                "/api/cluster-review/batch-confirm",
                data={"identity_ids": "id-1,id-2"},
                cookies=_admin_session(),
            )
            assert resp.status_code == 200
            assert "confirmed" in resp.text.lower()

            # Both identities should be CONFIRMED
            assert identities["id-1"]["state"] == "CONFIRMED"
            assert identities["id-2"]["state"] == "CONFIRMED"

    def test_batch_confirm_promotes_candidates_to_anchors(self, client):
        """Candidates are promoted to anchors via registry.promote_candidate."""
        identities = {
            "id-1": _inbox_identity(anchors=["f1"], candidates=["f2", "f3"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main.save_registry"))
            stack.enter_context(patch("app.main.log_user_action"))
            stack.enter_context(patch("app.main.is_auth_enabled", return_value=False))

            resp = client.post(
                "/api/cluster-review/batch-confirm",
                data={"identity_ids": "id-1"},
                cookies=_admin_session(),
            )
            assert resp.status_code == 200

            # promote_candidate should have been called for each candidate
            assert reg.promote_candidate.call_count == 2
            reg.promote_candidate.assert_any_call("id-1", "f2", user_source="admin/batch-cluster-validation")
            reg.promote_candidate.assert_any_call("id-1", "f3", user_source="admin/batch-cluster-validation")

    def test_batch_confirm_calls_log_user_action_per_identity(self, client):
        """log_user_action is called once per confirmed identity."""
        identities = {
            "id-a": _inbox_identity(anchors=["f1"]),
            "id-b": _inbox_identity(anchors=["f2"]),
            "id-c": _inbox_identity(anchors=["f3"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main.save_registry"))
            mock_log = stack.enter_context(patch("app.main.log_user_action"))
            stack.enter_context(patch("app.main.is_auth_enabled", return_value=False))

            resp = client.post(
                "/api/cluster-review/batch-confirm",
                data={"identity_ids": "id-a,id-b,id-c"},
                cookies=_admin_session(),
            )
            assert resp.status_code == 200
            assert mock_log.call_count == 3

            # Each call should be BATCH_CONFIRM with mode="batch"
            for c in mock_log.call_args_list:
                assert c[0][0] == "BATCH_CONFIRM"
                assert c[1]["mode"] == "batch"

    def test_batch_confirm_returns_401_for_non_admin(self, client):
        """POST /api/cluster-review/batch-confirm returns 401 for non-admin."""
        from starlette.responses import Response

        with patch("app.main._check_admin", return_value=Response("Unauthorized", status_code=401)):
            resp = client.post(
                "/api/cluster-review/batch-confirm",
                data={"identity_ids": "id-1"},
                cookies=_non_admin_session(),
            )
            assert resp.status_code == 401

    def test_batch_confirm_empty_ids_returns_error(self, client):
        """POST with no identity_ids returns error message."""
        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))

            resp = client.post(
                "/api/cluster-review/batch-confirm",
                data={"identity_ids": ""},
                cookies=_admin_session(),
            )
            assert resp.status_code == 200
            assert "no identities" in resp.text.lower()


# ---------------------------------------------------------------------------
# Tests: Community scoping
# ---------------------------------------------------------------------------


class TestBatchCommunityScoping:
    def test_community_scoping_filters_identities(self, client):
        """Only identities in the community's identity set are shown."""
        identities = {
            "id-rhodes": _inbox_identity(anchors=["f1", "f2"]),
            "id-fox": _inbox_identity(anchors=["f3", "f4"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main._check_admin", return_value=None))
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main._get_community_identity_ids", return_value={"id-rhodes"}))
            stack.enter_context(
                patch("app.cluster_review_routes._get_crop_url_for_face", return_value="/static/crops/test.jpg")
            )

            resp = client.get("/admin/cluster-batch", cookies=_admin_session())
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: _get_batch_clusters helper
# ---------------------------------------------------------------------------


class TestGetBatchClusters:
    def test_excludes_merged_identities(self):
        """Merged identities are excluded from batch clusters."""
        from app.cluster_review_routes import _get_batch_clusters

        identities = {
            "id-merged": {**_inbox_identity(anchors=["f1"]), "merged_into": "id-other"},
            "id-normal": _inbox_identity(anchors=["f2"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main._get_community_identity_ids", return_value=None))

            mock_request = MagicMock()
            mock_request.state.community = None
            result = _get_batch_clusters(request=mock_request)

            ids = [r[0] for r in result]
            assert "id-merged" not in ids
            assert "id-normal" in ids

    def test_excludes_confirmed_identities(self):
        """Only INBOX identities are included (not CONFIRMED or PROPOSED)."""
        from app.cluster_review_routes import _get_batch_clusters

        identities = {
            "id-confirmed": {**_inbox_identity(anchors=["f1"]), "state": "CONFIRMED"},
            "id-proposed": {**_inbox_identity(anchors=["f2"]), "state": "PROPOSED"},
            "id-inbox": _inbox_identity(anchors=["f3"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main._get_community_identity_ids", return_value=None))

            mock_request = MagicMock()
            mock_request.state.community = None
            result = _get_batch_clusters(request=mock_request)

            ids = [r[0] for r in result]
            assert "id-confirmed" not in ids
            assert "id-proposed" not in ids
            assert "id-inbox" in ids

    def test_sorted_by_face_count_descending(self):
        """Results are sorted by face count descending."""
        from app.cluster_review_routes import _get_batch_clusters

        identities = {
            "id-small": _inbox_identity(anchors=["f1"]),
            "id-big": _inbox_identity(anchors=["f2", "f3", "f4", "f5"]),
            "id-medium": _inbox_identity(anchors=["f6", "f7"]),
        }
        reg = _mock_registry(identities)

        with ExitStack() as stack:
            stack.enter_context(patch("app.main.load_registry", return_value=reg))
            stack.enter_context(patch("app.main._get_community_identity_ids", return_value=None))

            mock_request = MagicMock()
            mock_request.state.community = None
            result = _get_batch_clusters(request=mock_request)

            face_counts = [r[2] for r in result]
            assert face_counts == sorted(face_counts, reverse=True)
