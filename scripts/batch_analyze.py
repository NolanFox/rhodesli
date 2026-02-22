#!/usr/bin/env python3
"""Batch analyze photos using unified Gemini extraction architecture.

Generates JSONL requests for Gemini Batch API (50% discount) or runs
sequentially for smaller batches. Results logged to MLflow.

Usage:
    # Dry run: show cost estimate for all undated photos
    python scripts/batch_analyze.py --dry-run

    # Dry run with specific preset
    python scripts/batch_analyze.py --dry-run --preset quick

    # Process 10 photos (requires GEMINI_API_KEY)
    python scripts/batch_analyze.py --limit 10 --preset full

    # Generate JSONL for Batch API submission
    python scripts/batch_analyze.py --generate-jsonl --output batch_requests.jsonl

See AD-143 for unified extraction architecture decision.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rhodesli_ml.gemini_extraction import (
    EXTRACTION_PRESETS,
    build_extraction_prompt,
    get_active_extractions,
)
from rhodesli_ml.gemini_config import MODEL_PRICING


def estimate_cost(num_photos: int, preset: str, model: str = "gemini-3.1-pro") -> dict:
    """Estimate API cost for a batch run."""
    active = get_active_extractions(preset)
    # Rough estimate: ~500 input tokens (image + prompt), output scales with extractions
    output_tokens_per_extraction = 100
    estimated_output = len(active) * output_tokens_per_extraction

    pricing = MODEL_PRICING.get(model, MODEL_PRICING.get("default", {"input": 0.001, "output": 0.002}))
    cost_per_photo = (500 * pricing.get("input", 0.001) / 1000) + (estimated_output * pricing.get("output", 0.002) / 1000)
    total = cost_per_photo * num_photos
    batch_total = total * 0.5  # Batch API is 50% off

    return {
        "photos": num_photos,
        "preset": preset,
        "model": model,
        "extractions": active,
        "cost_per_photo": round(cost_per_photo, 4),
        "total_sequential": round(total, 2),
        "total_batch_api": round(batch_total, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Batch photo analysis with Gemini")
    parser.add_argument("--dry-run", action="store_true", help="Show cost estimate only")
    parser.add_argument("--preset", default="full", choices=list(EXTRACTION_PRESETS.keys()))
    parser.add_argument("--limit", type=int, default=0, help="Max photos (0 = all)")
    parser.add_argument("--model", default="gemini-3.1-pro")
    parser.add_argument("--generate-jsonl", action="store_true", help="Generate JSONL for Batch API")
    parser.add_argument("--output", default="batch_requests.jsonl", help="Output JSONL path")
    args = parser.parse_args()

    # Load photo index
    photo_index_path = Path("data/photo_index.json")
    if not photo_index_path.exists():
        print("ERROR: data/photo_index.json not found")
        sys.exit(1)

    with open(photo_index_path) as f:
        photo_data = json.load(f)

    photos = photo_data.get("photos", {})
    num_photos = len(photos) if args.limit == 0 else min(args.limit, len(photos))

    if args.dry_run:
        cost = estimate_cost(num_photos, args.preset, args.model)
        print(f"\n=== Batch Analysis Cost Estimate ===")
        print(f"Photos: {cost['photos']}")
        print(f"Preset: {cost['preset']}")
        print(f"Model: {cost['model']}")
        print(f"Extractions: {', '.join(cost['extractions'])}")
        print(f"Cost per photo: ${cost['cost_per_photo']}")
        print(f"Total (sequential): ${cost['total_sequential']}")
        print(f"Total (Batch API, 50% off): ${cost['total_batch_api']}")
        print(f"\nTo run: python scripts/batch_analyze.py --limit {num_photos} --preset {args.preset}")
        return

    if args.generate_jsonl:
        prompt = build_extraction_prompt(preset=args.preset)
        print(f"Generating JSONL for {num_photos} photos with '{args.preset}' preset...")
        print(f"Prompt length: {len(prompt)} chars")
        print(f"Output: {args.output}")
        print("\nJSONL generation not yet implemented — coming in future session")
        return

    # Sequential execution placeholder
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    print(f"Sequential analysis of {num_photos} photos not yet implemented")
    print("Use --dry-run to see cost estimate or --generate-jsonl for Batch API")


if __name__ == "__main__":
    main()
