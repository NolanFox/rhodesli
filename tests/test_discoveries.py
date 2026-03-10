"""Tests for the Discovery Notification System.

Discoveries = INBOX/PROPOSED faces with high-confidence matches to CONFIRMED identities.
The system surfaces these for one-click admin resolution.
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_identity(identity_id, name, state, anchor_ids=None, candidate_ids=None, negative_ids=None):
    """Build a minimal identity dict matching the schema."""
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": anchor_ids or [],
        "candidate_ids": candidate_ids or [],
        "negative_ids": negative_ids or [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _make_registry_mock(identities):
    """Build a registry mock from a list of identity dicts."""
    registry = MagicMock()

    def list_identities(state=None):
        if state is None:
            return identities
        return [i for i in identities if i["state"] == state.value]

    def get_identity(iid):
        for i in identities:
            if i["identity_id"] == iid:
                return i
        raise KeyError(iid)

    registry.list_identities = list_identities
    registry.get_identity = get_identity
    registry.list_proposed_matches = MagicMock(return_value=[])
    registry._identities = {i["identity_id"]: i for i in identities}
    return registry


# ---------------------------------------------------------------------------
# Test: _count_discoveries function
# ---------------------------------------------------------------------------


class TestCountDiscoveries:
    """Tests for the _count_discoveries function."""

    def test_function_exists(self):
        """_count_discoveries is importable from app.main."""
        from app.main import _count_discoveries

        assert callable(_count_discoveries)

    def test_returns_zero_when_no_confirmed(self):
        """No discoveries when there are no confirmed identities."""
        from app.main import _count_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("id1", "Person A", "INBOX", candidate_ids=["face1"]),
            _make_identity("id2", "Person B", "PROPOSED", candidate_ids=["face2"]),
        ]
        registry = _make_registry_mock(identities)

        # No CONFIRMED identities -> early return with empty list
        count = _count_discoveries(registry)
        assert count == 0

    def test_returns_zero_when_no_unreviewed(self):
        """No discoveries when there are no INBOX/PROPOSED identities."""
        from app.main import _count_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("id1", "Person A", "CONFIRMED", anchor_ids=["face1"]),
        ]
        registry = _make_registry_mock(identities)

        count = _count_discoveries(registry)
        assert count == 0

    def test_counts_high_confidence_match_via_proposal(self):
        """Counts a discovery when a proposal matches a confirmed identity."""
        from app.main import _count_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        proposal = {
            "target_identity_id": "conf1",
            "target_name": "Known Person",
            "distance": 0.7,
            "confidence": "HIGH",
        }

        with (
            patch("app.main._get_identities_with_proposals", return_value={"inbox1"}),
            patch("app.main._get_best_proposal_for_identity", return_value=proposal),
        ):
            count = _count_discoveries(registry)

        assert count == 1

    def test_ignores_low_confidence_match(self):
        """Does not count matches with distance >= threshold."""
        from app.main import _count_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        # Distance 1.5 is too far — not a discovery
        proposal = {
            "target_identity_id": "conf1",
            "target_name": "Known Person",
            "distance": 1.5,
            "confidence": "LOW",
        }

        with (
            patch("app.main._get_identities_with_proposals", return_value={"inbox1"}),
            patch("app.main._get_best_proposal_for_identity", return_value=proposal),
        ):
            count = _count_discoveries(registry)

        assert count == 0

    def test_includes_borderline_high_match(self):
        """Borderline matches at distance 1.01 are included (AD-172 widened threshold)."""
        from app.main import _count_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        # Distance 1.01 is within threshold (1.30)
        proposal = {
            "target_identity_id": "conf1",
            "target_name": "Known Person",
            "distance": 1.01,
            "confidence": "MEDIUM",
        }

        with (
            patch("app.main._get_identities_with_proposals", return_value={"inbox1"}),
            patch("app.main._get_best_proposal_for_identity", return_value=proposal),
        ):
            count = _count_discoveries(registry)

        assert count == 1

    def test_no_discovery_without_proposal(self):
        """Identity without a proposal does not appear in discoveries."""
        from app.main import _count_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        # No proposals exist for inbox1
        with (
            patch("app.main._get_identities_with_proposals", return_value=set()),
        ):
            count = _count_discoveries(registry)

        assert count == 0


class TestComputeDiscoveries:
    """Tests for the _compute_discoveries function."""

    def test_function_exists(self):
        """_compute_discoveries is importable from app.main."""
        from app.main import _compute_discoveries

        assert callable(_compute_discoveries)

    def test_returns_list(self):
        """_compute_discoveries returns a list."""
        from app.main import _compute_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [_make_identity("id1", "Person A", "CONFIRMED", anchor_ids=["f1"])]
        registry = _make_registry_mock(identities)
        result = _compute_discoveries(registry)
        assert isinstance(result, list)

    def test_discovery_has_required_fields(self):
        """Each discovery dict has the required fields."""
        from app.main import _compute_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        proposal = {
            "target_identity_id": "conf1",
            "target_name": "Known Person",
            "distance": 0.5,
            "confidence": "VERY HIGH",
        }

        with (
            patch("app.main._get_identities_with_proposals", return_value={"inbox1"}),
            patch("app.main._get_best_proposal_for_identity", return_value=proposal),
        ):
            result = _compute_discoveries(registry)

        assert len(result) == 1
        d = result[0]
        assert "source_id" in d
        assert "source_name" in d
        assert "target_id" in d
        assert "target_name" in d
        assert "distance" in d
        assert "confidence" in d
        assert d["source_id"] == "inbox1"
        assert d["target_id"] == "conf1"
        assert d["distance"] == 0.5
        assert d["confidence"] in ("VERY HIGH", "HIGH")  # AD-200: unified scoring

    def test_discoveries_sorted_by_distance(self):
        """Discoveries are sorted by distance ascending (best first)."""
        from app.main import _compute_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face1"]),
            _make_identity("inbox2", "Unknown 2", "PROPOSED", candidate_ids=["face2"]),
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["faceC"]),
        ]
        registry = _make_registry_mock(identities)

        # inbox2 is closer than inbox1 — both have proposals
        proposal1 = {
            "target_identity_id": "conf1",
            "target_name": "Known Person",
            "distance": 0.9,
            "confidence": "MEDIUM",
        }
        proposal2 = {
            "target_identity_id": "conf1",
            "target_name": "Known Person",
            "distance": 0.6,
            "confidence": "HIGH",
        }

        def mock_best_proposal(iid):
            if iid == "inbox1":
                return proposal1
            if iid == "inbox2":
                return proposal2
            return None

        with (
            patch("app.main._get_identities_with_proposals", return_value={"inbox1", "inbox2"}),
            patch("app.main._get_best_proposal_for_identity", side_effect=mock_best_proposal),
        ):
            result = _compute_discoveries(registry)

        assert len(result) == 2
        assert result[0]["distance"] < result[1]["distance"]
        assert result[0]["source_id"] == "inbox2"

    def test_uses_proposals_when_available(self):
        """Uses existing proposals instead of batch computation when available."""
        from app.main import _compute_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face1"]),
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["faceC"]),
        ]
        registry = _make_registry_mock(identities)

        proposal = {
            "target_identity_id": "conf1",
            "target_name": "Known Person",
            "distance": 0.75,
            "confidence": "HIGH",
        }

        with (
            patch("app.main._get_identities_with_proposals", return_value={"inbox1"}),
            patch("app.main._get_best_proposal_for_identity", return_value=proposal),
        ):
            result = _compute_discoveries(registry)

        assert len(result) == 1
        assert result[0]["distance"] == 0.75

    def test_skips_proposal_to_non_confirmed(self):
        """Proposal pointing to a non-confirmed identity is not a discovery."""
        from app.main import _compute_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face1"]),
            _make_identity("prop1", "Proposed Person", "PROPOSED", candidate_ids=["faceP"]),
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["faceC"]),
        ]
        registry = _make_registry_mock(identities)

        # Proposal points to prop1 (PROPOSED), not conf1 (CONFIRMED)
        proposal = {
            "target_identity_id": "prop1",
            "target_name": "Proposed Person",
            "distance": 0.5,
            "confidence": "VERY HIGH",
        }

        with (
            patch("app.main._get_identities_with_proposals", return_value={"inbox1"}),
            patch("app.main._get_best_proposal_for_identity", return_value=proposal),
        ):
            result = _compute_discoveries(registry)

        assert len(result) == 0


# ---------------------------------------------------------------------------
# Test: Sidebar includes discovery count
# ---------------------------------------------------------------------------


class TestSidebarDiscoveries:
    """Tests that the sidebar shows the Discoveries link with count."""

    def test_sidebar_has_discoveries_link(self):
        """Sidebar navigation includes a Discoveries link."""
        from app.main import sidebar
        from fastcore.xml import to_xml

        user = MagicMock()
        user.is_admin = True
        user.email = "admin@test.com"

        counts = {
            "to_review": 5,
            "confirmed": 10,
            "skipped": 3,
            "rejected": 1,
            "photos": 20,
            "pending_uploads": 0,
            "proposals": 2,
            "pending_annotations": 0,
            "discoveries": 3,
        }

        html = to_xml(sidebar(counts=counts, current_section="discoveries", user=user))
        assert 'href="/discoveries"' in html
        assert "Discoveries" in html

    def test_sidebar_shows_discovery_count(self):
        """Sidebar displays the correct discovery count badge."""
        from app.main import sidebar
        from fastcore.xml import to_xml

        user = MagicMock()
        user.is_admin = True
        user.email = "admin@test.com"

        counts = {
            "to_review": 5,
            "confirmed": 10,
            "skipped": 3,
            "rejected": 1,
            "photos": 20,
            "pending_uploads": 0,
            "proposals": 2,
            "pending_annotations": 0,
            "discoveries": 7,
        }

        html = to_xml(sidebar(counts=counts, current_section="to_review", user=user))
        # The count 7 should appear in the sidebar
        assert ">7<" in html or 'title="Discoveries (7)"' in html

    def test_sidebar_discovery_zero_still_shows(self):
        """Sidebar shows Discoveries link even when count is 0."""
        from app.main import sidebar
        from fastcore.xml import to_xml

        user = MagicMock()
        user.is_admin = False
        user.email = "user@test.com"

        counts = {
            "to_review": 5,
            "confirmed": 10,
            "skipped": 3,
            "rejected": 1,
            "photos": 20,
            "pending_uploads": 0,
            "proposals": 2,
            "pending_annotations": 0,
            "discoveries": 0,
        }

        html = to_xml(sidebar(counts=counts, current_section="to_review", user=user))
        assert 'href="/discoveries"' in html

    def test_sidebar_counts_includes_discoveries_key(self):
        """_compute_sidebar_counts returns a 'discoveries' key."""
        from app.main import _compute_sidebar_counts, load_registry
        import app.main as main_module

        registry = load_registry()

        with (
            patch.object(main_module, "_discovery_cache", []),
            patch.object(main_module, "_discovery_cache_key", (0, 0, 0)),
        ):
            counts = _compute_sidebar_counts(registry)

        assert "discoveries" in counts
        assert isinstance(counts["discoveries"], int)


# ---------------------------------------------------------------------------
# Test: /discoveries route
# ---------------------------------------------------------------------------


class TestDiscoveriesRoute:
    """Tests for the /discoveries page route."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def test_discoveries_route_returns_200_for_admin(self, client):
        """/discoveries returns 200 when accessed by admin."""
        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")),
            patch("app.main._count_discoveries", return_value=0),
            patch("app.main._compute_discoveries", return_value=[]),
        ):
            response = client.get("/discoveries")

        assert response.status_code == 200
        assert "Discoveries" in response.text

    def test_discoveries_route_requires_admin(self, client):
        """/discoveries returns 401 when not admin."""
        from app.main import Response

        with patch("app.main._check_admin", return_value=Response("Unauthorized", status_code=401)):
            response = client.get("/discoveries")

        assert response.status_code == 401


class TestApiDiscoveriesRoute:
    """Tests for the /api/discoveries HTMX endpoint."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def test_api_discoveries_empty_shows_message(self, client):
        """/api/discoveries shows 'all discoveries reviewed' when no discoveries."""
        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=[]),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
        ):
            response = client.get("/api/discoveries")

        assert response.status_code == 200
        assert "All discoveries reviewed" in response.text

    def test_api_discoveries_renders_cards(self, client):
        """Cards are rendered for each discovery match."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Unknown 1",
                "target_id": "conf1",
                "target_name": "Known Person",
                "distance": 0.6,
                "confidence": "VERY HIGH",
            }
        ]

        source_identity = _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face_inbox1"])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_photo_registry"),
            patch("app.main._compute_co_occurrence", return_value=0),
            patch("app.main.load_registry", return_value=_make_registry_mock([source_identity])),
        ):
            response = client.get("/api/discoveries")

        assert response.status_code == 200
        html = response.text
        assert "Known Person" in html
        assert "discovery-card-inbox1" in html
        # Confirm button present
        assert "/api/face/tag" in html
        # Reject button present
        assert "/api/discovery/reject" in html

    def test_api_discoveries_shows_confidence_tier_label(self, client):
        """Discovery cards show tier labels instead of misleading percentages."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Unknown 1",
                "target_id": "conf1",
                "target_name": "Known Person",
                "distance": 0.91,
                "confidence": "HIGH",
            }
        ]
        source_identity = _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face_inbox1"])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_photo_registry"),
            patch("app.main._compute_co_occurrence", return_value=0),
            patch("app.main.load_registry", return_value=_make_registry_mock([source_identity])),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        # Should show "Good match" tier label (distance 0.91 is in 0.80-1.00 range)
        assert "Good match" in html
        # Tier label is shown via data-testid
        assert 'data-testid="discovery-confidence-label"' in html
        # Should NOT show raw percentages — tier labels replace them
        assert "Discovery:" not in html

    def test_api_discoveries_source_face_is_clickable(self, client):
        """Source face image and name are wrapped in navigation links."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Unknown 1",
                "target_id": "conf1",
                "target_name": "Known Person",
                "distance": 0.6,
                "confidence": "VERY HIGH",
            }
        ]
        source_identity = _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face_inbox1"])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_photo_registry"),
            patch("app.main._compute_co_occurrence", return_value=0),
            patch("app.main.load_registry", return_value=_make_registry_mock([source_identity])),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        # Source face should link to person page
        assert 'href="/person/inbox1"' in html
        # Target face should also link to person page
        assert 'href="/person/conf1"' in html

    def test_api_discoveries_shows_photo_context(self, client):
        """Discovery cards show photo context (collection, view photo link)."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Unknown 1",
                "target_id": "conf1",
                "target_name": "Known Person",
                "distance": 0.6,
                "confidence": "VERY HIGH",
            }
        ]
        source_identity = _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face_inbox1"])
        photo_data = {
            "collection": "Betty Capeluto Miami Collection",
            "faces": [{"face_id": "face_inbox1", "bbox": [0, 0, 100, 100]}],
            "filename": "test_photo.jpg",
        }

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value="photo123"),
            patch("app.main.get_photo_metadata", return_value=photo_data),
            patch("app.main.load_registry", return_value=_make_registry_mock([source_identity])),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        # Collection name shown
        assert "Betty Capeluto Miami Collection" in html
        # View photo link present
        assert 'href="/photo/photo123"' in html
        assert "View photo" in html


class TestApiDiscoveryReject:
    """Tests for the /api/discovery/reject endpoint."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def test_reject_adds_negative_id(self, client):
        """Rejecting a discovery adds target to source's negative_ids."""
        identities = [
            _make_identity("inbox1", "Unknown 1", "INBOX", candidate_ids=["face1"]),
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["faceC"]),
        ]
        registry = _make_registry_mock(identities)

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.save_registry") as mock_save,
            patch("app.main._invalidate_discovery_cache"),
        ):
            response = client.post("/api/discovery/reject?source_id=inbox1&target_id=conf1")

        assert response.status_code == 200
        assert "Match dismissed" in response.text
        # Verify negative_ids was updated
        assert "identity:conf1" in registry._identities["inbox1"]["negative_ids"]
        mock_save.assert_called_once()

    def test_reject_requires_admin(self, client):
        """Reject endpoint requires admin auth."""
        from app.main import Response

        with patch("app.main._check_admin", return_value=Response("Unauthorized", status_code=401)):
            response = client.post("/api/discovery/reject?source_id=inbox1&target_id=conf1")

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Test: Cache invalidation
# ---------------------------------------------------------------------------


class TestDiscoveryCacheInvalidation:
    """Tests for discovery cache lifecycle."""

    def test_invalidate_clears_cache(self):
        """_invalidate_discovery_cache resets the cache."""
        import app.main as main_module
        from app.main import _invalidate_discovery_cache

        main_module._discovery_cache = [{"some": "data"}]
        main_module._discovery_cache_key = (1, 2, 3)

        _invalidate_discovery_cache()

        assert main_module._discovery_cache is None
        assert main_module._discovery_cache_key is None

    def test_cache_is_used_on_second_call(self):
        """Second call to _compute_discoveries uses cached result."""
        from app.main import _compute_discoveries, _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["faceC"]),
        ]
        registry = _make_registry_mock(identities)

        # First call
        result1 = _compute_discoveries(registry)
        # Second call should use cache (no need to mock anything)
        result2 = _compute_discoveries(registry)

        assert result1 == result2

    def test_discovery_threshold_is_1_point_30(self):
        """The discovery threshold is distance < 1.30 (Session 79, raised from 1.05)."""
        from app.main import DISCOVERY_DISTANCE_THRESHOLD

        assert DISCOVERY_DISTANCE_THRESHOLD == 1.30


# ---------------------------------------------------------------------------
# Test: Filter controls (Act 5a — Session 87)
# ---------------------------------------------------------------------------


class TestDiscoveriesFilterControls:
    """Tests for the discoveries page filter controls."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def test_discoveries_page_has_filter_controls(self, client):
        """The /discoveries page renders filter controls."""
        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")),
            patch("app.main._count_discoveries", return_value=5),
            patch("app.main._compute_discoveries", return_value=[]),
        ):
            response = client.get("/discoveries")

        assert response.status_code == 200
        html = response.text
        # Confidence filter buttons exist
        assert "Strong (70%+)" in html
        assert "Possible (50%+)" in html
        # Photo filter dropdown exists
        assert "discovery-photo-filter" in html
        assert "All photos" in html

    def test_api_discoveries_sorted_by_recency(self, client):
        """Discoveries sorted by created_at descending (newest first)."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Older Discovery",
                "target_id": "conf1",
                "target_name": "Known A",
                "distance": 0.5,
                "confidence": "VERY HIGH",
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "source_id": "inbox2",
                "source_name": "Newer Discovery",
                "target_id": "conf1",
                "target_name": "Known A",
                "distance": 1.2,
                "confidence": "LOW",
                "created_at": "2026-03-01T00:00:00Z",
            },
        ]
        source1 = _make_identity("inbox1", "Older Discovery", "INBOX", candidate_ids=["face1"])
        source2 = _make_identity("inbox2", "Newer Discovery", "INBOX", candidate_ids=["face2"])
        registry = _make_registry_mock([source1, source2])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch(
                "app.main._safe_get_identity",
                side_effect=lambda reg, sid: registry.get_identity(sid) if sid in registry._identities else None,
            ),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_registry", return_value=registry),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        # Newer discovery should appear before older one (recency sort)
        newer_pos = html.find("discovery-card-inbox2")
        older_pos = html.find("discovery-card-inbox1")
        assert newer_pos < older_pos, "Newer discovery should appear first (recency sort)"

    def test_api_discoveries_min_confidence_filter(self, client):
        """min_confidence filter excludes low-confidence items."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Low Match",
                "target_id": "conf1",
                "target_name": "Known",
                "distance": 1.25,  # Very low confidence
                "confidence": "LOW",
            },
            {
                "source_id": "inbox2",
                "source_name": "High Match",
                "target_id": "conf1",
                "target_name": "Known",
                "distance": 0.4,  # Very high confidence
                "confidence": "VERY HIGH",
            },
        ]
        source1 = _make_identity("inbox1", "Low Match", "INBOX", candidate_ids=["face1"])
        source2 = _make_identity("inbox2", "High Match", "INBOX", candidate_ids=["face2"])
        registry = _make_registry_mock([source1, source2])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch(
                "app.main._safe_get_identity",
                side_effect=lambda reg, sid: registry.get_identity(sid) if sid in registry._identities else None,
            ),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_registry", return_value=registry),
        ):
            response = client.get("/api/discoveries?min_confidence=70")

        html = response.text
        # High match should be present, low match excluded
        assert "discovery-card-inbox2" in html
        assert "discovery-card-inbox1" not in html

    def test_api_discoveries_empty_with_filter_shows_filter_message(self, client):
        """When filters exclude all items, show 'No matches' instead of 'All reviewed'."""
        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=[]),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
        ):
            response = client.get("/api/discoveries?min_confidence=70")

        html = response.text
        assert "No matches" in html

    def test_api_discoveries_photo_filter(self, client):
        """photo_id filter restricts to discoveries from a specific photo."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Match A",
                "target_id": "conf1",
                "target_name": "Known",
                "distance": 0.5,
                "confidence": "VERY HIGH",
            },
            {
                "source_id": "inbox2",
                "source_name": "Match B",
                "target_id": "conf1",
                "target_name": "Known",
                "distance": 0.6,
                "confidence": "VERY HIGH",
            },
        ]
        source1 = _make_identity("inbox1", "Match A", "INBOX", candidate_ids=["face_a"])
        source2 = _make_identity("inbox2", "Match B", "INBOX", candidate_ids=["face_b"])
        registry = _make_registry_mock([source1, source2])

        def mock_photo_for_face(fid):
            return "photo_X" if fid == "face_a" else "photo_Y"

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch(
                "app.main._safe_get_identity",
                side_effect=lambda reg, sid: registry.get_identity(sid) if sid in registry._identities else None,
            ),
            patch("app.main.get_photo_id_for_face", side_effect=mock_photo_for_face),
            patch("app.main.load_registry", return_value=registry),
        ):
            response = client.get("/api/discoveries?photo_id=photo_X")

        html = response.text
        assert "discovery-card-inbox1" in html
        assert "discovery-card-inbox2" not in html

    def test_api_discoveries_photo_options_endpoint(self, client):
        """Photo options endpoint returns Option elements."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Match",
                "target_id": "conf1",
                "target_name": "Known",
                "distance": 0.5,
                "confidence": "VERY HIGH",
            },
        ]
        source1 = _make_identity("inbox1", "Match", "INBOX", candidate_ids=["face_a"])
        registry = _make_registry_mock([source1])
        photo_data = {"collection": "Test Collection", "path": "test.jpg"}

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch(
                "app.main._safe_get_identity",
                side_effect=lambda reg, sid: registry.get_identity(sid) if sid in registry._identities else None,
            ),
            patch("app.main.get_photo_id_for_face", return_value="photo123"),
            patch("app.main.get_photo_metadata", return_value=photo_data),
            patch("app.main.load_registry", return_value=registry),
        ):
            response = client.get("/api/discoveries/photo-options")

        assert response.status_code == 200
        html = response.text
        assert "All photos" in html
        assert "Test Collection" in html


# ---------------------------------------------------------------------------
# Test: Inline compare links, larger faces, confidence percentage (Act 5b)
# ---------------------------------------------------------------------------


class TestDiscoveriesCardEnhancements:
    """Tests for discovery card visual improvements (Session 87 Act 5b)."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def _get_discovery_html(self, client, distance=0.6):
        """Helper to render a discovery card and return HTML."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Test Person",
                "target_id": "conf1",
                "target_name": "Known Person",
                "distance": distance,
                "confidence": "VERY HIGH",
            }
        ]
        source_identity = _make_identity("inbox1", "Test Person", "INBOX", candidate_ids=["face_inbox1"])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_photo_registry"),
            patch("app.main._compute_co_occurrence", return_value=0),
            patch("app.main.load_registry", return_value=_make_registry_mock([source_identity])),
        ):
            response = client.get("/api/discoveries")

        assert response.status_code == 200
        return response.text

    @pytest.fixture(scope="class")
    def default_discovery_html(self, client):
        """Cache the default discovery HTML (distance=0.6) for reuse across tests."""
        return self._get_discovery_html(client, distance=0.6)

    def test_discovery_card_has_compare_link(self, default_discovery_html):
        """Each discovery card has an inline Compare link."""
        html = default_discovery_html
        assert 'data-testid="discovery-compare-link"' in html
        assert "/compare?face_id=face_inbox1&amp;person_id=conf1" in html

    def test_discovery_card_uses_rounded_lg(self, default_discovery_html):
        """Face images use rounded-lg instead of rounded-full for better visibility."""
        html = default_discovery_html
        assert "rounded-lg" in html
        assert "rounded-full" not in html or html.count("rounded-full") < html.count("rounded-lg")

    def test_discovery_card_shows_confidence_tier_label(self, default_discovery_html):
        """Discovery cards show tier label instead of misleading percentage."""
        html = default_discovery_html
        assert 'data-testid="discovery-confidence-label"' in html
        # Should contain a tier label like "Good match" (distance 0.85)
        assert any(label in html for label in ["Strong match", "Good match", "Possible match", "Weak match"])

    def test_discovery_card_face_size_at_least_112px(self, default_discovery_html):
        """Face images are at least w-28 (112px) for better visibility."""
        html = default_discovery_html
        assert "w-28" in html
        assert "h-28" in html

    def test_discovery_card_hides_raw_distance(self, client):
        """Session 90b: Discovery cards do NOT show raw distance (non-admin UX rule)."""
        html = self._get_discovery_html(client, distance=0.92)
        assert 'data-testid="match-info-bar"' in html
        # Raw distance "Dist: 0.92" must NOT appear — only calibrated labels
        assert "Dist:" not in html
        # But the match-info-bar itself should still render
        assert "match-info-bar" in html

    def test_discovery_card_correct_compare_url(self, default_discovery_html):
        """Session 88: Compare link uses face_id + person_id params."""
        html = default_discovery_html
        assert "face_id=" in html
        assert "person_id=conf1" in html
        # Should NOT use old source=/target= params
        assert "source=inbox1" not in html

    def test_discovery_card_shows_co_occurrence(self, client):
        """Session 88: Discovery cards show co-occurrence when present."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Test Person",
                "target_id": "conf1",
                "target_name": "Known Person",
                "distance": 0.6,
                "confidence": "VERY HIGH",
                "co_occurrence": 3,
            }
        ]
        source_identity = _make_identity("inbox1", "Test Person", "INBOX", candidate_ids=["face_inbox1"])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_photo_registry"),
            patch("app.main._compute_co_occurrence", return_value=0),
            patch("app.main.load_registry", return_value=_make_registry_mock([source_identity])),
        ):
            response = client.get("/api/discoveries")

        assert response.status_code == 200
        html = response.text
        assert "3 photos" in html

    def test_discovery_card_tooltip_no_raw_distance(self, default_discovery_html):
        """Session 90b: Confidence badge tooltip shows label, not raw distance."""
        html = default_discovery_html
        # Should NOT contain "Distance: X.XX" in tooltips
        assert "Distance:" not in html
        # Should contain human-readable confidence tooltip
        assert "confidence" in html.lower()


class TestDiscoveriesPhotoDropdownLazyLoad:
    """Session 90b: Photo dropdown loads options via dedicated loader div."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def test_discoveries_page_has_photo_loader_div(self, client):
        """The /discoveries page has a dedicated div to lazy-load photo options."""
        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")),
            patch("app.main._count_discoveries", return_value=5),
            patch("app.main._compute_discoveries", return_value=[]),
        ):
            response = client.get("/discoveries")

        assert response.status_code == 200
        html = response.text
        # Dedicated loader div exists
        assert "discovery-photo-loader" in html
        # It targets the select element
        assert "/api/discoveries/photo-options" in html

    def test_photo_options_not_loaded_via_hx_select(self, client):
        """Session 90b: Photo options must NOT use hx-select (caused empty dropdown)."""
        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")),
            patch("app.main._count_discoveries", return_value=5),
            patch("app.main._compute_discoveries", return_value=[]),
        ):
            response = client.get("/discoveries")

        html = response.text
        # hx-select with discovery-photo-filter should NOT appear
        assert (
            "hx-select" not in html or "discovery-photo-filter" not in html.split("hx-select")[1].split('"')[1]
            if "hx-select" in html
            else True
        )
        # Simpler assertion: the old broken pattern should not exist
        assert 'hx-select="#discovery-photo-filter' not in html


class TestDiscoveriesExtraction:
    """Tests for discoveries_routes.py extraction and UX fixes."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def test_confidence_tier_labels(self):
        """confidence_tier_label returns correct labels for distance ranges."""
        from app.discoveries_routes import confidence_tier_label

        assert confidence_tier_label(0.50) == "Strong match"
        assert confidence_tier_label(0.79) == "Strong match"
        assert confidence_tier_label(0.80) == "Good match"
        assert confidence_tier_label(0.99) == "Good match"
        assert confidence_tier_label(1.00) == "Possible match"
        assert confidence_tier_label(1.19) == "Possible match"
        assert confidence_tier_label(1.20) == "Weak match"
        assert confidence_tier_label(1.50) == "Weak match"

    def test_confidence_tier_styles(self):
        """confidence_tier_style returns badge and ring CSS classes."""
        from app.discoveries_routes import confidence_tier_style

        badge_cls, ring_cls = confidence_tier_style(0.50)
        assert "emerald" in badge_cls
        assert "emerald" in ring_cls

        badge_cls, ring_cls = confidence_tier_style(0.90)
        assert "blue" in badge_cls

        badge_cls, ring_cls = confidence_tier_style(1.10)
        assert "amber" in badge_cls

        badge_cls, ring_cls = confidence_tier_style(1.30)
        assert "slate" in badge_cls

    def test_discovery_cards_have_navigation_links(self, client):
        """Discovery cards have clickable links: source face -> person, photo -> photo, target -> person."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Unknown Face",
                "target_id": "conf1",
                "target_name": "Known Person",
                "distance": 0.85,
                "confidence": "HIGH",
                "created_at": "2026-03-01T00:00:00Z",
            }
        ]
        source_identity = _make_identity("inbox1", "Unknown Face", "INBOX", candidate_ids=["face_inbox1"])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value="/crop/test.jpg"),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value="photo123"),
            patch("app.main.get_photo_metadata", return_value={"collection": "Test", "faces": []}),
            patch("app.main.load_photo_registry"),
            patch("app.main._compute_co_occurrence", return_value=0),
            patch("app.main.load_registry", return_value=_make_registry_mock([source_identity])),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        # Source face image links to /person/{source_id}
        assert 'href="/person/inbox1"' in html
        # Target face image links to /person/{target_id}
        assert 'href="/person/conf1"' in html
        # Photo link exists
        assert 'href="/photo/photo123"' in html
        # Source and target name links point to person pages
        assert 'data-testid="discovery-source-link"' in html
        assert 'data-testid="discovery-target-link"' in html

    def test_recency_sort_newest_first(self, client):
        """Discoveries are sorted by created_at descending — newest appear first."""
        discoveries = [
            {
                "source_id": "old_match",
                "source_name": "Old Match",
                "target_id": "conf1",
                "target_name": "Known",
                "distance": 0.5,
                "confidence": "VERY HIGH",
                "created_at": "2026-01-15T00:00:00Z",
            },
            {
                "source_id": "new_match",
                "source_name": "New Match",
                "target_id": "conf1",
                "target_name": "Known",
                "distance": 1.0,
                "confidence": "MODERATE",
                "created_at": "2026-03-07T00:00:00Z",
            },
        ]
        source1 = _make_identity("old_match", "Old Match", "INBOX", candidate_ids=["face_old"])
        source2 = _make_identity("new_match", "New Match", "INBOX", candidate_ids=["face_new"])
        registry = _make_registry_mock([source1, source2])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch(
                "app.main._safe_get_identity",
                side_effect=lambda reg, sid: registry.get_identity(sid) if sid in registry._identities else None,
            ),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_registry", return_value=registry),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        new_pos = html.find("discovery-card-new_match")
        old_pos = html.find("discovery-card-old_match")
        assert new_pos > -1 and old_pos > -1, "Both discovery cards should be present"
        assert new_pos < old_pos, "Newer discovery must appear before older one"

    def test_tier_labels_not_percentages_in_cards(self, client):
        """Discovery cards show tier labels (Strong/Good/Possible/Weak) not raw percentages."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Test",
                "target_id": "conf1",
                "target_name": "Known",
                "distance": 0.70,
                "confidence": "VERY HIGH",
                "created_at": "2026-03-01T00:00:00Z",
            }
        ]
        source_identity = _make_identity("inbox1", "Test", "INBOX", candidate_ids=["face1"])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_photo_registry"),
            patch("app.main._compute_co_occurrence", return_value=0),
            patch("app.main.load_registry", return_value=_make_registry_mock([source_identity])),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        # Tier label present
        assert "Strong match" in html
        # data-testid for the label element
        assert 'data-testid="discovery-confidence-label"' in html


# ---------------------------------------------------------------------------
# Test: Share buttons on discovery cards (Session 91b gap fix)
# ---------------------------------------------------------------------------


class TestDiscoveriesShareButtons:
    """Discovery cards must have share buttons for community outreach."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def test_discovery_card_has_share_button(self, client):
        """Each discovery card has a share button."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Unknown Face",
                "target_id": "conf1",
                "target_name": "Known Person",
                "distance": 0.85,
                "confidence": "HIGH",
                "created_at": "2026-03-01T00:00:00Z",
            }
        ]
        source_identity = _make_identity("inbox1", "Unknown Face", "INBOX", candidate_ids=["face_inbox1"])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value="/crop/test.jpg"),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value="photo123"),
            patch("app.main.get_photo_metadata", return_value={"collection": "Test", "faces": []}),
            patch("app.main.load_photo_registry"),
            patch("app.main._compute_co_occurrence", return_value=0),
            patch("app.main.load_registry", return_value=_make_registry_mock([source_identity])),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        assert 'data-action="share-photo"' in html
        assert "Share" in html


# ---------------------------------------------------------------------------
# Test: Three visually distinct sections (Session 91b gap fix)
# ---------------------------------------------------------------------------


class TestDiscoveriesThreeSections:
    """The discoveries page must have three visually distinct sections."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def test_tier_1_section_has_distinct_styling(self, client):
        """Tier 1 (auto-added) section has green accent and icon."""
        tier_1_entries = [
            {
                "source_identity_id": "inbox1",
                "source_identity_name": "Auto Match",
                "target_identity_id": "conf1",
                "target_identity_name": "Known",
                "distance": 0.5,
                "face_id": "face1",
                "created_at": "2026-03-01T00:00:00Z",
            }
        ]
        source_identity = _make_identity("inbox1", "Auto Match", "INBOX", candidate_ids=["face1"])
        registry = _make_registry_mock([source_identity])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=[]),
            patch("app.main._get_pending_discovery_entries", return_value=(tier_1_entries, [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_registry", return_value=registry),
            patch("app.main._get_community_identity_ids", return_value=None),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        assert 'data-testid="section-auto-added"' in html
        assert "Recently Auto-Added" in html
        assert "bg-emerald-500/5" in html

    def test_tier_2_section_has_distinct_styling(self, client):
        """Tier 2 (suggested matches) section has blue accent and icon."""
        discoveries = [
            {
                "source_id": "inbox1",
                "source_name": "Suggestion",
                "target_id": "conf1",
                "target_name": "Known",
                "distance": 0.9,
                "confidence": "HIGH",
                "created_at": "2026-03-01T00:00:00Z",
            }
        ]
        source_identity = _make_identity("inbox1", "Suggestion", "INBOX", candidate_ids=["face1"])
        registry = _make_registry_mock([source_identity])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=discoveries),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.discoveries_routes._resolve_identity_crop", return_value=None),
            patch("app.main._safe_get_identity", return_value=source_identity),
            patch("app.main.get_photo_id_for_face", return_value=None),
            patch("app.main.load_photo_registry"),
            patch("app.main._compute_co_occurrence", return_value=0),
            patch("app.main.load_registry", return_value=registry),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        assert 'data-testid="section-suggested-matches"' in html
        assert "Suggested Matches" in html
        assert "bg-blue-500/5" in html

    def test_help_identify_section_present(self, client):
        """Help Identify section shows when there are unidentified faces."""
        unid_identity = _make_identity("unid1", "Unidentified Person 001", "INBOX", candidate_ids=["face_unid1"])
        conf_identity = _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["faceC"])
        registry = _make_registry_mock([unid_identity, conf_identity])

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", return_value=[]),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value={"face_unid1.jpg"}),
            patch("app.main.resolve_face_image_url", return_value="/crop/face_unid1.jpg"),
            patch("app.main.get_best_face_id", return_value="face_unid1"),
            patch("app.main.get_face_quality", return_value=0.9),
            patch("app.main.get_photo_id_for_face", return_value="photo1"),
            patch("app.main._photo_cache", {"photo1": {"collection": "Test Collection"}}),
            patch("app.main.load_registry", return_value=registry),
        ):
            response = client.get("/api/discoveries")

        html = response.text
        assert 'data-testid="section-help-identify"' in html
        assert "Help Identify" in html
        assert "bg-amber-500/5" in html
        assert 'href="/help"' in html


# ---------------------------------------------------------------------------
# Test: Community scoping (COMMUNITY-007 fix)
# ---------------------------------------------------------------------------


class TestDiscoveriesCommunityScoping:
    """Tests for community-scoped discoveries page and HTMX endpoints."""

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app

        with TestClient(app) as c:
            yield c

    def test_discoveries_page_uses_community_prefix_in_htmx_urls(self, client):
        """Fox Family discoveries page uses /c/fox-family/ prefix in HTMX URLs."""
        mock_community = {"id": "fox-uuid", "name": "Fox Family Archive", "slug": "fox-family"}

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")),
            patch("app.main._count_discoveries", return_value=5),
            patch("app.main._compute_discoveries", return_value=[]),
            patch("app.main._get_community_identity_ids", return_value=set()),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.supabase_data.get_community_by_slug", return_value=mock_community),
        ):
            response = client.get("/c/fox-family/discoveries")

        assert response.status_code == 200
        html = response.text
        # HTMX URLs must include community prefix
        assert "/c/fox-family/api/discoveries" in html
        assert "/c/fox-family/api/discoveries/photo-options" in html

    def test_api_discoveries_scoped_by_community(self, client):
        """/c/fox-family/api/discoveries passes community_identity_ids to _compute_discoveries."""
        mock_community = {"id": "fox-uuid", "name": "Fox Family Archive", "slug": "fox-family"}
        fox_ids = {"fox-id-1", "fox-id-2"}

        captured_args = {}

        def mock_compute(registry=None, community_identity_ids=None):
            captured_args["community_identity_ids"] = community_identity_ids
            return []

        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main._compute_discoveries", side_effect=mock_compute),
            patch("app.main._get_pending_discovery_entries", return_value=([], [])),
            patch("app.main.get_crop_files", return_value=set()),
            patch("app.main._get_community_identity_ids", return_value=fox_ids),
            patch("app.supabase_data.get_community_by_slug", return_value=mock_community),
        ):
            response = client.get("/c/fox-family/api/discoveries")

        assert response.status_code == 200
        assert captured_args.get("community_identity_ids") == fox_ids

    def test_rhodes_discoveries_no_community_prefix(self, client):
        """Rhodes discoveries uses bare /api/discoveries URLs (no prefix)."""
        with (
            patch("app.main._check_admin", return_value=None),
            patch("app.main.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")),
            patch("app.main._count_discoveries", return_value=0),
            patch("app.main._compute_discoveries", return_value=[]),
        ):
            response = client.get("/discoveries")

        assert response.status_code == 200
        html = response.text
        # Rhodes should use bare URLs (no /c/rhodes/ prefix)
        assert 'hx-get="/api/discoveries"' in html
