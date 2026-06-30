"""Unit tests for DETROIT-CANDIDATE-FORCE-167.

The Session 167 Track D eval proved Round 2.5 cannot rescue a candidate the
model never proposes: pass 2 picked Brooklyn because it anchored Detroit on
Albert's single-year `1917 Detroit` (distance 1) and MISSED his `1917-1918
Detroit` (distance 0). These tests cover the deterministic candidate-force step
that:
  1. parses each CONFIRMED subject's OWN dated residences,
  2. computes year_distance against the FIXED photo_year (de-game),
  3. injects every place with year_distance <= 5 as a MANDATORY candidate, and
  4. records a de-gamed canonical distance for the model's primary in the grader.

All mocked — no Gemini, no network.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.session153_shadow_eval import (
    build_forced_candidates,
    build_prompt,
    evaluate_result,
    extract_subject_residences,
    render_forced_candidates_block,
    _canonical_year_distance_for_place,
    _normalize_place_key,
    _parse_residence_year_range,
    _year_distance,
)

FIXTURE = Path("tests/fixtures/session154_gedcom_context.json")
FIXTURE_FRESH = Path("tests/fixtures/session167_gedcom_context.json")
PID_02068 = "inbox_fox-charlie-001_204_02068_p_13akf5twbc3600"


@pytest.fixture(scope="module")
def ctx_02068() -> str:
    data = json.loads(FIXTURE.read_text())
    return data[PID_02068]


@pytest.fixture(scope="module")
def ctx_02068_fresh() -> str:
    """Post-Session-156 (Harry-repair) GEDCOM context for 02068, regenerated
    from current production data in Session 167 cont. Harry Fox's faces were
    detached from 02068 in Session 156, so this context lists only Irving +
    Albert as confirmed subjects."""
    data = json.loads(FIXTURE_FRESH.read_text())
    return data[PID_02068]


# ---------------------------------------------------------------------------
# _parse_residence_year_range
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "date_str, expected",
    [
        ("1917", (1917, 1917)),
        ("1917-1918", (1917, 1918)),
        ("1 June 1915", (1915, 1915)),
        ("Abt 1955", (1955, 1955)),
        ("1951-1952", (1951, 1952)),
        ("?", None),
        ("", None),
        ("no-year-here", None),
    ],
)
def test_parse_residence_year_range(date_str, expected):
    assert _parse_residence_year_range(date_str) == expected


# ---------------------------------------------------------------------------
# _year_distance — in-range is zero
# ---------------------------------------------------------------------------


def test_year_distance_in_range_is_zero():
    assert _year_distance((1917, 1918), 1918) == 0
    assert _year_distance((1917, 1918), 1917) == 0


def test_year_distance_outside_range_takes_nearest_bound():
    assert _year_distance((1917, 1917), 1918) == 1
    assert _year_distance((1910, 1910), 1918) == 8
    assert _year_distance((1920, 1920), 1918) == 2


# ---------------------------------------------------------------------------
# _normalize_place_key — ward / assembly-district stripping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "place, key",
    [
        ("Detroit, Wayne, Michigan, USA", "detroit"),
        ("Brooklyn Assembly District 19, Kings, New York, USA", "brooklyn"),
        ("Brooklyn, Kings, New York, USA", "brooklyn"),
        ("Manhattan Ward 7, New York, New York, USA", "manhattan"),
        ("Dayton Ward 9, Montgomery, Ohio, USA", "dayton"),
        ("New York, Kings, New York, United States", "new york"),
    ],
)
def test_normalize_place_key(place, key):
    assert _normalize_place_key(place) == key


# ---------------------------------------------------------------------------
# extract_subject_residences — subject-own only, relatives excluded
# ---------------------------------------------------------------------------


def test_extract_subject_residences_finds_three_subjects(ctx_02068):
    residences = extract_subject_residences(ctx_02068)
    subjects = {r["subject"] for r in residences}
    # The three column-0 confirmed subjects.
    assert any("Harry" in s for s in subjects)
    assert any("Albert" in s for s in subjects)
    assert any("Irving" in s or "Israel" in s for s in subjects)


def test_extract_subject_residences_excludes_relative_residences(ctx_02068):
    """A relative's residence (Meyer Fox, a Parent) must NOT be extracted as a
    subject-own residence — only the three confirmed subjects count."""
    residences = extract_subject_residences(ctx_02068)
    # Meyer Fox is a Parent sub-block, never a column-0 Person here.
    assert not any("Meyer" in r["subject"] for r in residences)
    # Albert's 1917-1918 Detroit IS a subject-own residence (the distance-0
    # anchor pass 2 missed).
    assert any(
        "Albert" in r["subject"]
        and r["place_key"] == "detroit"
        and (r["year_lo"], r["year_hi"]) == (1917, 1918)
        for r in residences
    )


def test_extract_subject_residences_empty_context():
    assert extract_subject_residences("") == []
    assert extract_subject_residences(None) == []


# ---------------------------------------------------------------------------
# build_forced_candidates — the core fix
# ---------------------------------------------------------------------------


def test_forced_candidates_surface_detroit_at_distance_zero(ctx_02068):
    """The headline fix: Detroit is forced onto the table at its TRUE distance 0
    (Albert 1917-1918), not the distance-1 the model mis-computed."""
    forced = build_forced_candidates(ctx_02068, 1918)
    detroit = [r for r in forced if r["place_key"] == "detroit"]
    assert detroit, "Detroit MUST be a forced candidate"
    assert detroit[0]["year_distance"] == 0


def test_forced_candidates_include_brooklyn_tie(ctx_02068):
    """Brooklyn genuinely ties Detroit at distance 0 (Irving 1917-1918) — the
    contradictory-ground-truth Track D documented. Both must be present so the
    tie-breaker (then visual rule 3) can fire."""
    forced = build_forced_candidates(ctx_02068, 1918)
    keys = {r["place_key"]: r["year_distance"] for r in forced}
    assert keys.get("detroit") == 0
    assert keys.get("brooklyn") == 0


def test_forced_candidates_exclude_out_of_window(ctx_02068):
    """Manhattan 1910 (distance 8) is outside the 5-year window → not forced."""
    forced = build_forced_candidates(ctx_02068, 1918)
    assert all(r["year_distance"] <= 5 for r in forced)
    assert "manhattan" not in {r["place_key"] for r in forced}


def test_forced_candidates_sorted_by_distance_then_subject_count(ctx_02068):
    forced = build_forced_candidates(ctx_02068, 1918)
    dists = [r["year_distance"] for r in forced]
    assert dists == sorted(dists), "forced table must be distance-ascending"


def test_forced_candidates_empty_without_photo_year(ctx_02068):
    """De-game contract: no FIXED photo_year => no deterministic distances =>
    no forcing (we never trust the model's own year)."""
    assert build_forced_candidates(ctx_02068, None) == []


def test_forced_candidates_empty_without_context():
    assert build_forced_candidates(None, 1918) == []
    assert build_forced_candidates("", 1918) == []


def test_forced_candidates_carry_verbatim_citations(ctx_02068):
    forced = build_forced_candidates(ctx_02068, 1918)
    detroit = [r for r in forced if r["place_key"] == "detroit"][0]
    assert any("Detroit" in c and "Residence" in c for c in detroit["citations"])
    assert detroit["subjects_at_min"], "must name the subject at the min distance"


# ---------------------------------------------------------------------------
# render_forced_candidates_block + build_prompt injection
# ---------------------------------------------------------------------------


def test_render_block_marks_mandatory_and_lists_candidates(ctx_02068):
    forced = build_forced_candidates(ctx_02068, 1918)
    block = render_forced_candidates_block(forced, 1918)
    assert "MANDATORY" in block
    assert "1918" in block
    assert "Detroit" in block
    assert "Brooklyn" in block
    # The de-game instruction must be explicit.
    assert "do NOT re-estimate" in block or "do NOT recompute" in block


def test_build_prompt_candidate_injects_forced_block(ctx_02068):
    forced = build_forced_candidates(ctx_02068, 1918)
    prompt = build_prompt(
        "candidate", gedcom_context=ctx_02068, forced_candidates=forced, photo_year=1918
    )
    assert "GEDCOM-FORCED CANDIDATES" in prompt
    assert "Detroit" in prompt


def test_build_prompt_candidate_with_prior_injects_forced_block(ctx_02068):
    forced = build_forced_candidates(ctx_02068, 1918)
    prior = {"place": "Brooklyn, NY", "confidence": "high", "reasoning": "x"}
    prompt = build_prompt(
        "candidate_with_prior",
        gedcom_context=ctx_02068,
        forced_candidates=forced,
        photo_year=1918,
        prior_prediction=prior,
    )
    assert "GEDCOM-FORCED CANDIDATES" in prompt


def test_build_prompt_baseline_never_injects_forced_block(ctx_02068):
    """Baseline is the legacy reference variant — it must stay un-forced so the
    A/B still measures the candidate-scaffold effect."""
    forced = build_forced_candidates(ctx_02068, 1918)
    prompt = build_prompt(
        "baseline", gedcom_context=ctx_02068, forced_candidates=forced, photo_year=1918
    )
    assert "GEDCOM-FORCED CANDIDATES" not in prompt


def test_build_prompt_no_forced_block_when_no_photo_year(ctx_02068):
    prompt = build_prompt("candidate", gedcom_context=ctx_02068, forced_candidates=[], photo_year=None)
    assert "GEDCOM-FORCED CANDIDATES" not in prompt


# ---------------------------------------------------------------------------
# evaluate_result — de-gamed canonical distance
# ---------------------------------------------------------------------------


def test_grader_records_canonical_distance_for_detroit(ctx_02068):
    forced = build_forced_candidates(ctx_02068, 1918)
    parsed = {"location": {"place": "Detroit, Michigan", "confidence": "high", "candidates": []}}
    graded = evaluate_result(parsed, ["Detroit"], forced_candidates=forced)
    assert graded["predicted_place_year_distance"] == 0
    assert graded["verdict"] == "correct"


def test_grader_canonical_distance_ignores_model_year_claim(ctx_02068):
    """De-game: even if the model claims a year inside its own (absent) table,
    the grader reports the Python-computed distance from the FIXED photo_year."""
    forced = build_forced_candidates(ctx_02068, 1918)
    # Model claims Brooklyn with a fabricated distance-0 self-report; grader's
    # canonical value comes from the deterministic table (still 0 here, but the
    # POINT is it is NOT read from the model output).
    parsed = {
        "location": {
            "place": "Brooklyn, New York",
            "confidence": "high",
            "residence_distance_table": [{"candidate": "Brooklyn", "year_distance": "0"}],
            "candidates": [],
        }
    }
    graded = evaluate_result(parsed, ["Detroit"], forced_candidates=forced)
    # Brooklyn IS distance 0 deterministically — but the grader got it from the
    # forced table, not the model's self-report.
    assert graded["predicted_place_year_distance"] == 0
    assert graded["verdict"] == "wrong"  # Detroit target, Brooklyn primary


def test_grader_canonical_distance_none_for_unforced_place(ctx_02068):
    forced = build_forced_candidates(ctx_02068, 1918)
    parsed = {"location": {"place": "Paris, France", "confidence": "low", "candidates": []}}
    graded = evaluate_result(parsed, ["Detroit"], forced_candidates=forced)
    assert graded["predicted_place_year_distance"] is None


def test_grader_without_forced_candidates_is_backward_compatible():
    parsed = {"location": {"place": "Detroit, Michigan", "candidates": []}}
    graded = evaluate_result(parsed, ["Detroit"])
    assert graded["predicted_place_year_distance"] is None
    assert graded["verdict"] == "correct"


def test_canonical_year_distance_helper_substring_match():
    forced = [{"place_key": "detroit", "year_distance": 0}]
    assert _canonical_year_distance_for_place("Detroit, Michigan", forced) == 0
    assert _canonical_year_distance_for_place("Nowhere", forced) is None
    assert _canonical_year_distance_for_place("Detroit", None) is None


# ---------------------------------------------------------------------------
# Fresh-context fixture (Session 167 cont.) — the post-156 cleanup lever.
# Locks in: Harry dropped, the d=0 Detroit/Brooklyn tie survives the cleanup,
# and the candidate-force still surfaces Detroit at its TRUE distance 0.
# ---------------------------------------------------------------------------


def test_fresh_context_drops_harry(ctx_02068_fresh):
    """The Session 156 repair detached Harry's faces from 02068. The
    regenerated context must NOT list Harry as a column-0 subject (and must
    still carry Irving + Albert)."""
    residences = extract_subject_residences(ctx_02068_fresh)
    subjects = {r["subject"] for r in residences}
    assert not any("Harry" in s for s in subjects), "Harry must be gone post-156"
    assert any("Albert" in s for s in subjects)
    assert any("Irving" in s or "Israel" in s for s in subjects)


def test_fresh_context_still_a_zero_distance_tie(ctx_02068_fresh):
    """Removing Harry's NY/Ohio noise does NOT break the tie: Irving is still
    in Brooklyn 1917-1918 (d=0) and Albert in Detroit 1917-1918 (d=0). The data
    alone cannot disambiguate — the candidate-force + visual rule-3 is the fix."""
    forced = build_forced_candidates(ctx_02068_fresh, 1918)
    keys = {r["place_key"]: r["year_distance"] for r in forced}
    assert keys.get("detroit") == 0, "Detroit must be forced at TRUE distance 0"
    assert keys.get("brooklyn") == 0, "Brooklyn genuinely ties at distance 0"


def test_fresh_context_excludes_harry_only_places(ctx_02068_fresh):
    """Randolph (Harry 1920, d=2) was a forced candidate in the STALE context;
    in the fresh post-156 context it must be gone (it was Harry-only noise)."""
    forced = build_forced_candidates(ctx_02068_fresh, 1918)
    assert "randolph" not in {r["place_key"] for r in forced}
