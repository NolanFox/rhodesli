"""Tests for cluster review + GEDCOM triage routes (AD-215, PRD-037 Phase 2)."""

import json
import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure app imports work
os.environ.setdefault("STORAGE_MODE", "local")


def _get_test_client():
    """Get a test client with admin session."""
    from starlette.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    return client


def _admin_session():
    """Return patches to simulate admin access."""
    return patch("app.cluster_review_routes._main_mod._check_admin", return_value=None)


def _mock_proposals(proposals=None):
    """Return a patch for _load_proposals."""
    if proposals is None:
        proposals = [
            {
                "source_identity_id": "src-001",
                "source_identity_name": "Unidentified Person 100",
                "source_state": "INBOX",
                "target_identity_id": "tgt-001",
                "target_identity_name": "Roland Fox",
                "face_id": "inbox_abc123",
                "distance": 0.75,
                "confidence": "VERY HIGH",
                "margin": 0.8,
                "ambiguous": False,
            },
            {
                "source_identity_id": "src-002",
                "source_identity_name": "Unidentified Person 200",
                "source_state": "INBOX",
                "target_identity_id": "tgt-001",
                "target_identity_name": "Roland Fox",
                "face_id": "inbox_def456",
                "distance": 1.02,
                "confidence": "HIGH",
                "margin": 0.3,
                "ambiguous": False,
            },
            {
                "source_identity_id": "src-003",
                "source_identity_name": "Unidentified Person 300",
                "source_state": "INBOX",
                "target_identity_id": "tgt-002",
                "target_identity_name": "Betty Capeluto Fox",
                "face_id": "inbox_ghi789",
                "distance": 0.92,
                "confidence": "HIGH",
                "margin": 0.5,
                "ambiguous": False,
            },
        ]
    return patch("app.cluster_review_routes._load_proposals", return_value=proposals)


def _mock_registry():
    """Return a patch for load_registry with test data."""
    mock_reg = MagicMock()
    mock_reg._identities = {
        "tgt-001": {
            "identity_id": "tgt-001",
            "name": "Roland Fox",
            "state": "CONFIRMED",
            "anchor_ids": [{"face_id": "anchor_roland_1"}, {"face_id": "anchor_roland_2"}],
            "candidate_ids": ["inbox_abc123", "inbox_def456"],
            "negative_ids": [],
            "gedcom_xref": "I001",
            "version_id": 1,
        },
        "tgt-002": {
            "identity_id": "tgt-002",
            "name": "Betty Capeluto Fox",
            "state": "CONFIRMED",
            "anchor_ids": [{"face_id": "anchor_betty_1"}],
            "candidate_ids": ["inbox_ghi789"],
            "negative_ids": [],
            "gedcom_xref": None,
            "version_id": 1,
        },
    }
    return patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg)


def _mock_crop_url():
    """Mock crop URL resolution."""
    return patch(
        "app.cluster_review_routes._get_crop_url_for_face",
        return_value="/static/crops/mock_face.jpg",
    )


def _mock_photo_registry():
    """Mock photo registry."""
    mock_pr = MagicMock()
    mock_pr.get_photo_for_face.return_value = "photo-001"
    return patch("app.cluster_review_routes._main_mod.load_photo_registry", return_value=mock_pr)


def _mock_face_data(face_data=None):
    """Mock face embedding payload."""
    if face_data is None:
        face_data = {}
    return patch("app.cluster_review_routes._main_mod.get_face_data", return_value=face_data)


def _mock_no_community_filter():
    """Disable community filtering so proposals aren't scoped by Supabase data."""
    return patch("app.cluster_review_routes._main_mod._get_community_identity_ids", return_value=None)


def _mock_active_learning_queue(payload=None):
    """Patch the offline active-learning queue payload."""
    if payload is None:
        payload = {
            "queue_run_id": "queue-1",
            "stats": {
                "queue_count": 2,
                "underrepresented_or_hard_share": 0.5,
                "first_batch_max_per_identity": 1,
            },
            "items": [
                {
                    "queue_item_id": "pair-1",
                    "pair_key": "inbox_abc123::anchor_roland_1",
                    "face_id_a": "inbox_abc123",
                    "face_id_b": "anchor_roland_1",
                    "source_identity_id": "src-001",
                    "source_identity_name": "Unidentified Person 100",
                    "target_identity_id": "tgt-001",
                    "target_identity_name": "Roland Fox",
                    "distance": 0.98,
                    "baseline_rank": 1,
                    "margin": 0.04,
                    "reasons": ["boundary_distance", "ambiguous_margin"],
                },
                {
                    "queue_item_id": "pair-2",
                    "pair_key": "inbox_ghi789::anchor_betty_1",
                    "face_id_a": "inbox_ghi789",
                    "face_id_b": "anchor_betty_1",
                    "source_identity_id": "src-003",
                    "source_identity_name": "Unidentified Person 300",
                    "target_identity_id": "tgt-002",
                    "target_identity_name": "Betty Capeluto Fox",
                    "distance": 1.01,
                    "baseline_rank": 2,
                    "margin": 0.03,
                    "reasons": ["tail_identity", "topk_alternative"],
                },
            ],
        }
    return patch("app.cluster_review_routes._active_learning_queue_payload", return_value=payload)


def _mock_recent_active_learning_labels(labels=None):
    """Patch recent active-learning labels."""
    if labels is None:
        labels = [
            {
                "pair_key": "inbox_abc123::anchor_roland_1",
                "face_id_a": "inbox_abc123",
                "face_id_b": "anchor_roland_1",
                "is_match": False,
                "active": True,
                "source_surface": "admin/upload-review-active-learning",
                "labeled_at": "2026-03-11T12:00:00+00:00",
            }
        ]
    return patch("app.cluster_review_routes._active_learning_labels", return_value=labels)


class TestUploadReviewPage:
    """Test the /admin/upload-review page."""

    def test_page_returns_200(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            resp = client.get("/admin/upload-review")
        assert resp.status_code == 200

    def test_page_shows_cluster_review_section(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            resp = client.get("/admin/upload-review")
        html = resp.text
        assert "Proposal Matches" in html or "Grouped Identities" in html
        # Proposals filtered to distance < 1.05 (Medium+ confidence)

    def test_page_shows_identity_groups(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            resp = client.get("/admin/upload-review")
        html = resp.text
        assert "Roland Fox" in html
        assert "Betty Capeluto Fox" in html

    def test_page_shows_confirm_reject_buttons(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            resp = client.get("/admin/upload-review")
        html = resp.text
        assert "Confirm" in html
        assert "Reject" in html
        assert "Confirm All" in html
        assert "Reject All" in html

    def test_page_shows_confidence_badges(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_no_community_filter())
            resp = client.get("/admin/upload-review")
        html = resp.text
        assert "Very High" in html  # distance 0.75
        assert "Medium" in html  # distance 1.02

    def test_page_shows_gedcom_triage_section(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            stack.enter_context(_mock_active_learning_queue())
            stack.enter_context(_mock_recent_active_learning_labels())
            resp = client.get("/admin/upload-review")
        html = resp.text
        assert "GEDCOM Triage" in html

    def test_page_shows_potential_review_groups(self):
        # Clear review groups cache to ensure mock is called (Session 124)
        from app.cluster_review_routes import invalidate_cluster_review_caches

        invalidate_cluster_review_caches()
        client = _get_test_client()
        unresolved_groups = [
            {
                "primary": {
                    "identity_id": "src-001",
                    "display_name": "Person 100",
                    "preview_crop_url": "/static/crops/mock_face.jpg",
                    "state": "INBOX",
                    "face_count": 3,
                },
                "members": [
                    {
                        "identity_id": "src-001",
                        "display_name": "Person 100",
                        "preview_crop_url": "/static/crops/mock_face.jpg",
                        "state": "INBOX",
                        "face_count": 3,
                        "best_match_distance": 0.64,
                        "is_primary": True,
                    },
                    {
                        "identity_id": "src-002",
                        "display_name": "Person 200",
                        "preview_crop_url": "/static/crops/mock_face.jpg",
                        "state": "SKIPPED",
                        "face_count": 1,
                        "best_match_distance": 0.79,
                        "is_primary": False,
                    },
                ],
                "hidden_member_count": 0,
                "size": 2,
                "best_distance": 0.64,
                "distance_range": (0.64, 0.79),
            }
        ]
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._build_unresolved_review_groups",
                    return_value=unresolved_groups,
                )
            )
            resp = client.get("/admin/upload-review")
        html = resp.text
        assert "Potential Review Groups" in html
        assert "Review Similar" in html
        assert "Open Queue" in html
        assert "Person 200" in html
        assert "Dismissed" in html

    def test_page_shows_empty_potential_review_groups_message(self):
        # Clear review groups cache to ensure mock is called (Session 124)
        from app.cluster_review_routes import invalidate_cluster_review_caches

        invalidate_cluster_review_caches()
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            stack.enter_context(
                patch(
                    "app.cluster_review_routes._build_unresolved_review_groups",
                    return_value=[],
                )
            )
            resp = client.get("/admin/upload-review")
        html = resp.text
        assert "No unresolved review groups surfaced right now." in html

    def test_page_shows_active_learning_section(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            stack.enter_context(_mock_active_learning_queue())
            stack.enter_context(_mock_recent_active_learning_labels())
            resp = client.get("/admin/upload-review")
        html = resp.text
        assert "Learning Queue" in html
        assert "Same Person" in html
        assert "Different People" in html
        assert "Recent Queue Labels" in html

    def test_page_requires_admin(self):
        client = _get_test_client()
        with patch(
            "app.cluster_review_routes._main_mod._check_admin",
            return_value=MagicMock(status_code=403),
        ):
            resp = client.get("/admin/upload-review")
        assert resp.status_code == 200  # FastHTML wraps the response

    def test_empty_proposals_shows_message(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals([]))
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            resp = client.get("/admin/upload-review")
        html = resp.text
        assert "No high-confidence proposal matches to review" in html

    def test_weakest_matches_shown_first(self):
        """AD-215: Weakest confidence (most likely false positive) at top."""
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_proposals())
            stack.enter_context(_mock_registry())
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_photo_registry())
            stack.enter_context(_mock_face_data())
            stack.enter_context(_mock_no_community_filter())
            resp = client.get("/admin/upload-review")
        html = resp.text
        # In Roland Fox's group, distance 1.02 should appear before 0.75
        pos_medium = html.find("Medium (1.02)")
        pos_very_high = html.find("Very High (0.75)")
        assert pos_medium < pos_very_high, "Weakest match should appear first"


class TestClusterReviewActions:
    """Test confirm/reject API endpoints."""

    def test_confirm_single_face(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            mock_registry = MagicMock()
            stack.enter_context(patch("app.cluster_review_routes.IdentityRegistry.load", return_value=mock_registry))
            stack.enter_context(patch("app.cluster_review_routes._main_mod._invalidate_all_caches"))
            resp = client.post("/api/cluster-review/confirm?identity_id=tgt-001&face_id=inbox_abc123")
        assert resp.status_code == 200
        assert "Confirmed" in resp.text
        mock_registry.promote_candidate.assert_called_once_with(
            "tgt-001", "inbox_abc123", user_source="admin/cluster-review"
        )

    def test_reject_single_face(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            mock_registry = MagicMock()
            mock_registry._identities = {
                "tgt-001": {
                    "anchor_ids": [{"face_id": "a1"}],
                    "candidate_ids": ["inbox_abc123"],
                }
            }
            stack.enter_context(patch("app.cluster_review_routes.IdentityRegistry.load", return_value=mock_registry))
            stack.enter_context(patch("app.cluster_review_routes._main_mod._invalidate_all_caches"))
            resp = client.post("/api/cluster-review/reject?identity_id=tgt-001&face_id=inbox_abc123")
        assert resp.status_code == 200
        assert "Rejected" in resp.text
        mock_registry.reject_candidate.assert_called_once()

    def test_confirm_all_faces(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            mock_registry = MagicMock()
            mock_registry._identities = {
                "tgt-001": {
                    "name": "Roland Fox",
                    "anchor_ids": [{"face_id": "a1"}],
                    "candidate_ids": ["inbox_abc123", "inbox_def456"],
                }
            }
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_registry))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            resp = client.post("/api/cluster-review/confirm-all?identity_id=tgt-001")
        assert resp.status_code == 200
        assert "confirmed for Roland Fox" in resp.text
        assert mock_registry.promote_candidate.call_count == 2

    def test_reject_all_faces(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            mock_registry = MagicMock()
            mock_registry._identities = {
                "tgt-001": {
                    "name": "Roland Fox",
                    "anchor_ids": [{"face_id": "a1"}],
                    "candidate_ids": ["inbox_abc123", "inbox_def456"],
                }
            }
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_registry))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            resp = client.post("/api/cluster-review/reject-all?identity_id=tgt-001")
        assert resp.status_code == 200
        assert "rejected for Roland Fox" in resp.text
        assert mock_registry.reject_candidate.call_count == 2

    def test_gedcom_panel_endpoint(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            mock_panel = MagicMock()
            stack.enter_context(
                patch("app.cluster_review_routes._main_mod._gedcom_link_panel", return_value=mock_panel)
            )
            resp = client.get("/api/cluster-review/gedcom-panel?identity_id=tgt-001&name=Roland+Fox")
        assert resp.status_code == 200

    def test_active_learning_same_endpoint(self):
        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes.record_active_learning_label"))
            stack.enter_context(patch("app.cluster_review_routes.get_supabase_client", return_value=None))
            resp = client.post(
                "/api/cluster-review/learn-same?face_id_a=inbox_abc123&face_id_b=anchor_roland_1"
                "&source_identity_id=src-001&target_identity_id=tgt-001&queue_item_id=pair-1&queue_run_id=queue-1"
            )
        assert resp.status_code == 200
        assert "Canonical identity state unchanged" in resp.text

    def test_active_learning_revert_endpoint(self):
        client = _get_test_client()
        reverted = {
            "pair_key": "inbox_abc123::anchor_roland_1",
            "active": False,
        }
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes.revert_active_learning_label", return_value=reverted))
            stack.enter_context(patch("app.cluster_review_routes.get_supabase_client", return_value=None))
            resp = client.post("/api/cluster-review/learn-revert?face_id_a=inbox_abc123&face_id_b=anchor_roland_1")
        assert resp.status_code == 200
        assert "Reverted" in resp.text


class TestConfidenceBadge:
    """Test confidence badge rendering."""

    def test_very_high_confidence(self):
        from app.cluster_review_routes import _confidence_badge

        badge = _confidence_badge(0.75)
        html = repr(badge)
        assert "Very High" in html
        assert "emerald" in html

    def test_high_confidence(self):
        from app.cluster_review_routes import _confidence_badge

        badge = _confidence_badge(0.90)
        html = repr(badge)
        assert "High" in html
        assert "indigo" in html or "blue" in html

    def test_medium_confidence(self):
        from app.cluster_review_routes import _confidence_badge

        badge = _confidence_badge(1.00)
        html = repr(badge)
        assert "Medium" in html
        assert "yellow" in html

    def test_low_confidence(self):
        from app.cluster_review_routes import _confidence_badge

        badge = _confidence_badge(1.10)
        html = repr(badge)
        assert "Low" in html
        assert "red" in html
