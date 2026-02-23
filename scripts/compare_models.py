#!/usr/bin/env python3
"""Run Gemini model comparison with optional GEDCOM enrichment.

Drives the 2×5 comparison matrix: Flash/Pro × 5 GEDCOM variants.
Each run processes a set of photos with a specific model and context variant.

Usage:
    python scripts/compare_models.py \
        --photos results/comparison_photo_set.json \
        --model gemini-3-flash \
        --preset full \
        --gedcom-variant none \
        --output results/run_A1_flash_none.json

Session: 61C
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# Gemini pricing per 1M tokens (as of Feb 2026)
MODEL_PRICING = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.02, "output": 0.10},
    "gemini-2.5-flash-preview-05-20": {"input": 0.15, "output": 0.60},
    "gemini-3-flash": {"input": 0.10, "output": 0.40},
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-2.5-pro-preview-05-06": {"input": 1.25, "output": 10.00},
}


def estimate_cost(input_tokens, output_tokens, model):
    """Estimate cost for a Gemini API call."""
    pricing = MODEL_PRICING.get(model, {"input": 1.0, "output": 5.0})
    return (input_tokens / 1_000_000 * pricing["input"] +
            output_tokens / 1_000_000 * pricing["output"])


def call_gemini(model, prompt, image_path, api_key):
    """Call Gemini API with image + text prompt. Returns response dict."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # Read image
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # Determine mime type
    ext = Path(image_path).suffix.lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(
        ext.lstrip("."), "image/jpeg"
    )

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

    # Extract token usage
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0
    cost = estimate_cost(input_tokens, output_tokens, model)

    # Parse JSON response
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


def run_comparison(photos_config, model, preset, gedcom_variant,
                   gedcom_contexts, api_key, photo_dir):
    """Run comparison for all photos with given model and variant."""
    from rhodesli_ml.gemini_extraction import build_extraction_prompt

    results = []
    total_cost = 0

    for i, photo in enumerate(photos_config["photos"]):
        photo_id = photo["photo_id"]
        filename = photo["filename"]
        image_path = photo_dir / filename

        if not image_path.exists():
            logger.warning(f"Photo not found: {image_path}")
            results.append({"photo_id": photo_id, "error": "file_not_found"})
            continue

        # Get GEDCOM context for this photo
        gedcom_context = ""
        if gedcom_contexts and gedcom_variant != "none":
            photo_contexts = gedcom_contexts.get(photo_id, {})
            gedcom_context = photo_contexts.get(gedcom_variant, "")

        # Build prompt
        prompt = build_extraction_prompt(
            preset=preset,
            gedcom_context=gedcom_context if gedcom_context else None,
        )

        # Call Gemini
        logger.info(
            f"  [{i+1}/{len(photos_config['photos'])}] {filename} "
            f"(model={model}, variant={gedcom_variant})"
        )
        try:
            response = call_gemini(model, prompt, str(image_path), api_key)
        except Exception as e:
            logger.error(f"  API error for {filename}: {e}")
            results.append({"photo_id": photo_id, "error": str(e)})
            continue

        response["photo_id"] = photo_id
        response["gedcom_variant"] = gedcom_variant
        response["gedcom_context_tokens"] = len(gedcom_context) // 4
        results.append(response)

        total_cost += response.get("cost", 0)
        logger.info(
            f"    tokens: {response['input_tokens']}+{response['output_tokens']} "
            f"cost: ${response['cost']:.4f} latency: {response['latency_seconds']}s"
        )

        # Brief pause to avoid rate limits
        time.sleep(0.5)

    return {
        "model": model,
        "preset": preset,
        "gedcom_variant": gedcom_variant,
        "photo_count": len(photos_config["photos"]),
        "total_cost": round(total_cost, 4),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Run Gemini model comparison")
    parser.add_argument('--photos', required=True, help='Path to photo set JSON')
    parser.add_argument('--model', required=True, help='Gemini model name')
    parser.add_argument('--preset', default='full', help='Extraction preset')
    parser.add_argument('--gedcom-variant', default='none', help='GEDCOM context variant')
    parser.add_argument('--gedcom-contexts', help='Path to pre-built GEDCOM contexts JSON')
    parser.add_argument('--output', required=True, help='Output path for results JSON')
    parser.add_argument('--photo-dir', default='raw_photos', help='Directory containing photos')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s'
    )

    # Load API key
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        sys.exit(1)

    # Load photo set
    with open(args.photos) as f:
        photos_config = json.load(f)
    logger.info(f"Loaded {len(photos_config['photos'])} photos")

    # Load GEDCOM contexts if provided
    gedcom_contexts = None
    if args.gedcom_contexts:
        with open(args.gedcom_contexts) as f:
            gedcom_contexts = json.load(f)
        logger.info(f"Loaded GEDCOM contexts for {len(gedcom_contexts)} photos")

    photo_dir = Path(args.photo_dir)

    # Run comparison
    logger.info(f"Running: model={args.model}, variant={args.gedcom_variant}")
    result = run_comparison(
        photos_config, args.model, args.preset, args.gedcom_variant,
        gedcom_contexts, api_key, photo_dir,
    )

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    logger.info(f"\nSaved to {output_path}")
    logger.info(f"Total cost: ${result['total_cost']:.4f}")


if __name__ == '__main__':
    main()
