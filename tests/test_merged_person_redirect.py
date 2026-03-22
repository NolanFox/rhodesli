"""Tests for merged identity redirect on /person/{person_id}.

Covers:
- Simple merged identity → 301 redirect to target
- Community-prefixed merged identity preserves prefix
- Chain following (A→B→C redirects to C)
- Circular chain (A→B→A) returns 404
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _make_identity(identity_id, name="Test Person", state="CONFIRMED", merged_into=None):
    d = {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": [],
        "candidate_ids": [],
        "negative_ids": [],
    }
    if merged_into:
        d["merged_into"] = merged_into
    return d


def _mock_registry(identities_dict):
    """Create a mock registry with given identities dict."""
    registry = MagicMock()

    def get_identity(identity_id):
        if identity_id not in identities_dict:
            raise KeyError(f"Identity not found: {identity_id}")
        return identities_dict[identity_id].copy()

    registry.get_identity = get_identity
    return registry


class TestMergedPersonRedirect:
    """Merged person page should 301 redirect to the merge target."""

    def test_simple_merged_redirects(self, client):
        """Visiting /person/{merged_id} returns 301 to canonical person."""
        identities = {
            "merged-aaa": _make_identity("merged-aaa", merged_into="target-bbb"),
            "target-bbb": _make_identity("target-bbb", name="Target Person"),
        }
        registry = _mock_registry(identities)

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.person_routes._main_mod.load_registry", return_value=registry),
        ):
            response = client.get("/person/merged-aaa", follow_redirects=False)

        assert response.status_code == 301
        assert "/person/target-bbb" in response.headers["location"]

    def test_community_prefixed_merged_preserves_prefix(self, client):
        """Merged redirect under /c/<slug>/person/ preserves the community prefix."""
        identities = {
            "merged-aaa": _make_identity("merged-aaa", merged_into="target-bbb"),
            "target-bbb": _make_identity("target-bbb", name="Target Person"),
        }
        registry = _mock_registry(identities)

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.person_routes._main_mod.load_registry", return_value=registry),
            patch("app.person_routes._main_mod.community_url_prefix", return_value="/c/fox-family"),
        ):
            response = client.get("/person/merged-aaa", follow_redirects=False)

        assert response.status_code == 301
        assert "/c/fox-family/person/target-bbb" in response.headers["location"]

    def test_chain_follows_to_final_target(self, client):
        """A→B→C chain follows to C."""
        identities = {
            "chain-a": _make_identity("chain-a", merged_into="chain-b"),
            "chain-b": _make_identity("chain-b", merged_into="chain-c"),
            "chain-c": _make_identity("chain-c", name="Final Person"),
        }
        registry = _mock_registry(identities)

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.person_routes._main_mod.load_registry", return_value=registry),
        ):
            response = client.get("/person/chain-a", follow_redirects=False)

        assert response.status_code == 301
        assert "/person/chain-c" in response.headers["location"]

    def test_circular_chain_returns_404(self, client):
        """A→B→A circular chain returns 404 instead of infinite loop."""
        identities = {
            "loop-a": _make_identity("loop-a", merged_into="loop-b"),
            "loop-b": _make_identity("loop-b", merged_into="loop-a"),
        }
        registry = _mock_registry(identities)

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.person_routes._main_mod.load_registry", return_value=registry),
        ):
            response = client.get("/person/loop-a", follow_redirects=False)

        assert response.status_code == 404

    def test_merged_to_nonexistent_target_still_redirects(self, client):
        """If merged_into target doesn't exist, still redirect (target page will 404)."""
        identities = {
            "merged-aaa": _make_identity("merged-aaa", merged_into="nonexistent-zzz"),
        }
        registry = _mock_registry(identities)

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.person_routes._main_mod.load_registry", return_value=registry),
        ):
            response = client.get("/person/merged-aaa", follow_redirects=False)

        assert response.status_code == 301
        assert "/person/nonexistent-zzz" in response.headers["location"]

    def test_three_hop_chain(self, client):
        """A→B→C→D follows through 3 hops to D."""
        identities = {
            "hop-a": _make_identity("hop-a", merged_into="hop-b"),
            "hop-b": _make_identity("hop-b", merged_into="hop-c"),
            "hop-c": _make_identity("hop-c", merged_into="hop-d"),
            "hop-d": _make_identity("hop-d", name="Final"),
        }
        registry = _mock_registry(identities)

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.person_routes._main_mod.load_registry", return_value=registry),
        ):
            response = client.get("/person/hop-a", follow_redirects=False)

        assert response.status_code == 301
        assert "/person/hop-d" in response.headers["location"]

    def test_three_way_circular_returns_404(self, client):
        """A→B→C→A three-way circular chain returns 404."""
        identities = {
            "tri-a": _make_identity("tri-a", merged_into="tri-b"),
            "tri-b": _make_identity("tri-b", merged_into="tri-c"),
            "tri-c": _make_identity("tri-c", merged_into="tri-a"),
        }
        registry = _mock_registry(identities)

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.person_routes._main_mod.load_registry", return_value=registry),
        ):
            response = client.get("/person/tri-a", follow_redirects=False)

        assert response.status_code == 404
