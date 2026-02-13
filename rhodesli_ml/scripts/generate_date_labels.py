"""Generate silver date labels and rich metadata for photos using Gemini Vision API.

Uses an evidence-first prompt architecture with decomposed analysis across
4 evidence categories (print/format, fashion, environment, technology).
Outputs structured JSON with decade probabilities, year estimates,
per-cue evidence ratings, plus rich photo metadata (scene description,
OCR, keywords, setting, photo type, people count, condition, clothing).

See AD-048 for the rich metadata extraction decision rationale.

Usage:
    # Dry run: process 3 photos, print results, show cost estimate
    python -m rhodesli_ml.scripts.generate_date_labels --dry-run

    # Test with free-tier model
    python -m rhodesli_ml.scripts.generate_date_labels --dry-run --model gemini-3-flash-preview

    # Full run with cost cap
    python -m rhodesli_ml.scripts.generate_date_labels --model gemini-3-pro-preview --max-cost 5.00

    # Label all undated photos
    python -m rhodesli_ml.scripts.generate_date_labels --model gemini-3-pro-preview --batch-size 0

Requires GEMINI_API_KEY environment variable. Get one at:
    https://aistudio.google.com/apikey (free, takes 30 seconds)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Cost per photo estimates (input + output tokens)
# Per photo: ~1,790 input tokens (image + prompt) + ~2,800 output tokens
# (increased from ~2,000 due to rich metadata fields — AD-048)
MODEL_COSTS = {
    "gemini-3-pro-preview": {
        "input_per_million": 2.00,
        "output_per_million": 12.00,
        "per_photo": 0.037,
        "note": "Best quality, SOTA vision reasoning",
    },
    "gemini-3-flash-preview": {
        "input_per_million": 0.50,
        "output_per_million": 3.00,
        "per_photo": 0.010,
        "note": "Free tier available, very good quality",
    },
    "gemini-2.5-flash": {
        "input_per_million": 0.30,
        "output_per_million": 2.50,
        "per_photo": 0.008,
        "note": "Stable, good price/performance",
    },
}

PROMPT = """You are a forensic photo analyst specializing in dating historical photographs
from Sephardic Jewish communities, particularly from Rhodes (Dodecanese), Greece and
diaspora communities in New York City, Miami, and Tampa, Florida.

## Task
Analyze this photograph and estimate when it was ORIGINALLY TAKEN (not when printed or scanned).

## Analysis Method
Examine FOUR independent evidence categories. For each, list ONLY what you can actually observe.
Do NOT invent specific brand names, car models, or named fashion styles unless clearly readable
in the image.

### 1. Print/Physical Format
Examine: border style (white, scalloped, deckled, borderless), color type (B&W, sepia, hand-tinted,
color), print shape (square, rectangular, oval), paper surface (glossy, matte, textured), print size
indicators, any visible studio stamps or markings.

### 2. Fashion/Grooming
Examine: clothing silhouettes (not brand names), hat styles, hairstyles, facial hair, jewelry,
accessories. Note whether this appears to be everyday wear or formal/studio attire.

### 3. Environmental/Geographic
Examine: architecture style (Mediterranean stone, NYC brick, Miami Art Deco, Tampa bungalow),
vegetation, street features, signage language, urban vs rural setting.

### 4. Technological/Object Markers
Examine: vehicles (general era, not specific models unless clearly visible), furniture style,
appliances, lighting fixtures, photography equipment visible.

## Cultural Context (IMPORTANT)
These photos are from a Sephardic Jewish community. Account for:
- Fashion in Rhodes and immigrant communities often LAGGED 5-15 years behind Paris/London mainstream
- Studio portraits used deliberately conservative formal attire that can appear older than actual date
- Early immigrant photos in the US often show a mix of old-world and new-world styles
- Rhodes stone architecture spans centuries — it is a WEAK dating signal on its own

## Output Rules
- Rate each observed cue as STRONG, MODERATE, or WEAK indicator
- Provide a suggested date range [start_year, end_year] for each cue
- Distinguish between the capture date and any evidence of reprinting
- If evidence is weak or ambiguous, say so — avoid overconfidence
- When evidence conflicts, explain which signals are stronger and why
- The decade_probabilities MUST sum to 1.0 and only include decades with >0.01 probability
- best_year_estimate should be your best point estimate, NOT just the midpoint of a decade

## Response Format (JSON only)
{
    "date_estimation": {
        "estimated_decade": 1940,
        "best_year_estimate": 1937,
        "confidence": "medium",
        "probable_range": [1935, 1955],
        "decade_probabilities": {
            "1920": 0.05,
            "1930": 0.15,
            "1940": 0.55,
            "1950": 0.20,
            "1960": 0.05
        },
        "capture_vs_print": "Likely 1940s capture. Print characteristics consistent with original.",
        "location_estimate": "Rhodes (stone masonry, Mediterranean vegetation)",
        "is_color": false,
        "evidence": {
            "print_format": [
                {"cue": "straight white border, ~3mm", "strength": "moderate", "suggested_range": [1930, 1955]}
            ],
            "fashion": [
                {"cue": "men in wide-lapel suits with padded shoulders", "strength": "moderate", "suggested_range": [1940, 1948]}
            ],
            "environment": [
                {"cue": "stone masonry arches, Mediterranean style", "strength": "weak", "suggested_range": [1900, 1950]}
            ],
            "technology": []
        },
        "cultural_lag_applied": true,
        "cultural_lag_note": "Adjusted +5 years from fashion cues due to Sephardic diaspora context",
        "reasoning_summary": "Fashion cues suggest 1940s. Border style consistent. Stone architecture indicates Rhodes but is weak for dating."
    },
    "scene_description": "Formal studio portrait of a middle-aged man and two women. The man stands in the center wearing a dark suit. The women are seated on either side in light-colored dresses. A painted backdrop depicts a garden scene.",
    "visible_text": "A mi querida Estrella de tu hermano Samuel",
    "keywords": ["formal portrait", "studio", "family group", "suit", "lace collar", "painted backdrop"],
    "setting": "indoor_studio",
    "photo_type": "formal_portrait",
    "people_count": 3,
    "condition": "good",
    "clothing_notes": "Man in dark three-piece suit with pocket watch chain. Younger woman in light embroidered dress. Older woman in dark dress with lace collar."
}

Valid decades for probabilities: 1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000.
Confidence levels: "high" (multiple strong cues agree), "medium" (moderate cues or some conflict), "low" (weak/ambiguous cues).

## Additional Metadata Instructions

In addition to date estimation, extract the following metadata:

scene_description: 2-3 sentences describing what is visible in the photo. Include people, their arrangement, the setting, and any notable objects. Write as if describing the photo to someone who cannot see it.

visible_text: If there is ANY handwritten or printed text visible on or around the photo (inscriptions, captions, dates written on the photo, text on clothing, signs, documents), transcribe it exactly. Include the original language. If no text is visible, return null.

keywords: 5-15 searchable tags covering: people descriptors (man, woman, child, elderly), setting (studio, outdoor, home), occasion (wedding, funeral, school, military), objects (hat, umbrella, car), and any culturally specific items (fez, traditional dress).

setting: Classify as one of: indoor_studio, outdoor_urban, outdoor_rural, indoor_home, indoor_other, outdoor_other, unknown.

photo_type: Classify as one of: formal_portrait, group_photo, candid, document, postcard, wedding, funeral, school, military, religious_ceremony, other.

people_count: How many people are visible in the photo (include partially visible people). Return 0 if no people are visible.

condition: Rate the physical condition of the photo: excellent, good, fair, poor. Consider fading, tears, stains, and damage.

clothing_notes: Brief description of notable clothing and accessories. This is valuable for both cultural documentation and date estimation cross-validation.
"""


def load_photo_index(path: str = "data/photo_index.json") -> dict:
    """Load photo index and return photos dict."""
    with open(path) as f:
        data = json.load(f)
    return data.get("photos", data)


def get_undated_photos(photos: dict) -> list[tuple[str, dict]]:
    """Return (photo_id, photo_entry) for photos without meaningful dates.

    Excludes photos where date_taken is a scan-era timestamp (2000+).
    """
    undated = []
    for pid, photo in photos.items():
        if not isinstance(photo, dict):
            continue
        date_taken = photo.get("date_taken", "")
        if date_taken:
            try:
                year = int(str(date_taken)[:4])
                if year < 2000:
                    continue  # Has a real pre-2000 date, skip
            except (ValueError, IndexError):
                pass
        undated.append((pid, photo))
    return undated


def load_existing_labels(path: str) -> dict:
    """Load existing labels to avoid re-labeling."""
    labels_path = Path(path)
    if not labels_path.exists():
        return {}
    with open(labels_path) as f:
        data = json.load(f)
    return {entry["photo_id"]: entry for entry in data.get("labels", [])}


def call_gemini(image_path: str, api_key: str, model: str = "gemini-3-pro-preview") -> dict | None:
    """Call Gemini Vision API with a photo and return parsed structured response.

    Uses the google-genai SDK (new unified SDK).
    Returns the full structured evidence dict or None on failure.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # Read image file
    image_bytes = Path(image_path).read_bytes()
    mime_type = "image/jpeg"
    if image_path.lower().endswith(".png"):
        mime_type = "image/png"

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text=PROMPT),
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        # Parse response
        text = response.text
        if not text:
            print("  WARNING: Empty response from Gemini")
            return None

        parsed = json.loads(text)

        # Handle nested date_estimation structure (new format) or flat (legacy)
        date_est = parsed.get("date_estimation", parsed)

        # Validate required fields
        decade = date_est.get("estimated_decade")
        if not isinstance(decade, int) or decade < 1900 or decade > 2030:
            print(f"  WARNING: Invalid decade {decade}, skipping")
            return None

        # Validate decade_probabilities sum to ~1.0
        probs = date_est.get("decade_probabilities", {})
        if probs:
            prob_sum = sum(probs.values())
            if abs(prob_sum - 1.0) > 0.05:
                print(f"  WARNING: decade_probabilities sum to {prob_sum:.3f}, normalizing")
                probs = {k: v / prob_sum for k, v in probs.items()}
                date_est["decade_probabilities"] = probs

        # Flatten date_estimation fields to top level for storage,
        # then merge in rich metadata fields
        if "date_estimation" in parsed:
            result = dict(date_est)
            for key in ("scene_description", "visible_text", "keywords",
                        "setting", "photo_type", "people_count",
                        "condition", "clothing_notes"):
                result[key] = parsed.get(key)
            return result
        else:
            return parsed

    except json.JSONDecodeError as e:
        print(f"  ERROR: Failed to parse JSON response: {e}")
        # Try to extract JSON from markdown code blocks
        if text:
            json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
        return None
    except Exception as e:
        print(f"  ERROR: Gemini API call failed: {e}")
        return None


def save_labels(labels: list[dict], path: str):
    """Save labels to JSON file with atomic write."""
    output = {
        "schema_version": 2,
        "labels": labels,
    }
    tmp_path = Path(path).with_suffix(".tmp")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_path, "w") as f:
        json.dump(output, f, indent=2)
    tmp_path.rename(path)
    print(f"Saved {len(labels)} labels to {path}")


def print_summary(labels: list[dict]):
    """Print a summary of labeling results."""
    if not labels:
        print("No labels to summarize.")
        return

    # Confidence distribution
    conf_counts = {}
    decade_counts = {}
    for label in labels:
        conf = label.get("confidence", "unknown")
        conf_counts[conf] = conf_counts.get(conf, 0) + 1
        decade = label.get("estimated_decade", 0)
        decade_counts[decade] = decade_counts.get(decade, 0) + 1

    print("\n--- Summary ---")
    print(f"Total labels: {len(labels)}")

    print("\nConfidence distribution:")
    for conf in ["high", "medium", "low"]:
        count = conf_counts.get(conf, 0)
        pct = count / len(labels) * 100
        bar = "#" * int(pct / 2)
        print(f"  {conf:8s}: {count:3d} ({pct:5.1f}%) {bar}")

    print("\nDecade distribution:")
    for decade in sorted(decade_counts.keys()):
        count = decade_counts[decade]
        pct = count / len(labels) * 100
        bar = "#" * int(pct / 2)
        print(f"  {decade}s: {count:3d} ({pct:5.1f}%) {bar}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate silver date labels via Gemini Vision API",
        epilog="Get a Gemini API key at: https://aistudio.google.com/apikey",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Process 3 photos, print results, show cost estimate, then STOP",
    )
    parser.add_argument(
        "--batch-size", type=int, default=10,
        help="Number of photos to label (0 = all, default: 10)",
    )
    parser.add_argument(
        "--photo-dir", default="raw_photos",
        help="Directory containing photos (default: raw_photos)",
    )
    parser.add_argument(
        "--output", default="rhodesli_ml/data/date_labels.json",
        help="Output labels file",
    )
    parser.add_argument(
        "--model", default="gemini-3-pro-preview",
        choices=list(MODEL_COSTS.keys()),
        help="Gemini model to use (default: gemini-3-pro-preview)",
    )
    parser.add_argument(
        "--max-cost", type=float, default=5.00,
        help="Maximum estimated cost in USD before halting (default: $5.00)",
    )
    args = parser.parse_args()

    # Load photos
    photos = load_photo_index()
    undated = get_undated_photos(photos)
    existing = load_existing_labels(args.output)

    # Filter out already-labeled photos
    to_label = [(pid, p) for pid, p in undated if pid not in existing]

    print(f"Total photos: {len(photos)}")
    print(f"Undated photos: {len(undated)}")
    print(f"Already labeled: {len(existing)}")
    print(f"To label: {len(to_label)}")

    # Cost estimate
    cost_info = MODEL_COSTS.get(args.model, MODEL_COSTS["gemini-3-pro-preview"])
    total_count = len(to_label) if args.batch_size == 0 else min(args.batch_size, len(to_label))
    estimated_cost = total_count * cost_info["per_photo"]

    print(f"\nModel: {args.model} ({cost_info['note']})")
    print(f"Estimated cost: ${estimated_cost:.2f} for {total_count} photos")
    print(f"Cost per photo: ${cost_info['per_photo']:.4f}")
    print(f"Max cost cap: ${args.max_cost:.2f}")

    if estimated_cost > args.max_cost:
        print(f"\nWARNING: Estimated cost (${estimated_cost:.2f}) exceeds max-cost (${args.max_cost:.2f})")
        print(f"Reducing batch to {int(args.max_cost / cost_info['per_photo'])} photos")
        total_count = int(args.max_cost / cost_info["per_photo"])

    if args.batch_size > 0:
        to_label = to_label[:min(args.batch_size, total_count)]
    else:
        to_label = to_label[:total_count]

    if args.dry_run:
        to_label = to_label[:3]
        print(f"\nDRY RUN — processing {len(to_label)} photos:")

    print()

    # Check for API key
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set")
        print()
        print("To get started:")
        print("  1. Go to https://aistudio.google.com/apikey")
        print("  2. Create a new API key (free, takes 30 seconds)")
        print("  3. export GEMINI_API_KEY=your_key_here")
        print(f"  4. python -m rhodesli_ml.scripts.generate_date_labels --dry-run --model {args.model}")
        sys.exit(1)

    # Process photos
    all_labels = list(existing.values())
    labeled_count = 0
    error_count = 0
    running_cost = 0.0

    for i, (pid, photo) in enumerate(to_label):
        path = photo.get("path", photo.get("filename", ""))
        photo_path = Path(args.photo_dir) / Path(path).name
        collection = photo.get("collection", "unknown")

        print(f"[{i+1}/{len(to_label)}] {pid[:16]} | {collection} | {Path(path).name}")

        if not photo_path.exists():
            print(f"  SKIP: Photo file not found at {photo_path}")
            error_count += 1
            continue

        # Check cost cap
        running_cost += cost_info["per_photo"]
        if running_cost > args.max_cost:
            print(f"\n  HALT: Running cost (${running_cost:.2f}) exceeds max-cost (${args.max_cost:.2f})")
            break

        # Call Gemini
        result = call_gemini(str(photo_path), api_key, model=args.model)
        if result is None:
            error_count += 1
            continue

        label = {
            "photo_id": pid,
            "source": "gemini",
            "model": args.model,
            # Date estimation fields
            "estimated_decade": result.get("estimated_decade"),
            "best_year_estimate": result.get("best_year_estimate"),
            "confidence": result.get("confidence", "medium"),
            "probable_range": result.get("probable_range"),
            "decade_probabilities": result.get("decade_probabilities", {}),
            "location_estimate": result.get("location_estimate", ""),
            "is_color": result.get("is_color", False),
            "evidence": result.get("evidence", {}),
            "cultural_lag_applied": result.get("cultural_lag_applied", False),
            "cultural_lag_note": result.get("cultural_lag_note", ""),
            "capture_vs_print": result.get("capture_vs_print", ""),
            "reasoning_summary": result.get("reasoning_summary", ""),
            # Rich metadata fields (AD-048)
            "scene_description": result.get("scene_description"),
            "visible_text": result.get("visible_text"),
            "keywords": result.get("keywords", []),
            "setting": result.get("setting"),
            "photo_type": result.get("photo_type"),
            "people_count": result.get("people_count"),
            "condition": result.get("condition"),
            "clothing_notes": result.get("clothing_notes"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        all_labels.append(label)
        labeled_count += 1

        # Print concise result
        year = result.get("best_year_estimate", "?")
        decade = result.get("estimated_decade", "?")
        conf = result.get("confidence", "?")
        loc = result.get("location_estimate", "?")
        summary = result.get("reasoning_summary", "")[:80]
        print(f"  -> circa {year} ({decade}s, {conf}) | {loc}")
        print(f"     {summary}")

        # Print rich metadata (AD-048)
        scene = result.get("scene_description")
        if scene:
            print(f"     Scene: {scene[:100]}")
        visible_text = result.get("visible_text")
        if visible_text:
            print(f"     Text: \"{visible_text[:80]}\"")
        keywords = result.get("keywords", [])
        if keywords:
            print(f"     Tags: {', '.join(keywords[:8])}")
        setting = result.get("setting")
        photo_type = result.get("photo_type")
        people = result.get("people_count")
        condition = result.get("condition")
        meta_parts = []
        if setting:
            meta_parts.append(setting)
        if photo_type:
            meta_parts.append(photo_type)
        if people is not None:
            meta_parts.append(f"{people} people")
        if condition:
            meta_parts.append(f"condition: {condition}")
        if meta_parts:
            print(f"     Meta: {' | '.join(meta_parts)}")
        clothing = result.get("clothing_notes")
        if clothing:
            print(f"     Clothing: {clothing[:100]}")

        # Rate limiting: 1 request per second
        if i < len(to_label) - 1:
            time.sleep(1.0)

    # Save results
    if labeled_count > 0:
        save_labels(all_labels, args.output)

    print(f"\nResults: {labeled_count} labeled, {error_count} errors, "
          f"{len(all_labels)} total labels")
    print(f"Estimated cost: ${running_cost:.2f}")

    if args.dry_run:
        remaining = len(get_undated_photos(photos)) - len(existing) - labeled_count
        full_cost = remaining * cost_info["per_photo"]
        print(f"\nFull run would label {remaining} more photos at ~${full_cost:.2f}")

    # Print summary
    print_summary(all_labels)


if __name__ == "__main__":
    main()
