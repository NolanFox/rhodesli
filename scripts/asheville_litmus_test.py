#!/usr/bin/env python3
"""Asheville Litmus Test — 3-Variant Gemini GEDCOM Enrichment Experiment.

Tests whether GEDCOM genealogical context improves Gemini's location
identification for a photo known to be taken in Asheville, NC.

Session: 82c | Phase 1
Ground truth: Photo taken in Asheville, North Carolina

Variants:
  A: No GEDCOM context (visual-only baseline)
  B: Full GEDCOM context (all biographical data for identified people)
  C: Curated GEDCOM context (filtered to ±15yr of estimated photo date)
"""

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

# --- Constants ---
ASHEVILLE_PHOTO_ID = "inbox_staged-20260210-182610_7_596771420.719238"
ASHEVILLE_PHOTO_PATH = PROJECT_ROOT / "raw_photos" / "596771420.719238.jpg"
MODEL = "gemini-3.1-pro-preview"
BUDGET_CAP = 3.00  # USD hard cap for Phase 1

# Pricing per 1M tokens
PRICING = {"input": 2.00, "output": 12.00}


def estimate_cost(input_tokens, output_tokens):
    return (input_tokens / 1_000_000 * PRICING["input"] +
            output_tokens / 1_000_000 * PRICING["output"])


def call_gemini(prompt, image_path, model=MODEL):
    """Call Gemini API with image + text. Returns structured response."""
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


# --- GEDCOM Context Builders ---

def build_victoria_context():
    """Build GEDCOM context for Victoria Capuano Capeluto from identity metadata."""
    return """Person: Victoria Capuano Capeluto
  Born: 25 September 1905 in Rhodes, Regional unit of Rhodes, South Aegean, Greece
  Died: 20 June 1989 in Clearwater, Pinellas County, Florida, United States
  Immigration: Arrived in United States (from Rhodes, Greece)
  Residential History:
    Rhodes, Greece (birth - emigration)
    Brooklyn, New York (after immigration)
    Clearwater, Florida (later life)"""


def build_leon_context():
    """Build GEDCOM context for Big Leon Capeluto from identity metadata."""
    return """Person: Big Leon Capeluto (spouse of Victoria)
  Born: 24 June 1904 in Milas, Muğla, Türkiye
  Died: 1 December 1983 in Pinellas, Florida, United States
  Residential History:
    Milas/Rhodes area (birth - emigration)
    33 Elizabeth Street, Asheville, Buncombe, North Carolina (residence)
    Brooklyn, New York (residence)
    Clearwater/Pinellas, Florida (later life)
  Occupation: Merchant"""


def build_betty_context():
    """Build GEDCOM context for Betty Capeluto Fox from identity metadata."""
    return """Person: Betty Capeluto Fox (daughter of Victoria and Leon)
  Born: in United States
  GEDCOM xref: @I132123771036@
  Family connection: Daughter of Victoria Capuano Capeluto and Big Leon Capeluto"""


def build_full_gedcom_context():
    """Variant B: Full GEDCOM context — all biographical data."""
    sections = [
        "GENEALOGICAL CONTEXT FOR IDENTIFIED INDIVIDUALS:",
        "",
        build_victoria_context(),
        "",
        build_leon_context(),
        "",
        build_betty_context(),
        "",
        "Family structure: Victoria and Leon had children including Betty.",
        "The Capeluto/Capuano family originated from Rhodes, Greece (Sephardic Jewish community).",
        "Migration pattern: Rhodes → various US cities including Brooklyn NY, Asheville NC, Florida.",
        "Leon had a known residence at 33 Elizabeth Street, Asheville, North Carolina.",
    ]
    return "\n".join(sections)


def build_curated_gedcom_context(photo_date_estimate=1945):
    """Variant C: Curated GEDCOM context — filtered to ±15yr of estimated photo date."""
    window_start = photo_date_estimate - 15
    window_end = photo_date_estimate + 15

    sections = [
        "GENEALOGICAL CONTEXT FOR IDENTIFIED INDIVIDUALS:",
        f"(Filtered to events within {window_start}-{window_end})",
        "",
        f"""Person: Victoria Capuano Capeluto
  Born: 25 September 1905 in Rhodes, Greece
  Age in photo (if ~{photo_date_estimate}): approximately {photo_date_estimate - 1905} years old
  Known residences in this period:
    Brooklyn, New York
    Asheville, North Carolina (family connection via spouse)""",
        "",
        f"""Person: Big Leon Capeluto (spouse of Victoria)
  Born: 24 June 1904 in Milas/Rhodes area
  Age in photo (if ~{photo_date_estimate}): approximately {photo_date_estimate - 1904} years old
  Known residences in this period:
    33 Elizabeth Street, Asheville, Buncombe, North Carolina
    Brooklyn, New York""",
        "",
        f"""Person: Betty Capeluto Fox (daughter)
  Family: Daughter of Victoria and Leon Capeluto""",
        "",
        f"Key location data: Leon Capeluto had a documented residence at 33 Elizabeth Street, Asheville, NC.",
        f"The family migrated from Rhodes, Greece to the United States. Multiple residences documented.",
    ]
    return "\n".join(sections)


# --- Prompts ---

PROMPT_A = """Analyze this historical photograph. Describe the scene, estimate the
date and location, identify any text or landmarks, and describe the
people visible. Be as specific as possible about the likely geographic
location based on visual evidence.

Focus especially on:
1. Architecture and environmental clues for location
2. Clothing and fashion for date estimation
3. Number and arrangement of people
4. Any visible text, signs, or landmarks

Respond in JSON with this schema:
{
  "location": {
    "place": "City, State or Country",
    "confidence": "high|medium|low",
    "visual_evidence": "description of visual clues used",
    "reasoning": "step by step reasoning for location"
  },
  "date_estimation": {
    "estimated_year": YYYY,
    "confidence": "high|medium|low",
    "probable_range": [YYYY, YYYY],
    "reasoning": "step by step reasoning for date"
  },
  "people": {
    "count": N,
    "descriptions": ["person 1 description", "person 2 description"]
  },
  "visible_text": "any text visible in photo",
  "scene_description": "overall scene description"
}"""


def build_prompt_b(gedcom_context):
    return f"""Analyze this historical photograph. You have access to genealogical
records for the people identified in this photo:

{gedcom_context}

Using both the visual evidence in the photo AND the genealogical records
above, estimate the date and location of this photo. Consider:
- Where did these people live at various points in their lives?
- Do any visual clues (architecture, vegetation, clothing, signs)
  match a specific location from their records?
- What life events (weddings, gatherings, holidays) might this photo
  document?
- How many people are visible vs how many children are known?
  (Missing children can narrow the date.)

Be specific about your location reasoning. If you can narrow it to a
city or neighborhood, do so with your confidence level.

Respond in JSON with this schema:
{{
  "location": {{
    "place": "City, State or Country",
    "confidence": "high|medium|low",
    "visual_evidence": "description of visual clues used",
    "biographical_evidence": "which genealogical data points helped",
    "reasoning": "step by step reasoning combining visual + biographical"
  }},
  "date_estimation": {{
    "estimated_year": YYYY,
    "confidence": "high|medium|low",
    "probable_range": [YYYY, YYYY],
    "reasoning": "step by step reasoning for date"
  }},
  "people": {{
    "count": N,
    "descriptions": ["person 1 description", "person 2 description"]
  }},
  "visible_text": "any text visible in photo",
  "scene_description": "overall scene description",
  "gedcom_value_assessment": "how much did the genealogical data help vs visual-only?"
}}"""


def main():
    print("=" * 60)
    print("ASHEVILLE LITMUS TEST — 3-Variant GEDCOM Enrichment")
    print(f"Photo: {ASHEVILLE_PHOTO_ID}")
    print(f"Model: {MODEL}")
    print(f"Budget cap: ${BUDGET_CAP:.2f}")
    print("Ground truth: Asheville, North Carolina")
    print("=" * 60)

    if not ASHEVILLE_PHOTO_PATH.exists():
        print(f"ERROR: Photo not found at {ASHEVILLE_PHOTO_PATH}")
        sys.exit(1)

    total_cost = 0
    results = {}

    # --- Variant A: No GEDCOM ---
    print("\n--- Variant A: No GEDCOM Context ---")
    try:
        resp_a = call_gemini(PROMPT_A, str(ASHEVILLE_PHOTO_PATH))
        results["A_no_gedcom"] = resp_a
        total_cost += resp_a["cost"]
        loc_a = resp_a["result"].get("location", {})
        print(f"  Location: {loc_a.get('place', 'N/A')}")
        print(f"  Confidence: {loc_a.get('confidence', 'N/A')}")
        print(f"  Cost: ${resp_a['cost']:.4f}")
        print(f"  Tokens: {resp_a['input_tokens']}+{resp_a['output_tokens']}")
        print(f"  Latency: {resp_a['latency_seconds']}s")
    except Exception as e:
        print(f"  ERROR: {e}")
        results["A_no_gedcom"] = {"error": str(e)}

    if total_cost >= BUDGET_CAP:
        print(f"\n*** BUDGET CAP REACHED: ${total_cost:.4f} ***")
        _save_and_exit(results, total_cost)
        return

    time.sleep(2)

    # --- Variant B: Full GEDCOM ---
    print("\n--- Variant B: Full GEDCOM Context ---")
    full_context = build_full_gedcom_context()
    print(f"  Context tokens: ~{len(full_context) // 4}")
    try:
        resp_b = call_gemini(build_prompt_b(full_context), str(ASHEVILLE_PHOTO_PATH))
        results["B_full_gedcom"] = resp_b
        total_cost += resp_b["cost"]
        loc_b = resp_b["result"].get("location", {})
        print(f"  Location: {loc_b.get('place', 'N/A')}")
        print(f"  Confidence: {loc_b.get('confidence', 'N/A')}")
        print(f"  Biographical evidence: {loc_b.get('biographical_evidence', 'N/A')[:200]}")
        print(f"  Cost: ${resp_b['cost']:.4f}")
        print(f"  Tokens: {resp_b['input_tokens']}+{resp_b['output_tokens']}")
        print(f"  Latency: {resp_b['latency_seconds']}s")
    except Exception as e:
        print(f"  ERROR: {e}")
        results["B_full_gedcom"] = {"error": str(e)}

    if total_cost >= BUDGET_CAP:
        print(f"\n*** BUDGET CAP REACHED: ${total_cost:.4f} ***")
        _save_and_exit(results, total_cost)
        return

    time.sleep(2)

    # --- Variant C: Curated GEDCOM ---
    print("\n--- Variant C: Curated GEDCOM Context ---")
    curated_context = build_curated_gedcom_context(photo_date_estimate=1945)
    print(f"  Context tokens: ~{len(curated_context) // 4}")
    try:
        resp_c = call_gemini(build_prompt_b(curated_context), str(ASHEVILLE_PHOTO_PATH))
        results["C_curated_gedcom"] = resp_c
        total_cost += resp_c["cost"]
        loc_c = resp_c["result"].get("location", {})
        print(f"  Location: {loc_c.get('place', 'N/A')}")
        print(f"  Confidence: {loc_c.get('confidence', 'N/A')}")
        print(f"  Biographical evidence: {loc_c.get('biographical_evidence', 'N/A')[:200]}")
        print(f"  Cost: ${resp_c['cost']:.4f}")
        print(f"  Tokens: {resp_c['input_tokens']}+{resp_c['output_tokens']}")
        print(f"  Latency: {resp_c['latency_seconds']}s")
    except Exception as e:
        print(f"  ERROR: {e}")
        results["C_curated_gedcom"] = {"error": str(e)}

    time.sleep(2)

    # --- Meta-comparison ---
    print("\n--- Meta-Comparison ---")
    if total_cost < BUDGET_CAP:
        try:
            meta_result = _run_meta_comparison(results)
            results["meta_comparison"] = meta_result
            total_cost += meta_result.get("cost", 0)
        except Exception as e:
            print(f"  Meta-comparison error: {e}")
            results["meta_comparison"] = {"error": str(e)}

    _save_and_exit(results, total_cost)


def _run_meta_comparison(results):
    """Ask Gemini to compare its own three analyses."""
    result_a = json.dumps(results.get("A_no_gedcom", {}).get("result", {}), indent=2)
    result_b = json.dumps(results.get("B_full_gedcom", {}).get("result", {}), indent=2)
    result_c = json.dumps(results.get("C_curated_gedcom", {}).get("result", {}), indent=2)

    meta_prompt = f"""You previously analyzed the same photograph three times with different
levels of genealogical context. Here are your three analyses:

Variant A (no genealogy data):
{result_a}

Variant B (full genealogy data):
{result_b}

Variant C (curated genealogy data — filtered to relevant timeframe):
{result_c}

The GROUND TRUTH is that this photo was taken in Asheville, North Carolina.

Compare your three analyses:
1. Which variant got closest to the correct location (Asheville, NC)?
2. What specific genealogical data points helped (or would have helped)?
3. What visual clues in the photo support Asheville?
4. Rate each variant's location accuracy on a 1-10 scale.
5. Recommend which variant approach should be used for batch processing.

Respond in JSON:
{{
  "accuracy_ratings": {{
    "A_no_gedcom": {{"score": N, "location_given": "...", "distance_from_truth": "..."}},
    "B_full_gedcom": {{"score": N, "location_given": "...", "distance_from_truth": "..."}},
    "C_curated_gedcom": {{"score": N, "location_given": "...", "distance_from_truth": "..."}}
  }},
  "winning_variant": "A|B|C",
  "key_gedcom_data_points": ["list of specific data that helped"],
  "visual_clues_for_asheville": ["list of visual evidence"],
  "recommendation_for_batch": "which variant and why",
  "gedcom_value_verdict": "Did GEDCOM clearly help? yes/no/mixed"
}}"""

    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)

    t0 = time.time()
    response = client.models.generate_content(
        model=MODEL,
        contents=[types.Part.from_text(text=meta_prompt)],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    latency = time.time() - t0

    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0
    cost = estimate_cost(input_tokens, output_tokens)

    text = response.text or ""
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = {"raw_text": text}

    print(f"  Cost: ${cost:.4f}")
    print(f"  Tokens: {input_tokens}+{output_tokens}")

    if isinstance(result, dict):
        winner = result.get("winning_variant", "?")
        verdict = result.get("gedcom_value_verdict", "?")
        print(f"  Winning variant: {winner}")
        print(f"  GEDCOM value verdict: {verdict}")
        ratings = result.get("accuracy_ratings", {})
        for var, rating in ratings.items():
            print(f"    {var}: score={rating.get('score')}/10, location='{rating.get('location_given', '?')}'")

    return {"result": result, "cost": cost, "input_tokens": input_tokens,
            "output_tokens": output_tokens, "latency_seconds": round(latency, 2)}


def _save_and_exit(results, total_cost):
    """Save results and print summary."""
    output_path = PROJECT_ROOT / "results" / "asheville_litmus_test.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "experiment": "asheville_litmus_test",
        "photo_id": ASHEVILLE_PHOTO_ID,
        "model": MODEL,
        "ground_truth_location": "Asheville, North Carolina",
        "total_cost": round(total_cost, 4),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "variants": results,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "=" * 60)
    print("ASHEVILLE TEST COST SUMMARY")
    print("=" * 60)
    for variant, resp in results.items():
        if variant == "meta_comparison":
            print(f"  Meta-comparison: ${resp.get('cost', 0):.4f}")
        elif "error" in resp:
            print(f"  {variant}: ERROR")
        else:
            print(f"  {variant}: ${resp.get('cost', 0):.4f}")
    print(f"  TOTAL: ${total_cost:.4f}")
    print(f"  Budget remaining: ${BUDGET_CAP - total_cost:.4f}")
    if total_cost > BUDGET_CAP:
        print("  *** OVER BUDGET — STOP AND REPORT ***")
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
