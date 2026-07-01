"""Progressive Refinement: Re-analyze photos with verified facts.

When verified facts exist for a photo (confirmed identities, birth years,
GEDCOM relationships), re-run Gemini with enriched context and compare
to previous results.

Usage:
    # Dry run: show enriched prompts for 3 photos, no API calls
    python -m rhodesli_ml.scripts.progressive_refinement --dry-run

    # Mock run: simulate API calls with mock responses
    python -m rhodesli_ml.scripts.progressive_refinement --dry-run --mock

    # Single photo
    python -m rhodesli_ml.scripts.progressive_refinement --photo-id P001

    # All eligible photos with cost cap
    python -m rhodesli_ml.scripts.progressive_refinement --all --max-cost 5.00

See AD-138 for progressive refinement architecture.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from rhodesli_ml.gemini_config import (
    GEMINI_MODEL,
    DRY_RUN_PHOTO_LIMIT,
    MAX_COST_DEFAULT,
    get_model_pricing,
)
from rhodesli_ml.utils.api_logger import (
    log_api_call,
    get_previous_result,
)

DATA_DIR = Path("data")
ML_DATA_DIR = Path("rhodesli_ml/data")

# --- Fact Gathering ---


def load_identities() -> dict:
    """Load identities registry."""
    path = DATA_DIR / "identities.json"
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    return data.get("identities", {})


def load_photo_index() -> dict:
    """Load photo index."""
    path = DATA_DIR / "photo_index.json"
    if not path.exists():
        return {"photos": {}, "face_to_photo": {}}
    with open(path) as f:
        return json.load(f)


def load_date_labels() -> dict:
    """Load existing date labels keyed by photo_id."""
    path = ML_DATA_DIR / "date_labels.json"
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    labels = data.get("labels", data.get("date_labels", []))
    if isinstance(labels, list):
        return {l["photo_id"]: l for l in labels if "photo_id" in l}
    return labels


def load_relationships() -> list[dict]:
    """Load GEDCOM-derived relationships."""
    path = DATA_DIR / "relationships.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("relationships", [])


def load_annotations() -> list[dict]:
    """Load community annotations (approved only)."""
    path = DATA_DIR / "annotations.json"
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    annotations = data.get("annotations", {})
    # annotations can be a dict (keyed by ID) or a list
    if isinstance(annotations, dict):
        annotations = list(annotations.values())
    return [a for a in annotations if isinstance(a, dict) and a.get("status") == "approved"]


def gather_facts_for_photo(
    photo_id: str,
    photo_data: dict,
    identities: dict,
    relationships: list,
    annotations: list,
) -> dict:
    """Gather all verified facts for a given photo.

    Returns a structured dict of verified facts that can be used to
    enrich a Gemini prompt.
    """
    facts = {
        "photo_id": photo_id,
        "confirmed_people": [],
        "birth_years": {},
        "relationships": [],
        "annotations": [],
        "collection": photo_data.get("collection", ""),
        "source": photo_data.get("source", ""),
    }

    face_ids = set(photo_data.get("face_ids", []))

    # Find confirmed identities for faces in this photo
    for identity_id, identity in identities.items():
        if identity.get("merged_into"):
            continue
        if identity.get("state") != "CONFIRMED":
            continue

        # Check if any anchor face belongs to this photo
        anchors = set(identity.get("anchor_ids", []))
        matching_faces = anchors & face_ids
        if not matching_faces:
            continue

        name = identity.get("name", "Unknown")
        facts["confirmed_people"].append({
            "identity_id": identity_id,
            "name": name,
            "face_ids": list(matching_faces),
        })

        # Check for birth year in metadata
        metadata = identity.get("metadata", {})
        birth_year = metadata.get("birth_year")
        if birth_year:
            facts["birth_years"][name] = birth_year

    # Find GEDCOM relationships between confirmed people in this photo
    confirmed_ids = {p["identity_id"] for p in facts["confirmed_people"]}
    for rel in relationships:
        if rel.get("person_a") in confirmed_ids or rel.get("person_b") in confirmed_ids:
            # Get names for readability
            name_a = _get_name(identities, rel["person_a"])
            name_b = _get_name(identities, rel["person_b"])
            facts["relationships"].append({
                "type": rel.get("type", "unknown"),
                "person_a": name_a,
                "person_b": name_b,
            })

    # Find relevant annotations
    for ann in annotations:
        target_id = ann.get("target_id", "")
        if target_id in confirmed_ids:
            facts["annotations"].append({
                "type": ann.get("type"),
                "value": ann.get("value"),
                "target": _get_name(identities, target_id),
            })

    return facts


def _get_name(identities: dict, identity_id: str) -> str:
    """Get display name for an identity ID."""
    identity = identities.get(identity_id, {})
    return identity.get("name", f"Unknown ({identity_id[:8]})")


def count_verified_facts(facts: dict) -> int:
    """Count total verified facts for ranking photos."""
    count = len(facts.get("confirmed_people", []))
    count += len(facts.get("birth_years", {}))
    count += len(facts.get("relationships", []))
    count += len(facts.get("annotations", []))
    return count


# --- Enriched Prompt Builder ---

ENRICHED_PROMPT_TEMPLATE = """You are a forensic photo analyst specializing in dating historical photographs
from Sephardic Jewish communities, particularly from Rhodes (Dodecanese), Greece and
diaspora communities in New York City, Miami, and Tampa, Florida.

IMPORTANT CONTEXT — VERIFIED FACTS about this photo:
{verified_facts_section}

Using these verified facts as anchoring evidence, analyze this photo and provide:

1. **Date estimation** — decade probabilities and best year estimate.
   Cross-reference with the verified birth years to narrow the date range.
   Example: If someone born in 1905 appears to be ~30 years old, the photo is circa 1935.

2. **Per-face descriptions** — For each visible person, describe their apparent age,
   clothing, and any distinguishing features. Match to confirmed identities where possible.

3. **Location analysis** — Interior/exterior, studio vs casual, any geographic indicators.

4. **Cultural context** — Note that Rhodes diaspora fashion often lagged 5-15 years
   behind mainstream European/American trends.

Provide your analysis as JSON with this structure:
{{
    "estimated_decade": <int, e.g. 1940>,
    "best_year_estimate": <int>,
    "confidence": "high" | "medium" | "low",
    "probable_range": [<start_year>, <end_year>],
    "decade_probabilities": {{"1920": 0.1, "1930": 0.6, "1940": 0.3}},
    "reasoning_summary": "<2-3 sentences>",
    "per_face_descriptions": [
        {{"name": "<if known>", "apparent_age": <int>, "clothing": "<description>", "notes": "<any>"}}
    ],
    "location_analysis": "<description>",
    "cultural_context_notes": "<any relevant observations>",
    "evidence_changes": "<what changed vs previous estimate and why>",
    "scene_description": "<2-3 sentences>"
}}
"""


def build_verified_facts_section(facts: dict) -> str:
    """Build the verified facts section for the enriched prompt."""
    lines = []

    if facts["confirmed_people"]:
        lines.append("CONFIRMED IDENTITIES in this photo:")
        for person in facts["confirmed_people"]:
            name = person["name"]
            by_line = f"  - {name}"
            if name in facts.get("birth_years", {}):
                by_line += f" (born {facts['birth_years'][name]})"
            lines.append(by_line)

    if facts["relationships"]:
        lines.append("\nKNOWN RELATIONSHIPS:")
        for rel in facts["relationships"]:
            rel_type = rel["type"].replace("_", " ")
            lines.append(f"  - {rel['person_a']} ↔ {rel['person_b']} ({rel_type})")

    if facts["annotations"]:
        lines.append("\nCOMMUNITY ANNOTATIONS:")
        for ann in facts["annotations"]:
            lines.append(f"  - {ann['target']}: {ann['value']} (type: {ann['type']})")

    if facts["collection"]:
        lines.append(f"\nCOLLECTION: {facts['collection']}")

    if not lines:
        lines.append("No verified facts available for this photo.")

    return "\n".join(lines)


def build_enriched_prompt(facts: dict) -> str:
    """Build the full enriched prompt with verified facts."""
    facts_section = build_verified_facts_section(facts)
    return ENRICHED_PROMPT_TEMPLATE.format(verified_facts_section=facts_section)


# --- Comparison Engine ---


def compare_analyses(old_label: dict, new_result: dict) -> dict:
    """Compare old and new analysis results, highlighting changes."""
    changes = {
        "has_changes": False,
        "improvements": [],
        "regressions": [],
        "unchanged": [],
    }

    # Decade change
    old_decade = old_label.get("estimated_decade")
    new_decade = new_result.get("estimated_decade")
    if old_decade and new_decade:
        if old_decade != new_decade:
            changes["has_changes"] = True
            changes["improvements"].append(
                f"Decade: {old_decade}s → {new_decade}s"
            )
        else:
            changes["unchanged"].append(f"Decade: {old_decade}s (unchanged)")

    # Confidence change
    old_conf = old_label.get("confidence", "")
    new_conf = new_result.get("confidence", "")
    conf_rank = {"low": 0, "medium": 1, "high": 2}
    if old_conf and new_conf and old_conf != new_conf:
        changes["has_changes"] = True
        if conf_rank.get(new_conf, 0) > conf_rank.get(old_conf, 0):
            changes["improvements"].append(f"Confidence: {old_conf} → {new_conf}")
        else:
            changes["regressions"].append(f"Confidence: {old_conf} → {new_conf}")

    # Year range narrowing
    old_range = old_label.get("probable_range", [])
    new_range = new_result.get("probable_range", [])
    if len(old_range) == 2 and len(new_range) == 2:
        old_span = old_range[1] - old_range[0]
        new_span = new_range[1] - new_range[0]
        if new_span < old_span:
            changes["has_changes"] = True
            changes["improvements"].append(
                f"Range narrowed: {old_range[0]}-{old_range[1]} → {new_range[0]}-{new_range[1]}"
            )

    return changes


# --- Mock Response ---

MOCK_RESPONSE = json.dumps({
    "estimated_decade": 1940,
    "best_year_estimate": 1942,
    "confidence": "high",
    "probable_range": [1938, 1945],
    "decade_probabilities": {"1930": 0.15, "1940": 0.70, "1950": 0.15},
    "reasoning_summary": "Birth years of confirmed identities narrow the window. "
    "Military-era clothing and studio backdrop consistent with early 1940s.",
    "per_face_descriptions": [
        {"name": "Unknown", "apparent_age": 35, "clothing": "Dark suit, tie", "notes": "Formal pose"}
    ],
    "location_analysis": "Indoor studio, painted backdrop, professional lighting.",
    "cultural_context_notes": "Formal studio portrait consistent with Rhodes diaspora tradition.",
    "evidence_changes": "Birth year anchors narrowed estimate from 1930-1950 to 1938-1945.",
    "scene_description": "A formal studio portrait of a family group in their best attire.",
})


# --- Pipeline ---


def find_eligible_photos(
    photo_index: dict,
    identities: dict,
    relationships: list,
    annotations: list,
    date_labels: dict,
) -> list[tuple[str, dict, dict, int]]:
    """Find photos eligible for progressive refinement.

    Returns list of (photo_id, photo_data, facts, fact_count) tuples,
    sorted by fact_count descending (most facts first).
    """
    eligible = []
    photos = photo_index.get("photos", {})

    for photo_id, photo_data in photos.items():
        facts = gather_facts_for_photo(
            photo_id, photo_data, identities, relationships, annotations
        )
        fact_count = count_verified_facts(facts)

        # Only eligible if there are verified facts to add context
        if fact_count > 0:
            eligible.append((photo_id, photo_data, facts, fact_count))

    # Sort by fact count descending
    eligible.sort(key=lambda x: x[3], reverse=True)
    return eligible


def run_refinement(
    photo_id: str,
    photo_data: dict,
    facts: dict,
    date_labels: dict,
    model: str,
    mock: bool = False,
) -> dict | None:
    """Run progressive refinement for a single photo.

    Returns the new analysis result dict, or None on failure.
    """
    prompt = build_enriched_prompt(facts)
    old_label = date_labels.get(photo_id, {})

    if mock:
        response_text = MOCK_RESPONSE
        input_tokens = 2000
        output_tokens = 1500
    else:
        # Real API call — uses enriched prompt with verified facts
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: GEMINI_API_KEY not set.")
            print("Get one at: https://aistudio.google.com/apikey")
            return None

        image_path = Path("raw_photos") / photo_data.get("path", "")
        if not image_path.exists():
            print(f"  WARNING: Image not found at {image_path}")
            return None

        from rhodesli_ml.scripts.generate_date_labels import call_gemini
        # Pass enriched prompt with verified facts — this is the critical
        # connection that was missing in Session 60 (see Session 61, ACT 1)
        result = call_gemini(
            str(image_path), api_key, model=model, prompt=prompt
        )
        if result is None:
            return None
        response_text = json.dumps(result)
        input_tokens = 2000  # Approximate — actual counts from API
        output_tokens = 1500

    # Log the API call
    previous = get_previous_result(photo_id)
    log_api_call(
        photo_id=photo_id,
        model=model,
        prompt=prompt,
        response_text=response_text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        verified_facts=facts,
        previous_result=previous or old_label,
        metadata={"refinement": True, "fact_count": count_verified_facts(facts)},
    )

    # Parse and compare
    try:
        new_result = json.loads(response_text) if isinstance(response_text, str) else response_text
    except json.JSONDecodeError:
        print(f"  ERROR: Could not parse response for {photo_id}")
        return None

    comparison = compare_analyses(old_label, new_result)
    new_result["_refinement_comparison"] = comparison
    new_result["_verified_facts_used"] = facts

    return new_result


# --- Main ---


def main():
    parser = argparse.ArgumentParser(
        description="Progressive refinement: re-analyze photos with verified facts"
    )
    parser.add_argument("--photo-id", help="Refine a specific photo")
    parser.add_argument("--all", action="store_true", help="Refine all eligible photos")
    parser.add_argument("--dry-run", action="store_true",
                        help=f"Show prompts for {DRY_RUN_PHOTO_LIMIT} photos without API calls")
    parser.add_argument("--mock", action="store_true", help="Use mock API responses")
    parser.add_argument("--model", default=GEMINI_MODEL, help=f"Model to use (default: {GEMINI_MODEL})")
    parser.add_argument("--max-cost", type=float, default=MAX_COST_DEFAULT,
                        help=f"Max cost in USD (default: ${MAX_COST_DEFAULT})")
    parser.add_argument("--output", default="rhodesli_ml/data/refinement_results.json",
                        help="Output file for results")
    args = parser.parse_args()

    print("=== Progressive Refinement Pipeline ===")
    print(f"Model: {args.model}")
    print(f"Max cost: ${args.max_cost:.2f}")

    # Load all data
    identities = load_identities()
    photo_index = load_photo_index()
    date_labels = load_date_labels()
    relationships = load_relationships()
    annotations = load_annotations()

    print("\nData loaded:")
    print(f"  Photos: {len(photo_index.get('photos', {}))}")
    print(f"  Identities: {len(identities)} ({sum(1 for i in identities.values() if i.get('state') == 'CONFIRMED')} confirmed)")
    print(f"  Date labels: {len(date_labels)}")
    print(f"  Relationships: {len(relationships)}")
    print(f"  Annotations: {len(annotations)} (approved)")

    # Find eligible photos
    eligible = find_eligible_photos(
        photo_index, identities, relationships, annotations, date_labels
    )
    print(f"\nEligible for refinement: {len(eligible)} photos")

    if not eligible:
        print("No photos have verified facts. Nothing to refine.")
        return

    # Show top candidates
    print("\nTop candidates (most verified facts):")
    for photo_id, _, facts, fact_count in eligible[:5]:
        people = [p["name"] for p in facts["confirmed_people"]]
        print(f"  {photo_id}: {fact_count} facts — {', '.join(people[:3])}")

    # Determine which photos to process
    if args.photo_id:
        targets = [(pid, pd, f, fc) for pid, pd, f, fc in eligible if pid == args.photo_id]
        if not targets:
            print(f"\nPhoto {args.photo_id} not found or has no verified facts.")
            return
    elif args.dry_run:
        targets = eligible[:DRY_RUN_PHOTO_LIMIT]
    elif args.all:
        targets = eligible
    else:
        targets = eligible[:DRY_RUN_PHOTO_LIMIT]
        print(f"\nProcessing top {len(targets)} photos (use --all for all)")

    # Cost estimate
    pricing = get_model_pricing(args.model)
    estimated_cost = len(targets) * pricing.get("per_photo", 0.03)
    print(f"\nEstimated cost: ${estimated_cost:.2f} for {len(targets)} photos")

    if estimated_cost > args.max_cost and not args.dry_run:
        print(f"WARNING: Exceeds max cost (${args.max_cost:.2f}). Reducing batch.")
        max_photos = int(args.max_cost / pricing.get("per_photo", 0.03))
        targets = targets[:max_photos]
        print(f"Processing {len(targets)} photos instead.")

    # Process
    results = []
    for i, (photo_id, photo_data, facts, fact_count) in enumerate(targets):
        print(f"\n--- [{i+1}/{len(targets)}] Photo: {photo_id} ({fact_count} facts) ---")

        if args.dry_run and not args.mock:
            # Just show the enriched prompt
            prompt = build_enriched_prompt(facts)
            print(f"Enriched prompt ({len(prompt)} chars):")
            print(prompt[:500])
            if len(prompt) > 500:
                print(f"  ... ({len(prompt) - 500} more chars)")
            continue

        result = run_refinement(
            photo_id, photo_data, facts, date_labels, args.model, mock=args.mock
        )
        if result:
            results.append({
                "photo_id": photo_id,
                "fact_count": fact_count,
                "result": result,
                "comparison": result.get("_refinement_comparison", {}),
            })
            comp = result.get("_refinement_comparison", {})
            if comp.get("has_changes"):
                print(f"  CHANGES: {comp.get('improvements', [])}")
            else:
                print("  No changes from previous estimate.")

    # Save results
    if results:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump({"results": results, "model": args.model}, f, indent=2)
        print(f"\nResults saved to {output_path}")

    # Summary
    if results:
        changed = sum(1 for r in results if r["comparison"].get("has_changes"))
        print("\n=== Summary ===")
        print(f"Processed: {len(results)} photos")
        print(f"Changed: {changed}")
        print(f"Unchanged: {len(results) - changed}")


if __name__ == "__main__":
    main()
