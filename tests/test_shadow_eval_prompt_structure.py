"""Structural tests for the Session 155 / AD-243 shadow-eval prompt redesign.

These tests check that the prompt sections in `scripts/session153_shadow_eval.py`
encode the AD-243 invariants (Round 2.5 residence-distance table, NAMED-event
CONFIRM gate, 5-year year_distance threshold).

They do not call Gemini and do not require network access. They only verify
the static prompt strings emitted by `build_prompt(...)`.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.session153_shadow_eval import (
    BASELINE_LOCATION_SECTION,
    CANDIDATE_LOCATION_SECTION,
    CANDIDATE_LOCATION_SCHEMA,
    PRIOR_PREDICTION_BLOCK,
    build_prompt,
    evaluate_result,
    resolve_photo,
)


# Minimal prior-prediction stub used by candidate_with_prior tests.
PRIOR = {
    "place": "Detroit, Michigan, USA",
    "confidence": "medium",
    "reasoning": "Albert Fox was a Detroit resident in 1917.",
}


# ---------------------------------------------------------------------------
# Round 2.5 + residence_distance_table
# ---------------------------------------------------------------------------


def test_candidate_section_contains_round_2_5() -> None:
    assert "Round 2.5" in CANDIDATE_LOCATION_SECTION


def test_candidate_section_contains_residence_distance_table() -> None:
    assert "residence_distance_table" in CANDIDATE_LOCATION_SECTION


def test_candidate_schema_contains_residence_distance_table() -> None:
    assert "residence_distance_table" in CANDIDATE_LOCATION_SCHEMA


def test_baseline_section_does_not_contain_round_2_5() -> None:
    """Baseline is the legacy reference variant — must NOT contain Round 2.5."""
    assert "Round 2.5" not in BASELINE_LOCATION_SECTION
    assert "residence_distance_table" not in BASELINE_LOCATION_SECTION


def test_build_prompt_candidate_includes_round_2_5() -> None:
    prompt = build_prompt(variant="candidate")
    assert "Round 2.5" in prompt
    assert "residence_distance_table" in prompt


def test_build_prompt_candidate_with_prior_includes_round_2_5() -> None:
    prompt = build_prompt(variant="candidate_with_prior", prior_prediction=PRIOR)
    assert "Round 2.5" in prompt
    assert "residence_distance_table" in prompt


def test_build_prompt_baseline_excludes_round_2_5() -> None:
    prompt = build_prompt(variant="baseline")
    assert "Round 2.5" not in prompt
    assert "residence_distance_table" not in prompt


# ---------------------------------------------------------------------------
# AD-243 CONFIRM-path tightening (NAMED GEDCOM event + year_distance threshold)
# ---------------------------------------------------------------------------


def test_prior_block_requires_named_gedcom_event_for_confirm() -> None:
    """CONFIRM path must demand citing the exact GEDCOM event verbatim."""
    assert "Cite the EXACT GEDCOM event" in PRIOR_PREDICTION_BLOCK


def test_prior_block_requires_year_distance_check() -> None:
    """CONFIRM path must reference the Round 2.5 year_distance + 5-year limit."""
    # The numeric threshold must be present literally as "5".
    assert "year_distance" in PRIOR_PREDICTION_BLOCK
    # The literal numeric threshold (the rule says "> 5" or "greater than 5").
    assert "greater than 5" in PRIOR_PREDICTION_BLOCK or "year_distance > 5" in PRIOR_PREDICTION_BLOCK


def test_prior_block_forbids_visual_only_confirmations() -> None:
    """Forbidden patterns from AD-243 must be listed explicitly."""
    forbidden_patterns = (
        "It seems plausible",
        "The architecture is consistent with",
    )
    for phrase in forbidden_patterns:
        assert phrase in PRIOR_PREDICTION_BLOCK, f"missing forbidden-pattern listing: {phrase!r}"


def test_prior_block_forbids_relative_residence_for_confirm() -> None:
    """A relative's residence must NOT count as confirming evidence."""
    assert "relative" in PRIOR_PREDICTION_BLOCK.lower()


def test_prior_block_emits_zero_match_lower_confidence_rule() -> None:
    """If subject_residence_match=0, the model must REFUTE/LOWER, not CONFIRM."""
    text = PRIOR_PREDICTION_BLOCK
    # Either the literal "0 subjects" rule or the "0 subject_residence_match" rule.
    assert "0 subject" in text or "0 subjects" in text


def test_build_prompt_prior_block_substitutes_place() -> None:
    prompt = build_prompt(variant="candidate_with_prior", prior_prediction=PRIOR)
    assert PRIOR["place"] in prompt
    # Placeholder must have been substituted out, not left as <PLACE>.
    assert "<PLACE>" not in prompt


# ---------------------------------------------------------------------------
# Variant guards
# ---------------------------------------------------------------------------


def test_candidate_with_prior_requires_prior_prediction_kwarg() -> None:
    with pytest.raises(ValueError, match="prior_prediction"):
        build_prompt(variant="candidate_with_prior")


def test_unknown_variant_raises() -> None:
    with pytest.raises(ValueError, match="Unknown variant"):
        build_prompt(variant="bogus")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# AD-243 confidence-gate teeth (the sycophancy guard must require a NAMED,
# date-anchored GEDCOM match — not just "the architecture is consistent with")
# ---------------------------------------------------------------------------


def test_high_confidence_gate_requires_year_distance_threshold() -> None:
    """`confidence=high` may only be claimed when year_distance <= 5.

    This is the structural teeth from Lesson 174 — a high-confidence answer
    must be anchored to a GEDCOM residence event within 5 years of the photo
    date, not to visual intuition the model can confabulate.
    """
    section = CANDIDATE_LOCATION_SECTION
    assert "year_distance ≤ 5" in section or "year_distance <= 5" in section


def test_high_confidence_gate_requires_subject_residence_match() -> None:
    """High confidence requires the primary to win Round 2.5 with >=1 match."""
    section = CANDIDATE_LOCATION_SECTION
    assert "subject_residence_match ≥ 1" in section or "subject_residence_match >= 1" in section


def test_all_zero_fallback_emits_literal_visual_only_phrase() -> None:
    """When no candidate has a GEDCOM match, the prompt forces a low-confidence
    'visual-only' admission with the exact literal phrase (so a downstream
    consumer can detect the no-anchor case)."""
    assert "no biographical anchoring available — visual-only" in CANDIDATE_LOCATION_SECTION


def test_round_2_5_excludes_immigration_and_relative_residences() -> None:
    """Round 2.5 must explicitly disqualify the two failure modes that let
    NYC win on 02068: port-of-entry events and a relative's residence."""
    section = CANDIDATE_LOCATION_SECTION.lower()
    assert "immigration" in section or "port-of-entry" in section or "port of entry" in section
    assert "relative" in section


# ---------------------------------------------------------------------------
# Round 2.5 v2 tie-breaker (Session 167 — PROMPT-A-ITERATION-001)
# The Session 167 Detroit eval proved the count-primary tie-breaker FLIPPED
# 02068 to Brooklyn (3 loosely-dated matches > Detroit's 2 on-year matches).
# v2 makes date-proximity the PRIMARY rule and excludes undated residences.
# ---------------------------------------------------------------------------


def test_round_2_5_tiebreaker_is_date_proximity_primary() -> None:
    """The PRIMARY tie-breaker must be smallest year_distance, NOT raw count.

    Guards against regressing to the count-primary rule that picked Brooklyn
    over Detroit on photo 02068 (Session 167 eval)."""
    section = CANDIDATE_LOCATION_SECTION
    assert "SMALLEST `year_distance` wins" in section
    # The count rule must be SECONDARY (only on a year_distance tie), and the
    # prompt must explicitly warn against picking by longest citation list.
    assert "longest list" in section.lower() or "longest list of residence" in section.lower()


def test_round_2_5_excludes_undated_residences() -> None:
    """An undated 'Residence ? in Brooklyn' must not count — it inflated
    Brooklyn's match count on 02068."""
    section = CANDIDATE_LOCATION_SECTION
    assert "DATED EVENTS ONLY" in section
    assert "Residence ?" in section


def test_round_2_5_has_date_window() -> None:
    """A residence 11+ years from the photo date is not a match."""
    section = CANDIDATE_LOCATION_SECTION.lower()
    assert "within 10 years" in section or "date-window" in section


def test_prior_confirm_requires_round_2_5_winner() -> None:
    """CONFIRM may only fire when the prior IS the Round 2.5 winner (Codex P1)."""
    block = PRIOR_PREDICTION_BLOCK
    assert "Round 2.5 WINNER" in block or "Round 2.5 winner" in block
    assert "ALL THREE" in block  # CONFIRM now has three requirements, not two


# ---------------------------------------------------------------------------
# evaluate_result — the grader that decides Detroit pass/fail
# ---------------------------------------------------------------------------


def test_evaluate_result_grades_detroit_correct() -> None:
    parsed = {"location": {"place": "Detroit, Michigan", "confidence": "medium", "candidates": []}}
    graded = evaluate_result(parsed, ["Belle Isle", "Detroit"])
    assert graded["top1_match"] is True
    assert graded["verdict"] == "correct"
    assert graded["place"] == "Detroit, Michigan"


def test_evaluate_result_grades_nyc_wrong_for_detroit_target() -> None:
    """The Session 154 failure: NYC primary must grade as wrong for a Detroit
    target even when Detroit is buried in the candidate list (top3)."""
    parsed = {
        "location": {
            "place": "New York City, New York",
            "confidence": "high",
            "candidates": [{"place": "Detroit, Michigan"}, {"place": "Dayton, Ohio"}],
        }
    }
    graded = evaluate_result(parsed, ["Belle Isle", "Detroit"])
    assert graded["top1_match"] is False
    assert graded["verdict"] == "candidate_has_answer"  # Detroit present but not primary
    assert graded["top3_match"] is True


def test_evaluate_result_handles_error_parse() -> None:
    graded = evaluate_result(None, ["Detroit"])
    assert graded["verdict"] == "error"
    assert graded["top1_match"] is False


# ---------------------------------------------------------------------------
# resolve_photo --photo-root override (worktree-empty-raw_photos case)
# ---------------------------------------------------------------------------


def test_resolve_photo_uses_photo_root_for_relative_path(tmp_path: Path) -> None:
    """A relative path from Supabase must resolve under the supplied photo_root,
    not the script's own (worktree) repo root."""
    raw = tmp_path / "raw_photos"
    raw.mkdir()
    img = raw / "02068.jpg"
    img.write_bytes(b"\xff\xd8\xff")  # minimal JPEG magic

    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"photo_id": "pid", "path": "raw_photos/02068.jpg", "collection": "Charlie Fox", "source": "album"}
    ]

    out = resolve_photo("pid", sb, photo_root=tmp_path)
    assert out is not None
    assert out["path"] == str(img)
    assert out["collection"] == "Charlie Fox"


def test_resolve_photo_returns_none_when_file_missing(tmp_path: Path) -> None:
    sb = MagicMock()
    sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"photo_id": "pid", "path": "raw_photos/missing.jpg", "collection": None, "source": None}
    ]
    assert resolve_photo("pid", sb, photo_root=tmp_path) is None
