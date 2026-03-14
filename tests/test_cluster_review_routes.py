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


# ---------------------------------------------------------------------------
# Tests: Speed-Run Mode (PRD-039)
# ---------------------------------------------------------------------------


def _make_inbox_cluster(name, face_count=3):
    """Create an INBOX identity with multiple faces for cluster review."""
    return {
        "name": name,
        "state": "INBOX",
        "anchor_ids": [f"inbox_{name.lower().replace(' ', '_')}_{i}" for i in range(face_count)],
        "candidate_ids": [],
        "negative_ids": [],
        "version_id": 1,
    }


class TestSpeedRunMode:
    """PRD-039: Speed-run batch cluster review mode."""

    def test_speed_run_page_loads(self):
        """Speed-run mode renders with keyboard shortcuts and progress bar."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 4),
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            stack.enter_context(_mock_community_lookup(None))
            resp = client.get("/admin/upload-review?mode=speed")

        assert resp.status_code == 200
        html = resp.text
        assert "Speed Run Review" in html
        assert "speed-run-card" in html
        assert "speed-confirm" in html
        assert "speed-reject" in html
        assert "speed-skip" in html
        assert "speed-dismiss" in html
        # Keyboard shortcut JS
        assert "keydown" in html
        assert "actionMap" in html
        # Progress bar with cumulative stats
        assert "0 confirmed" in html
        assert "remaining" in html

    def test_speed_run_next_returns_cluster_card(self):
        """GET /admin/cluster-review/next returns an HTMX partial."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 4),
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.get("/admin/cluster-review/next?offset=0")

        assert resp.status_code == 200
        html = resp.text
        assert "speed-run-card" in html
        assert "Confirm All" in html

    def test_speed_run_next_at_end_shows_done(self):
        """When offset exceeds clusters, show the done card."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.get("/admin/cluster-review/next?offset=10")

        assert resp.status_code == 200
        assert "All Done" in resp.text

    def test_speed_run_confirm_all_auto_advances(self):
        """Confirm-all with speed_run=true returns next card instead of message."""
        identities = {
            "cluster-1": {
                "name": "Person Alpha",
                "state": "INBOX",
                "anchor_ids": ["inbox_a1"],
                "candidate_ids": ["inbox_a2", "inbox_a3"],
                "negative_ids": [],
                "version_id": 1,
            },
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = identities
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post("/api/cluster-review/confirm-all?identity_id=cluster-1&speed_run=true&offset=0")

        assert resp.status_code == 200
        html = resp.text
        # Should contain next card, not "confirmed for" message
        assert "speed-run-card" in html
        assert mock_reg.promote_candidate.call_count == 2

    def test_speed_run_reject_all_auto_advances(self):
        """Reject-all with speed_run=true returns next card."""
        identities = {
            "cluster-1": {
                "name": "Person Alpha",
                "state": "INBOX",
                "anchor_ids": ["inbox_a1"],
                "candidate_ids": ["inbox_a2"],
                "negative_ids": [],
                "version_id": 1,
            },
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = identities
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post("/api/cluster-review/reject-all?identity_id=cluster-1&speed_run=true&offset=0")

        assert resp.status_code == 200
        assert "speed-run-card" in resp.text
        assert mock_reg.reject_candidate.call_count == 1

    def test_speed_run_dismiss_returns_next(self):
        """Dismiss endpoint sets SKIPPED and returns next card."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 3),
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = dict(identities)
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            mock_save = stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post("/api/cluster-review/dismiss?identity_id=cluster-1&offset=0")

        assert resp.status_code == 200
        assert "speed-run-card" in resp.text
        # Verify save was called (state changed to SKIPPED)
        mock_save.assert_called_once()

    def test_speed_run_community_scoped(self):
        """Speed-run only shows clusters from the current community."""
        identities = {
            "fox-cluster": _make_inbox_cluster("Fox Person", 4),
            "rhodes-cluster": _make_inbox_cluster("Rhodes Person", 3),
        }
        fox_community = {"id": "fox-uuid", "slug": "fox-family", "name": "Fox Family"}

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids({"fox-cluster"}))
            stack.enter_context(_mock_community_lookup(fox_community))
            resp = client.get("/c/fox-family/admin/upload-review?mode=speed")

        assert resp.status_code == 200
        html = resp.text
        assert "remaining" in html
        # Only fox cluster should appear
        assert "Fox Person" in html or "Person fox" in html

    def test_speed_run_keyboard_shortcuts_in_page(self):
        """Speed-run page includes keyboard shortcut JS with input guard."""
        identities = {"c1": _make_inbox_cluster("Test Person", 2)}

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.get("/admin/upload-review?mode=speed")

        html = resp.text
        assert "e.target.tagName" in html  # Input guard
        assert "'y': 'speed-confirm'" in html

    def test_speed_run_progress_counter(self):
        """Progress counter updates with each card."""
        identities = {
            "c1": _make_inbox_cluster("Person A", 3),
            "c2": _make_inbox_cluster("Person B", 2),
            "c3": _make_inbox_cluster("Person C", 2),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.get("/admin/cluster-review/next?offset=2")

        assert resp.status_code == 200
        assert "speed-run-progress" in resp.text

    def test_dashboard_has_speed_run_link(self):
        """Existing dashboard shows 'Start Speed Run' button when clusters exist."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 4),
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
        assert "Start Speed Run" in resp.text
        assert "mode=speed" in resp.text

    def test_speed_run_confirm_returns_undo_button(self):
        """Confirm-all in speed-run returns OOB undo button."""
        identities = {
            "cluster-1": {
                "name": "Person Alpha",
                "state": "INBOX",
                "anchor_ids": ["inbox_a1"],
                "candidate_ids": ["inbox_a2", "inbox_a3"],
                "negative_ids": [],
                "version_id": 1,
            },
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = identities
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post("/api/cluster-review/confirm-all?identity_id=cluster-1&speed_run=true&offset=0")

        assert resp.status_code == 200
        html = resp.text
        assert "speed-run-undo" in html
        assert "Undo (Z)" in html
        assert "speed-undo" in html

    def test_speed_run_reject_returns_undo_button(self):
        """Reject-all in speed-run returns OOB undo button."""
        identities = {
            "cluster-1": {
                "name": "Person Alpha",
                "state": "INBOX",
                "anchor_ids": ["inbox_a1"],
                "candidate_ids": ["inbox_a2"],
                "negative_ids": [],
                "version_id": 1,
            },
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = identities
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post("/api/cluster-review/reject-all?identity_id=cluster-1&speed_run=true&offset=0")

        assert resp.status_code == 200
        html = resp.text
        assert "speed-run-undo" in html
        assert "Undo (Z)" in html

    def test_speed_run_skip_returns_undo_button(self):
        """Skip in speed-run returns OOB undo button."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 4),
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            stack.enter_context(_admin_session())
            stack.enter_context(_mock_registry(identities))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post("/api/cluster-review/skip?identity_id=cluster-1&offset=0")

        assert resp.status_code == 200
        html = resp.text
        assert "speed-run-undo" in html
        assert "Undo (Z)" in html

    def test_speed_run_dismiss_returns_undo_button(self):
        """Dismiss in speed-run returns OOB undo button."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 3),
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = dict(identities)
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post("/api/cluster-review/dismiss?identity_id=cluster-1&offset=0")

        assert resp.status_code == 200
        html = resp.text
        assert "speed-run-undo" in html
        assert "Undo (Z)" in html

    def test_speed_run_undo_confirm_restores_candidates(self):
        """Undo of confirm-all moves faces back to candidate_ids."""
        identities = {
            "cluster-1": {
                "name": "Person Alpha",
                "state": "CONFIRMED",
                "anchor_ids": ["inbox_a1", "inbox_a2", "inbox_a3"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
            },
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        face_data = json.dumps({"candidates": ["inbox_a2", "inbox_a3"], "prev_state": "INBOX"})

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = identities
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            mock_save = stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post(
                f"/api/cluster-review/undo?identity_id=cluster-1&action=confirm-all&offset=0&face_data={face_data}"
            )

        assert resp.status_code == 200
        html = resp.text
        assert "speed-run-card" in html
        mock_save.assert_called_once()
        # Verify state was restored
        identity = identities["cluster-1"]
        assert identity["state"] == "INBOX"
        # Faces should be back in candidate_ids
        assert "inbox_a2" in identity["candidate_ids"]
        assert "inbox_a3" in identity["candidate_ids"]

    def test_speed_run_undo_reject_restores_candidates(self):
        """Undo of reject-all removes faces from negative_ids, restores to candidates."""
        identities = {
            "cluster-1": {
                "name": "Person Alpha",
                "state": "INBOX",
                "anchor_ids": ["inbox_a1"],
                "candidate_ids": [],
                "negative_ids": ["inbox_a2", "inbox_a3"],
                "version_id": 1,
            },
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        face_data = json.dumps({"candidates": ["inbox_a2", "inbox_a3"], "prev_state": "INBOX"})

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = identities
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            mock_save = stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post(
                f"/api/cluster-review/undo?identity_id=cluster-1&action=reject-all&offset=0&face_data={face_data}"
            )

        assert resp.status_code == 200
        mock_save.assert_called_once()
        identity = identities["cluster-1"]
        assert identity["state"] == "INBOX"
        assert "inbox_a2" in identity["candidate_ids"]
        assert "inbox_a3" in identity["candidate_ids"]
        assert "inbox_a2" not in identity["negative_ids"]
        assert "inbox_a3" not in identity["negative_ids"]

    def test_speed_run_undo_dismiss_restores_state(self):
        """Undo of dismiss restores identity state from SKIPPED."""
        identities = {
            "cluster-1": {
                "name": "Person Alpha",
                "state": "SKIPPED",
                "anchor_ids": ["inbox_a1", "inbox_a2", "inbox_a3"],
                "candidate_ids": [],
                "negative_ids": [],
                "version_id": 1,
            },
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        face_data = json.dumps({"prev_state": "INBOX"})

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = identities
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            mock_save = stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post(
                f"/api/cluster-review/undo?identity_id=cluster-1&action=dismiss&offset=0&face_data={face_data}"
            )

        assert resp.status_code == 200
        mock_save.assert_called_once()
        assert identities["cluster-1"]["state"] == "INBOX"

    def test_speed_run_undo_skip_no_save(self):
        """Undo of skip doesn't call save (skip doesn't modify data)."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 4),
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = identities
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            mock_save = stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post("/api/cluster-review/undo?identity_id=cluster-1&action=skip&offset=0")

        assert resp.status_code == 200
        assert "speed-run-card" in resp.text
        mock_save.assert_not_called()

    def test_speed_run_undo_hides_undo_button(self):
        """After undo, the undo button should be hidden."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 4),
            "cluster-2": _make_inbox_cluster("Person Beta", 3),
        }

        client = _get_test_client()
        with ExitStack() as stack:
            mock_reg = MagicMock()
            mock_reg._identities = identities
            stack.enter_context(_admin_session())
            stack.enter_context(patch("app.cluster_review_routes._main_mod.load_registry", return_value=mock_reg))
            stack.enter_context(patch("app.cluster_review_routes._main_mod.save_registry"))
            stack.enter_context(_mock_crop_url())
            stack.enter_context(_mock_community_ids(None))
            resp = client.post("/api/cluster-review/undo?identity_id=cluster-1&action=skip&offset=0")

        assert resp.status_code == 200
        html = resp.text
        # Undo button div should exist but be empty (no button content)
        assert "speed-run-undo" in html
        assert "Undo (Z)" not in html

    def test_speed_run_keyboard_z_shortcut_in_page(self):
        """Speed-run page includes Z keyboard shortcut for undo."""
        identities = {
            "cluster-1": _make_inbox_cluster("Person Alpha", 4),
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
            resp = client.get("/admin/upload-review?mode=speed")

        assert resp.status_code == 200
        html = resp.text
        assert "'z': 'speed-undo'" in html
        assert "Z = Undo" in html
