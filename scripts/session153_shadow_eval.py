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
        "gt_source": "Session 153 audit: Albert Fox GEDCOM 1917-1918 Detroit + Belle Isle Conservatory visual match (external Burton Historical Collection comparison needed for full certainty)",
        "bucket": "Detroit control",
    },
    # Detroit control #2 — second Belle Isle Conservatory frame. Session 153b Phase 5 gate.
    {
        "photo_id": "inbox_fox-charlie-001_3_01659_p_13akf5twbc1045",
        "expected_location": "Detroit, Michigan",
        "expected_aliases": ["Belle Isle", "Detroit"],
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
CANDIDATE_LOCATION_SECTION = """## Location Identification (structured three-round reasoning)

Work through the following THREE ROUNDS in order. Each round must be completed
before the next. Do not jump ahead to a final answer.

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

**ROUND 3 — Pick the primary location and eliminate the runner-up.**
Choose ONE candidate as primary. Explicitly name at least ONE other candidate
you are eliminating and cite the specific visual feature that rules it out. If
you cannot eliminate a runner-up with a specific feature, lower your confidence.

**Subject-weighted geography rule.** When GEDCOM context is provided and a
subject's own residence at the photo's estimated date range conflicts with a
relative's residence, prefer the subject's own residence. Immigration / port-of-
entry events are NEVER evidence of where someone lived.

**Output contract.**
- `place` = the primary location chosen in Round 3
- `candidates[]` = ALL considered candidates from Round 2 (minimum 2), each with
  `feature_supporting`, `feature_refuting`, and `reasoning`
- `diagnostic_features[]` = at least 2 features from Round 1 that pinned the answer
- `eliminated_runner_up` = {"place": ..., "refuting_feature": ...}
- `confidence` = "high" only if (a) ≥2 diagnostic features support the primary
  AND (b) runner-up was eliminated via a specific feature AND (c) biographical
  support agrees (when context provided). Otherwise "medium" or "low".
- `source_type` = "visual" | "biographical" | "both"

If the photograph is itself a REPRODUCTION of another photograph (e.g., newspaper
clipping, magazine page, album page), say so: set `place` to describe the
reproduction type (e.g., "Newspaper clipping — venue not determinable from
reproduction") and note it in `diagnostic_features`.

Do NOT collapse the rounds into a single paragraph. Return your work for each
round in the JSON fields below."""


# --- Candidate location schema (JSON body hint). ---
CANDIDATE_LOCATION_SCHEMA = """"location": {
  "place": "<primary chosen in Round 3>",
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
  "eliminated_runner_up": {"place": "...", "refuting_feature": "..."},
  "source_type": "visual|biographical|both"
}"""


# --- Iterative refinement block (AD-242, Session 154 Phase A2). ---
# Embedded into the candidate_with_prior variant on the second pass. The
# refuting-feature requirement guards against sycophantic self-agreement.
PRIOR_PREDICTION_BLOCK = """## Prior prediction to cross-check
Your first-pass prediction for this photo: place=<PLACE>, confidence=<CONF>.
First-pass reasoning: <REASONING>

Cross-check this prior prediction against:
- The subjects' GEDCOM residences at the photo's likely date range (above)
- The diagnostic visual features from Round 1

Decide ONE of the following and state which:
  - CONFIRM the prior prediction. To do so, name at least ONE specific
    GEDCOM fact OR ONE specific Round-1 visual feature that POSITIVELY
    supports it (not just absence of refutation).
  - REFUTE the prior prediction. To do so, name the specific feature or
    GEDCOM fact that REFUTES it, and propose an amended `place`.
  - LOWER CONFIDENCE without changing place. To do so, name the specific
    feature or GEDCOM fact that introduces doubt.

Do NOT simply agree with the prior prediction without naming a positive
supporting feature or fact. "It seems plausible" is not a confirmation."""


def build_prompt(
    variant: str,
    photo_metadata: dict | None = None,
    gedcom_context: str | None = None,
    prior_prediction: dict | None = None,
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

    if variant == "baseline":
        parts.append(BASELINE_LOCATION_SECTION)
        schema = "{\n  " + _SCHEMA_FRAGMENTS["location"] + "\n}"
    elif variant == "candidate":
        parts.append(CANDIDATE_LOCATION_SECTION)
        schema = "{\n  " + CANDIDATE_LOCATION_SCHEMA + "\n}"
    elif variant == "candidate_with_prior":
        if not prior_prediction:
            raise ValueError("candidate_with_prior requires prior_prediction kwarg")
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


def resolve_photo(photo_id: str, sb) -> dict | None:
    """Pull path + collection + source for a photo from Supabase."""
    r = sb.table("photos").select("photo_id, path, collection, source").eq("photo_id", photo_id).execute()
    if not r.data:
        return None
    p = r.data[0]
    path = Path(p.get("path") or "")
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
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


def evaluate_result(parsed: dict | None, expected_aliases: list[str], special: str | None = None) -> dict:
    """Grade a parsed Gemini location result against expected aliases."""
    if parsed is None:
        return {"verdict": "error", "top1_match": False, "top3_match": False, "place": None, "confidence": None}

    loc = parsed.get("location") if isinstance(parsed.get("location"), dict) else parsed
    if not isinstance(loc, dict):
        return {"verdict": "error", "top1_match": False, "top3_match": False, "place": None, "confidence": None}

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
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-cost", type=float, default=2.0)
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
    args = ap.parse_args()

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
        photo = resolve_photo(entry["photo_id"], sb)
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

    # Unique experiment ID for this run
    experiment_id = f"session154_shadow_eval_{int(time.time())}"
    logger.info(f"Experiment ID: {experiment_id}")

    results = []
    total_cost = 0.0

    for i, row in enumerate(test_rows):
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

        # Per-photo cache of first-pass candidate result for the candidate_with_prior variant.
        # Same photo's `candidate` run feeds the prior_prediction for `candidate_with_prior`.
        first_pass_cache = None

        for variant in variants:
            if total_cost >= args.max_cost:
                logger.warning(f"Cost cap ${args.max_cost} reached — halting")
                break

            # Build the prompt — candidate_with_prior needs a first-pass result
            if variant == "candidate_with_prior":
                if first_pass_cache is None:
                    # If `candidate` wasn't run for this photo (e.g. user passed
                    # --variants candidate_with_prior alone), run a silent first pass
                    # so the prior-prediction has substance. Cost still bills under
                    # the same budget.
                    fp_prompt = build_prompt(
                        "candidate", photo_metadata=photo_metadata, gedcom_context=photo_gedcom_context
                    )
                    logger.info(f"[{i+1}/{len(test_rows)}] {pid[:40]} variant=candidate (silent first pass)")
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
                prompt_text = build_prompt(
                    variant,
                    photo_metadata=photo_metadata,
                    gedcom_context=photo_gedcom_context,
                    prior_prediction=first_pass_cache,
                )
            else:
                prompt_text = build_prompt(
                    variant, photo_metadata=photo_metadata, gedcom_context=photo_gedcom_context
                )

            logger.info(f"[{i+1}/{len(test_rows)}] {pid[:40]} variant={variant}")

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

            graded = evaluate_result(parsed, row["expected_aliases"], row.get("special_verdict"))
            logger.info(
                f"    result place={graded['place']!r} conf={graded['confidence']} "
                f"verdict={graded['verdict']} cost=${cost:.4f}"
            )

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
            }
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
                    "gedcom_context_present": photo_gedcom_context is not None,
                    "gedcom_context_chars": len(photo_gedcom_context) if photo_gedcom_context else 0,
                }
            )
        if total_cost >= args.max_cost:
            break

    logger.info(f"Total cost: ${total_cost:.4f}  results rows: {len(results)}")

    # Write raw results to disk. Output path mirrors the test-set scope so
    # Detroit-only reruns and full-eval runs don't clobber each other.
    is_detroit_only = bool(photo_id_filter) and photo_id_filter.issubset({
        "inbox_fox-charlie-001_204_02068_p_13akf5twbc3600",
        "inbox_fox-charlie-001_3_01659_p_13akf5twbc1045",
    })
    if is_detroit_only:
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
