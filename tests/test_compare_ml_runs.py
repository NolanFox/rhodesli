"""Tests for scripts/compare_ml_runs.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.compare_ml_runs import compare_proposals, format_markdown


def _make_proposal(source_id, face_id, target_id, distance, confidence="HIGH", **kwargs):
    p = {
        "source_identity_id": source_id,
        "source_identity_name": f"Person {source_id[:8]}",
        "face_id": face_id,
        "target_identity_id": target_id,
        "target_identity_name": f"Target {target_id[:8]}",
        "distance": distance,
        "confidence": confidence,
    }
    p.update(kwargs)
    return p


class TestCompareProposals:
    def test_identical_proposals(self):
        a = [_make_proposal("s1", "f1", "t1", 0.5)]
        b = [_make_proposal("s1", "f1", "t1", 0.5)]
        diff = compare_proposals(a, b)
        assert diff["count_a"] == 1
        assert diff["count_b"] == 1
        assert len(diff["same_match"]) == 1
        assert len(diff["target_changes"]) == 0
        assert len(diff["added"]) == 0
        assert len(diff["removed"]) == 0

    def test_added_proposal(self):
        a = [_make_proposal("s1", "f1", "t1", 0.5)]
        b = [
            _make_proposal("s1", "f1", "t1", 0.5),
            _make_proposal("s2", "f2", "t2", 0.7),
        ]
        diff = compare_proposals(a, b)
        assert len(diff["added"]) == 1
        assert diff["added"][0]["source_identity_id"] == "s2"

    def test_removed_proposal(self):
        a = [
            _make_proposal("s1", "f1", "t1", 0.5),
            _make_proposal("s2", "f2", "t2", 0.7),
        ]
        b = [_make_proposal("s1", "f1", "t1", 0.5)]
        diff = compare_proposals(a, b)
        assert len(diff["removed"]) == 1
        assert diff["removed"][0]["source_identity_id"] == "s2"

    def test_target_change(self):
        a = [_make_proposal("s1", "f1", "t1", 0.5)]
        b = [_make_proposal("s1", "f1", "t2", 0.6)]
        diff = compare_proposals(a, b)
        assert len(diff["target_changes"]) == 1
        assert diff["target_changes"][0]["target_a"] == "Target t1"
        assert diff["target_changes"][0]["target_b"] == "Target t2"

    def test_tier_change(self):
        a = [_make_proposal("s1", "f1", "t1", 0.5, confidence="HIGH")]
        b = [_make_proposal("s1", "f1", "t1", 0.3, confidence="VERY HIGH")]
        diff = compare_proposals(a, b)
        assert len(diff["tier_changes"]) == 1
        assert diff["tier_changes"][0]["tier_a"] == "HIGH"
        assert diff["tier_changes"][0]["tier_b"] == "VERY HIGH"

    def test_score_delta(self):
        a = [_make_proposal("s1", "f1", "t1", 0.5)]
        b = [_make_proposal("s1", "f1", "t1", 0.45)]
        diff = compare_proposals(a, b)
        assert len(diff["same_match"]) == 1
        assert abs(diff["same_match"][0]["delta"] - (-0.05)) < 0.001


class TestFormatMarkdown:
    def test_outputs_diff_format(self):
        diff = compare_proposals(
            [_make_proposal("s1", "f1", "t1", 0.5)],
            [_make_proposal("s1", "f1", "t1", 0.5)],
        )
        md = format_markdown(diff)
        assert "## Summary" in md
        assert "## Assessment" in md
        assert "Neutral" in md

    def test_active_assessment_on_target_change(self):
        diff = compare_proposals(
            [_make_proposal("s1", "f1", "t1", 0.5)],
            [_make_proposal("s1", "f1", "t2", 0.6)],
        )
        md = format_markdown(diff)
        assert "Active" in md
        assert "Target Changes" in md
