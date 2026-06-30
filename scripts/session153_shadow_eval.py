#!/usr/bin/env python3
"""Session 153 Shadow Eval — Gemini Location Prompt A/B.

Addresses Codex P1 finding from session-153-codex-audit.md:
  "Attempt 3 included candidate hints with the correct answer baked in.
   One photo cannot justify permanent prompt changes. Shadow-evaluate on
   ≥10 diverse known-location photos."

Design:
  - Test set: 10-12 photos pulled from Supabase where collection + visual
    evidence strongly co-pin the location. Bucketed (Rhodes, Tampa, Dayton,
    Fader, Newspapers.com, Detroit control).
  - Ground truth: established from (a) collection name, (b) community metadata,
    (c) for the Detroit control, external visual evidence (Belle Isle
    Conservatory). Explicitly NOT from Gemini's own prior output on the same
    photo.
  - Baseline variant = the current production `location` prompt section from
    rhodesli_ml/gemini_extraction.py (unmodified).
  - Candidate variant = three-round scaffold (describe → propose 2-3 candidates
    → pick & eliminate). NO cheat-sheet city names pre-seeded. Same inputs
    (image, optional metadata) as baseline.
  - Both variants use the same model (GEMINI_MODEL), same temperature (0.1),
    same response_mime_type.
  - Logs every call to gemini_api_calls with experiment_id=session153_shadow_eval_<ts>.
  - NO writes to date_labels, photos, identities, photo_faces.

Cost cap: default $2.00 total, enforced by halting early if exceeded.

Run:
    source venv/bin/activate
    python scripts/session153_shadow_eval.py --dry-run      # print plan, no calls
    python scripts/session153_shadow_eval.py --max-cost 2.0 # execute

Writes:
    docs/feedback/session-153-gemini-shadow-eval-raw.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --- Test set: (photo_id, expected_location, ground_truth_source) ---
# Established BEFORE running Gemini. Collection-based with independent
# reasoning where possible. NOT derived from current date_labels.gemini_raw_location.
TEST_SET = [
    # Positive control (session 153 audit subject) — known-wrong baseline, Belle Isle Detroit correct
    {
        "photo_id": "inbox_fox-charlie-001_204_02068_p_13akf5twbc3600",
        "expected_location": "Detroit, Michigan",
        "expected_aliases": ["Belle Isle", "Detroit"],
        # photo_year is the FIXED archival date (de-game: the model cannot shift
        # it to make Brooklyn's 1917-1918 residence tie). Albert + Irving both
        # have 1917-1918 residences; Belle Isle Conservatory dates the frame to
        # ~1917-1918. Used by build_forced_candidates + the grader.
        "photo_year": 1918,
        "gt_source": "Session 153 audit: Albert Fox GEDCOM 1917-1918 Detroit + Belle Isle Conservatory visual match (external Burton Historical Collection comparison needed for full certainty)",
        "bucket": "Detroit control",
    },
    # Detroit control #2 — second Belle Isle Conservatory frame. Session 153b Phase 5 gate.
    {
        "photo_id": "inbox_fox-charlie-001_3_01659_p_13akf5twbc1045",
        "expected_location": "Detroit, Michigan",
        "expected_aliases": ["Belle Isle", "Detroit"],
        "photo_year": 1918,
        "gt_source": "Same event as 02068 per Gemini 3.1 Pro 100%-confidence cross-frame match (Session 153 visual audit). Same 3 seated men + 2 standing women, identical outfits + conservatory backdrop.",
        "bucket": "Detroit control",
    },
    # Rhodes — 4 community-submitted photos. GT is high-prior from context but caveat: Rhodes community photos can also depict diaspora.
    {
        "photo_id": "inbox_community-batch-20260214_20_simon_israel_522630495_10172484677500346_3828197167749831184_n",
        "expected_location": "Rhodes, Greece",
        "expected_aliases": ["Rhodes", "Dodecanese", "Greece"],
        "gt_source": "Jews of Rhodes community collection (Simon Israel). Caveat: diaspora photos can appear in this collection.",
        "bucket": "Rhodes",
    },
    {
        "photo_id": "inbox_community-batch-20260214_38_masliah_alhadeff_498643123_10171847102790346_6237952123946428779_n",
        "expected_location": "Rhodes, Greece",
        "expected_aliases": ["Rhodes", "Dodecanese", "Greece"],
        "gt_source": "Jews of Rhodes collection (Alhadeff family). Caveat: same as above.",
        "bucket": "Rhodes",
    },
    # Tampa — Nace Capeluto Tampa collection. Nace was Tampa-based.
    {
        "photo_id": "inbox_staged-20260210-182610_2_596771023.203463",
        "expected_location": "Tampa, Florida",
        "expected_aliases": ["Tampa", "Ybor", "Florida"],
        "gt_source": "Nace Capeluto Tampa Collection. Nace lived in Tampa; collection is personal photos.",
        "bucket": "Tampa",
    },
    {
        "photo_id": "inbox_staged-20260210-182610_1_596771174.533589",
        "expected_location": "Tampa, Florida",
        "expected_aliases": ["Tampa", "Ybor", "Florida"],
        "gt_source": "Nace Capeluto Tampa Collection.",
        "bucket": "Tampa",
    },
    # Charles Fox Dayton Ohio — family lived in Dayton 1923+. Session 151 validated 67/72 batch.
    {
        "photo_id": "inbox_fox-charlie-001_203_01832_p_13akf5twbc2276",
        "expected_location": "Dayton, Ohio",
        "expected_aliases": ["Dayton", "Ohio"],
        "gt_source": "Charles Fox Dayton collection; Albert Fox + family lived in Dayton 1923+.",
        "bucket": "Dayton",
    },
    {
        "photo_id": "inbox_fox-charlie-001_67_01721_p_13akf5twbc1134",
        "expected_location": "Dayton, Ohio",
        "expected_aliases": ["Dayton", "Ohio"],
        "gt_source": "Charles Fox Dayton collection.",
        "bucket": "Dayton",
    },
    # Fader collection — Brooklyn/NY metro per session-145 research
    {
        "photo_id": "inbox_fader-002_0_7CBDF0D7-84DE-4D3A-8D58-F1B3B1F64DB9",
        "expected_location": "New York metro",
        "expected_aliases": ["New York", "Brooklyn", "Queens", "Long Island", "New Jersey", "NY"],
        "gt_source": "Sarah Fox Fader Family — Faders lived Brooklyn/NY per session-148 genealogical research.",
        "bucket": "Fader NY",
    },
    # Newspapers.com — newspaper clipping; correct answer can be either "newspaper clipping" (reproduction)
    # or the newspaper's publication city (Dayton Daily News → Dayton).
    {
        "photo_id": "inbox_76c3afa9_0_bernard_shane_deber_wedding_Dayton_Daily_News_1949_10_11_25",
        "expected_location": "Newspaper clipping (Dayton Daily News)",
        "expected_aliases": ["newspaper", "clipping", "newsprint", "halftone", "reproduction", "Dayton"],
        "gt_source": "Filename indicates Dayton Daily News 1949. Correct answer: recognize as newspaper reproduction OR identify Dayton.",
        "bucket": "Newspaper",
        "special_verdict": "newspaper_recognition_or_dayton",
    },
    {
        "photo_id": "inbox_26cc946e_0_Obituary_for_Jacob_E_Levine",
        "expected_location": "Newspaper clipping",
        "expected_aliases": ["newspaper", "clipping", "newsprint", "halftone", "reproduction", "obituary"],
        "gt_source": "Filename indicates obituary newspaper clipping.",
        "bucket": "Newspaper",
        "special_verdict": "newspaper_recognition_or_dayton",
    },
    # Claude Benatar Congo — Sephardic family that lived in Belgian Congo. Photos are from Congo.
    {
        "photo_id": "inbox_community-batch-20260214_12_claude_benatar_collection_victor_bohor_sabatai_soriano_494266545_10171704019995346_7718030381364654083_n",
        "expected_location": "Congo or Rhodes",
        "expected_aliases": ["Congo", "Elisabethville", "Lubumbashi", "Leopoldville", "Kinshasa", "Rhodes", "Belgian Congo"],
        "gt_source": "Claude Benatar collection — Sephardic Rhodes diaspora in Belgian Congo. Caveat: could be either origin or Congo destination.",
        "bucket": "Rhodes diaspora",
    },
]


# --- Baseline location prompt = current production text (copied verbatim from
# rhodesli_ml/gemini_extraction.py::_PROMPT_SECTIONS["location"] as of 2026-04-18). ---
BASELINE_LOCATION_SECTION = """## Location Identification
Identify the likely geographic location using BOTH visual evidence AND biographical context.

**Step 1: Visual Analysis**
Examine architecture style, vegetation, signage, street features, and environmental cues.

**Step 2: Biographical Cross-Reference** (if genealogical context provided)
Cross-reference visual observations with known biographical data:
- Compare visual clues against known family addresses and residential history
- Check if children's birth places match the apparent location
- Consider the "missing child" test: count people visible vs known children at a given date
  to narrow the date AND location (e.g., if 3 of 4 children are present, the photo predates
  the 4th child's birth)
- Use occupation/workplace info to narrow geographic possibilities
- Consider migration patterns: where did this family live at different times?

**Step 2b: Business Name Cross-Reference**
- Cross-reference visible business names (signs, storefronts) with known family members
- Example: A sign reading "LEON'S RESTAURANT" + a family member named "Leon Capeluto"
  strongly suggests this is Leon's business. Use Leon's RESIDENTIAL ADDRESS, not his
  relatives' addresses, to determine the photo location.
- Business name matches are the STRONGEST location evidence — stronger than any other signal.
- If a business name matches a family member, the photo location is WHERE THAT PERSON LIVED
  AND WORKED, based on their RESIDENCE events (not immigration/transit records).

**Step 2c: Immigration & Transit Disambiguation**
- GEDCOM events tagged with [PORT OF ENTRY] are TRANSIT POINTS, not residences
- ONLY use RESIDENCE events, OCCUPATION events, and children's BIRTH PLACES to determine
  where someone actually lived

**Step 3: Confidence Assessment & Candidates**
Rate confidence. If visual evidence AND biographical data agree on a location, rate
confidence higher. If they conflict, explain the discrepancy.

For "source_type": use "visual" if location is purely from what you see, "biographical"
if purely from GEDCOM/genealogical data, or "both" if evidence from both sources.

IMPORTANT: If you considered multiple locations, list up to 3 alternative "candidates"
with their reasoning. The primary location goes in "place", alternatives in "candidates".
If evidence is genuinely ambiguous with no clear winner, set confidence to "low" and
list all options as candidates."""


# --- Candidate scaffold = three-round structure. NO pre-seeded city list.
# This is the permanent-change candidate minus cheat sheet (Codex P1 fix). ---
CANDIDATE_LOCATION_SECTION = """## Location Identification (structured four-round reasoning, AD-243)

Work through the following FOUR ROUNDS in order (Round 1, Round 2, Round 2.5,
Round 3). Each round must be completed before the next. Do not jump ahead to a
final answer.

**ROUND 1 — Describe the scene architecturally (do NOT name a city yet).**
List at least 2 concrete, diagnostic visual features that could distinguish this
location from other similar locations. Examples of diagnostic features: specific
material (limestone vs all-glass), roofline (curved-eave vs flat vs gabled),
attached vs detached glass conservatory, visible signage language/script,
vegetation type (palms vs deciduous), street furniture, vehicle era/make, and
any inscriptions or posters. Do not yet propose candidate cities.

**ROUND 2 — Propose 2-3 candidate locations.**
Using (a) the architectural features from Round 1, (b) any biographical context
provided, and (c) any visible text/signage, propose 2 to 3 candidate places. For
EACH candidate, list:
  - `feature_supporting`: at least one specific visual feature from Round 1 that
    supports this candidate
  - `feature_refuting`: at least one visual feature that would REFUTE this candidate
    if it were actually at this location (or "none found" if truly no refuting evidence)
  - `biographical_support`: if genealogical context is provided, whether subjects'
    RESIDENCE at the photo's likely date range supports this candidate. Weight
    each subject's own residence over their relatives' residences.

**ROUND 2.5 — Residence-Distance Scoring (MANDATORY before naming a primary).**

For EACH candidate location proposed in Round 2, fill out a row in the
`residence_distance_table` with these three columns:

| candidate | subject_residence_match | year_distance |
|-----------|-------------------------|---------------|
| <place from Round 2> | <verbatim GEDCOM citations> | <smallest absolute year delta> |

For each row, you MUST:
- Cite each matching GEDCOM event verbatim in `subject_residence_match`. The
  expected citation format is: "<subject name>: <event type> <date> in <place>"
  (e.g., "Albert Fox: Residence 1917 in Detroit, Michigan, USA"). If there are
  zero matches for a candidate, write the literal string `"0 subjects"`.
- "RELATED" or "FAMILY" is NOT a match — only the named CONFIRMED subject's
  OWN RESI / OCCU events, or one of their CHILDREN's BIRTH places.
- A relative's residence (parent, sibling, in-law, spouse where the spouse is
  not the photo's confirmed subject) does NOT count.
- Immigration / port-of-entry / ship-arrival events do NOT count even if they
  list the candidate city.
- **DATED EVENTS ONLY.** A residence with NO determinable year (e.g.
  "Residence ? in Brooklyn", "Residence in X" with no date) MUST NOT be
  cited as a match and MUST NOT be counted — you cannot compute a
  `year_distance` for it, so it carries zero weight. Drop it entirely.
- **DATE-WINDOW.** A residence only counts as a match if its year is within
  10 years of the photo's estimated date. A residence 11+ years away is NOT
  a match for this photo (a 1934 residence does not anchor a ~1917 photo).
- `year_distance` = for the candidate, the SMALLEST absolute integer year
  delta between the photo's estimated date (use the lower bound of any range
  you would estimate) and any one of that candidate's matching, dated events.
  If `subject_residence_match = "0 subjects"`, write `"n/a"`.

**Tie-breaker rules (apply IN STRICT ORDER, do not skip). The key principle:
DATE PROXIMITY beats RAW COUNT. A city where 2 subjects are documented in the
photo's exact year outranks a city where 3 subjects have loosely-dated or
older residences.**
1. SMALLEST `year_distance` wins (the candidate whose closest dated residence
   is nearest the photo's estimated year). This is the PRIMARY rule.
2. If two or more candidates TIE on the smallest `year_distance`, the winner
   is the one with the MOST DISTINCT confirmed subjects documented AT that
   smallest year_distance (i.e. count only subjects whose residence sits at
   the tying minimum distance, not every residence the candidate has).
3. If STILL tied AND no GEDCOM signal distinguishes them, fall back to visual
   evidence ONLY (Round 1 diagnostic features) — name the deciding feature.

Do NOT pick a candidate merely because it has the longest list of residence
citations. A long list of off-year residences loses to a short list of
on-year ones.

If ALL candidates have `subject_residence_match = "0 subjects"` (after dropping
undated and out-of-window events): lower confidence to `"low"` and the response
MUST explicitly include the literal phrase "no biographical anchoring available
— visual-only" in the `round_2_5_summary` field.

**ROUND 3 — Pick the primary location AS DETERMINED BY the Round 2.5 table.**
Choose ONE candidate as primary, applying the Round 2.5 tie-breaker rules.
The chosen primary MUST be the candidate that wins by Round 2.5 — you may
NOT override the table with visual intuition unless rule 3 (all-zero
fallback) applies. Then explicitly name at least ONE other candidate you are
eliminating and cite the specific visual feature OR Round 2.5 row that rules
it out. If you cannot eliminate a runner-up with a specific feature or row,
lower your confidence.

**Subject-weighted geography rule.** When GEDCOM context is provided and a
subject's own residence at the photo's estimated date range conflicts with a
relative's residence, prefer the subject's own residence. Immigration / port-of-
entry events are NEVER evidence of where someone lived. This is enforced
mechanically by Round 2.5 — relative-only matches do not count toward
`subject_residence_match`.

**Output contract.**
- `place` = the primary location chosen in Round 3 (== the Round 2.5 winner)
- `round_2_5_summary` = a short prose explanation of which Round 2.5 rule chose
  the primary, OR the literal "no biographical anchoring available — visual-only"
  if all candidates were zero-match.
- `residence_distance_table[]` = REQUIRED. One row per Round 2 candidate, in
  the order they appeared in Round 2. Each row: `{candidate, subject_residence_match, year_distance}`.
- `candidates[]` = ALL considered candidates from Round 2 (minimum 2), each with
  `feature_supporting`, `feature_refuting`, and `reasoning`.
- `diagnostic_features[]` = at least 2 features from Round 1 that pinned the answer.
- `eliminated_runner_up` = {"place": ..., "refuting_feature": ...}
- `confidence` = "high" only if (a) ≥2 diagnostic features support the primary
  AND (b) runner-up was eliminated via a specific feature AND (c) biographical
  support agrees (when context provided) AND (d) the primary is the Round 2.5
  winner with `subject_residence_match ≥ 1` AND (e) `year_distance ≤ 5`.
  Otherwise "medium" or "low". If the all-zero fallback fired, confidence
  MUST be "low".
- `source_type` = "visual" | "biographical" | "both"

If the photograph is itself a REPRODUCTION of another photograph (e.g., newspaper
clipping, magazine page, album page), say so: set `place` to describe the
reproduction type (e.g., "Newspaper clipping — venue not determinable from
reproduction") and note it in `diagnostic_features`. In that case
`residence_distance_table` may be omitted or use a single row with
`subject_residence_match = "0 subjects"`.

Do NOT collapse the rounds into a single paragraph. Return your work for each
round in the JSON fields below."""


# --- Candidate location schema (JSON body hint). ---
CANDIDATE_LOCATION_SCHEMA = """"location": {
  "place": "<primary chosen in Round 3 == Round 2.5 winner>",
  "confidence": "high|medium|low",
  "round1_description": "<architectural description, no city names>",
  "diagnostic_features": ["feature A", "feature B", ...],
  "candidates": [
    {
      "place": "...",
      "feature_supporting": "...",
      "feature_refuting": "...",
      "biographical_support": "...",
      "reasoning": "..."
    }
  ],
  "residence_distance_table": [
    {
      "candidate": "<place name, must match a Round 2 candidate>",
      "subject_residence_match": "<verbatim GEDCOM citation(s) like \"Albert Fox: Residence 1917 in Detroit, Michigan, USA\" — or the literal string \"0 subjects\">",
      "year_distance": "<smallest absolute integer year delta to the matching event, or \"n/a\" if 0 subjects>"
    }
  ],
  "round_2_5_summary": "<which Round 2.5 rule chose the primary, OR the literal \"no biographical anchoring available — visual-only\" if all candidates were zero-match>",
  "eliminated_runner_up": {"place": "...", "refuting_feature": "..."},
  "source_type": "visual|biographical|both"
}"""


# --- Deterministic GEDCOM candidate-force (DETROIT-CANDIDATE-FORCE-167) ---
# Root cause (Track D / Session 167 eval): Round 2.5 only SCORES the candidates
# the model proposes. If the model never lists Detroit, the residence-distance
# tie-breaker never fires — so an omitted city silently bypasses the whole
# mechanism. Pass 2 even MISSED Albert's `1917-1918 Detroit` (distance 0) and
# anchored Detroit on his single-year `1917 Detroit` (distance 1), which lost the
# date-proximity tie to Brooklyn.
#
# Fix: BEFORE the model scores, deterministically parse every confirmed subject's
# OWN dated residence from the GEDCOM context, compute year_distance against the
# photo's FIXED date (from TEST_SET metadata, NOT the model's own estimate — this
# is also the de-game step), and INJECT any place with year_distance <= 5 as a
# MANDATORY candidate + authoritative residence_distance_table row. The model may
# still pick the primary via the tie-breaker (incl. the visual rule-3 fallback on
# a genuine tie), but it can no longer omit a city or mis-compute its distance.

_RESIDENCE_WINDOW_YEARS = 5

# Place-key normalization: collapse ward / assembly-district / numeric-district
# qualifiers so "Brooklyn Assembly District 19" and "Brooklyn, Kings, NY" group
# under one key, while keeping Detroit / Brooklyn / New York / Dayton distinct.
_PLACE_QUALIFIER_RE = re.compile(
    r"\b(ward\s+\d+|assembly\s+district\s+\d+|district\s+\d+|ward|assembly\s+district)\b",
    re.IGNORECASE,
)


def _normalize_place_key(place: str) -> str:
    """Coarse city/region key from a full GEDCOM place string.

    Takes the first comma segment, strips ward / assembly-district / district
    qualifiers, lowercases, and squeezes whitespace. Conservative: it never
    merges two distinct first-segments (Brooklyn vs New York stay separate).
    """
    first = (place or "").split(",")[0]
    first = _PLACE_QUALIFIER_RE.sub("", first)
    return " ".join(first.lower().split()).strip()


def _parse_residence_year_range(date_str: str) -> tuple[int, int] | None:
    """Extract a (lo, hi) inclusive year range from a GEDCOM date prefix.

    Handles "1917", "1917-1918", "1 June 1915", "Abt 1955". Returns None for
    undated entries ("?", "") — those carry zero weight (Round 2.5 DATED-ONLY
    rule) because no year_distance can be computed for them.
    """
    if not date_str:
        return None
    years = [int(y) for y in re.findall(r"\b(1[89]\d{2}|20\d{2})\b", date_str)]
    if not years:
        return None
    if len(years) >= 2 and years[1] >= years[0]:
        return (years[0], years[1])
    return (years[0], years[0])


def _year_distance(year_range: tuple[int, int], photo_year: int) -> int:
    """Smallest absolute year delta from a residence range to the photo year.

    In-range (lo <= photo_year <= hi) -> 0.
    """
    lo, hi = year_range
    if lo <= photo_year <= hi:
        return 0
    return min(abs(lo - photo_year), abs(hi - photo_year))


def extract_subject_residences(gedcom_context: str) -> list[dict]:
    """Parse each CONFIRMED subject's OWN dated residential history.

    ONLY the "Residential History:" block directly under a column-0 "Person:"
    line is parsed — relatives' residences (indented "Parent:"/"Spouse:"/
    "Sibling:" sub-blocks) are deliberately ignored, mirroring the Round 2.5
    rule that a relative's residence does not count.

    Returns a list of {subject, place, place_key, year_lo, year_hi}.
    """
    if not gedcom_context:
        return []
    lines = gedcom_context.split("\n")
    out: list[dict] = []
    i = 0
    n = len(lines)
    while i < n:
        m = re.match(r"^Person: (.+)$", lines[i])
        if not m:
            i += 1
            continue
        subject = m.group(1).strip()
        j = i + 1
        in_res = False
        while j < n and not re.match(r"^Person: ", lines[j]):
            line = lines[j]
            if re.match(r"^  Residential History:", line):
                in_res = True
                j += 1
                continue
            if in_res:
                # Residence rows are indented 4 spaces and are NOT a new "  Key:"
                # section header (those start with exactly 2 leading spaces).
                if re.match(r"^    \S", line) and not re.match(r"^  [A-Z]", line):
                    body = line.strip()
                    if ": " in body:
                        date_str, place = body.split(": ", 1)
                    else:
                        date_str, place = body, ""
                    yr = _parse_residence_year_range(date_str)
                    place = place.strip()
                    if yr and place:
                        out.append(
                            {
                                "subject": subject,
                                "place": place,
                                "place_key": _normalize_place_key(place),
                                "year_lo": yr[0],
                                "year_hi": yr[1],
                            }
                        )
                    j += 1
                    continue
                else:
                    in_res = False
            j += 1
        i = j
    return out


def build_forced_candidates(
    gedcom_context: str | None,
    photo_year: int | None,
    window: int = _RESIDENCE_WINDOW_YEARS,
) -> list[dict]:
    """Deterministic residence_distance_table for candidate-forcing.

    Groups subject-own dated residences by normalized place key, computes the
    SMALLEST year_distance per place against the FIXED photo_year, and returns
    every place whose min year_distance <= window. Each row:
        {candidate, place_key, year_distance, subjects_at_min, citations}
    Sorted by (year_distance asc, -len(subjects_at_min)) so the most likely
    primary appears first. Empty list if no context or no fixed photo_year.
    """
    if not gedcom_context or photo_year is None:
        return []
    residences = extract_subject_residences(gedcom_context)
    by_key: dict[str, list[dict]] = {}
    for r in residences:
        dist = _year_distance((r["year_lo"], r["year_hi"]), photo_year)
        if dist > window:
            continue
        rec = {**r, "year_distance": dist}
        by_key.setdefault(r["place_key"], []).append(rec)

    rows: list[dict] = []
    for key, recs in by_key.items():
        min_dist = min(rec["year_distance"] for rec in recs)
        subjects_at_min = sorted({rec["subject"] for rec in recs if rec["year_distance"] == min_dist})
        # Display place: the full string of a min-distance match (deterministic:
        # pick the lexicographically-first to stay stable across runs).
        display = sorted(
            rec["place"] for rec in recs if rec["year_distance"] == min_dist
        )[0]
        # Verbatim citations for the model (subject + year + place).
        citations = sorted(
            f"{rec['subject']}: Residence "
            f"{rec['year_lo'] if rec['year_lo'] == rec['year_hi'] else str(rec['year_lo']) + '-' + str(rec['year_hi'])} "
            f"in {rec['place']}"
            for rec in recs
        )
        rows.append(
            {
                "candidate": display,
                "place_key": key,
                "year_distance": min_dist,
                "subjects_at_min": subjects_at_min,
                "citations": citations,
            }
        )
    rows.sort(key=lambda x: (x["year_distance"], -len(x["subjects_at_min"]), x["candidate"]))
    return rows


def render_forced_candidates_block(forced: list[dict], photo_year: int) -> str:
    """Render the MANDATORY-candidate prompt block from a forced table."""
    lines = [
        "## GEDCOM-FORCED CANDIDATES (MANDATORY — DETROIT-CANDIDATE-FORCE-167)",
        "",
        f"The photo's established date is **{photo_year}** (fixed from archival",
        "metadata — do NOT re-estimate it for the residence_distance_table).",
        "",
        "The following table was computed DETERMINISTICALLY from the confirmed",
        "subjects' OWN dated residences in the Genealogical Context above. Each",
        "`year_distance` is the smallest absolute delta between a subject's dated",
        "residence and the photo year. Relatives' residences and undated entries",
        "are already excluded.",
        "",
        "RULES (binding):",
        "1. EVERY place below MUST appear in your `candidates[]` AND in your",
        "   `residence_distance_table[]`. You may NOT omit any of them.",
        "2. Use these `year_distance` values verbatim — they are authoritative.",
        "   Do NOT recompute them from a different photo year.",
        "3. Pick the primary with the Round 2.5 tie-breaker: smallest",
        "   `year_distance` first; on a tie, the most distinct subjects at that",
        "   distance; on a STILL-tie, the visual rule-3 fallback (name the",
        "   deciding diagnostic feature from Round 1).",
        "",
        "| candidate | year_distance | subjects_at_min | citations |",
        "|-----------|---------------|-----------------|-----------|",
    ]
    for row in forced:
        subj = "; ".join(row["subjects_at_min"])
        cites = " || ".join(row["citations"])
        lines.append(
            f"| {row['candidate']} | {row['year_distance']} | {subj} | {cites} |"
        )
    return "\n".join(lines)


# --- Iterative refinement block (AD-242, Session 154 Phase A2). ---
# Embedded into the candidate_with_prior variant on the second pass. The
# refuting-feature requirement guards against sycophantic self-agreement.
PRIOR_PREDICTION_BLOCK = """## Prior prediction to cross-check (AD-242 + AD-243 tightened CONFIRM)
Your first-pass prediction for this photo: place=<PLACE>, confidence=<CONF>.
First-pass reasoning: <REASONING>

Re-run the FOUR-ROUND analysis (Round 1, Round 2, Round 2.5, Round 3) on
this photo per the Location Identification spec above. The
`residence_distance_table` from Round 2.5 is REQUIRED — fill it out before
deciding whether to confirm the prior.

Then cross-check this prior prediction against the Round 2.5 table you
just produced.

Decide ONE of the following and state which in the response:

  - CONFIRM the prior prediction. To do so, you MUST satisfy ALL THREE of these:
    1. Cite the EXACT GEDCOM event (subject name + event type + date + place
       verbatim, e.g. "Albert Fox: Residence 1917 in Detroit, Michigan, USA")
       that POSITIVELY supports the prior prediction. NOT a visual feature on
       its own. If no GEDCOM event in the supplied Genealogical Context
       supports the prior, you MUST refute or lower confidence.
    2. State the prior prediction's `year_distance` from the Round 2.5
       table you just produced. If that distance is greater than 5 years
       OR the prior prediction's row had `subject_residence_match = "0 subjects"`,
       you MUST refute or lower confidence — you may NOT confirm.
    3. The prior prediction's place MUST BE the Round 2.5 WINNER under the
       tie-breaker rules (smallest year_distance, then most distinct subjects
       at that distance). If a DIFFERENT candidate wins Round 2.5, you may NOT
       confirm — you MUST REFUTE and amend `place` to the Round 2.5 winner.
       A prior is not confirmable just because some nearby event exists for it;
       it must actually win the table.

  - REFUTE the prior prediction. To do so, name the specific feature OR
    Round 2.5 row (with its citation) that REFUTES it, and propose an
    amended `place` chosen from the Round 2.5 winner per the same
    tie-breaker rules.

  - LOWER CONFIDENCE without changing place. To do so, name the specific
    feature OR Round 2.5 row that introduces doubt — typically a candidate
    with stronger `subject_residence_match` that you couldn't fully eliminate.

Forbidden agreement patterns (these are NOT confirmations, do NOT use them):
- "It seems plausible"
- "The architecture is consistent with"
- "This could be"
- Any visual-only confirmation when the prior's Round 2.5 row had 0
  subject_residence_match.
- Any confirmation citing a relative's residence rather than the named
  subject's own RESI / OCCU / child-BIRTH event.
- Any confirmation where `year_distance > 5`."""


def build_prompt(
    variant: str,
    photo_metadata: dict | None = None,
    gedcom_context: str | None = None,
    prior_prediction: dict | None = None,
    forced_candidates: list[dict] | None = None,
    photo_year: int | None = None,
) -> str:
    """Build a minimal prompt (preamble + one task section) for A/B comparison.

    To isolate the prompt-structure effect, all variants receive the same
    preamble, the same photo_metadata, the same gedcom_context (when available),
    and the same task framing. Only the location section and the JSON schema
    fragment differ.

    Args:
        variant: One of "baseline", "candidate", "candidate_with_prior".
        photo_metadata: Dict with collection / source / filename.
        gedcom_context: Optional GEDCOM-derived biographical context string
            (residences, occupations, children's birth events) for confirmed
            subjects in the photo. Threading this through both baseline and
            candidate is mandatory: AD-241. The shadow eval is invalid otherwise.
        prior_prediction: Dict with `place`, `confidence`, `reasoning` keys.
            Required ONLY when variant == "candidate_with_prior" — embeds the
            first-pass prediction in a refute-or-confirm block per AD-242.
        forced_candidates: Deterministic residence_distance_table rows (from
            `build_forced_candidates`) injected as MANDATORY candidates so an
            omitted city cannot bypass the Round 2.5 tie-breaker
            (DETROIT-CANDIDATE-FORCE-167). Only injected for the `candidate` /
            `candidate_with_prior` variants — the `baseline` reference variant
            never receives it.
        photo_year: The photo's FIXED archival date used to render the forced
            block's de-game notice. Required when forced_candidates is non-empty.
    """
    from rhodesli_ml.gemini_extraction import _PREAMBLE, _SCHEMA_FRAGMENTS

    parts = [_PREAMBLE, "## Task\nAnalyze this photograph and identify the location.\n"]

    if photo_metadata:
        meta = "## Photo Metadata Context\n"
        if photo_metadata.get("collection"):
            meta += f"Collection: {photo_metadata['collection']}\n"
        if photo_metadata.get("source"):
            meta += f"Source: {photo_metadata['source']}\n"
        if photo_metadata.get("filename"):
            meta += f"Original filename: {photo_metadata['filename']}\n"
        meta += (
            "\nNOTE ON COLLECTION NAMES: A collection name indicates WHO HAD these photos and\n"
            "WHERE THEY WERE STORED, not necessarily where the photos were taken.\n"
            "Do NOT assume the collection city is the photo location."
        )
        parts.append(meta)

    # Genealogical context — mirrors production format at
    # rhodesli_ml/gemini_extraction.py:364-369. Threaded through ALL variants
    # so the A/B measures prompt structure, not data availability (AD-241).
    if gedcom_context:
        parts.append(
            f"## Genealogical Context\n{gedcom_context}\n\n"
            "Use this genealogical data to improve location analysis. The subject's "
            "OWN residence at the photo's likely date range outweighs a relative's "
            "residence. Immigration / port-of-entry events are NEVER evidence of "
            "where someone lived."
        )

    # Deterministic candidate-force block — rendered once, injected for both
    # candidate variants (NOT baseline) right before the location section so the
    # model reads the MANDATORY table before it proposes candidates.
    forced_block = None
    if forced_candidates and photo_year is not None:
        forced_block = render_forced_candidates_block(forced_candidates, photo_year)

    if variant == "baseline":
        parts.append(BASELINE_LOCATION_SECTION)
        schema = "{\n  " + _SCHEMA_FRAGMENTS["location"] + "\n}"
    elif variant == "candidate":
        if forced_block:
            parts.append(forced_block)
        parts.append(CANDIDATE_LOCATION_SECTION)
        schema = "{\n  " + CANDIDATE_LOCATION_SCHEMA + "\n}"
    elif variant == "candidate_with_prior":
        if not prior_prediction:
            raise ValueError("candidate_with_prior requires prior_prediction kwarg")
        if forced_block:
            parts.append(forced_block)
        parts.append(CANDIDATE_LOCATION_SECTION)
        # Inject prior-prediction values into the refinement block
        prior_block = PRIOR_PREDICTION_BLOCK
        prior_block = prior_block.replace("<PLACE>", str(prior_prediction.get("place", "<unknown>")))
        prior_block = prior_block.replace("<CONF>", str(prior_prediction.get("confidence", "<unknown>")))
        prior_block = prior_block.replace("<REASONING>", str(prior_prediction.get("reasoning", "<none provided>"))[:500])
        parts.append(prior_block)
        schema = "{\n  " + CANDIDATE_LOCATION_SCHEMA + "\n}"
    else:
        raise ValueError(f"Unknown variant: {variant}")

    parts.append(f"\n## Response Format (JSON only)\n{schema}")
    return "\n\n".join(parts)


def resolve_gedcom_context(photo_id: str, sb) -> str | None:
    """Build a GEDCOM context string for a shadow-eval photo.

    For each face in the photo, look up its identity (in identities table) and
    check whether that identity has a confirmed GEDCOM link. For each linked
    confirmed subject, build a curated residence/occupation/family-events
    summary using the production helper at
    `rhodesli_ml.gedcom_context.build_photo_context`.

    Returns the formatted context string, or None if no confirmed subjects in
    this photo have GEDCOM links.

    Notes:
        - Wraps `scripts.run_combined_pipeline.load_gedcom_data()` which already
          fetches face_links + parsed_gedcom from Supabase.
        - Uses variant="first_order" (matches production batch pipeline default).
        - Honest fallback: if any step fails, log + return None. The caller
          decides whether to send no-context or skip the photo.
    """
    try:
        # Photo's faces
        photo_faces_resp = sb.table("photo_faces").select("face_id").eq("photo_id", photo_id).execute()
        if not photo_faces_resp.data:
            logger.info(f"resolve_gedcom_context: no photo_faces rows for {photo_id}")
            return None
        face_ids = [r["face_id"] for r in photo_faces_resp.data]

        # Identities for those faces. Supabase REST defaults to 1000 rows per page;
        # the registry has ~4000 identities so we MUST paginate or we silently miss
        # the bulk of confirmed identities (root cause of the empty-context dry-run
        # observed during 154 A1 development).
        all_identity_rows: list[dict] = []
        page_size = 1000
        offset = 0
        while True:
            resp = (
                sb.table("identities")
                .select("identity_id, name, state, anchor_ids, candidate_ids")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not resp or not resp.data:
                break
            all_identity_rows.extend(resp.data)
            if len(resp.data) < page_size:
                break
            offset += page_size

        if not all_identity_rows:
            logger.info("resolve_gedcom_context: no identities rows")
            return None

        # Build face_id -> identity record map (only CONFIRMED count toward GEDCOM context;
        # mirror production's _build_gedcom_context_for_photo logic)
        face_to_identity = {}
        identities_dict = {}
        for ident in all_identity_rows:
            iid = ident["identity_id"]
            identities_dict[iid] = ident
            for fid in (ident.get("anchor_ids") or []):
                face_to_identity[fid] = ident

        confirmed_face_ids_in_photo = [
            fid for fid in face_ids
            if face_to_identity.get(fid, {}).get("state") == "CONFIRMED"
        ]
        if not confirmed_face_ids_in_photo:
            logger.info(f"resolve_gedcom_context: photo {photo_id} has no CONFIRMED faces")
            return None

        # Pull the heavy GEDCOM data via the canonical loader (face_links + parsed_gedcom)
        from scripts.run_combined_pipeline import load_gedcom_data
        from rhodesli_ml.gedcom_context import build_photo_context

        gedcom_data = load_gedcom_data()
        if not gedcom_data:
            logger.info("resolve_gedcom_context: load_gedcom_data() returned None")
            return None
        parsed_gedcom = gedcom_data.get("parsed_gedcom")
        face_links = gedcom_data.get("face_links", {})
        if not parsed_gedcom or not face_links:
            return None

        # Filter to faces whose identities have GEDCOM links
        identified_face_ids = [
            fid for fid in confirmed_face_ids_in_photo
            if face_to_identity[fid]["identity_id"] in face_links
        ]
        if not identified_face_ids:
            logger.info(f"resolve_gedcom_context: no GEDCOM-linked confirmed faces in {photo_id}")
            return None

        context = build_photo_context(
            photo_id=photo_id,
            identified_faces=identified_face_ids,
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=face_links,
            identities=identities_dict,
            variant="first_order",
        )
        return context or None
    except Exception as e:
        logger.warning(f"resolve_gedcom_context({photo_id}) failed: {e}", exc_info=True)
        return None


def resolve_photo(photo_id: str, sb, photo_root: Path | None = None) -> dict | None:
    """Pull path + collection + source for a photo from Supabase.

    Args:
        photo_root: Base directory for resolving RELATIVE photo paths
            (e.g. ``raw_photos/<file>.jpg``). Defaults to the script's repo
            root. When the eval runs from a git worktree whose ``raw_photos/``
            is empty (images are gitignored and live only in the main repo),
            pass the main-repo root here so the local image bytes can be read.
    """
    r = sb.table("photos").select("photo_id, path, collection, source").eq("photo_id", photo_id).execute()
    if not r.data:
        return None
    p = r.data[0]
    base = photo_root or Path(__file__).resolve().parent.parent
    path = Path(p.get("path") or "")
    if not path.is_absolute():
        path = base / path
    if not path.exists():
        return None
    return {"photo_id": p["photo_id"], "path": str(path), "collection": p.get("collection"), "source": p.get("source")}


# Backoff schedule for transient Gemini 5xx (Session 154 Phase A0).
# Session 153b observed intermittent 503/504 from Gemini 3.1 Pro; the original
# script treated those as permanent failures, throwing away expensive prompt
# context. Three retries with exponential backoff is cheap insurance.
_RETRY_BACKOFF_SECONDS = (2, 5, 15)
_RETRYABLE_STATUS_CODES = (500, 502, 503, 504, 408, 429)


def _is_retryable_error(err_str: str) -> bool:
    """Decide whether a Gemini failure is worth retrying.

    We retry only on (a) transient HTTP statuses raised by the SDK, (b) network
    timeouts, and (c) explicitly-empty responses. We do NOT retry on 4xx other
    than 408/429 — those are the caller's fault and will keep failing.
    """
    if not err_str:
        return False
    e = err_str.lower()
    if "empty_response" in e or "json_parse" in e:
        # JSON parse failures might be a model glitch; one retry is reasonable.
        return True
    if "timeout" in e or "connection" in e or "transport" in e:
        return True
    for code in _RETRYABLE_STATUS_CODES:
        if str(code) in e:
            return True
    return False


def call_gemini(prompt_text: str, image_bytes: bytes, suffix: str, model: str, api_key: str):
    """Call Gemini with retry-with-backoff. Returns (parsed_dict, latency_ms, usage_meta, err).

    Retries 5xx / 408 / 429 / network errors with exponential backoff (2s, 5s, 15s).
    Does NOT retry on 4xx (other than 408/429) — those are request-side failures.
    The latency_ms returned reflects total wall-clock for the FINAL attempt only;
    the err string includes attempt count for retried calls.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key, http_options={"timeout": 180_000})
    mime = "image/png" if suffix.lower() == ".png" else "image/jpeg"

    last_err = None
    for attempt in range(len(_RETRY_BACKOFF_SECONDS) + 1):
        t0 = time.time()
        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_text(text=prompt_text),
                            types.Part.from_bytes(data=image_bytes, mime_type=mime),
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            latency_ms = int((time.time() - t0) * 1000)
            text = response.text
            if not text:
                last_err = "empty_response"
            else:
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list) and parsed:
                        parsed = parsed[0]
                except Exception as parse_err:
                    last_err = f"json_parse: {parse_err}"
                else:
                    usage = None
                    if hasattr(response, "usage_metadata") and response.usage_metadata:
                        um = response.usage_metadata
                        usage = {
                            "prompt_token_count": getattr(um, "prompt_token_count", None),
                            "candidates_token_count": getattr(um, "candidates_token_count", None),
                            "total_token_count": getattr(um, "total_token_count", None),
                        }
                    return parsed, latency_ms, usage, None
        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            last_err = str(e)

        # Decide whether to retry
        if attempt < len(_RETRY_BACKOFF_SECONDS) and _is_retryable_error(last_err):
            wait = _RETRY_BACKOFF_SECONDS[attempt]
            logger.warning(
                f"    Gemini call failed (attempt {attempt + 1}/{len(_RETRY_BACKOFF_SECONDS) + 1}): "
                f"{last_err[:140]} — retrying in {wait}s"
            )
            time.sleep(wait)
            continue
        break

    annotated_err = f"{last_err} [after {attempt + 1} attempt(s)]" if last_err else "unknown_error"
    return None, latency_ms, None, annotated_err


def _canonical_year_distance_for_place(
    place: str, forced_candidates: list[dict] | None
) -> int | None:
    """Look up the DETERMINISTIC year_distance for a model-named place.

    De-game guard: the model cannot lower a place's year_distance by shifting
    the photo year — we report the value computed in Python from the fixed
    photo_year. Match by normalized place key (substring-tolerant). Returns
    None if the place is not in the forced table.
    """
    if not forced_candidates or not place:
        return None
    place_key = _normalize_place_key(place)
    for row in forced_candidates:
        rk = row.get("place_key", "")
        if rk and (rk == place_key or rk in place_key or place_key in rk):
            return row.get("year_distance")
    return None


def evaluate_result(
    parsed: dict | None,
    expected_aliases: list[str],
    special: str | None = None,
    forced_candidates: list[dict] | None = None,
) -> dict:
    """Grade a parsed Gemini location result against expected aliases.

    When `forced_candidates` is supplied, the result also carries
    `predicted_place_year_distance` — the DETERMINISTIC (de-gamed) distance for
    the model's primary, computed in Python from the fixed photo_year, not the
    model's self-reported table.
    """
    if parsed is None:
        return {
            "verdict": "error",
            "top1_match": False,
            "top3_match": False,
            "place": None,
            "confidence": None,
            "predicted_place_year_distance": None,
        }

    loc = parsed.get("location") if isinstance(parsed.get("location"), dict) else parsed
    if not isinstance(loc, dict):
        return {
            "verdict": "error",
            "top1_match": False,
            "top3_match": False,
            "place": None,
            "confidence": None,
            "predicted_place_year_distance": None,
        }

    place = (loc.get("place") or "").strip()
    confidence = loc.get("confidence")

    # Normalize alias match
    place_l = place.lower()

    def matches_any(aliases, text):
        return any(a.lower() in text for a in aliases)

    top1_match = matches_any(expected_aliases, place_l)

    # Top-3: also check candidates list
    cands = loc.get("candidates") or []
    cand_texts = []
    for c in cands:
        if isinstance(c, dict):
            cand_texts.append((c.get("place") or "").lower())
        elif isinstance(c, str):
            cand_texts.append(c.lower())
    top3_match = top1_match or any(matches_any(expected_aliases, t) for t in cand_texts)

    if special == "newspaper_recognition":
        # For a newspaper clipping, "correct" means recognizing it as a reproduction
        text_blob = json.dumps(loc).lower()
        recognized = any(kw in text_blob for kw in ["newspaper", "clipping", "newsprint", "halftone", "reproduction"])
        top1_match = recognized
        top3_match = recognized

    return {
        "verdict": "correct" if top1_match else ("candidate_has_answer" if top3_match else "wrong"),
        "top1_match": top1_match,
        "top3_match": top3_match,
        "place": place,
        "confidence": confidence,
        "candidates": [c if isinstance(c, str) else (c.get("place") if isinstance(c, dict) else None) for c in cands],
        "predicted_place_year_distance": _canonical_year_distance_for_place(place, forced_candidates),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-cost", type=float, default=2.0)
    ap.add_argument(
        "--max-calls",
        type=int,
        default=None,
        help=(
            "Hard ceiling on the TOTAL number of Gemini calls (including silent "
            "first passes). The run ABORTS the moment this many calls have been "
            "made, even mid-photo. Use alongside --max-cost for a mechanical "
            "double cap on bounded eval runs."
        ),
    )
    ap.add_argument(
        "--no-db-log",
        action="store_true",
        help=(
            "Skip the append-only gemini_api_calls audit logging. The eval still "
            "writes its results to the --out-path JSON. Use for bounded reruns "
            "where the only required artifact is the docs/feedback file."
        ),
    )
    ap.add_argument("--limit", type=int, default=None, help="limit to first N photos (after dedup)")
    ap.add_argument(
        "--variants",
        default="baseline,candidate,candidate_with_prior",
        help="Comma-separated list of variants to run. Default: all three.",
    )
    ap.add_argument(
        "--photo-ids",
        default=None,
        help="Comma-separated photo_ids to filter test set (e.g. for Detroit-only rerun).",
    )
    ap.add_argument(
        "--gedcom-context-fixture",
        default=None,
        help=(
            "Path to a JSON fixture mapping photo_id -> gedcom_context string. "
            "When set, the script READS context from the fixture instead of "
            "re-resolving from Supabase. Use this for deterministic re-runs. "
            "If a photo_id is missing from the fixture, the script resolves it "
            "from Supabase and writes back to the fixture so subsequent runs "
            "are stable. Default: tests/fixtures/session154_gedcom_context.json"
        ),
    )
    ap.add_argument(
        "--no-gedcom-context",
        action="store_true",
        help="Disable GEDCOM context entirely (legacy 153b behavior — use only to reproduce that run).",
    )
    ap.add_argument(
        "--photo-root",
        default=None,
        help=(
            "Base directory for resolving RELATIVE photo paths (raw_photos/...). "
            "Defaults to the script's repo root. When running from a git worktree "
            "whose raw_photos/ is empty, point this at the main repo root so the "
            "local image bytes can be read."
        ),
    )
    ap.add_argument(
        "--experiment-id",
        default=None,
        help=(
            "Override the experiment_id used for gemini_api_calls logging + the "
            "results file. Default: session154_shadow_eval_<ts>. Pass a "
            "session-specific tag (e.g. session167_detroit_eval_<ts>) for honest "
            "provenance so a later rerun is distinguishable from the 154 run."
        ),
    )
    ap.add_argument(
        "--out-path",
        default=None,
        help=(
            "Override the raw-results JSON output path. Default is derived from "
            "the test-set scope (Detroit-only -> session-154-...detroit-rerun.json). "
            "Pass an explicit path to avoid clobbering a prior session's record."
        ),
    )
    args = ap.parse_args()

    photo_root = Path(args.photo_root).resolve() if args.photo_root else None

    from dotenv import load_dotenv

    load_dotenv(".env")

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        sys.exit(1)

    from supabase import create_client

    sb = create_client(
        os.environ["SUPABASE_URL"],
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_ANON_KEY"],
    )

    from rhodesli_ml.gemini_config import GEMINI_MODEL, get_model_pricing
    from app.supabase_data import log_gemini_call

    pricing = get_model_pricing(GEMINI_MODEL)
    logger.info(f"Model: {GEMINI_MODEL}  pricing(input/output per 1M): {pricing.get('input')}/{pricing.get('output')}")

    # Resolve test photos (optionally filter by --photo-ids)
    photo_id_filter = None
    if args.photo_ids:
        photo_id_filter = {x.strip() for x in args.photo_ids.split(",") if x.strip()}
        logger.info(f"Filtering test set to {len(photo_id_filter)} photo_ids: {sorted(photo_id_filter)}")

    test_rows = []
    for entry in TEST_SET:
        if photo_id_filter and entry["photo_id"] not in photo_id_filter:
            continue
        photo = resolve_photo(entry["photo_id"], sb, photo_root=photo_root)
        if not photo:
            logger.warning(f"SKIP {entry['photo_id']} — not found or no local file")
            continue
        test_rows.append({**entry, "_path": photo["path"], "_collection": photo["collection"], "_source": photo["source"]})

    if args.limit:
        test_rows = test_rows[: args.limit]

    logger.info(f"Test set: {len(test_rows)} photos")
    for r in test_rows:
        logger.info(f"  {r['photo_id'][:55]:55s}  bucket={r['bucket']}  gt={r['expected_location']}")

    # Resolve variants
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    valid_variants = {"baseline", "candidate", "candidate_with_prior"}
    bad = set(variants) - valid_variants
    if bad:
        logger.error(f"Unknown variants: {bad}. Valid: {valid_variants}")
        sys.exit(1)
    logger.info(f"Variants: {variants}")

    # Resolve GEDCOM context for each photo (fixture-cached for determinism, AD-241).
    fixture_path = Path(args.gedcom_context_fixture or "tests/fixtures/session154_gedcom_context.json")
    fixture_data: dict[str, str | None] = {}
    if fixture_path.exists():
        try:
            with open(fixture_path) as f:
                fixture_data = json.load(f)
            logger.info(f"GEDCOM fixture: loaded {len(fixture_data)} entries from {fixture_path}")
        except Exception as e:
            logger.warning(f"GEDCOM fixture {fixture_path} unreadable: {e} — re-resolving")

    context_map: dict[str, str | None] = {}
    if not args.no_gedcom_context:
        for r in test_rows:
            pid = r["photo_id"]
            if pid in fixture_data:
                context_map[pid] = fixture_data[pid]
                logger.info(
                    f"GEDCOM context: {pid[:50]:50s} fixture-hit  "
                    f"({'present' if fixture_data[pid] else 'NULL'})"
                )
            else:
                ctx = resolve_gedcom_context(pid, sb)
                context_map[pid] = ctx
                logger.info(
                    f"GEDCOM context: {pid[:50]:50s} resolved  "
                    f"({'present, ' + str(len(ctx)) + ' chars' if ctx else 'NULL'})"
                )
        # Persist the resolved contexts so subsequent runs are deterministic
        try:
            fixture_path.parent.mkdir(parents=True, exist_ok=True)
            persisted = {**fixture_data, **context_map}
            with open(fixture_path, "w") as f:
                json.dump(persisted, f, indent=2)
            logger.info(f"GEDCOM fixture: wrote {len(persisted)} entries to {fixture_path}")
        except Exception as e:
            logger.warning(f"Could not persist GEDCOM fixture {fixture_path}: {e}")
    else:
        logger.warning("--no-gedcom-context set: running shadow eval WITHOUT GEDCOM context (legacy 153b mode)")

    if args.dry_run:
        logger.info("Dry run — exiting before any API calls")
        # Useful side-effect: dry-run still resolves+writes the fixture above.
        return

    # Unique experiment ID for this run. Honest provenance: an explicit
    # --experiment-id keeps a later (e.g. Session 167) rerun distinguishable
    # from the Session 154 run in gemini_api_calls.
    experiment_id = args.experiment_id or f"session154_shadow_eval_{int(time.time())}"
    logger.info(f"Experiment ID: {experiment_id}")

    results = []
    total_cost = 0.0
    call_count = 0  # every Gemini call (incl. silent first passes) counts toward --max-calls

    def _cap_hit() -> str | None:
        """Mechanical double-cap. Returns a reason string if a ceiling is hit."""
        if total_cost >= args.max_cost:
            return f"cost cap ${args.max_cost:.2f} (spent ${total_cost:.4f})"
        if args.max_calls is not None and call_count >= args.max_calls:
            return f"call cap {args.max_calls} (made {call_count})"
        return None

    if args.max_calls is not None:
        logger.info(f"Mechanical caps: max_cost=${args.max_cost:.2f}  max_calls={args.max_calls}")

    aborted = False
    for i, row in enumerate(test_rows):
        if aborted:
            break
        pid = row["photo_id"]
        photo_path = Path(row["_path"])
        suffix = photo_path.suffix
        try:
            image_bytes = photo_path.read_bytes()
        except Exception as e:
            logger.error(f"Could not read {photo_path}: {e}")
            continue

        photo_metadata = {"collection": row["_collection"], "source": row["_source"], "filename": photo_path.name}
        photo_gedcom_context = context_map.get(pid)

        # Deterministic candidate-force (DETROIT-CANDIDATE-FORCE-167). Requires a
        # FIXED photo_year (de-game) AND GEDCOM context. Computed ONCE per photo,
        # injected into both candidate variants below.
        photo_year = row.get("photo_year")
        forced_candidates = build_forced_candidates(photo_gedcom_context, photo_year)
        if forced_candidates:
            logger.info(
                f"    FORCED CANDIDATES (photo_year={photo_year}): "
                + ", ".join(f"{r['candidate']}(d={r['year_distance']})" for r in forced_candidates)
            )

        # Per-photo cache of first-pass candidate result for the candidate_with_prior variant.
        # Same photo's `candidate` run feeds the prior_prediction for `candidate_with_prior`.
        first_pass_cache = None

        for variant in variants:
            cap_reason = _cap_hit()
            if cap_reason:
                logger.warning(f"ABORT: {cap_reason} reached — halting before next call")
                aborted = True
                break

            # Build the prompt — candidate_with_prior needs a first-pass result
            if variant == "candidate_with_prior":
                if first_pass_cache is None:
                    # If `candidate` wasn't run for this photo (e.g. user passed
                    # --variants candidate_with_prior alone), run a silent first pass
                    # so the prior-prediction has substance. Cost still bills under
                    # the same budget.
                    fp_prompt = build_prompt(
                        "candidate",
                        photo_metadata=photo_metadata,
                        gedcom_context=photo_gedcom_context,
                        forced_candidates=forced_candidates,
                        photo_year=photo_year,
                    )
                    logger.info(f"[{i+1}/{len(test_rows)}] {pid[:40]} variant=candidate (silent first pass)")
                    call_count += 1
                    fp_parsed, _, fp_usage, fp_err = call_gemini(fp_prompt, image_bytes, suffix, GEMINI_MODEL, api_key)
                    if fp_err or not fp_parsed:
                        logger.warning(f"    silent first pass failed ({fp_err}); skipping candidate_with_prior")
                        continue
                    fp_loc = fp_parsed.get("location", fp_parsed) if isinstance(fp_parsed.get("location"), dict) else fp_parsed
                    first_pass_cache = {
                        "place": fp_loc.get("place"),
                        "confidence": fp_loc.get("confidence"),
                        "reasoning": (
                            fp_loc.get("round1_description")
                            or json.dumps(fp_loc.get("candidates"))[:400]
                        ),
                    }
                    # Token accounting for the silent first pass
                    fp_pt = (fp_usage or {}).get("prompt_token_count") or len(fp_prompt) // 4
                    fp_ct = (fp_usage or {}).get("candidates_token_count") or len(json.dumps(fp_parsed)) // 4
                    total_cost += fp_pt * pricing.get("input", 2.0) / 1_000_000 + fp_ct * pricing.get("output", 12.0) / 1_000_000
                    logger.info(f"    LEDGER: calls={call_count}  spent=${total_cost:.4f} / cap ${args.max_cost:.2f}")
                prompt_text = build_prompt(
                    variant,
                    photo_metadata=photo_metadata,
                    gedcom_context=photo_gedcom_context,
                    prior_prediction=first_pass_cache,
                    forced_candidates=forced_candidates,
                    photo_year=photo_year,
                )
            else:
                prompt_text = build_prompt(
                    variant,
                    photo_metadata=photo_metadata,
                    gedcom_context=photo_gedcom_context,
                    forced_candidates=forced_candidates,
                    photo_year=photo_year,
                )

            logger.info(f"[{i+1}/{len(test_rows)}] {pid[:40]} variant={variant}")

            call_count += 1
            parsed, latency_ms, usage, err = call_gemini(prompt_text, image_bytes, suffix, GEMINI_MODEL, api_key)

            # If this is the candidate variant, cache the result for any subsequent
            # candidate_with_prior pass (avoids the silent first-pass spend above).
            if variant == "candidate" and parsed is not None and "candidate_with_prior" in variants:
                cand_loc = parsed.get("location", parsed) if isinstance(parsed.get("location"), dict) else parsed
                first_pass_cache = {
                    "place": cand_loc.get("place"),
                    "confidence": cand_loc.get("confidence"),
                    "reasoning": (
                        cand_loc.get("round1_description")
                        or json.dumps(cand_loc.get("candidates"))[:400]
                    ),
                }

            # Token accounting (prefer Gemini's own counts, fall back to char/4 estimate)
            if usage and usage.get("prompt_token_count"):
                pt = usage["prompt_token_count"]
                ct = usage.get("candidates_token_count") or 0
            else:
                pt = len(prompt_text) // 4
                resp_text = json.dumps(parsed) if parsed else ""
                ct = len(resp_text) // 4
            cost = pt * pricing.get("input", 2.0) / 1_000_000 + ct * pricing.get("output", 12.0) / 1_000_000
            total_cost += cost

            graded = evaluate_result(
                parsed,
                row["expected_aliases"],
                row.get("special_verdict"),
                forced_candidates=forced_candidates,
            )
            logger.info(
                f"    result place={graded['place']!r} conf={graded['confidence']} "
                f"verdict={graded['verdict']} canon_year_dist={graded.get('predicted_place_year_distance')} "
                f"cost=${cost:.4f}"
            )
            logger.info(f"    LEDGER: calls={call_count}  spent=${total_cost:.4f} / cap ${args.max_cost:.2f}")

            # Log to gemini_api_calls — record gedcom_context presence + variant.
            # Sub-keys pass=1 (candidate) vs pass=2 (candidate_with_prior) per AD-242.
            pass_num = 2 if variant == "candidate_with_prior" else 1
            response_summary = {
                "experiment_variant": variant,
                "experiment_id": experiment_id,
                "pass": pass_num,
                "predicted_place": graded["place"],
                "predicted_confidence": graded["confidence"],
                "ground_truth_location": row["expected_location"],
                "top1_match": graded["top1_match"],
                "top3_match": graded["top3_match"],
                "verdict": graded["verdict"],
                "bucket": row["bucket"],
                "candidates": graded.get("candidates"),
                "gedcom_context_present": photo_gedcom_context is not None,
                "gedcom_context_chars": len(photo_gedcom_context) if photo_gedcom_context else 0,
                "forced_candidates_count": len(forced_candidates),
                "predicted_place_year_distance": graded.get("predicted_place_year_distance"),
            }
            if args.no_db_log:
                logger.info("    --no-db-log set: skipping gemini_api_calls audit write")
            else:
                try:
                    log_gemini_call(
                        photo_id=pid,
                        model_used=GEMINI_MODEL,
                        call_type="experiment_location_shadow_eval",
                        prompt_tokens=pt,
                        completion_tokens=ct,
                        total_tokens=pt + ct,
                        cost_usd=round(cost, 6),
                        latency_ms=latency_ms,
                        status="success" if err is None else "error",
                        error_message=err,
                        response_summary=response_summary,
                        gemini_config={
                            "experiment_id": experiment_id,
                            "variant": variant,
                            "pass": pass_num,
                            "attempt_label": f"{variant}_shadow_eval_pass{pass_num}",
                            "request_surface": "scripts.session153_shadow_eval",
                            "request_mode": "experiment",
                            "trigger": "shadow_eval_prompt_ab",
                            "preset": "location_only",
                            "temperature": 0.1,
                            "gedcom_context_present": photo_gedcom_context is not None,
                        },
                        prompt_text=prompt_text,
                        full_response=parsed,
                        experiment_id=experiment_id,
                    )
                except Exception as log_err:
                    logger.warning(f"    failed to log to gemini_api_calls: {log_err}")

            # Capture the Round 2.5 audit trail in the file output so the
            # docs/feedback artifact is independently auditable (Codex P1 —
            # the JSON must not omit residence_distance_table / round_2_5_summary).
            _loc = {}
            if isinstance(parsed, dict):
                _loc = parsed.get("location") if isinstance(parsed.get("location"), dict) else parsed
            results.append(
                {
                    "photo_id": pid,
                    "bucket": row["bucket"],
                    "variant": variant,
                    "pass": pass_num,
                    "expected_location": row["expected_location"],
                    "predicted_place": graded["place"],
                    "predicted_confidence": graded["confidence"],
                    "top1_match": graded["top1_match"],
                    "top3_match": graded["top3_match"],
                    "verdict": graded["verdict"],
                    "cost_usd": round(cost, 6),
                    "latency_ms": latency_ms,
                    "error": err,
                    "candidates": graded.get("candidates"),
                    "residence_distance_table": _loc.get("residence_distance_table"),
                    "round_2_5_summary": _loc.get("round_2_5_summary"),
                    "eliminated_runner_up": _loc.get("eliminated_runner_up"),
                    "gedcom_context_present": photo_gedcom_context is not None,
                    "gedcom_context_chars": len(photo_gedcom_context) if photo_gedcom_context else 0,
                    # DETROIT-CANDIDATE-FORCE-167: the deterministic forced table
                    # + the de-gamed canonical distance for the model's primary.
                    "photo_year": photo_year,
                    "forced_candidates": forced_candidates,
                    "predicted_place_year_distance": graded.get("predicted_place_year_distance"),
                }
            )
        cap_reason = _cap_hit()
        if cap_reason:
            logger.warning(f"ABORT: {cap_reason} reached — stopping after photo {i+1}")
            aborted = True
            break

    logger.info(f"Total cost: ${total_cost:.4f}  results rows: {len(results)}")

    # Write raw results to disk. Output path mirrors the test-set scope so
    # Detroit-only reruns and full-eval runs don't clobber each other.
    is_detroit_only = bool(photo_id_filter) and photo_id_filter.issubset({
        "inbox_fox-charlie-001_204_02068_p_13akf5twbc3600",
        "inbox_fox-charlie-001_3_01659_p_13akf5twbc1045",
    })
    if args.out_path:
        # Explicit override always wins — never clobber a prior session's record.
        out_path = Path(args.out_path)
    elif is_detroit_only:
        out_path = Path("docs/feedback/session-154-shadow-eval-detroit-rerun.json")
    elif args.no_gedcom_context:
        out_path = Path("docs/feedback/session-154-shadow-eval-no-context.json")
    else:
        out_path = Path("docs/feedback/session-154-shadow-eval-full.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(
            {
                "experiment_id": experiment_id,
                "model": GEMINI_MODEL,
                "variants": variants,
                "total_cost_usd": round(total_cost, 6),
                "n_photos": len({r["photo_id"] for r in results}),
                "n_calls": len(results),
                "gedcom_context_disabled": args.no_gedcom_context,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "results": results,
            },
            f,
            indent=2,
        )
    logger.info(f"Wrote raw results to {out_path}")


if __name__ == "__main__":
    main()
