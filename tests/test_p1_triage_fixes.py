"""Tests for Session 103 Phase 7 P1 triage fixes (FB-153, FB-159/160, FB-162)."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _read_source(relpath: str) -> str:
    """Read source file as text."""
    return (_ROOT / relpath).read_text()


# =====================================================================
# FB-153: /identify/ shows correct community for cross-community identity
# =====================================================================


class TestFB153IdentifyCommunityLookup:
    """FB-153: Identify page should show identity's actual community, not URL community."""

    def test_identify_page_source_code_has_fb153_fix(self):
        """Verify the FB-153 community lookup code exists in page_routes.py."""
        source = _read_source("app/page_routes.py")
        assert "FB-153" in source, "FB-153 fix comment should be in page_routes.py"
        assert "differ from url community" in source.lower() or "actual community" in source.lower(), (
            "FB-153 fix should reference actual community lookup"
        )

    def test_identify_page_checks_community_membership(self):
        """The identify page should check if identity belongs to current community."""
        source = _read_source("app/page_routes.py")
        assert "person_id not in comm_ids" in source, (
            "FB-153 fix should check if person_id is not in current community's identity set"
        )

    def test_identify_page_loads_other_communities(self):
        """The fix should load other communities to find the identity's actual community."""
        source = _read_source("app/page_routes.py")
        assert "load_communities" in source, "FB-153 fix should use load_communities() to check other communities"


# =====================================================================
# FB-159/160: Similar panel boosts CONFIRMED identities
# =====================================================================


class TestFB159160SimilarPanelRanking:
    """FB-159/160: Similar panel should rank CONFIRMED identities above unnamed fragments."""

    def test_browse_routes_has_state_boost_sort(self):
        """Verify the state boost re-sort exists in browse_routes.py."""
        source = _read_source("app/browse_routes.py")
        assert "_state_boost" in source, "FB-159/160 fix should define _state_boost dict"
        assert '"CONFIRMED": 0' in source, "CONFIRMED should have boost priority 0"

    def test_confirmed_sorts_before_inbox(self):
        """CONFIRMED identity should sort before INBOX even at higher distance."""
        _state_boost = {"CONFIRMED": 0, "PROPOSED": 1, "INBOX": 1, "SKIPPED": 2, "REJECTED": 2}
        neighbors = [
            {"identity_id": "a", "state": "INBOX", "distance": 0.87, "name": "Unidentified Person 1"},
            {"identity_id": "b", "state": "INBOX", "distance": 0.89, "name": "Unidentified Person 2"},
            {"identity_id": "c", "state": "CONFIRMED", "distance": 0.95, "name": "Esther Burd Fox"},
        ]
        neighbors.sort(key=lambda n: (_state_boost.get(n.get("state", "INBOX"), 1), n.get("distance", 99)))
        assert neighbors[0]["name"] == "Esther Burd Fox", "CONFIRMED should sort first despite higher distance"
        assert neighbors[0]["state"] == "CONFIRMED"

    def test_distance_order_preserved_within_tier(self):
        """Within same state tier, distance ordering is preserved."""
        _state_boost = {"CONFIRMED": 0, "PROPOSED": 1, "INBOX": 1, "SKIPPED": 2, "REJECTED": 2}
        neighbors = [
            {"identity_id": "a", "state": "INBOX", "distance": 0.95, "name": "Person A"},
            {"identity_id": "b", "state": "INBOX", "distance": 0.87, "name": "Person B"},
            {"identity_id": "c", "state": "INBOX", "distance": 0.90, "name": "Person C"},
        ]
        neighbors.sort(key=lambda n: (_state_boost.get(n.get("state", "INBOX"), 1), n.get("distance", 99)))
        assert neighbors[0]["distance"] == 0.87
        assert neighbors[1]["distance"] == 0.90
        assert neighbors[2]["distance"] == 0.95

    def test_two_sort_locations_in_browse_routes(self):
        """Both similar panel endpoints should have the state boost sort."""
        source = _read_source("app/browse_routes.py")
        count = source.count("FB-159/160")
        assert count >= 2, f"Expected FB-159/160 fix in both similar panel endpoints, found {count}"


# =====================================================================
# FB-162: Tag search prioritizes same-community + confirmed
# =====================================================================


class TestFB162TagSearchPriority:
    """FB-162: Tag search should prioritize confirmed + same-community identities."""

    def test_tag_search_has_community_sort(self):
        """Verify the FB-162 community re-sort exists in identity_routes.py."""
        source = _read_source("app/identity_routes.py")
        assert "FB-162" in source, "FB-162 fix comment should be in identity_routes.py"
        assert "comm_ids" in source, "FB-162 fix should reference community identity IDs"

    def test_community_sort_logic(self):
        """Same-community + confirmed + higher face count should sort first."""
        comm_ids = {"id1", "id3"}
        _sr = {"CONFIRMED": 0, "PROPOSED": 1, "INBOX": 2, "SKIPPED": 3}
        results = [
            {
                "identity_id": "id2",
                "name": "Esther Brenda Israel",
                "state": "CONFIRMED",
                "face_count": 1,
            },  # other community
            {"identity_id": "id1", "name": "Esther Burd Fox", "state": "CONFIRMED", "face_count": 24},  # same community
        ]
        results.sort(
            key=lambda r: (
                0 if r["identity_id"] in comm_ids else 1,
                _sr.get(r.get("state", "INBOX"), 9),
                -(r.get("face_count", 0)),
            )
        )
        assert results[0]["name"] == "Esther Burd Fox", "Same-community identity should sort first"

    def test_face_count_tiebreaker(self):
        """When same community + same state, higher face count wins."""
        comm_ids = {"id1", "id2"}
        _sr = {"CONFIRMED": 0, "PROPOSED": 1, "INBOX": 2}
        results = [
            {"identity_id": "id1", "name": "Person A", "state": "CONFIRMED", "face_count": 3},
            {"identity_id": "id2", "name": "Person B", "state": "CONFIRMED", "face_count": 24},
        ]
        results.sort(
            key=lambda r: (
                0 if r["identity_id"] in comm_ids else 1,
                _sr.get(r.get("state", "INBOX"), 9),
                -(r.get("face_count", 0)),
            )
        )
        assert results[0]["name"] == "Person B", "Higher face count should sort first as tiebreaker"
