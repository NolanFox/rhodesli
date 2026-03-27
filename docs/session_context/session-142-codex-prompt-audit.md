OpenAI Codex v0.115.0 (research preview)
--------
workdir: /Users/nolanfox/rhodesli
model: gpt-5.4
provider: openai
approval: never
sandbox: workspace-write [workdir, /tmp, $TMPDIR, /Users/nolanfox/.codex/memories]
reasoning effort: xhigh
reasoning summaries: none
session id: 019d2f07-9b7c-7a41-b246-c5383e0780ca
--------
user
Review the Gemini extraction prompt in rhodesli_ml/gemini_extraction.py (build_extraction_prompt function) and the batch calling code in scripts/batch_gemini_for_person.py. Focus on: (1) Is the prompt optimized for historical photo dating from 1910-1970? (2) Are we extracting all useful metadata for family identification? (3) Are face coordinates being used effectively? (4) Is GEDCOM context being passed optimally? (5) Any improvements to get better date estimates, age estimates, or relationship inference? Rate suggestions P0/P1/P2/P3. Also check app/estimate_routes.py _call_gemini_date_estimate for the production prompt path.
mcp startup: no servers
codex
I’m reviewing the Gemini prompt construction and the two calling paths to assess dating, family-identification metadata, coordinate usage, GEDCOM context, and inference quality. First step is to read the relevant files and trace how the production prompt differs from the batch script path.
exec
/bin/zsh -lc "sed -n '1,260p' rhodesli_ml/gemini_extraction.py" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '1,260p' app/estimate_routes.py" in /Users/nolanfox/rhodesli succeeded in 39ms:
"""Unified Gemini extraction architecture with configurable presets.

One API call per photo extracts everything needed. Presets control which
extraction types are included, saving ~80% on costs vs separate calls.

See AD-143 for decision rationale.

Usage:
    from rhodesli_ml.gemini_extraction import build_extraction_prompt, EXTRACTION_PRESETS

    # Full analysis (batch runs)
    prompt = build_extraction_prompt(preset="full")

    # Quick estimate (interactive upload)
    prompt = build_extraction_prompt(preset="quick")

    # Custom: full minus face_analysis
    prompt = build_extraction_prompt(preset="full", exclude=["face_analysis"])
"""

exec
/bin/zsh -lc "sed -n '1,260p' scripts/batch_gemini_for_person.py" in /Users/nolanfox/rhodesli succeeded in 47ms:
"""
Estimate routes extracted from app/main.py.

All /tools/estimate/* and /api/estimate/* routes plus estimate-exclusive helpers.
"""

import logging
import os
from datetime import datetime, timezone

from fasthtml.common import *
from starlette.datastructures import UploadFile

from starlette.responses import Response as StarletteResponse

from core import storage

# Import route decorator only
from app.main import rt
from app.rate_limit import check_rate_limit
 succeeded in 42ms:
#!/usr/bin/env python3
"""Batch Gemini date estimation for all photos containing specific identities.

Uses the production _call_gemini_date_estimate() function with:
- GEDCOM genealogical context for identified faces
- Full Supabase logging to gemini_api_calls table
- Prompt manifest tracking
- Retry logic with exponential backoff
- Incremental results saved to date_labels.json

Usage:
    # Dry run: count photos, show cost estimate
    python scripts/batch_gemini_for_person.py --dry-run \\
        --identity 65207728-9ee6-48c1-be68-a2da23354caf \\
        --identity 85546ebf-75b9-4971-a9d4-b2ce2271bc19

    # Run estimation for Esther + Albert
    python scripts/batch_gemini_for_person.py \\
        --identity 65207728-9ee6-48c1-be68-a2da23354caf \\
        --identity 85546ebf-75b9-4971-a9d4-b2ce2271bc19 \\
codex
I’ve got the top-level prompt builder and batch script; now I’m tracing the exact production call path and the rest of the prompt assembly, including how GEDCOM and face boxes are actually injected.
exec
/bin/zsh -lc "sed -n '260,520p' rhodesli_ml/gemini_extraction.py" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "rg -n \"def build_extraction_prompt|_call_gemini_date_estimate|gedcom_context|face_coordinates|build_extraction_prompt\\(\" rhodesli_ml/gemini_extraction.py scripts/batch_gemini_for_person.py app/estimate_routes.py" in /Users/nolanfox/rhodesli succeeded in 44ms:
        sections.append(
            f"## Genealogical Context\n{gedcom_context}\n\n"
            "Use this genealogical data to improve date, location, and identity analysis."
        )

    # Add photo metadata context if provided
    if photo_metadata:
        meta_section = "## Photo Metadata Context\n"
        if photo_metadata.get("collection"):
            meta_section += f"Collection: {photo_metadata['collection']}\n"
        if photo_metadata.get("source"):
            meta_section += f"Source: {photo_metadata['source']}\n"
        if photo_metadata.get("filename"):
            meta_section += f"Original filename: {photo_metadata['filename']}\n"
        if photo_metadata.get("visible_text"):
            meta_section += f"Previously extracted text: {photo_metadata['visible_text']}\n"
        meta_section += (
            "\nNOTE ON COLLECTION NAMES: A collection name indicates WHO HAD these photos and\n"
            "WHERE THEY WERE STORED, not necessarily where the photos were taken. For example,\n"
            'a "Tampa Collection" means the photos were found in Tampa -- but the actual photos\n'
exec
/bin/zsh -lc "sed -n '260,520p' scripts/batch_gemini_for_person.py" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '260,520p' app/estimate_routes.py" in /Users/nolanfox/rhodesli succeeded in 115ms:
scripts/batch_gemini_for_person.py:4:Uses the production _call_gemini_date_estimate() function with:
scripts/batch_gemini_for_person.py:269:    from app.estimate_routes import _build_gedcom_context_for_photo
scripts/batch_gemini_for_person.py:299:    def _get_cached_gedcom_context(photo_id):
scripts/batch_gemini_for_person.py:302:                ctx = _build_gedcom_context_for_photo(photo_id)
scripts/batch_gemini_for_person.py:309:    def _get_face_coordinates(photo_id):
scripts/batch_gemini_for_person.py:330:    def _call_gemini_full(image_bytes, suffix, photo_id, gedcom_context, photo_metadata, face_coordinates):
scripts/batch_gemini_for_person.py:334:        prompt_text = build_extraction_prompt(
scripts/batch_gemini_for_person.py:336:            face_coordinates=face_coordinates,
scripts/batch_gemini_for_person.py:337:            gedcom_context=gedcom_context,
scripts/batch_gemini_for_person.py:342:            if gedcom_context and face_coordinates
scripts/batch_gemini_for_person.py:343:            else ("gedcom" if gedcom_context else ("faces" if face_coordinates else "none"))
scripts/batch_gemini_for_person.py:353:                "uses_gedcom": bool(gedcom_context),
scripts/batch_gemini_for_person.py:356:                "uses_face_coords": bool(face_coordinates),
scripts/batch_gemini_for_person.py:458:                            "face_count": len(face_coordinates) if face_coordinates else 0,
scripts/batch_gemini_for_person.py:483:                            "face_count": len(face_coordinates) if face_coordinates else 0,
scripts/batch_gemini_for_person.py:490:                        gedcom_context=gedcom_context,
scripts/batch_gemini_for_person.py:526:        gedcom_context = _get_cached_gedcom_context(pid)
scripts/batch_gemini_for_person.py:529:        face_coordinates = _get_face_coordinates(pid)
scripts/batch_gemini_for_person.py:530:        if face_coordinates:
scripts/batch_gemini_for_person.py:531:            logger.info(f"  {len(face_coordinates)} faces with bounding boxes")
 succeeded in 43ms:
    )

    page_style = Style("""
        html, body { margin: 0; }
        body { background-color: #0f172a; }
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator,
        .htmx-request.htmx-indicator { display: inline; }
        div.htmx-request.htmx-indicator,
        .htmx-request div.htmx-indicator { display: block; }
        form.htmx-request button[type="submit"] {
            opacity: 0.5;
            pointer-events: none;
        }
    """)

    return (
        Title("When Was This Photo Taken? — Date Estimator"),
        *og,
        page_style,
 succeeded in 44ms:
        for pid, photo in photo_list[:10]:
            filename = photo.get("filename", photo.get("path", "unknown"))
            identities_str = ", ".join(photo.get("identities", []))
            logger.info(f"  {pid[:12]}... {filename} [{identities_str}]")
        if len(photo_list) > 10:
            logger.info(f"  ... and {len(photo_list) - 10} more")
        return

    # Import production functions
    from app.estimate_routes import _build_gedcom_context_for_photo
    from rhodesli_ml.gemini_extraction import build_extraction_prompt
    from rhodesli_ml.gemini_config import GEMINI_MODEL, get_model_pricing
    from rhodesli_ml.prompt_manifest import build_prompt_lineage_fields, build_prompt_manifest
    from app.supabase_data import log_gemini_call
    from google import genai
    from google.genai import types
    import numpy as np

    # Pre-load face data for bounding box coordinates
    embeddings_path = Path("data/embeddings.npy")
exec
/bin/zsh -lc "sed -n '520,760p' scripts/batch_gemini_for_person.py" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '520,760p' app/estimate_routes.py" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '1215,1315p' app/estimate_routes.py" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '1080,1215p' app/estimate_routes.py" in /Users/nolanfox/rhodesli succeeded in 213ms:
            error_count += 1
            continue

        suffix = local_path.suffix

        # Build GEDCOM context (cached per photo)
        gedcom_context = _get_cached_gedcom_context(pid)

        # Get face coordinates for this photo
        face_coordinates = _get_face_coordinates(pid)
        if face_coordinates:
            logger.info(f"  {len(face_coordinates)} faces with bounding boxes")

        # Call Gemini with FULL preset
        try:
            result = _call_gemini_full(
                image_bytes=image_bytes,
                suffix=suffix,
                photo_id=pid,
                gedcom_context=gedcom_context,
 succeeded in 213ms:
        channel="interactive" if trigger == "interactive_upload" else "admin_rerun",
        context_flags={
            "uses_gedcom": bool(gedcom_context),
            "uses_geo": True,
            "uses_time": True,
            "uses_face_coords": False,
        },
        template_source="rhodesli_ml.gemini_extraction.build_extraction_prompt",
    )

    client = genai.Client(
        api_key=api_key,
        http_options={"timeout": 180_000 if gedcom_context else 30_000},
    )

    mime_type = "image/png" if suffix.lower() == ".png" else "image/jpeg"

    max_retries = 2
    retry_delays = [5, 15]  # seconds
    start_time = _time.time()
 succeeded in 80ms:
    # Get old data for comparison
    old_labels = _main_mod._load_date_labels()
    old_label = old_labels.get(photo_id, {})
    old_locations = _main_mod._load_photo_locations()
    old_location = old_locations.get(photo_id, {})
    old_location_name = old_location.get("location_name", "Unknown")

    # Build photo metadata for collection/source context
    _main_mod._build_caches()
    photo_meta = _main_mod.get_photo_metadata(photo_id)
    p_metadata = None
    visible_text = None
    if photo_meta:
        p_metadata = {
            "collection": photo_meta.get("collection", ""),
            "source": photo_meta.get("source", ""),
            "filename": photo_meta.get("filename", ""),
        }
        # Extract visible text from previous analysis for business owner lookup (AD-210)
        visible_text = photo_meta.get("visible_text")
 succeeded in 78ms:
                return resp.read(), suffix
        except Exception as e:
            logger.warning(f"Failed to fetch photo from R2: {e}")
            return None, ""
    else:
        local_path = Path("raw_photos") / Path(filename).name
        if local_path.exists():
            return local_path.read_bytes(), suffix
        return None, ""


def _build_gedcom_context_for_photo(photo_id: str, visible_text: str | None = None) -> str | None:
    """Build GEDCOM context string for identified faces in a photo.

    Args:
        photo_id: Photo ID to build context for.
        visible_text: Text visible in photo (signage, storefronts) for
            business owner GEDCOM lookup (AD-210).

    Returns context string or None if no GEDCOM data available.
codex
I’m checking the shape of the GEDCOM context itself and how face order maps to identities, because several review points hinge on whether the prompt has aligned person-level context rather than just a raw text dump.
exec
/bin/zsh -lc "rg -n \"def build_gedcom_context|class _FaceStub|find_business_owner_context|face_index|bbox|subject_ages|face_analysis\" scripts/run_combined_pipeline.py rhodesli_ml app | sed -n '1,260p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '1,260p' scripts/run_combined_pipeline.py" in /Users/nolanfox/rhodesli succeeded in 8ms:
#!/usr/bin/env python3
"""
Combined Gemini processing pipeline for photos.

Combines face alignment (coordinate bridging) with GEDCOM-curated context
injection. This is the canonical "process a photo with AI" script.

Built from Session 63's alignment-only batch + Session 61C's GEDCOM context.
See AD-152 for data layer decisions.

Usage:
    python scripts/run_combined_pipeline.py --limit 5          # validation
    python scripts/run_combined_pipeline.py --execute          # all unprocessed
    python scripts/run_combined_pipeline.py --retry-failed     # retry rate-limited
    python scripts/run_combined_pipeline.py --photo-ids p1 p2  # specific photos
"""

import argparse
import asyncio
import json
 succeeded in 79ms:
scripts/run_combined_pipeline.py:93:        bbox = None
scripts/run_combined_pipeline.py:100:                bbox_raw = emb.get("bbox", [0, 0, 0, 0])
scripts/run_combined_pipeline.py:101:                bbox = [int(b) for b in bbox_raw]
scripts/run_combined_pipeline.py:107:        if bbox is None and i < len(face_embs):
scripts/run_combined_pipeline.py:109:            bbox_raw = emb.get("bbox", [0, 0, 0, 0])
scripts/run_combined_pipeline.py:110:            bbox = [int(b) for b in bbox_raw]
scripts/run_combined_pipeline.py:114:        if bbox is None:
scripts/run_combined_pipeline.py:120:            bbox=bbox,
scripts/run_combined_pipeline.py:121:            face_index=i,
scripts/run_combined_pipeline.py:130:def build_gedcom_context(photo_id: str, faces: list[FaceDetection],
scripts/run_combined_pipeline.py:479:        return {"photo_id": photo_id, "status": "skipped", "reason": "no faces with bboxes"}
scripts/run_combined_pipeline.py:552:        return {"photo_id": photo_id, "status": "skipped", "reason": "no faces with bboxes"}
rhodesli_ml/gemini_extraction.py:17:    # Custom: full minus face_analysis
rhodesli_ml/gemini_extraction.py:18:    prompt = build_extraction_prompt(preset="full", exclude=["face_analysis"])
rhodesli_ml/gemini_extraction.py:26:        "face_analysis": True,
rhodesli_ml/gemini_extraction.py:34:        "subject_ages": True,
rhodesli_ml/gemini_extraction.py:38:        "face_analysis": False,
rhodesli_ml/gemini_extraction.py:46:        "subject_ages": False,
rhodesli_ml/gemini_extraction.py:50:        "face_analysis": True,
rhodesli_ml/gemini_extraction.py:58:        "subject_ages": True,
exec
/bin/zsh -lc "sed -n '1,260p' rhodesli_ml/gedcom_context.py" in /Users/nolanfox/rhodesli succeeded in 17ms:
"""GEDCOM context builder for Gemini prompt enrichment.

Builds per-photo context strings at 5 enrichment levels:
  - none: empty string (baseline)
  - full: all events for identified people
  - curated: events within ±15yr of photo_date_estimate
  - first_order: full + all events for immediate family
  - co_occurrence: first_order + events for anyone sharing ANY photo

Each level adds more genealogical context to the Gemini prompt,
at the cost of more tokens. Designed for the 2×5 comparison matrix
(Flash/Pro × 5 variants).

Session: 61C | AD-146
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)
exec
/bin/zsh -lc "sed -n '260,520p' rhodesli_ml/gedcom_context.py" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '120,260p' app/face_alignment.py" in /Users/nolanfox/rhodesli succeeded in 69ms:
    """
    Build the full Gemini prompt for face alignment.

    Uses the unified extraction architecture (AD-143) with face_analysis type.
    Includes coordinate block, per-face analysis request, and JSON output schema.
    """
    coords_block = format_faces_for_gemini(faces)

    prompt_parts = [
        "You are a forensic photo analyst specializing in heritage photographs.",
        "",
        "## Face Coordinate Analysis",
        coords_block,
        "",
        "For EACH face listed above, provide:",
        "1. estimated_age: integer age estimate",
        "2. gender: 'male' or 'female'",
        "3. description: brief physical description (hair, facial features)",
        "4. clothing: clothing/attire description visible in the photo",
        "5. position: where this person is in the photo (e.g., 'center, standing')",
 succeeded in 70ms:
        lines.append(p_str)
        # Include parent events (residence and occupation for location context)
        for event in parent.events:
            e_str = f"    {event.event_type.title()}: {event.raw_date or '?'}"
            if event.place:
                e_str += f" in {event.place}"
            # Tag immigration/emigration as transit (AD-209)
            if event.event_type in ("immigration", "emigration"):
                e_str += " [PORT OF ENTRY — transit point, NOT necessarily residence]"
            lines.append(e_str)

    # Spouses (with residence and occupation events for location context)
    spouses = parsed_gedcom.get_spouses(indi)
    for spouse in spouses:
        s_str = f"  Spouse: {spouse.full_name}"
        if spouse.birth and spouse.birth_year:
            s_str += f" (b.{spouse.birth_year})"
        if spouse.birth_place:
            s_str += f", born in {spouse.birth_place}"
        lines.append(s_str)
exec
/bin/zsh -lc "sed -n '100,170p' rhodesli_ml/pipelines/birth_year_estimation.py" in /Users/nolanfox/rhodesli succeeded in 168ms:
    """Get all face IDs for an identity (anchors + candidates)."""
    anchors = identity.get("anchor_ids", [])
    candidates = identity.get("candidate_ids", [])
    return list(set(anchors + candidates))


def match_faces_to_ages(photo_face_ids, face_bboxes, subject_ages):
    """Match face IDs to Gemini age estimates via left-to-right bbox ordering.

    Args:
        photo_face_ids: List of face IDs detected in this photo
        face_bboxes: Dict mapping face_id -> bbox [x1, y1, x2, y2]
        subject_ages: List of integer ages from Gemini (left-to-right)

    Returns:
        Dict mapping face_id -> estimated_age, or empty dict if matching fails.
        Also returns matching_method: "single_person", "bbox_matched", or "ambiguous".
    """
    if not subject_ages or not photo_face_ids:
        return {}, "no_data"
codex
I’m checking for schema drift between what the prompt asks Gemini to return and what the batch script expects to save. That matters because some “missing metadata” may actually be dropped before it ever reaches downstream code.
exec
/bin/zsh -lc "nl -ba rhodesli_ml/gemini_extraction.py | sed -n '1,340p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "rg -n 'scene_description|people_count|photo_type|setting|keywords|controlled_tags|visible_text|text_signage|photo_condition|group_composition|cultural_markers|photo_technique' -S rhodesli_ml scripts app | sed -n '1,260p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba app/estimate_routes.py | sed -n '470,1315p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba scripts/batch_gemini_for_person.py | sed -n '260,640p'" in /Users/nolanfox/rhodesli succeeded in 162ms:
     1	"""Unified Gemini extraction architecture with configurable presets.
     2	
     3	One API call per photo extracts everything needed. Presets control which
     4	extraction types are included, saving ~80% on costs vs separate calls.
     5	
     6	See AD-143 for decision rationale.
     7	
     8	Usage:
     9	    from rhodesli_ml.gemini_extraction import build_extraction_prompt, EXTRACTION_PRESETS
    10	
    11	    # Full analysis (batch runs)
    12	    prompt = build_extraction_prompt(preset="full")
    13	
    14	    # Quick estimate (interactive upload)
    15	    prompt = build_extraction_prompt(preset="quick")
    16	
    17	    # Custom: full minus face_analysis
    18	    prompt = build_extraction_prompt(preset="full", exclude=["face_analysis"])
    19	"""
    20	
 succeeded in 115ms:
   260	        for pid, photo in photo_list[:10]:
   261	            filename = photo.get("filename", photo.get("path", "unknown"))
   262	            identities_str = ", ".join(photo.get("identities", []))
   263	            logger.info(f"  {pid[:12]}... {filename} [{identities_str}]")
   264	        if len(photo_list) > 10:
   265	            logger.info(f"  ... and {len(photo_list) - 10} more")
   266	        return
   267	
   268	    # Import production functions
   269	    from app.estimate_routes import _build_gedcom_context_for_photo
   270	    from rhodesli_ml.gemini_extraction import build_extraction_prompt
   271	    from rhodesli_ml.gemini_config import GEMINI_MODEL, get_model_pricing
   272	    from rhodesli_ml.prompt_manifest import build_prompt_lineage_fields, build_prompt_manifest
   273	    from app.supabase_data import log_gemini_call
   274	    from google import genai
   275	    from google.genai import types
   276	    import numpy as np
   277	
   278	    # Pre-load face data for bounding box coordinates
   279	    embeddings_path = Path("data/embeddings.npy")
 succeeded in 118ms:
   470	                cls="flex justify-center mt-4",
   471	                id="load-more-container",
   472	                hx_swap_oob="true",
   473	            )
   474	        )
   475	
   476	    return tuple(items)
   477	
   478	
   479	def _call_gemini_date_estimate(
   480	    image_bytes: bytes,
   481	    suffix: str,
   482	    api_key: str,
   483	    photo_id: str | None = None,
   484	    gedcom_context: str | None = None,
   485	    call_type: str = "date_estimation",
   486	    trigger: str = "interactive_upload",
   487	    photo_metadata: dict | None = None,
   488	) -> dict | None:
   489	    """Call Gemini Vision API for date/location estimation using the enriched prompt.
 succeeded in 829ms:
rhodesli_ml/gemini_extraction.py:28:        "cultural_markers": True,
rhodesli_ml/gemini_extraction.py:30:        "photo_technique": True,
rhodesli_ml/gemini_extraction.py:31:        "text_signage": True,
rhodesli_ml/gemini_extraction.py:32:        "group_composition": True,
rhodesli_ml/gemini_extraction.py:33:        "photo_condition": True,
rhodesli_ml/gemini_extraction.py:40:        "cultural_markers": False,
rhodesli_ml/gemini_extraction.py:42:        "photo_technique": False,
rhodesli_ml/gemini_extraction.py:43:        "text_signage": True,
rhodesli_ml/gemini_extraction.py:44:        "group_composition": False,
rhodesli_ml/gemini_extraction.py:45:        "photo_condition": False,
rhodesli_ml/gemini_extraction.py:52:        "cultural_markers": False,
rhodesli_ml/gemini_extraction.py:54:        "photo_technique": False,
rhodesli_ml/gemini_extraction.py:55:        "text_signage": False,
rhodesli_ml/gemini_extraction.py:56:        "group_composition": False,
rhodesli_ml/gemini_extraction.py:57:        "photo_condition": False,
rhodesli_ml/gemini_extraction.py:90:    "cultural_markers": """"cultural_markers": ["Sephardic formal attire", "studio backdrop typical of Rhodes photographers"]""",
rhodesli_ml/gemini_extraction.py:92:    "photo_technique": """"photo_technique": {
rhodesli_ml/gemini_extraction.py:98:    "text_signage": """"visible_text": {
rhodesli_ml/gemini_extraction.py:104:    "group_composition": """"group_composition": {
rhodesli_ml/gemini_extraction.py:106:    "people_count": 3,
codex
I’ve confirmed one likely drift already: the prompt asks for top-level `visible_text`, but the batch saver looks for `text_signage`. I’m tracing whether that causes production/business-name context to miss the very text Gemini extracted.
exec
/bin/zsh -lc "rg -n 'new_entry\\[\"visible_text\"\\]|result.get\\(\"visible_text\"|text_signage' app/estimate_routes.py scripts/batch_gemini_for_person.py app/supabase_data.py app/main.py rhodesli_ml | sed -n '1,240p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '1,120p' rhodesli_ml/data/model_comparisons/manual_rerun_inbox_benatar_old_2.5.json" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba app/estimate_routes.py | sed -n '1315,1365p'" in /Users/nolanfox/rhodesli succeeded in 80ms:
{
  "photo_id": "inbox_benatar-20260213b_0_472157630_10170853657825346_1042246886224871126_n",
  "source": "gemini",
  "model": "gemini-2.5-flash",
  "source_method": "api",
  "estimated_decade": 1920,
  "best_year_estimate": 1928,
  "confidence": "high",
  "probable_range": [1927, 1929],
  "decade_probabilities": {"1920": 0.95, "1930": 0.05},
  "location_estimate": "Indoor studio, no specific geographic indicators.",
  "is_color": false,
  "evidence": {
    "print_format": [
      {"cue": "Sepia tone, monochrome print", "strength": "moderate", "suggested_range": [1910, 1940]},
      {"cue": "Straight white border, typical for studio prints", "strength": "moderate", "suggested_range": [1910, 1940]}
    ],
    "fashion": [
      {"cue": "Man's suit with structured shoulders and moderate-width lapels", "strength": "strong", "suggested_range": [1925, 1935]},
      {"cue": "Neatly parted and slicked-back hairstyle", "strength": "strong", "suggested_range": [1920, 1935]},
 succeeded in 88ms:
  1315	            from rhodesli_ml.gemini_config import GEMINI_MODEL as _reanalyze_model
  1316	
  1317	            new_entry = {
  1318	                "photo_id": photo_id,
  1319	                "estimated_decade": new_decade,
  1320	                "best_year_estimate": new_year,
  1321	                "confidence": new_confidence,
  1322	                "probable_range": result.get("probable_range", []),
  1323	                "reasoning_summary": result.get("reasoning_summary", ""),
  1324	                "scene_description": result.get("scene_description", ""),
  1325	                "evidence": result.get("evidence", {}),
  1326	                "location_estimate": new_location,
  1327	                "model": _reanalyze_model,
  1328	                "location_evidence": location_data if isinstance(location_data, dict) else {},
  1329	                "reanalyzed_at": datetime.now(timezone.utc).isoformat(),
  1330	                "reanalyzed_with_gedcom": bool(gedcom_context),
  1331	                "prompt_version": "v3_enriched" if gedcom_context else "v3_visual_only",
  1332	            }
  1333	            # Store visible_text for future re-analyses (AD-210)
  1334	            if visible_text:
 succeeded in 229ms:
scripts/batch_gemini_for_person.py:587:                "text_signage": result.get("text_signage", {}),
app/estimate_routes.py:506:    # Build enriched prompt (quick preset: date + location + text_signage)
app/estimate_routes.py:1335:                new_entry["visible_text"] = visible_text
rhodesli_ml/gemini_extraction.py:31:        "text_signage": True,
rhodesli_ml/gemini_extraction.py:43:        "text_signage": True,
rhodesli_ml/gemini_extraction.py:55:        "text_signage": False,
rhodesli_ml/gemini_extraction.py:98:    "text_signage": """"visible_text": {
rhodesli_ml/gemini_extraction.py:179:    "text_signage": """## Text & Signage Detection
rhodesli_ml/scripts/generate_date_labels.py:494:            "visible_text": result.get("visible_text"),
rhodesli_ml/scripts/generate_date_labels.py:526:        visible_text = result.get("visible_text")
rhodesli_ml/scripts/add_manual_label.py:226:        "visible_text": result.get("visible_text"),
rhodesli_ml/tests/test_gemini_extraction.py:26:        assert quick["text_signage"] is True
rhodesli_ml/tests/test_gemini_extraction.py:230:        assert "text_signage" in active
codex
I’m looking at existing prompt tests and legacy outputs next. That helps separate intentional simplification from accidental loss of useful fields like `scene_description`, `visible_text`, and capture-vs-print reasoning.
exec
/bin/zsh -lc "sed -n '1,320p' rhodesli_ml/tests/test_gemini_extraction.py" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '130,260p' rhodesli_ml/scripts/generate_date_labels.py" in /Users/nolanfox/rhodesli succeeded in 32ms:

## Additional Metadata Instructions

In addition to date estimation, extract the following metadata:

scene_description: 2-3 sentences describing what is visible in the photo. Include people, their arrangement, the setting, and any notable objects. Write as if describing the photo to someone who cannot see it.

visible_text: If there is ANY handwritten or printed text visible on or around the photo (inscriptions, captions, dates written on the photo, text on clothing, signs, documents), transcribe it exactly. Include the original language. If no text is visible, return null.
IMPORTANT for visible text: Inscriptions on these photos may be in Ladino (Judeo-Spanish), French, Italian, Greek, or English. Handwritten text may use Solitreo (Sephardic cursive Hebrew script). DO NOT normalize Ladino spelling to standard Spanish. Preserve the original orthography exactly. For the visible_text_language field, detect the language. For visible_text_script field, classify as: Latin, Hebrew, Solitreo, Mixed, or Unknown.

keywords: 5-15 searchable tags covering: people descriptors (man, woman, child, elderly), setting (studio, outdoor, home), occasion (wedding, funeral, school, military), objects (hat, umbrella, car), and any culturally specific items (fez, traditional dress).

controlled_tags: Choose ALL that apply from this strict list (do not invent new values): ["Studio", "Outdoor", "Beach", "Street", "Home_Interior", "Synagogue", "Cemetery", "Wedding", "Funeral", "Religious_Ceremony", "School", "Military", "Formal_Event", "Casual", "Group_Portrait", "Document", "Postcard"]

setting: Classify as one of: indoor_studio, outdoor_urban, outdoor_rural, indoor_home, indoor_other, outdoor_other, unknown.

photo_type: Classify as one of: formal_portrait, group_photo, candid, document, postcard, wedding, funeral, school, military, religious_ceremony, other.

people_count: How many people are visible in the photo (include partially visible people). Return 0 if no people are visible.

 succeeded in 37ms:
"""Tests for unified Gemini extraction architecture.

Verifies presets, prompt building, and schema generation.
"""

import pytest
from rhodesli_ml.gemini_extraction import (
    EXTRACTION_PRESETS,
    build_extraction_prompt,
    get_active_extractions,
)


class TestExtractionPresets:
    """Verify preset configurations are correct."""

    def test_full_preset_includes_all_types(self):
        """Full preset enables every extraction type."""
        full = EXTRACTION_PRESETS["full"]
        assert all(v is True for v in full.values()), "Full preset must enable all types"
exec
/bin/zsh -lc "rg -n 'capture_vs_print|visible_text_language|visible_text_script|scene_description|keywords|controlled_tags|setting|photo_type|people_count' rhodesli_ml/scripts/generate_date_labels.py | sed -n '1,220p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "sed -n '1,140p' rhodesli_ml/scripts/generate_date_labels.py" in /Users/nolanfox/rhodesli succeeded in 575ms:
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

 succeeded in 786ms:
7:OCR, keywords, setting, photo type, people count, condition, clothing).
63:vegetation, street features, signage language, urban vs rural setting.
102:        "capture_vs_print": "Likely 1940s capture. Print characteristics consistent with original.",
118:    "scene_description": "Formal studio portrait of a middle-aged man and two women. The man stands in the center wearing a dark suit. The women are seated on either side in light-colored dresses. A painted backdrop depicts a garden scene.",
120:    "keywords": ["formal portrait", "studio", "family group", "suit", "lace collar", "painted backdrop"],
121:    "setting": "indoor_studio",
122:    "photo_type": "formal_portrait",
123:    "people_count": 3,
135:scene_description: 2-3 sentences describing what is visible in the photo. Include people, their arrangement, the setting, and any notable objects. Write as if describing the photo to someone who cannot see it.
138:IMPORTANT for visible text: Inscriptions on these photos may be in Ladino (Judeo-Spanish), French, Italian, Greek, or English. Handwritten text may use Solitreo (Sephardic cursive Hebrew script). DO NOT normalize Ladino spelling to standard Spanish. Preserve the original orthography exactly. For the visible_text_language field, detect the language. For visible_text_script field, classify as: Latin, Hebrew, Solitreo, Mixed, or Unknown.
140:keywords: 5-15 searchable tags covering: people descriptors (man, woman, child, elderly), setting (studio, outdoor, home), occasion (wedding, funeral, school, military), objects (hat, umbrella, car), and any culturally specific items (fez, traditional dress).
142:controlled_tags: Choose ALL that apply from this strict list (do not invent new values): ["Studio", "Outdoor", "Beach", "Street", "Home_Interior", "Synagogue", "Cemetery", "Wedding", "Funeral", "Religious_Ceremony", "School", "Military", "Formal_Event", "Casual", "Group_Portrait", "Document", "Postcard"]
144:setting: Classify as one of: indoor_studio, outdoor_urban, outdoor_rural, indoor_home, indoor_other, outdoor_other, unknown.
146:photo_type: Classify as one of: formal_portrait, group_photo, candid, document, postcard, wedding, funeral, school, military, religious_ceremony, other.
148:people_count: How many people are visible in the photo (include partially visible people). Return 0 if no people are visible.
276:                for key in ("scene_description", "visible_text", "keywords",
277:                            "controlled_tags", "setting", "photo_type",
278:                            "people_count", "condition", "clothing_notes",
490:            "capture_vs_print": result.get("capture_vs_print", ""),
493:            "scene_description": result.get("scene_description"),
codex
I’m verifying the face-order assumption now. The prompt says `face_index` is left-to-right, so I need to see whether the batch code actually sorts bboxes that way before sending them.
exec
/bin/zsh -lc "nl -ba app/main.py | sed -n '4128,4195p'" in /Users/nolanfox/rhodesli succeeded in 129ms:
  4128	
  4129	def load_embeddings_for_photos():
  4130	    """
  4131	    Load embeddings and build photo metadata cache.
  4132	
  4133	    Session 125: Uses unified raw embeddings cache instead of separate np.load.
  4134	
  4135	    Returns:
  4136	        dict mapping photo_id -> {
  4137	            "filename": str,
  4138	            "faces": list of {face_id, bbox, face_index}
  4139	        }
  4140	    """
  4141	    raw = _load_raw_embeddings()
  4142	    if not raw:
  4143	        return {}
  4144	
  4145	    # Group faces by photo_id
  4146	    photos = {}
  4147	    filename_face_counts = {}
exec
/bin/zsh -lc "nl -ba app/page_routes.py | sed -n '3578,3608p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba scripts/run_combined_pipeline.py | sed -n '60,150p'" in /Users/nolanfox/rhodesli succeeded in 122ms:
  3578	            prev_id = context_photo_ids[idx - 1]
  3579	        if idx < len(context_photo_ids) - 1:
  3580	            next_id = context_photo_ids[idx + 1]
  3581	        nav_idx = idx
  3582	        nav_total = len(context_photo_ids)
  3583	
  3584	    # Pre-pass: identify unidentified faces for sequential mode + "Name These Faces" button
  3585	    # Sort by left-to-right bbox position for natural left-to-right naming order
  3586	    unidentified_face_ids = []
  3587	    total_face_count = len(photo.get("faces", []))
  3588	    for fd in photo.get("faces", []):
  3589	        fid = fd["face_id"]
  3590	        ident = _main_mod.get_identity_for_face(registry, fid)
  3591	        ident_state = ident.get("state", "INBOX") if ident else None
  3592	        ident_name = ident.get("name", "Unidentified") if ident else "Unidentified"
  3593	        is_named = ident_state == "CONFIRMED" and not ident_name.startswith("Unidentified")
  3594	        if not is_named:
  3595	            unidentified_face_ids.append(fid)
  3596	
  3597	    # Sort unidentified faces left-to-right by bbox x1
 succeeded in 107ms:
    60	
    61	    r2_url = os.getenv("R2_PUBLIC_URL", "")
    62	    if r2_url:
    63	        filename = Path(photo_path).name
    64	        url = f"{r2_url}/raw_photos/{urllib.parse.quote(filename)}"
    65	        try:
    66	            with urllib.request.urlopen(url, timeout=30) as resp:
    67	                return resp.read()
    68	        except (urllib.error.URLError, TimeoutError, OSError) as e:
    69	            logger.warning(f"R2 load failed for {filename}: {e}")
    70	
    71	    return None
    72	
    73	
    74	def build_faces_for_photo(photo_data: dict, identities: dict, embeddings) -> list[FaceDetection]:
    75	    """Build FaceDetection objects from photo + embeddings data."""
    76	    face_ids = photo_data.get("face_ids", [])
    77	    path = photo_data.get("path", "")
    78	    filename = Path(path).name
    79	
codex
I have enough to draft the main findings, but I want exact line refs for the GEDCOM-builder behavior before I close this out. I’m pulling those now so the review points to the precise prompt/context seams.
exec
/bin/zsh -lc "nl -ba scripts/run_combined_pipeline.py | sed -n '130,170p'" in /Users/nolanfox/rhodesliexec
/bin/zsh -lc "nl -ba rhodesli_ml/gedcom_context.py | sed -n '1,240p'" in /Users/nolanfox/rhodesli succeeded in 66ms:
     1	"""GEDCOM context builder for Gemini prompt enrichment.
     2	
     3	Builds per-photo context strings at 5 enrichment levels:
     4	  - none: empty string (baseline)
     5	  - full: all events for identified people
     6	  - curated: events within ±15yr of photo_date_estimate
     7	  - first_order: full + all events for immediate family
     8	  - co_occurrence: first_order + events for anyone sharing ANY photo
     9	
    10	Each level adds more genealogical context to the Gemini prompt,
    11	at the cost of more tokens. Designed for the 2×5 comparison matrix
    12	(Flash/Pro × 5 variants).
    13	
    14	Session: 61C | AD-146
    15	"""
    16	
    17	import logging
    18	from typing import Optional
    19	
    20	logger = logging.getLogger(__name__)
 succeeded in 67ms:
   130	def build_gedcom_context(photo_id: str, faces: list[FaceDetection],
   131	                         identities: dict, gedcom_data: dict | None) -> str:
   132	    """Build GEDCOM context string for a photo's identified faces.
   133	
   134	    Returns empty string if no GEDCOM data or no identified faces.
   135	    """
   136	    if not gedcom_data:
   137	        return ""
   138	
   139	    parsed_gedcom = gedcom_data.get("parsed_gedcom")
   140	    face_links = gedcom_data.get("face_links", {})
   141	    if not parsed_gedcom or not face_links:
   142	        return ""
   143	
   144	    # Get face_ids that have confirmed identities
   145	    identified_face_ids = [f.face_id for f in faces if f.identity_name]
   146	    if not identified_face_ids:
   147	        return ""
   148	
   149	    try:
exec
/bin/zsh -lc "nl -ba rhodesli_ml/gedcom_context.py | sed -n '240,360p'" in /Users/nolanfox/rhodesli succeeded in 44ms:
   240	
   241	    return "\n".join(lines)
   242	
   243	
   244	def _build_family_context(indi, parsed_gedcom, photo_date_estimate=None):
   245	    """Build context for immediate family members.
   246	
   247	    Enhanced to include residential addresses and occupation data for spouses
   248	    and parents, and children's birth places prominently for location inference.
   249	    """
   250	    lines = []
   251	
   252	    # Parents
   253	    parents = parsed_gedcom.get_parents(indi)
   254	    for parent in parents:
   255	        p_str = f"  Parent: {parent.full_name}"
   256	        if parent.birth and parent.birth_year:
   257	            p_str += f" (b.{parent.birth_year})"
   258	        if parent.birth_place:
   259	            p_str += f", born in {parent.birth_place}"
codex
**Findings**
- `P0` Prompt/consumer contract drift is the biggest issue. The active prompt emits top-level `visible_text` and nested `group_composition`, but batch reads `text_signage`, top-level `people_count`, `photo_type`, `setting`, and several fields the prompt no longer requests at all. Production `_call_gemini_date_estimate()` also collapses the response to `date_estimation` plus merged `location`, so any other top-level metadata is discarded before callers can use it. Refs: [gemini_extraction.py:64](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L64), [gemini_extraction.py:98](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L98), [batch_gemini_for_person.py:560](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L560), [estimate_routes.py:583](/Users/nolanfox/rhodesli/app/estimate_routes.py#L583).
- `P0` Admin reanalysis can erase existing scene metadata. `new_entry["scene_description"]` is populated from `result.get("scene_description", "")`, but the quick production path never returns that field, so reruns overwrite prior scene descriptions with `""`. Refs: [estimate_routes.py:597](/Users/nolanfox/rhodesli/app/estimate_routes.py#L597), [estimate_routes.py:1317](/Users/nolanfox/rhodesli/app/estimate_routes.py#L1317).
- `P0` Face coordinates are not being used reliably. The prompt says `face_index` is left-to-right, but batch sends raw `photo_entry["face_ids"]` order with no bbox sort, and coordinates are only injected into `face_analysis`, not `subject_ages`. Elsewhere in the codebase, left-to-right alignment is enforced by sorting on `bbox[0]`. Refs: [gemini_extraction.py:124](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L124), [gemini_extraction.py:190](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L190), [batch_gemini_for_person.py:309](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L309), [face_alignment.py:205](/Users/nolanfox/rhodesli/app/face_alignment.py#L205), [birth_year_estimation.py:126](/Users/nolanfox/rhodesli/rhodesli_ml/pipelines/birth_year_estimation.py#L126).
- `P1` The current prompt is only partially optimized for 1910-1970 dating. The Sephardic/Rhodes cultural-lag framing is good, but the active prompt dropped the older explicit “original capture date vs print/scan” guidance and `capture_vs_print` output, which matters a lot for historical prints and later reprints. Refs: [gemini_extraction.py:195](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L195), [gemini_extraction.py:118](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L118), [generate_date_labels.py:37](/Users/nolanfox/rhodesli/rhodesli_ml/scripts/generate_date_labels.py#L37), [generate_date_labels.py:102](/Users/nolanfox/rhodesli/rhodesli_ml/scripts/generate_date_labels.py#L102).
- `P1` GEDCOM context is helpful but not passed optimally. The wrappers always use `first_order` context with no year window, even though the context builder supports `curated` ±15-year filtering, and batch does not pass `visible_text`, so business-owner/signage context is skipped there. Refs: [run_combined_pipeline.py:161](/Users/nolanfox/rhodesli/scripts/run_combined_pipeline.py#L161), [gedcom_context.py:97](/Users/nolanfox/rhodesli/rhodesli_ml/gedcom_context.py#L97), [gedcom_context.py:155](/Users/nolanfox/rhodesli/rhodesli_ml/gedcom_context.py#L155), [batch_gemini_for_person.py:299](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L299), [estimate_routes.py:1168](/Users/nolanfox/rhodesli/app/estimate_routes.py#L1168).
- `P1` The production prompt path is too thin for archival reruns. `app/estimate_routes.py` always uses `preset="quick"` with `uses_face_coords=False`; that is reasonable for the public upload tool, but weak for admin reruns where known identities and face geometry exist. Refs: [estimate_routes.py:506](/Users/nolanfox/rhodesli/app/estimate_routes.py#L506), [estimate_routes.py:521](/Users/nolanfox/rhodesli/app/estimate_routes.py#L521), [estimate_routes.py:1278](/Users/nolanfox/rhodesli/app/estimate_routes.py#L1278).

**Answers**
- `1. Historical dating 1910-1970:` decent baseline, not optimized. Good cultural context; missing capture-vs-print handling, stronger era-specific calibration, and explicit prioritization of inscriptions/date stamps over style.
- `2. Family-identification metadata:` no, not fully. Useful fields are missing or dropped: `scene_description`, reliable `visible_text`, `people_count`, `photo_type`, `setting`, per-face position/clothing, and relationship hypotheses.
- `3. Face coordinates:` not effectively. Only batch uses them, they are unsorted, and they are not tied to `subject_ages`.
- `4. GEDCOM context:` useful but not optimal. It is richer than nothing, but it is noisier than necessary and batch misses the signage/business-owner path entirely.
- `5. Better date/age/relationship inference:` yes, there are clear wins.

**Suggested Changes**
- `P0` Align the prompt contract and consumers. Either restore the rich metadata fields in `build_extraction_prompt()` or stop expecting them downstream; for admin/batch paths, return the full parsed object, not just `date_estimation`.
- `P0` Sort face boxes left-to-right before prompt construction and require `face_index` on both face analysis and age outputs. Best version: replace bare `subject_ages: [45,12,8]` with per-face objects.
- `P0` Stop overwriting `scene_description` on rerun unless the prompt actually returned a new value.
- `P1` Restore `capture_vs_print`, `scene_description`, `visible_text` persistence, and ideally `visible_text_language`/`visible_text_script`.
- `P1` Add per-face `age_range`, `age_confidence`, `position`, `clothing`, `is_subject`, and `relationship_hypotheses`. Relationship inference should be based on ages, pose, grouping, and GEDCOM, not facial resemblance alone.
- `P1` Use a two-pass GEDCOM flow for admin/batch: baseline year estimate, then `curated` GEDCOM context around that year, then rerun.
- `P1` Pass `visible_text` into the batch GEDCOM builder so business-name clues can influence location/date inference there too.
- `P2` Add a 1910s-1970s cue ladder and ask for `ruled_out_decades` or strongest conflicting cues. That usually improves calibration more than adding more free-form prose.
- `P3` If search/admin UX still benefits, add back `keywords` and `controlled_tags`, but after fixing the contract and per-face outputs.

No tests run; this was a code review only.
tokens used
145,921
**Findings**
- `P0` Prompt/consumer contract drift is the biggest issue. The active prompt emits top-level `visible_text` and nested `group_composition`, but batch reads `text_signage`, top-level `people_count`, `photo_type`, `setting`, and several fields the prompt no longer requests at all. Production `_call_gemini_date_estimate()` also collapses the response to `date_estimation` plus merged `location`, so any other top-level metadata is discarded before callers can use it. Refs: [gemini_extraction.py:64](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L64), [gemini_extraction.py:98](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L98), [batch_gemini_for_person.py:560](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L560), [estimate_routes.py:583](/Users/nolanfox/rhodesli/app/estimate_routes.py#L583).
- `P0` Admin reanalysis can erase existing scene metadata. `new_entry["scene_description"]` is populated from `result.get("scene_description", "")`, but the quick production path never returns that field, so reruns overwrite prior scene descriptions with `""`. Refs: [estimate_routes.py:597](/Users/nolanfox/rhodesli/app/estimate_routes.py#L597), [estimate_routes.py:1317](/Users/nolanfox/rhodesli/app/estimate_routes.py#L1317).
- `P0` Face coordinates are not being used reliably. The prompt says `face_index` is left-to-right, but batch sends raw `photo_entry["face_ids"]` order with no bbox sort, and coordinates are only injected into `face_analysis`, not `subject_ages`. Elsewhere in the codebase, left-to-right alignment is enforced by sorting on `bbox[0]`. Refs: [gemini_extraction.py:124](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L124), [gemini_extraction.py:190](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L190), [batch_gemini_for_person.py:309](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L309), [face_alignment.py:205](/Users/nolanfox/rhodesli/app/face_alignment.py#L205), [birth_year_estimation.py:126](/Users/nolanfox/rhodesli/rhodesli_ml/pipelines/birth_year_estimation.py#L126).
- `P1` The current prompt is only partially optimized for 1910-1970 dating. The Sephardic/Rhodes cultural-lag framing is good, but the active prompt dropped the older explicit “original capture date vs print/scan” guidance and `capture_vs_print` output, which matters a lot for historical prints and later reprints. Refs: [gemini_extraction.py:195](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L195), [gemini_extraction.py:118](/Users/nolanfox/rhodesli/rhodesli_ml/gemini_extraction.py#L118), [generate_date_labels.py:37](/Users/nolanfox/rhodesli/rhodesli_ml/scripts/generate_date_labels.py#L37), [generate_date_labels.py:102](/Users/nolanfox/rhodesli/rhodesli_ml/scripts/generate_date_labels.py#L102).
- `P1` GEDCOM context is helpful but not passed optimally. The wrappers always use `first_order` context with no year window, even though the context builder supports `curated` ±15-year filtering, and batch does not pass `visible_text`, so business-owner/signage context is skipped there. Refs: [run_combined_pipeline.py:161](/Users/nolanfox/rhodesli/scripts/run_combined_pipeline.py#L161), [gedcom_context.py:97](/Users/nolanfox/rhodesli/rhodesli_ml/gedcom_context.py#L97), [gedcom_context.py:155](/Users/nolanfox/rhodesli/rhodesli_ml/gedcom_context.py#L155), [batch_gemini_for_person.py:299](/Users/nolanfox/rhodesli/scripts/batch_gemini_for_person.py#L299), [estimate_routes.py:1168](/Users/nolanfox/rhodesli/app/estimate_routes.py#L1168).
- `P1` The production prompt path is too thin for archival reruns. `app/estimate_routes.py` always uses `preset="quick"` with `uses_face_coords=False`; that is reasonable for the public upload tool, but weak for admin reruns where known identities and face geometry exist. Refs: [estimate_routes.py:506](/Users/nolanfox/rhodesli/app/estimate_routes.py#L506), [estimate_routes.py:521](/Users/nolanfox/rhodesli/app/estimate_routes.py#L521), [estimate_routes.py:1278](/Users/nolanfox/rhodesli/app/estimate_routes.py#L1278).

**Answers**
- `1. Historical dating 1910-1970:` decent baseline, not optimized. Good cultural context; missing capture-vs-print handling, stronger era-specific calibration, and explicit prioritization of inscriptions/date stamps over style.
- `2. Family-identification metadata:` no, not fully. Useful fields are missing or dropped: `scene_description`, reliable `visible_text`, `people_count`, `photo_type`, `setting`, per-face position/clothing, and relationship hypotheses.
- `3. Face coordinates:` not effectively. Only batch uses them, they are unsorted, and they are not tied to `subject_ages`.
- `4. GEDCOM context:` useful but not optimal. It is richer than nothing, but it is noisier than necessary and batch misses the signage/business-owner path entirely.
- `5. Better date/age/relationship inference:` yes, there are clear wins.

**Suggested Changes**
- `P0` Align the prompt contract and consumers. Either restore the rich metadata fields in `build_extraction_prompt()` or stop expecting them downstream; for admin/batch paths, return the full parsed object, not just `date_estimation`.
- `P0` Sort face boxes left-to-right before prompt construction and require `face_index` on both face analysis and age outputs. Best version: replace bare `subject_ages: [45,12,8]` with per-face objects.
- `P0` Stop overwriting `scene_description` on rerun unless the prompt actually returned a new value.
- `P1` Restore `capture_vs_print`, `scene_description`, `visible_text` persistence, and ideally `visible_text_language`/`visible_text_script`.
- `P1` Add per-face `age_range`, `age_confidence`, `position`, `clothing`, `is_subject`, and `relationship_hypotheses`. Relationship inference should be based on ages, pose, grouping, and GEDCOM, not facial resemblance alone.
- `P1` Use a two-pass GEDCOM flow for admin/batch: baseline year estimate, then `curated` GEDCOM context around that year, then rerun.
- `P1` Pass `visible_text` into the batch GEDCOM builder so business-name clues can influence location/date inference there too.
- `P2` Add a 1910s-1970s cue ladder and ask for `ruled_out_decades` or strongest conflicting cues. That usually improves calibration more than adding more free-form prose.
- `P3` If search/admin UX still benefits, add back `keywords` and `controlled_tags`, but after fixing the contract and per-face outputs.

No tests run; this was a code review only.
