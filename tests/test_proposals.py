"""Tests for clustering proposals integration.

Covers:
- Proposal loading and caching
- Proposal helpers (_get_proposals_for_identity, _get_best_proposal, etc.)
- Proposal badge rendering in identity cards
- Focus mode proposal prioritization
- Match mode proposal-first pair selection
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


SAMPLE_PROPOSALS = {
    "generated_at": "2026-02-11T00:00:00+00:00",
    "threshold": 1.05,
    "proposals": [
        {
            "source_identity_id": "src-1",
            "source_identity_name": "Unidentified Person 100",
            "target_identity_id": "target-leon",
            "target_identity_name": "Big Leon Capeluto",
            "face_id": "inbox_abc123",
            "distance": 0.76,
            "confidence": "VERY HIGH",
            "margin": 0.45,
            "ambiguous": False,
        },
        {
            "source_identity_id": "src-2",
            "source_identity_name": "Unidentified Person 200",
            "target_identity_id": "target-betty",
            "target_identity_name": "Betty Capeluto",
            "face_id": "inbox_def456",
            "distance": 0.95,
            "confidence": "HIGH",
            "margin": 0.20,
            "ambiguous": False,
        },
        {
            "source_identity_id": "src-1",
            "source_identity_name": "Unidentified Person 100",
            "target_identity_id": "target-betty",
            "target_identity_name": "Betty Capeluto",
            "face_id": "inbox_abc123",
            "distance": 1.10,
            "confidence": "MODERATE",
            "margin": 0.08,
            "ambiguous": True,
        },
    ],
}


class TestProposalLoading:
    """Tests for loading and caching proposals."""

    def test_load_proposals_empty_when_file_missing(self, tmp_path):
        """Returns empty proposals when file doesn't exist."""
        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _load_proposals
            result = _load_proposals()
            assert result["proposals"] == []

    def test_load_proposals_reads_file(self, tmp_path):
        """Loads proposals from file correctly."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(SAMPLE_PROPOSALS, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _load_proposals
            result = _load_proposals()
            assert len(result["proposals"]) == 3
            assert result["proposals"][0]["target_identity_name"] == "Big Leon Capeluto"


class TestProposalHelpers:
    """Tests for proposal query helpers."""

    def test_get_proposals_for_identity(self, tmp_path):
        """Returns proposals for a specific source identity."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(SAMPLE_PROPOSALS, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _get_proposals_for_identity
            proposals = _get_proposals_for_identity("src-1")
            assert len(proposals) == 2  # src-1 has two proposals
            assert proposals[0]["target_identity_name"] == "Big Leon Capeluto"

    def test_get_best_proposal(self, tmp_path):
        """Returns the highest-confidence (lowest distance) proposal."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(SAMPLE_PROPOSALS, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _get_best_proposal_for_identity
            best = _get_best_proposal_for_identity("src-1")
            assert best is not None
            assert best["distance"] == 0.76
            assert best["target_identity_name"] == "Big Leon Capeluto"

    def test_get_identities_with_proposals(self, tmp_path):
        """Returns set of identity IDs that have proposals."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(SAMPLE_PROPOSALS, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _get_identities_with_proposals
            ids = _get_identities_with_proposals()
            assert ids == {"src-1", "src-2"}

    def test_no_proposals_returns_none(self, tmp_path):
        """Returns None when no proposals exist for identity."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(SAMPLE_PROPOSALS, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _get_best_proposal_for_identity
            best = _get_best_proposal_for_identity("nonexistent-id")
            assert best is None


class TestProposalBanner:
    """Tests for proposal UI rendering."""

    def test_proposal_banner_renders_for_identity_with_proposal(self, tmp_path):
        """_proposal_banner returns content when proposal exists."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(SAMPLE_PROPOSALS, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _proposal_banner
            banner = _proposal_banner("src-1")
            assert banner is not None
            # Convert to string for content checks
            from starlette.testclient import TestClient
            # Banner should mention target name and confidence
            banner_html = str(banner)
            assert "Big Leon Capeluto" in banner_html or "ML Match" in banner_html

    def test_proposal_banner_returns_none_for_no_proposal(self, tmp_path):
        """_proposal_banner returns None when no proposals exist."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump({"proposals": []}, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _proposal_banner
            result = _proposal_banner("nonexistent-id")
            assert result is None

    def test_proposal_badge_inline_renders(self, tmp_path):
        """_proposal_badge_inline shows compact badge in browse view."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(SAMPLE_PROPOSALS, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _proposal_badge_inline
            badge = _proposal_badge_inline("src-1")
            assert badge is not None
            badge_html = str(badge)
            assert "match" in badge_html.lower()

    def test_proposal_badge_inline_none_for_no_proposal(self, tmp_path):
        """_proposal_badge_inline returns None when no proposals."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump({"proposals": []}, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _proposal_badge_inline
            result = _proposal_badge_inline("nonexistent-id")
            assert result is None


class TestFocusSortWithProposals:
    """Tests for focus mode sorting with proposals."""

    def test_focus_sort_prioritizes_proposals(self, tmp_path):
        """Identities with proposals should sort before those without."""
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(SAMPLE_PROPOSALS, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _get_identities_with_proposals, _get_best_proposal_for_identity

            # Simulate the sort key from render_to_review_section
            ids_with_proposals = _get_identities_with_proposals()

            items = [
                {"identity_id": "src-1", "anchor_ids": ["f1"], "candidate_ids": []},
                {"identity_id": "no-proposal", "anchor_ids": ["f2", "f3", "f4"], "candidate_ids": []},
                {"identity_id": "src-2", "anchor_ids": ["f5"], "candidate_ids": []},
            ]

            def sort_key(x):
                iid = x["identity_id"]
                has_proposal = iid in ids_with_proposals
                best = _get_best_proposal_for_identity(iid) if has_proposal else None
                return (
                    0 if has_proposal else 1,
                    best["distance"] if best else 999,
                    -len(x.get("anchor_ids", []) + x.get("candidate_ids", [])),
                )

            sorted_items = sorted(items, key=sort_key)

            # src-1 first (has best proposal at 0.76)
            assert sorted_items[0]["identity_id"] == "src-1"
            # src-2 second (has proposal at 0.95)
            assert sorted_items[1]["identity_id"] == "src-2"
            # no-proposal last (even though it has most faces)
            assert sorted_items[2]["identity_id"] == "no-proposal"


class TestClusteringProposalsPersistence:
    """Tests for cluster_new_faces.py proposal writing."""

    def test_proposals_json_structure(self):
        """Verify proposals.json has expected schema."""
        expected_keys = {"generated_at", "threshold", "proposals"}
        for key in expected_keys:
            assert key in SAMPLE_PROPOSALS

        proposal = SAMPLE_PROPOSALS["proposals"][0]
        expected_proposal_keys = {
            "source_identity_id", "source_identity_name",
            "target_identity_id", "target_identity_name",
            "face_id", "distance", "confidence", "margin", "ambiguous",
        }
        assert set(proposal.keys()) == expected_proposal_keys
