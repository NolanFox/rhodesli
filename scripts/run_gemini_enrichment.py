#!/usr/bin/env python3
"""Gemini enrichment batch pipeline with GEDCOM context.

Processes photos in batches with cost controls. Uses curated GEDCOM
variant (AD-194) — the validated winner from Asheville litmus test.

Usage:
    # Dry run (first 3 photos)
    python scripts/run_gemini_enrichment.py --dry-run

    # First batch of 10
    python scripts/run_gemini_enrichment.py --batch-size 10 --max-cost 1.00

    # Full run (all GEDCOM-linked photos)
    python scripts/run_gemini_enrichment.py --batch-size 10 --max-cost 10.00

    # Resume from last completed photo
    python scripts/run_gemini_enrichment.py --resume --batch-size 10 --max-cost 10.00

Features:
- Processes photos in configurable batches
- Prints cost after each batch
- Stops if cumulative cost exceeds --max-cost
- Saves results incrementally (no data loss on crash)
- Uses Gatekeeper pattern: all results are PROPOSALS
- Supports resume from last completed photo
- Privacy filter: only sends deceased/pre-1930 people's data

Session: 82c | AD-194
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Pricing per 1M tokens for gemini-3.1-pro-preview
PRICING = {"input": 2.00, "output": 12.00}
MODEL = "gemini-3.1-pro-preview"


def estimate_cost(input_tokens, output_tokens):
    return (input_tokens / 1_000_000 * PRICING["input"] +
            output_tokens / 1_000_000 * PRICING["output"])


def call_gemini(prompt, image_path, model=MODEL, max_retries=3):
    """Call Gemini API with image + text. Retries on rate limit errors."""
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    ext = Path(image_path).suffix.lower().lstrip(".")
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")

    for attempt in range(max_retries):
        try:
            t0 = time.time()
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime),
                    types.Part.from_text(text=prompt),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            latency = time.time() - t0
            break
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                wait = 60 * (attempt + 1)
                logger.warning(f"    Rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
                if attempt == max_retries - 1:
                    raise
            else:
                raise

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0
    cost = estimate_cost(input_tokens, output_tokens)

    text = response.text or ""
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"raw_text": text, "parse_error": True}

    return {
        "result": result,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": cost,
        "latency_seconds": round(latency, 2),
        "model": model,
    }


def build_enrichment_prompt(gedcom_context=None):
    """Build enrichment prompt with optional GEDCOM context."""
    base = """You are a forensic photo analyst specializing in dating historical photographs
from Sephardic Jewish communities, particularly from Rhodes (Dodecanese), Greece and
diaspora communities in the United States.

## Cultural Context (IMPORTANT)
- Fashion in Rhodes and immigrant communities often LAGGED 5-15 years behind mainstream
- Studio portraits used deliberately conservative formal attire
- Early immigrant photos show a mix of old-world and new-world styles
- Rhodes stone architecture spans centuries — it is a WEAK dating signal alone

## Task
Analyze this photograph and extract the following information.
"""
    if gedcom_context:
        base += f"""
## Genealogical Context
{gedcom_context}

Use this genealogical data to improve date, location, and identity analysis.
Cross-reference visual observations with known biographical data:
- Compare visual clues against known family addresses and residential history
- Check if children's birth places match the apparent location
- Consider the "missing child" test: count visible vs known children to narrow date
- Use occupation/workplace info to narrow geographic possibilities
"""

    base += """
## Date Estimation
Examine FOUR evidence categories: (1) Print/Physical Format, (2) Fashion/Grooming,
(3) Environmental/Geographic, (4) Technological/Object Markers.
Rate each cue as STRONG, MODERATE, or WEAK.

## Location Identification
Identify the likely geographic location using both visual evidence and any biographical context.

## People Description
Describe each visible person with estimated age and appearance.

## Response Format (JSON only)
{
  "date_estimation": {
    "estimated_year": YYYY,
    "confidence": "high|medium|low",
    "probable_range": [YYYY, YYYY],
    "evidence_summary": "key evidence points",
    "decade_probabilities": {"1920": 0.05, "1930": 0.55}
  },
  "location": {
    "place": "City, State/Country",
    "confidence": "high|medium|low",
    "visual_evidence": "visual clues used",
    "biographical_evidence": "genealogical data used (if any)",
    "reasoning": "step by step"
  },
  "people": {
    "count": N,
    "descriptions": ["person 1", "person 2"]
  },
  "scene_description": "overall description",
  "visible_text": "any text in photo"
}"""
    return base


def filter_gedcom_for_privacy(identity_metadata):
    """Filter GEDCOM data for privacy — only include deceased or pre-1930 people.

    MANDATORY before any GEDCOM data goes to Gemini:
    - Remove anyone born after 1930
    - Remove anyone flagged as living
    - Keep only: name, birth year, death year, locations, events
    """
    birth_year = identity_metadata.get("birth_year")
    death_year = identity_metadata.get("death_year")
    death_date = identity_metadata.get("death_date_full")

    # Must be deceased OR born before 1930
    if death_year or death_date:
        return True  # deceased, safe to include
    if birth_year and birth_year <= 1930:
        return True  # born before 1930, likely deceased
    return False  # might be living, exclude


def build_curated_context_from_metadata(face_ids, identities, photo_date_estimate=None):
    """Build curated GEDCOM context from identity metadata.

    Uses the ±15yr window approach validated in AD-194.
    """
    sections = []

    for face_id in face_ids:
        identity_id = None
        identity = None
        for iid, ident in identities.items():
            if face_id in ident.get("anchor_ids", []) + ident.get("candidate_ids", []):
                if ident.get("state") == "CONFIRMED":
                    identity_id = iid
                    identity = ident
                    break
                if identity_id is None:
                    identity_id = iid
                    identity = ident

        if not identity or not identity.get("metadata", {}).get("gedcom_xref"):
            continue

        meta = identity.get("metadata", {})

        # Privacy filter
        if not filter_gedcom_for_privacy(meta):
            continue

        name = identity.get("name", "Unknown")
        lines = [f"Person: {name}"]

        birth_year = meta.get("birth_year") or identity.get("birth_year")
        birth_place = meta.get("birth_place", "")
        birth_date = meta.get("birth_date_full", "")
        death_place = meta.get("death_place", "")
        death_date = meta.get("death_date_full", "")

        if birth_date:
            birth_str = f"  Born: {birth_date}"
            if birth_place:
                birth_str += f" in {birth_place}"
            lines.append(birth_str)
        elif birth_year:
            birth_str = f"  Born: {birth_year}"
            if birth_place:
                birth_str += f" in {birth_place}"
            lines.append(birth_str)

        if death_date:
            death_str = f"  Died: {death_date}"
            if death_place:
                death_str += f" in {death_place}"
            lines.append(death_str)

        if photo_date_estimate and birth_year:
            age = photo_date_estimate - birth_year
            if 0 < age < 120:
                lines.append(f"  Estimated age in photo (~{photo_date_estimate}): {age}")

        sections.append("\n".join(lines))

    if not sections:
        return ""

    return "GENEALOGICAL CONTEXT FOR IDENTIFIED INDIVIDUALS:\n\n" + "\n\n".join(sections)


def find_photo_file(photo_path):
    """Resolve photo file path — try multiple locations."""
    candidates = [
        PROJECT_ROOT / photo_path,
        PROJECT_ROOT / "raw_photos" / Path(photo_path).name,
        PROJECT_ROOT / photo_path.replace("data/uploads/", ""),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def build_photo_batch(identities, photo_index, gedcom_only=True):
    """Build list of photos to process, optionally filtered to GEDCOM-linked."""
    gedcom_identity_ids = set()
    for iid, ident in identities.items():
        if ident.get("metadata", {}).get("gedcom_xref"):
            gedcom_identity_ids.add(iid)

    photos = []
    for pid, photo in photo_index.get("photos", {}).items():
        face_ids = photo.get("face_ids", [])
        has_gedcom = False

        for fid in face_ids:
            for iid in gedcom_identity_ids:
                ident = identities[iid]
                if fid in ident.get("anchor_ids", []) + ident.get("candidate_ids", []):
                    has_gedcom = True
                    break
            if has_gedcom:
                break

        if gedcom_only and not has_gedcom:
            continue

        photo_file = find_photo_file(photo.get("path", ""))
        if not photo_file:
            continue

        photos.append({
            "photo_id": pid,
            "path": str(photo_file),
            "face_ids": face_ids,
            "has_gedcom": has_gedcom,
            "face_count": len(face_ids),
        })

    return photos


def load_existing_results(output_path):
    """Load previously saved results for resume support."""
    if output_path.exists():
        with open(output_path) as f:
            data = json.load(f)
        return data.get("results", [])
    return []


def save_results(output_path, results, total_cost, batch_info):
    """Save results incrementally."""
    output = {
        "experiment": "gemini_gedcom_enrichment",
        "model": MODEL,
        "variant": "curated",
        "timestamp": datetime.now().isoformat(),
        "total_cost": round(total_cost, 4),
        "photos_processed": len(results),
        "batch_info": batch_info,
        "results": results,
    }
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Run Gemini enrichment with GEDCOM context")
    parser.add_argument("--batch-size", type=int, default=10, help="Photos per batch")
    parser.add_argument("--max-cost", type=float, default=10.00, help="Max cost in USD")
    parser.add_argument("--dry-run", action="store_true", help="Process only 3 photos")
    parser.add_argument("--resume", action="store_true", help="Resume from last run")
    parser.add_argument("--output", default=None, help="Output path")
    parser.add_argument("--all-photos", action="store_true",
                        help="Process all photos, not just GEDCOM-linked")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Output path
    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = PROJECT_ROOT / "results" / f"enrichment_{ts}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load data
    with open(PROJECT_ROOT / "data" / "identities.json") as f:
        identities = json.load(f).get("identities", {})
    with open(PROJECT_ROOT / "data" / "photo_index.json") as f:
        photo_index = json.load(f)

    # Build photo batch
    gedcom_only = not args.all_photos
    photos = build_photo_batch(identities, photo_index, gedcom_only=gedcom_only)
    logger.info(f"Found {len(photos)} photos to process (GEDCOM-only: {gedcom_only})")

    if args.dry_run:
        photos = photos[:3]
        logger.info(f"DRY RUN: processing {len(photos)} photos")

    # Resume support
    existing_results = []
    completed_ids = set()
    if args.resume:
        existing_results = load_existing_results(output_path)
        completed_ids = {r["photo_id"] for r in existing_results if r.get("status") == "success"}
        logger.info(f"Resuming: {len(completed_ids)} already completed")
        photos = [p for p in photos if p["photo_id"] not in completed_ids]

    results = existing_results.copy()
    total_cost = sum(r.get("cost", 0) for r in results if r.get("status") == "success")
    batch_num = 0

    for i in range(0, len(photos), args.batch_size):
        batch = photos[i:i + args.batch_size]
        batch_num += 1
        batch_cost = 0

        logger.info(f"\n=== Batch {batch_num} ({len(batch)} photos) ===")

        for j, photo in enumerate(batch):
            pid = photo["photo_id"]
            logger.info(f"  [{i+j+1}/{len(photos)}] {Path(photo['path']).name} "
                        f"(faces={photo['face_count']}, gedcom={photo['has_gedcom']})")

            # Build GEDCOM context
            gedcom_context = None
            if photo["has_gedcom"]:
                gedcom_context = build_curated_context_from_metadata(
                    photo["face_ids"], identities, photo_date_estimate=None
                )

            prompt = build_enrichment_prompt(gedcom_context)

            try:
                resp = call_gemini(prompt, photo["path"])
                resp["photo_id"] = pid
                resp["status"] = "success"
                resp["has_gedcom"] = photo["has_gedcom"]
                resp["gedcom_context_tokens"] = len(gedcom_context) // 4 if gedcom_context else 0

                batch_cost += resp["cost"]
                total_cost += resp["cost"]

                loc = resp["result"].get("location", {})
                logger.info(f"    Location: {loc.get('place', 'N/A')} "
                            f"[{loc.get('confidence', '?')}]")
                logger.info(f"    Cost: ${resp['cost']:.4f} | "
                            f"Running: ${total_cost:.4f}")

            except Exception as e:
                logger.error(f"    ERROR: {e}")
                resp = {"photo_id": pid, "status": "error", "error": str(e)}

            results.append(resp)
            time.sleep(1)  # Rate limit buffer

            # Budget check per-photo
            if total_cost >= args.max_cost:
                logger.warning(f"*** BUDGET CAP REACHED: ${total_cost:.4f} >= ${args.max_cost:.2f} ***")
                save_results(output_path, results, total_cost, {
                    "stopped_reason": "budget_cap",
                    "batch_size": args.batch_size,
                    "max_cost": args.max_cost,
                })
                _print_summary(results, total_cost)
                return

        # Batch summary
        logger.info(f"\n  Batch {batch_num} cost: ${batch_cost:.4f}")
        logger.info(f"  Running total: ${total_cost:.4f}")
        logger.info(f"  Budget remaining: ${args.max_cost - total_cost:.4f}")

        # Save incrementally after each batch
        save_results(output_path, results, total_cost, {
            "batch_size": args.batch_size,
            "max_cost": args.max_cost,
            "batches_completed": batch_num,
        })

    logger.info(f"\nAll {len(photos)} photos processed!")
    save_results(output_path, results, total_cost, {
        "batch_size": args.batch_size,
        "max_cost": args.max_cost,
        "completed": True,
    })
    _print_summary(results, total_cost)


def _print_summary(results, total_cost):
    """Print final summary."""
    success = [r for r in results if r.get("status") == "success"]
    errors = [r for r in results if r.get("status") == "error"]
    gedcom = [r for r in success if r.get("has_gedcom")]
    no_gedcom = [r for r in success if not r.get("has_gedcom")]

    print("\n" + "=" * 60)
    print("ENRICHMENT PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Total processed: {len(results)}")
    print(f"  Successful: {len(success)}")
    print(f"  Errors: {len(errors)}")
    print(f"  With GEDCOM: {len(gedcom)}")
    print(f"  Without GEDCOM: {len(no_gedcom)}")
    print(f"  Total cost: ${total_cost:.4f}")
    if success:
        avg = total_cost / len(success)
        print(f"  Avg cost/photo: ${avg:.4f}")

    # Location confidence breakdown
    high = sum(1 for r in success
               if r.get("result", {}).get("location", {}).get("confidence") == "high")
    medium = sum(1 for r in success
                 if r.get("result", {}).get("location", {}).get("confidence") == "medium")
    low = sum(1 for r in success
              if r.get("result", {}).get("location", {}).get("confidence") == "low")
    print(f"  Location confidence: high={high}, medium={medium}, low={low}")


if __name__ == "__main__":
    main()
