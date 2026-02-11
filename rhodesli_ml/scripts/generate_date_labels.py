"""Generate silver date labels for photos using Gemini Vision API.

Sends each undated photo to Gemini and asks for an approximate decade estimate.
Outputs data/date_labels.json with structured estimates.

Usage:
    # Preview what would be labeled (no API calls)
    python -m rhodesli_ml.scripts.generate_date_labels --dry-run

    # Label first 10 photos
    python -m rhodesli_ml.scripts.generate_date_labels --batch-size 10

    # Label all undated photos
    python -m rhodesli_ml.scripts.generate_date_labels --batch-size 0
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path


PROMPT = """You are analyzing a scanned family photograph from a Sephardic Jewish family
originally from Rhodes, Greece. Many photos are from the 1920s-1970s, taken in Rhodes,
New York City, Miami, or Tampa.

Estimate the approximate decade this photograph was originally taken (not when it was scanned).
Look at: clothing styles, hairstyles, photo quality/format, print characteristics,
background details, and any visible text.

Respond in JSON format only:
{
    "decade": 1940,
    "confidence": "high",
    "reasoning": "Brief explanation of visual cues used"
}

Valid decades: 1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020.
Confidence levels: "high" (strong visual cues), "medium" (some cues), "low" (uncertain).
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
            # Check if it's a scan-era date (2000+) — not a real date
            try:
                year = int(str(date_taken)[:4])
                if year < 2000:
                    continue  # Has a real pre-2000 date, skip
            except (ValueError, IndexError):
                pass
        undated.append((pid, photo))
    return undated


def load_existing_labels(path: str = "data/date_labels.json") -> dict:
    """Load existing labels to avoid re-labeling."""
    labels_path = Path(path)
    if not labels_path.exists():
        return {}
    with open(labels_path) as f:
        data = json.load(f)
    return {entry["photo_id"]: entry for entry in data.get("labels", [])}


def encode_photo_base64(photo_path: str) -> str | None:
    """Read a photo file and return base64-encoded string."""
    p = Path(photo_path)
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_gemini(image_b64: str, api_key: str, model: str = "gemini-2.0-flash") -> dict | None:
    """Call Gemini Vision API with a photo and return parsed response.

    Returns dict with {decade, confidence, reasoning} or None on failure.
    """
    import urllib.request
    import urllib.error

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT},
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_b64,
                    }
                },
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1,
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        # Extract text from Gemini response
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)

        # Validate
        decade = parsed.get("decade")
        if not isinstance(decade, int) or decade < 1900 or decade > 2030:
            print(f"  WARNING: Invalid decade {decade}, skipping")
            return None

        return {
            "decade": decade,
            "confidence": parsed.get("confidence", "medium"),
            "reasoning": parsed.get("reasoning", ""),
        }
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"  ERROR: Gemini API call failed: {e}")
        return None


def save_labels(labels: list[dict], path: str = "data/date_labels.json"):
    """Save labels to JSON file with atomic write."""
    output = {
        "schema_version": 1,
        "labels": labels,
    }
    tmp_path = Path(path).with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(output, f, indent=2)
    tmp_path.rename(path)
    print(f"Saved {len(labels)} labels to {path}")


def main():
    parser = argparse.ArgumentParser(description="Generate date labels via Gemini Vision API")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, no API calls")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Number of photos to label (0 = all)")
    parser.add_argument("--photo-dir", default="raw_photos",
                        help="Directory containing photos")
    parser.add_argument("--output", default="data/date_labels.json",
                        help="Output labels file")
    parser.add_argument("--model", default="gemini-2.0-flash",
                        help="Gemini model to use")
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

    if args.batch_size > 0:
        to_label = to_label[:args.batch_size]

    print(f"Batch size: {len(to_label)}")
    print()

    if args.dry_run:
        print("DRY RUN — would label these photos:")
        for pid, photo in to_label:
            path = photo.get("path", photo.get("filename", "unknown"))
            collection = photo.get("collection", "unknown")
            print(f"  {pid[:12]}... | {collection} | {path}")
        return

    # Check for API key
    import os
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set")
        print("Get a key at: https://aistudio.google.com/apikey")
        sys.exit(1)

    # Process photos
    all_labels = list(existing.values())
    labeled_count = 0
    error_count = 0

    for i, (pid, photo) in enumerate(to_label):
        path = photo.get("path", photo.get("filename", ""))
        photo_path = Path(args.photo_dir) / Path(path).name
        collection = photo.get("collection", "unknown")

        print(f"[{i+1}/{len(to_label)}] {pid[:12]}... | {collection} | {path}")

        # Encode photo
        image_b64 = encode_photo_base64(str(photo_path))
        if image_b64 is None:
            print(f"  SKIP: Photo file not found at {photo_path}")
            error_count += 1
            continue

        # Call Gemini
        result = call_gemini(image_b64, api_key, model=args.model)
        if result is None:
            error_count += 1
            continue

        label = {
            "photo_id": pid,
            "decade": result["decade"],
            "confidence": result["confidence"],
            "source": "gemini",
            "reasoning": result["reasoning"],
        }
        all_labels.append(label)
        labeled_count += 1

        print(f"  -> {result['decade']}s ({result['confidence']}): {result['reasoning'][:80]}")

        # Rate limiting: 1 request per second
        if i < len(to_label) - 1:
            time.sleep(1.0)

    # Save results
    if labeled_count > 0:
        save_labels(all_labels, args.output)

    print()
    print(f"Summary: {labeled_count} labeled, {error_count} errors, "
          f"{len(all_labels)} total labels")


if __name__ == "__main__":
    main()
