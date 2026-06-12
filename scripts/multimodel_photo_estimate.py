#!/usr/bin/env python3
"""Multi-model photo date/location estimate — manual admin workflow.

Runs the SAME fully-enriched prompt (date + location + GEDCOM context) against
multiple models so a human + Claude can compare and choose the best estimate
for a single photo. Only the CHOSEN estimate is written to the website DB
(date_labels); ALL candidate outputs + the decision live as a repo artifact
under docs/experiments/photo-estimates/<photo_id>/.

This script handles the GEMINI run (the one provider with first-class infra in
rhodesli) and emits the shared prompt + image so the Fable and Codex runs can
use an IDENTICAL prompt for a fair comparison.

Provenance / manual-vs-platform differentiation:
  - gemini_api_calls.experiment_id = "manual-multimodel-<photo>-<date>"
  - gemini_api_calls.gemini_config.operator = "claude-code-manual"
  (Platform calls leave experiment_id NULL and operator = "platform".)

Phases:
  run-gemini   : build enriched prompt, run Gemini, save candidate + prompt
  finalize     : given a chosen model, write chosen estimate -> date_labels +
                 photo_locations (Supabase), tagged with decision provenance.

Usage:
  python scripts/multimodel_photo_estimate.py run-gemini <photo_id> <experiment_date>
  python scripts/multimodel_photo_estimate.py finalize  <photo_id> <chosen_model> <artifact_dir>
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv("/Users/nolanfox/rhodesli/.env")

SITE = "https://rhodesli.nolanandrewfox.com"
ARTIFACT_ROOT = Path("docs/experiments/photo-estimates")


def _fetch_image(filename: str) -> tuple[bytes, str]:
    import ssl

    suffix = Path(filename).suffix.lower() or ".jpg"
    cache = Path(f"/tmp/{Path(filename).name}")
    url = f"{SITE}/photos/{urllib.parse.quote(filename)}"
    try:
        import certifi

        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Rhodesli/1.0"})
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            data = resp.read()
        cache.write_bytes(data)
        return data, suffix
    except Exception:
        if cache.exists():
            return cache.read_bytes(), suffix
        raise


def run_gemini(photo_id: str, exp_date: str):
    import time
    import warnings

    warnings.filterwarnings("ignore")
    from app import estimate_routes as er
    from app import main as m
    from rhodesli_ml.gemini_extraction import build_extraction_prompt
    from rhodesli_ml.gemini_config import GEMINI_MODEL

    m._build_caches()
    meta = m.get_photo_metadata(photo_id)
    if not meta:
        print(f"ERROR: photo {photo_id} not found", file=sys.stderr)
        sys.exit(1)
    filename = meta.get("filename", "")
    collection = meta.get("collection", "")
    source = meta.get("source", "")
    image_bytes, suffix = _fetch_image(filename)

    gedcom_context = er._build_gedcom_context_for_photo(photo_id)
    photo_metadata = {"collection": collection, "source": source, "filename": filename}

    # The exact shared prompt all three models receive (fair comparison)
    prompt_text = build_extraction_prompt(
        preset="quick", gedcom_context=gedcom_context, photo_metadata=photo_metadata
    )

    art_dir = ARTIFACT_ROOT / f"{photo_id}-{exp_date}"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / "PROMPT.txt").write_text(prompt_text)
    (art_dir / "image.jpg").write_bytes(image_bytes)
    (art_dir / "meta.json").write_text(
        json.dumps(
            {
                "photo_id": photo_id,
                "filename": filename,
                "collection": collection,
                "source": source,
                "gemini_model": GEMINI_MODEL,
                "experiment_date": exp_date,
                "gedcom_enriched": bool(gedcom_context),
                "gedcom_context_chars": len(gedcom_context or ""),
                "site_url": f"{SITE}/c/fox-family/photo/{photo_id}",
            },
            indent=2,
        )
    )

    experiment_id = f"manual-multimodel-{photo_id}-{exp_date}"
    t0 = time.time()
    result = er._call_gemini_date_estimate(
        image_bytes,
        suffix,
        __import__("os").environ["GEMINI_API_KEY"],
        photo_id=photo_id,
        gedcom_context=gedcom_context,
        call_type="re_analysis",
        trigger="admin_rerun",
        photo_metadata=photo_metadata,
        operator="claude-code-manual",
        experiment_id=experiment_id,
    )
    latency_ms = int((time.time() - t0) * 1000)

    candidate = {
        "model": GEMINI_MODEL,
        "provider": "google-gemini",
        "operator": "claude-code-manual",
        "experiment_id": experiment_id,
        "latency_ms": latency_ms,
        "gedcom_enriched": bool(gedcom_context),
        "result": result,
    }
    (art_dir / "candidate-gemini.json").write_text(json.dumps(candidate, indent=2, ensure_ascii=False))
    print(f"Artifact dir: {art_dir}")
    print(f"Prompt chars: {len(prompt_text)} | GEDCOM enriched: {bool(gedcom_context)}")
    print(f"Gemini latency: {latency_ms}ms | experiment_id: {experiment_id}")
    print("\n=== Gemini result ===")
    print(json.dumps(result, indent=2, ensure_ascii=False) if result else "(FAILED)")
    if not result:
        sys.exit(2)


def finalize(photo_id: str, chosen_model: str, artifact_dir: str):
    """Write ONLY the chosen estimate to date_labels + photo_locations (Supabase),
    tagged with decision provenance pointing back to the artifact."""
    import warnings

    warnings.filterwarnings("ignore")
    from app import estimate_routes as er
    from app.supabase_data import sync_date_label, sync_photo_location
    from rhodesli_ml.gemini_config import GEMINI_MODEL

    art_dir = Path(artifact_dir)
    cand_file = {
        "gemini": "candidate-gemini.json",
        "fable": "candidate-fable.json",
        "codex": "candidate-codex.json",
    }.get(chosen_model.split("-")[0].lower())
    if not cand_file or not (art_dir / cand_file).exists():
        # Allow explicit filename
        cand_path = art_dir / chosen_model if (art_dir / chosen_model).exists() else None
        if not cand_path:
            print(f"ERROR: cannot find candidate file for {chosen_model} in {art_dir}", file=sys.stderr)
            sys.exit(1)
    else:
        cand_path = art_dir / cand_file
    cand = json.loads(cand_path.read_text())
    result = cand["result"]
    model_name = cand.get("model", chosen_model)

    decided_at = datetime.now(timezone.utc).isoformat()
    decision = {
        "operator": "claude-code-manual",
        "chosen_model": model_name,
        "chosen_provider": cand.get("provider"),
        "decision_method": "multi-model side-by-side (Gemini 3.1 Pro vs Fable 5.0 vs Codex gpt-5.5-xhigh), "
        "scored on GEDCOM-consistency + visual-evidence specificity + location/date plausibility",
        "decision_artifact": str(art_dir / "DECISION.md"),
        "candidates_compared": ["gemini-3.1-pro", "fable-5.0", "codex-gpt-5.5-xhigh"],
        "decided_at": decided_at,
    }

    # Build date_labels entry (mirror of estimate_routes reanalyze) + provenance
    location_data = result.get("location", {}) if isinstance(result.get("location"), dict) else {}
    new_location = location_data.get("place", "") if isinstance(location_data, dict) else ""
    entry = {
        "photo_id": photo_id,
        "estimated_decade": result.get("estimated_decade"),
        "best_year_estimate": result.get("best_year_estimate"),
        "confidence": result.get("confidence", "unknown"),
        "probable_range": result.get("probable_range", []),
        "reasoning_summary": result.get("reasoning_summary", ""),
        "scene_description": result.get("scene_description", ""),
        "evidence": result.get("evidence", {}),
        "location_estimate": new_location,
        "model": model_name,
        "location_evidence": location_data,
        "reanalyzed_at": decided_at,
        "reanalyzed_with_gedcom": cand.get("gedcom_enriched", True),
        "prompt_version": "v3_enriched_multimodel",
        "analysis_provenance": decision,
    }
    sync_date_label(photo_id, entry)
    print(f"date_labels written for {photo_id} (model={model_name})")

    if new_location:
        loc_entry = {
            "photo_id": photo_id,
            "lat": er._geocode_location(new_location)[0],
            "lng": er._geocode_location(new_location)[1],
            "location_name": er._geocode_display_name(new_location),
            "location_estimate": location_data.get("visual_evidence", ""),
            "biographical_evidence": location_data.get("biographical_evidence", ""),
            "confidence": location_data.get("confidence", "medium"),
            "region": er._guess_region(new_location),
            "gemini_raw_location": new_location,
            "reanalyzed_at": decided_at,
            "analysis_provenance": decision,
        }
        sync_photo_location(photo_id, loc_entry)
        print(f"photo_locations written for {photo_id} ({loc_entry['location_name']})")

    # Invalidate caches so a locally-running app reflects the change immediately
    try:
        from app import page_routes as _pr

        _pr._date_labels_cache = None
        _pr._photo_locations_cache = None
    except Exception:
        pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run-gemini":
        run_gemini(sys.argv[2], sys.argv[3])
    elif cmd == "finalize":
        finalize(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        print(__doc__)
        sys.exit(1)
