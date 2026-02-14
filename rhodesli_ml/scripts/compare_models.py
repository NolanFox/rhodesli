"""A/B comparison of two Gemini models on the same set of photos.

Runs each photo through both models using the same prompt, then prints
side-by-side comparison of date estimates, metadata quality, and costs.

Usage:
    python -m rhodesli_ml.scripts.compare_models \
        --photos /tmp/ab_test_photos.json \
        --model-a gemini-3-pro-preview \
        --model-b gemini-3-flash-preview
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Import from the existing generate_date_labels module
from rhodesli_ml.scripts.generate_date_labels import PROMPT, MODEL_COSTS, call_gemini
from rhodesli_ml.scripts.cost_tracker import estimate_cost, log_api_call


COST_HARD_LIMIT = 2.00  # Stop if total cost exceeds this


def run_model(photo_path: str, api_key: str, model: str, max_retries: int = 3) -> dict | None:
    """Call a model with retry logic for rate limiting."""
    for attempt in range(max_retries):
        result = call_gemini(photo_path, api_key, model=model)
        if result is not None:
            return result
        if attempt < max_retries - 1:
            wait = 2 ** (attempt + 1)  # Exponential backoff: 2, 4, 8 seconds
            print(f"    Retry {attempt + 1}/{max_retries} in {wait}s...")
            time.sleep(wait)
    return None


def format_value(val, max_len: int = 60) -> str:
    """Format a value for display, truncating long strings."""
    if val is None:
        return "(none)"
    if isinstance(val, list):
        s = ", ".join(str(v) for v in val)
        return s[:max_len] + "..." if len(s) > max_len else s
    s = str(val)
    return s[:max_len] + "..." if len(s) > max_len else s


def compare_one(photo_name: str, result_a: dict | None, result_b: dict | None,
                model_a: str, model_b: str) -> dict:
    """Compare results from two models on one photo. Returns comparison dict."""
    comp = {
        "photo": photo_name,
        "a_ok": result_a is not None,
        "b_ok": result_b is not None,
    }

    if result_a is None or result_b is None:
        return comp

    # Date comparison
    comp["a_decade"] = result_a.get("estimated_decade")
    comp["b_decade"] = result_b.get("estimated_decade")
    comp["a_year"] = result_a.get("best_year_estimate")
    comp["b_year"] = result_b.get("best_year_estimate")
    comp["a_confidence"] = result_a.get("confidence")
    comp["b_confidence"] = result_b.get("confidence")
    comp["decade_agree"] = comp["a_decade"] == comp["b_decade"]
    comp["a_range"] = result_a.get("probable_range")
    comp["b_range"] = result_b.get("probable_range")

    # Visible text comparison
    comp["a_text"] = result_a.get("visible_text")
    comp["b_text"] = result_b.get("visible_text")
    comp["a_has_text"] = comp["a_text"] is not None and comp["a_text"] != ""
    comp["b_has_text"] = comp["b_text"] is not None and comp["b_text"] != ""

    # Controlled tags
    comp["a_tags"] = result_a.get("controlled_tags", [])
    comp["b_tags"] = result_b.get("controlled_tags", [])

    # Subject ages
    comp["a_ages"] = result_a.get("subject_ages", [])
    comp["b_ages"] = result_b.get("subject_ages", [])

    # Scene description
    comp["a_scene"] = result_a.get("scene_description", "")
    comp["b_scene"] = result_b.get("scene_description", "")

    # People count
    comp["a_people"] = result_a.get("people_count")
    comp["b_people"] = result_b.get("people_count")

    return comp


def print_comparison(comp: dict, model_a: str, model_b: str, idx: int):
    """Print side-by-side comparison for one photo."""
    print(f"\n{'='*80}")
    print(f"Photo {idx}: {comp['photo']}")
    print(f"{'='*80}")

    if not comp["a_ok"]:
        print(f"  {model_a}: FAILED")
    if not comp["b_ok"]:
        print(f"  {model_b}: FAILED")
    if not comp["a_ok"] or not comp["b_ok"]:
        return

    # Date estimates
    agree_marker = " [AGREE]" if comp["decade_agree"] else " [DISAGREE]"
    print(f"\n  Date Estimate:{agree_marker}")
    print(f"    {model_a:30s}: {comp['a_decade']}s (circa {comp['a_year']}, {comp['a_confidence']}) range={comp['a_range']}")
    print(f"    {model_b:30s}: {comp['b_decade']}s (circa {comp['b_year']}, {comp['b_confidence']}) range={comp['b_range']}")

    # Scene descriptions
    print(f"\n  Scene Description:")
    print(f"    {model_a:30s}: {format_value(comp['a_scene'], 100)}")
    print(f"    {model_b:30s}: {format_value(comp['b_scene'], 100)}")

    # Controlled tags
    print(f"\n  Controlled Tags:")
    print(f"    {model_a:30s}: {format_value(comp['a_tags'])}")
    print(f"    {model_b:30s}: {format_value(comp['b_tags'])}")

    # Visible text (key differentiator)
    text_marker = ""
    if comp["a_has_text"] != comp["b_has_text"]:
        text_marker = " [ONE FOUND TEXT, OTHER DIDN'T]"
    elif comp["a_has_text"] and comp["b_has_text"]:
        text_marker = " [BOTH FOUND TEXT]"
    print(f"\n  Visible Text:{text_marker}")
    print(f"    {model_a:30s}: {format_value(comp['a_text'], 100)}")
    print(f"    {model_b:30s}: {format_value(comp['b_text'], 100)}")

    # Subject ages
    print(f"\n  Subject Ages:")
    print(f"    {model_a:30s}: {format_value(comp['a_ages'])}")
    print(f"    {model_b:30s}: {format_value(comp['b_ages'])}")

    # People count
    print(f"\n  People Count:")
    print(f"    {model_a:30s}: {comp['a_people']}")
    print(f"    {model_b:30s}: {comp['b_people']}")


def print_summary(comparisons: list[dict], model_a: str, model_b: str,
                  cost_a: float, cost_b: float, count_a: int, count_b: int):
    """Print aggregate summary and recommendation."""
    valid = [c for c in comparisons if c["a_ok"] and c["b_ok"]]

    print(f"\n{'='*80}")
    print(f"SUMMARY: {model_a} vs {model_b}")
    print(f"{'='*80}")
    print(f"\n  Photos compared: {len(valid)} / {len(comparisons)}")

    if not valid:
        print("  No valid comparisons to summarize.")
        return

    # Decade agreement
    decade_agree = sum(1 for c in valid if c["decade_agree"])
    decade_disagree = len(valid) - decade_agree
    print(f"\n  Decade Agreement: {decade_agree}/{len(valid)} agree, {decade_disagree} disagree")
    for c in valid:
        if not c["decade_agree"]:
            print(f"    {c['photo']}: {model_a}={c['a_decade']}s vs {model_b}={c['b_decade']}s")

    # Year estimate closeness
    year_diffs = []
    for c in valid:
        if c["a_year"] and c["b_year"]:
            year_diffs.append(abs(c["a_year"] - c["b_year"]))
    if year_diffs:
        avg_diff = sum(year_diffs) / len(year_diffs)
        print(f"  Average year estimate difference: {avg_diff:.1f} years")

    # Visible text detection
    a_found_text = sum(1 for c in valid if c["a_has_text"])
    b_found_text = sum(1 for c in valid if c["b_has_text"])
    both_found = sum(1 for c in valid if c["a_has_text"] and c["b_has_text"])
    only_a = sum(1 for c in valid if c["a_has_text"] and not c["b_has_text"])
    only_b = sum(1 for c in valid if not c["a_has_text"] and c["b_has_text"])
    print(f"\n  Visible Text Detection:")
    print(f"    {model_a}: found text in {a_found_text}/{len(valid)} photos")
    print(f"    {model_b}: found text in {b_found_text}/{len(valid)} photos")
    print(f"    Both found: {both_found}, Only {model_a}: {only_a}, Only {model_b}: {only_b}")

    # Controlled tags consistency
    a_avg_tags = sum(len(c["a_tags"]) for c in valid) / len(valid)
    b_avg_tags = sum(len(c["b_tags"]) for c in valid) / len(valid)
    tag_overlap_pcts = []
    for c in valid:
        a_set = set(c["a_tags"])
        b_set = set(c["b_tags"])
        if a_set or b_set:
            overlap = len(a_set & b_set) / len(a_set | b_set) * 100
            tag_overlap_pcts.append(overlap)
    avg_overlap = sum(tag_overlap_pcts) / len(tag_overlap_pcts) if tag_overlap_pcts else 0
    print(f"\n  Controlled Tags:")
    print(f"    {model_a}: avg {a_avg_tags:.1f} tags/photo")
    print(f"    {model_b}: avg {b_avg_tags:.1f} tags/photo")
    print(f"    Average tag overlap (Jaccard): {avg_overlap:.1f}%")

    # Cost comparison
    avg_cost_a = cost_a / count_a if count_a else 0
    avg_cost_b = cost_b / count_b if count_b else 0
    print(f"\n  Cost:")
    print(f"    {model_a}: ${cost_a:.4f} total, ${avg_cost_a:.4f}/photo ({count_a} calls)")
    print(f"    {model_b}: ${cost_b:.4f} total, ${avg_cost_b:.4f}/photo ({count_b} calls)")
    print(f"    Total run cost: ${cost_a + cost_b:.4f}")
    ratio = cost_a / cost_b if cost_b > 0 else float("inf")
    print(f"    {model_a} is {ratio:.1f}x the cost of {model_b}")

    # Recommendation
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}")

    # Score each model
    pro_a = []
    pro_b = []

    if a_found_text > b_found_text:
        pro_a.append(f"Better OCR ({a_found_text} vs {b_found_text} photos with text)")
    elif b_found_text > a_found_text:
        pro_b.append(f"Better OCR ({b_found_text} vs {a_found_text} photos with text)")

    if a_avg_tags > b_avg_tags + 0.5:
        pro_a.append(f"More controlled tags ({a_avg_tags:.1f} vs {b_avg_tags:.1f} avg)")
    elif b_avg_tags > a_avg_tags + 0.5:
        pro_b.append(f"More controlled tags ({b_avg_tags:.1f} vs {a_avg_tags:.1f} avg)")

    if avg_cost_a < avg_cost_b:
        pro_a.append(f"Cheaper (${avg_cost_a:.4f} vs ${avg_cost_b:.4f}/photo)")
    else:
        pro_b.append(f"Cheaper (${avg_cost_b:.4f} vs ${avg_cost_a:.4f}/photo)")

    # Confidence comparison
    conf_rank = {"high": 3, "medium": 2, "low": 1}
    a_conf_avg = sum(conf_rank.get(c["a_confidence"], 0) for c in valid) / len(valid)
    b_conf_avg = sum(conf_rank.get(c["b_confidence"], 0) for c in valid) / len(valid)
    if a_conf_avg > b_conf_avg + 0.2:
        pro_a.append(f"Higher confidence ({a_conf_avg:.2f} vs {b_conf_avg:.2f} avg)")
    elif b_conf_avg > a_conf_avg + 0.2:
        pro_b.append(f"Higher confidence ({b_conf_avg:.2f} vs {a_conf_avg:.2f} avg)")

    print(f"\n  {model_a} advantages:")
    for p in pro_a:
        print(f"    + {p}")
    if not pro_a:
        print(f"    (none)")

    print(f"\n  {model_b} advantages:")
    for p in pro_b:
        print(f"    + {p}")
    if not pro_b:
        print(f"    (none)")

    # Final recommendation
    if len(pro_a) >= len(pro_b):
        recommended = model_a
    else:
        recommended = model_b

    per_photo = MODEL_COSTS.get(recommended, {}).get("per_photo", 0.037)
    print(f"\n  >>> Use {recommended} for full batch.")
    print(f"  >>> Command: python -m rhodesli_ml.scripts.generate_date_labels --model {recommended} --batch-size 0")
    print(f"  >>> Estimated full-batch cost: ~${155 * per_photo:.2f} for 155 photos")


def main():
    parser = argparse.ArgumentParser(description="A/B compare two Gemini models")
    parser.add_argument("--photos", required=True, help="JSON file with list of photo filenames")
    parser.add_argument("--model-a", default="gemini-3-pro-preview", help="First model")
    parser.add_argument("--model-b", default="gemini-3-flash-preview", help="Second model")
    parser.add_argument("--photo-dir", default="raw_photos", help="Directory containing photos")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    with open(args.photos) as f:
        photo_names = json.load(f)

    print(f"A/B Comparison: {args.model_a} vs {args.model_b}")
    print(f"Photos: {len(photo_names)}")
    print(f"Cost limit: ${COST_HARD_LIMIT:.2f}")

    cost_a_info = MODEL_COSTS.get(args.model_a, MODEL_COSTS["gemini-3-pro-preview"])
    cost_b_info = MODEL_COSTS.get(args.model_b, MODEL_COSTS["gemini-3-flash-preview"])
    est_total = len(photo_names) * (cost_a_info["per_photo"] + cost_b_info["per_photo"])
    print(f"Estimated total cost: ${est_total:.2f}")
    print()

    comparisons = []
    total_cost = 0.0
    cost_a_total = 0.0
    cost_b_total = 0.0
    count_a = 0
    count_b = 0

    for i, photo_name in enumerate(photo_names):
        photo_path = str(Path(args.photo_dir) / photo_name)
        if not Path(photo_path).exists():
            print(f"\n[{i+1}/{len(photo_names)}] {photo_name} — SKIP (file not found)")
            comparisons.append({"photo": photo_name, "a_ok": False, "b_ok": False})
            continue

        print(f"\n[{i+1}/{len(photo_names)}] {photo_name}")

        # Check cost limit before each photo (both models)
        photo_cost_est = cost_a_info["per_photo"] + cost_b_info["per_photo"]
        if total_cost + photo_cost_est > COST_HARD_LIMIT:
            print(f"  HALT: Would exceed ${COST_HARD_LIMIT:.2f} limit "
                  f"(current: ${total_cost:.4f}, next photo est: ${photo_cost_est:.4f})")
            break

        # Run Model A
        print(f"  Running {args.model_a}...")
        result_a = run_model(photo_path, api_key, args.model_a)
        cost_a = cost_a_info["per_photo"]
        cost_a_total += cost_a
        total_cost += cost_a
        count_a += 1
        if result_a:
            decade_a = result_a.get("estimated_decade", "?")
            year_a = result_a.get("best_year_estimate", "?")
            conf_a = result_a.get("confidence", "?")
            print(f"    -> {decade_a}s (circa {year_a}, {conf_a})")
        else:
            print(f"    -> FAILED")

        # Brief pause between models
        time.sleep(1.0)

        # Run Model B
        print(f"  Running {args.model_b}...")
        result_b = run_model(photo_path, api_key, args.model_b)
        cost_b = cost_b_info["per_photo"]
        cost_b_total += cost_b
        total_cost += cost_b
        count_b += 1
        if result_b:
            decade_b = result_b.get("estimated_decade", "?")
            year_b = result_b.get("best_year_estimate", "?")
            conf_b = result_b.get("confidence", "?")
            print(f"    -> {decade_b}s (circa {year_b}, {conf_b})")
        else:
            print(f"    -> FAILED")

        # Compare
        comp = compare_one(photo_name, result_a, result_b, args.model_a, args.model_b)
        comparisons.append(comp)

        # Running cost
        print(f"  Cost this photo: ${cost_a + cost_b:.4f} | Running total: ${total_cost:.4f}")

        # Pause between photos
        if i < len(photo_names) - 1:
            time.sleep(1.5)

    # Print per-photo comparisons
    for i, comp in enumerate(comparisons):
        if comp.get("a_ok") and comp.get("b_ok"):
            print_comparison(comp, args.model_a, args.model_b, i + 1)

    # Print summary
    print_summary(comparisons, args.model_a, args.model_b,
                  cost_a_total, cost_b_total, count_a, count_b)


if __name__ == "__main__":
    main()
