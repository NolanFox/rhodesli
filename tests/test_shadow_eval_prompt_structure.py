"""Structural tests for the Session 155 / AD-243 shadow-eval prompt redesign.

These tests check that the prompt sections in `scripts/session153_shadow_eval.py`
encode the AD-243 invariants (Round 2.5 residence-distance table, NAMED-event
CONFIRM gate, 5-year year_distance threshold).

They do not call Gemini and do not require network access. They only verify
the static prompt strings emitted by `build_prompt(...)`.
"""
from __future__ import annotations

import pytest

from scripts.session153_shadow_eval import (
    BASELINE_LOCATION_SECTION,
    CANDIDATE_LOCATION_SECTION,
    CANDIDATE_LOCATION_SCHEMA,
    PRIOR_PREDICTION_BLOCK,
    build_prompt,
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
