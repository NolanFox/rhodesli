"""Tests for cluster_review_routes.py — community scoping + nav prefix.

COMMUNITY-016: GEDCOM triage filters by community, person links use community prefix,
unlinked identities sort before linked ones.
"""

import json
import os
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("STORAGE_MODE", "local")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_test_client():
    from starlette.testclient import TestClient

    from app.main import app

    return TestClient(app)


def _admin_session():
    return patch("app.cluster_review_routes._main_mod._check_admin", return_value=None)


def _mock_no_proposals():
    return patch("app.cluster_review_routes._load_proposals", return_value=[])


def _mock_crop_url():
    return patch(
        "app.cluster_review_routes._get_crop_url_for_face",
        return_value="/static/crops/mock.jpg",
    )


def _make_identity(name, state="CONFIRMED", anchor_ids=None, gedcom_xref=None, n_candidates=3):
    """Create identity with enough faces (anchor + candidates >= 3)."""
    return {
        "identity_id": "placeholder",
        "name": name,
        "state": state,
        "anchor_ids": anchor_ids or ["face_a"],
        "candidate_ids": [f"face_c{i}" for i in range(n_candidates)],
        "negative_ids": [],
        "gedcom_xref": gedcom_xref,
        "version_id": 1,
    }


def _mock_registry(identities_dict):
    mock_reg = MagicMock()
    mock_reg._identities = identities_dict
    mock_reg.get = lambda iid: identities_dict.get(iid)
    return patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg)


def _mock_community_ids(ids_set):
    """Mock _get_community_identity_ids to return a specific set."""
    return patch(
        "app.cluster_review_routes._main_mod._get_community_identity_ids",
        return_value=ids_set,
    )


def _mock_community_lookup(community_data):
    """Mock the Supabase community lookup used by CommunityMiddleware."""
    return patch(
        "app.supabase_data.get_community_by_slug",
        return_value=community_data,
    )


def _mock_community_url_prefix():
    """Mock community_url_prefix — the real function works fine, but ensure it's called."""
    # Use the real function — it's simple enough
    return patch(
        "app.cluster_review_routes._main_mod.community_url_prefix",
        side_effect=lambda slug: "" if not slug or slug == "rhodes" else f"/c/{slug}",
    )


# ---------------------------------------------------------------------------
# Tests: GEDCOM Triage Community Filtering
# ---------------------------------------------------------------------------


class TestGedcomTriageCommunityFiltering:
    """GEDCOM triage should only show identities belonging to the current community."""

    def test_gedcom_triage_filters_by_community(self):
        """When community context exists, only community identities appear in triage."""
        identities = {
            "id-fox-1": _make_identity("Charlie Fox"),
            "id-rhodes-1": _make_identity("Moise Capeluto"),
        }
        fox_community = {"id": "fox-uuid", "slug": "fox-family", "name": "Fox Family"}

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_no_proposals())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids({"id-fox-1"}))
            stack.enter_context(_mock_community_lookup(fox_community))
            stack.enter_context(_mock_community_url_prefix())
            resp = client.get("/c/fox-family/admin/upload-review")

        assert resp.status_code == 200
        html = resp.text
        assert "Charlie Fox" in html
        assert "Moise Capeluto" not in html

    def test_gedcom_triage_shows_all_without_community(self):
        """Without community context, all identities appear."""
        identities = {
            "id-fox-1": _make_identity("Charlie Fox"),
            "id-rhodes-1": _make_identity("Moise Capeluto"),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_no_proposals())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            stack.enter_context(_mock_community_lookup(None))
            stack.enter_context(_mock_community_url_prefix())
            resp = client.get("/admin/upload-review")

        assert resp.status_code == 200
        html = resp.text
        assert "Charlie Fox" in html
        assert "Moise Capeluto" in html


# ---------------------------------------------------------------------------
# Tests: Person Links Use Community Prefix
# ---------------------------------------------------------------------------


class TestPersonLinksUseCommunityPrefix:
    """Person links in GEDCOM triage and cluster review should use nav_prefix."""

    def test_gedcom_triage_links_have_community_prefix(self):
        """Person links in GEDCOM triage use /c/fox-family prefix."""
        identities = {
            "id-fox-1": _make_identity("Charlie Fox"),
        }
        fox_community = {"id": "fox-uuid", "slug": "fox-family", "name": "Fox Family"}

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_no_proposals())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids({"id-fox-1"}))
            stack.enter_context(_mock_community_lookup(fox_community))
            stack.enter_context(_mock_community_url_prefix())
            resp = client.get("/c/fox-family/admin/upload-review")

        html = resp.text
        assert "/c/fox-family/person/id-fox-1" in html

    def test_rhodes_links_have_no_prefix(self):
        """Person links for Rhodes use bare /person/ URLs."""
        identities = {
            "id-rhodes-1": _make_identity("Moise Capeluto"),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_no_proposals())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            stack.enter_context(_mock_community_lookup(None))
            stack.enter_context(_mock_community_url_prefix())
            resp = client.get("/admin/upload-review")

        html = resp.text
        assert "/person/id-rhodes-1" in html
        # Make sure there's no /c/ prefix for rhodes
        assert '"/c/' not in html

    def test_cluster_review_links_have_community_prefix(self):
        """Person links in cluster review section use community prefix."""
        proposals = [
            {
                "source_identity_id": "id-fox-src",
                "source_identity_name": "Unknown Face",
                "source_state": "INBOX",
                "target_identity_id": "id-fox-1",
                "target_identity_name": "Charlie Fox",
                "face_id": "inbox_abc123",
                "distance": 0.90,
                "confidence": "HIGH",
                "margin": 0.5,
                "ambiguous": False,
            }
        ]

        identities = {
            "id-fox-1": _make_identity("Charlie Fox"),
            "id-fox-src": _make_identity("Unknown Face", state="INBOX"),
        }
        fox_community = {"id": "fox-uuid", "slug": "fox-family", "name": "Fox Family"}

        mock_pr = MagicMock()
        mock_pr.get_photo_for_face.return_value = None

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._load_proposals", return_value=proposals))
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids({"id-fox-1", "id-fox-src"}))
            stack.enter_context(_mock_community_lookup(fox_community))
            stack.enter_context(_mock_community_url_prefix())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_photo_registry", return_value=mock_pr))
            resp = client.get("/c/fox-family/admin/upload-review")

        html = resp.text
        assert "/c/fox-family/person/id-fox-1" in html


# ---------------------------------------------------------------------------
# Tests: GEDCOM Triage Sorting
# ---------------------------------------------------------------------------


class TestGedcomTriageSorting:
    """Unlinked identities should sort before linked ones."""

    def test_unlinked_sorts_before_linked(self):
        """Identities without gedcom_xref appear before those with it."""
        identities = {
            "id-linked": _make_identity("Linked Person", gedcom_xref="@I123@"),
            "id-unlinked": _make_identity("Unlinked Person"),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_no_proposals())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            stack.enter_context(_mock_community_lookup(None))
            stack.enter_context(_mock_community_url_prefix())
            resp = client.get("/admin/upload-review")

        html = resp.text
        unlinked_pos = html.index("Unlinked Person")
        linked_pos = html.index("Linked Person")
        assert unlinked_pos < linked_pos, "Unlinked identity should appear before linked identity"

    def test_within_unlinked_sort_by_face_count(self):
        """Among unlinked identities, higher face count comes first."""
        identities = {
            "id-few": _make_identity("Few Faces", n_candidates=2),  # 3 total
            "id-many": _make_identity("Many Faces", n_candidates=5),  # 6 total
        }

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_no_proposals())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            stack.enter_context(_mock_community_lookup(None))
            stack.enter_context(_mock_community_url_prefix())
            resp = client.get("/admin/upload-review")

        html = resp.text
        many_pos = html.index("Many Faces")
        few_pos = html.index("Few Faces")
        assert many_pos < few_pos, "Higher face count should appear first among unlinked"
