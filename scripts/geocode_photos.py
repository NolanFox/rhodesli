"""
Geocode photos by matching Gemini location_estimate to curated location dictionary.

Uses fuzzy string matching against known Rhodes diaspora places.
No external API calls — all geocoding is local dictionary lookup.

Usage:
    python scripts/geocode_photos.py --dry-run     # Preview matches
    python scripts/geocode_photos.py --execute      # Write photo_locations.json
"""

import argparse
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_location_dictionary() -> dict:
    """Load curated location dictionary."""
    path = DATA_DIR / "location_dictionary.json"
    with open(path) as f:
        data = json.load(f)
    return data["locations"]


def load_date_labels() -> list:
    """Load Gemini date labels with location_estimate."""
    path = DATA_DIR / "date_labels.json"
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and "labels" in data:
        return data["labels"]
    return data if isinstance(data, list) else []


def match_location(text: str, dictionary: dict) -> list[dict]:
    """Match a location_estimate string against the curated dictionary.

    Returns list of matched locations sorted by specificity (most specific first).
    More specific places (Lower East Side) are preferred over general ones (NYC).
    """
    if not text:
        return []

    text_lower = text.lower()
    matches = []

    # Specificity ranking: more specific aliases get higher priority
    specificity = {
        "lower_east_side": 10,
        "brooklyn": 9,
        "elisabethville": 9,
        "asheville": 8,
        "montgomery": 8,
        "portland": 8,
        "seattle": 8,
        "atlanta": 8,
        "tampa": 7,
        "miami": 7,
        "los_angeles": 7,
        "buenos_aires": 7,
        "havana": 7,
        "jerusalem": 7,
        "istanbul": 7,
        "auschwitz": 7,
        "nyc": 6,
        "rhodes": 6,
        "italy": 5,
        "florida": 4,
        "united_states": 1,
    }

    for key, loc in dictionary.items():
        for alias in loc["aliases"]:
            # Use word boundary matching for short aliases to avoid false positives
            if len(alias) <= 3:
                pattern = r'\b' + re.escape(alias) + r'\b'
                if re.search(pattern, text_lower):
                    matches.append({
                        "key": key,
                        "name": loc["name"],
                        "lat": loc["lat"],
                        "lng": loc["lng"],
                        "region": loc["region"],
                        "specificity": specificity.get(key, 5),
                        "matched_alias": alias,
                    })
                    break
            elif alias in text_lower:
                matches.append({
                    "key": key,
                    "name": loc["name"],
                    "lat": loc["lat"],
                    "lng": loc["lng"],
                    "region": loc["region"],
                    "specificity": specificity.get(key, 5),
                    "matched_alias": alias,
                })
                break

    # Sort by specificity (highest first), deduplicate by key
    seen = set()
    unique = []
    for m in sorted(matches, key=lambda x: -x["specificity"]):
        if m["key"] not in seen:
            seen.add(m["key"])
            unique.append(m)

    # If we have both a specific and general match, drop the general
    # e.g., if "Lower East Side" matched, drop "NYC"
    # e.g., if "Miami" matched, drop "Florida" and "United States"
    if len(unique) > 1:
        has_specific_us = any(m["specificity"] >= 7 and m["region"] == "United States" for m in unique)
        if has_specific_us:
            unique = [m for m in unique if m["key"] not in ("united_states", "florida") or m["specificity"] >= 7]

    return unique


def geocode_all(labels: list, dictionary: dict) -> dict:
    """Geocode all photos from their Gemini location estimates.

    Returns dict mapping photo_id -> location info.
    """
    results = {}
    for label in labels:
        photo_id = label.get("photo_id", "")
        location_estimate = label.get("location_estimate", "")
        if not photo_id or not location_estimate:
            continue

        matches = match_location(location_estimate, dictionary)
        if matches:
            primary = matches[0]
            result = {
                "photo_id": photo_id,
                "lat": primary["lat"],
                "lng": primary["lng"],
                "location_name": primary["name"],
                "location_key": primary["key"],
                "region": primary["region"],
                "location_estimate": location_estimate,
                "confidence": "high" if primary["specificity"] >= 7 else "medium" if primary["specificity"] >= 4 else "low",
                "all_matches": [{"key": m["key"], "name": m["name"]} for m in matches],
            }
            results[photo_id] = result

    return results


def main():
    parser = argparse.ArgumentParser(description="Geocode photos from Gemini location estimates")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Preview without writing (default)")
    parser.add_argument("--execute", action="store_true", help="Write photo_locations.json")
    args = parser.parse_args()

    if args.execute:
        args.dry_run = False

    dictionary = load_location_dictionary()
    labels = load_date_labels()

    print(f"Loaded {len(dictionary)} locations, {len(labels)} photos")

    results = geocode_all(labels, dictionary)

    # Statistics
    matched = len(results)
    unmatched = len(labels) - matched
    print(f"\nMatched: {matched}/{len(labels)} ({100*matched/len(labels):.1f}%)")
    print(f"Unmatched: {unmatched}")

    # Region breakdown
    regions = {}
    for r in results.values():
        region = r["region"]
        regions[region] = regions.get(region, 0) + 1
    print("\nBy region:")
    for region, count in sorted(regions.items(), key=lambda x: -x[1]):
        print(f"  {count:3d}  {region}")

    # Location breakdown
    locs = {}
    for r in results.values():
        name = r["location_name"]
        locs[name] = locs.get(name, 0) + 1
    print("\nBy location:")
    for name, count in sorted(locs.items(), key=lambda x: -x[1]):
        print(f"  {count:3d}  {name}")

    # Confidence breakdown
    confs = {}
    for r in results.values():
        c = r["confidence"]
        confs[c] = confs.get(c, 0) + 1
    print("\nBy confidence:")
    for c in ["high", "medium", "low"]:
        print(f"  {confs.get(c, 0):3d}  {c}")

    # Show unmatched
    if unmatched > 0:
        print(f"\nUnmatched locations ({unmatched}):")
        for label in labels:
            pid = label.get("photo_id", "")
            loc = label.get("location_estimate", "")
            if pid and loc and pid not in results:
                print(f"  {pid[:16]}  {loc[:80]}")

    if not args.dry_run:
        output = {
            "version": 1,
            "description": "Geocoded photo locations from Gemini location estimates + curated dictionary",
            "photos": results,
        }
        output_path = DATA_DIR / "photo_locations.json"
        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nWritten to {output_path}")
    else:
        print("\n[DRY RUN] Use --execute to write photo_locations.json")


if __name__ == "__main__":
    main()
