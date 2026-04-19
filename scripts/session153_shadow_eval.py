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


def build_prompt(variant: str, photo_metadata: dict | None = None) -> str:
    """Build a minimal prompt (preamble + one task section) for A/B comparison.

    To isolate the prompt-structure effect, both variants receive the same
    preamble, the same photo_metadata, and the same task framing. Only the
    location section and the JSON schema fragment differ.
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

    if variant == "baseline":
        parts.append(BASELINE_LOCATION_SECTION)
        schema = "{\n  " + _SCHEMA_FRAGMENTS["location"] + "\n}"
    elif variant == "candidate":
        parts.append(CANDIDATE_LOCATION_SECTION)
        schema = "{\n  " + CANDIDATE_LOCATION_SCHEMA + "\n}"
    else:
        raise ValueError(f"Unknown variant: {variant}")

    parts.append(f"\n## Response Format (JSON only)\n{schema}")
    return "\n\n".join(parts)


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


def call_gemini(prompt_text: str, image_bytes: bytes, suffix: str, model: str, api_key: str):
    """Call Gemini with the given prompt + image. Returns (parsed_dict, latency_ms, usage_meta, err)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key, http_options={"timeout": 180_000})
    mime = "image/png" if suffix.lower() == ".png" else "image/jpeg"
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
            return None, latency_ms, None, "empty_response"
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list) and parsed:
                parsed = parsed[0]
        except Exception as parse_err:
            return None, latency_ms, None, f"json_parse: {parse_err}"
        # Extract usage metadata if present
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
        return None, int((time.time() - t0) * 1000), None, str(e)


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

    # Resolve test photos
    test_rows = []
    for entry in TEST_SET:
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

    if args.dry_run:
        logger.info("Dry run — exiting before any API calls")
        return

    # Unique experiment ID for this run
    experiment_id = f"session153_shadow_eval_{int(time.time())}"
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

        for variant in ("baseline", "candidate"):
            if total_cost >= args.max_cost:
                logger.warning(f"Cost cap ${args.max_cost} reached — halting")
                break

            prompt_text = build_prompt(variant, photo_metadata=photo_metadata)
            logger.info(f"[{i+1}/{len(test_rows)}] {pid[:40]} variant={variant}")

            parsed, latency_ms, usage, err = call_gemini(prompt_text, image_bytes, suffix, GEMINI_MODEL, api_key)

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

            # Log to gemini_api_calls
            response_summary = {
                "experiment_variant": variant,
                "experiment_id": experiment_id,
                "predicted_place": graded["place"],
                "predicted_confidence": graded["confidence"],
                "ground_truth_location": row["expected_location"],
                "top1_match": graded["top1_match"],
                "top3_match": graded["top3_match"],
                "verdict": graded["verdict"],
                "bucket": row["bucket"],
                "candidates": graded.get("candidates"),
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
                        "attempt_label": f"{variant}_shadow_eval",
                        "request_surface": "scripts.session153_shadow_eval",
                        "request_mode": "experiment",
                        "trigger": "shadow_eval_prompt_ab",
                        "preset": "location_only",
                        "temperature": 0.1,
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
                }
            )
        if total_cost >= args.max_cost:
            break

    logger.info(f"Total cost: ${total_cost:.4f}  results rows: {len(results)}")

    # Write raw results to disk for the markdown writeup
    out_path = Path("docs/feedback/session-153-gemini-shadow-eval-raw.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(
            {
                "experiment_id": experiment_id,
                "model": GEMINI_MODEL,
                "total_cost_usd": round(total_cost, 6),
                "n_photos": len({r["photo_id"] for r in results}),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "results": results,
            },
            f,
            indent=2,
        )
    logger.info(f"Wrote raw results to {out_path}")


if __name__ == "__main__":
    main()
