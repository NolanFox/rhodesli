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
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

# Supabase/network exception types for narrowed exception handling.
# Schema bugs (KeyError, AttributeError) intentionally NOT caught.
try:
    import httpx
    from postgrest.exceptions import APIError as PostgRESTError
    _SUPABASE_ERRORS = (httpx.HTTPError, PostgRESTError, ConnectionError, TimeoutError, OSError)
except ImportError:
    _SUPABASE_ERRORS = (ConnectionError, TimeoutError, OSError)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.face_alignment import (
    FaceDetection,
    run_face_alignment,
    save_alignment,
)
from rhodesli_ml.gemini_config import GEMINI_MODEL, get_model_pricing
from rhodesli_ml.importers.gedcom_matching import resolve_redirect_chain

logger = logging.getLogger(__name__)


def load_photo_bytes(photo_path: str) -> bytes | None:
    """Load photo from local filesystem or R2."""
    local_path = PROJECT_ROOT / "raw_photos" / Path(photo_path).name
    if local_path.exists():
        return local_path.read_bytes()

    r2_url = os.getenv("R2_PUBLIC_URL", "")
    if r2_url:
        filename = Path(photo_path).name
        url = f"{r2_url}/raw_photos/{urllib.parse.quote(filename)}"
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning(f"R2 load failed for {filename}: {e}")

    return None


def build_faces_for_photo(photo_data: dict, identities: dict, embeddings) -> list[FaceDetection]:
    """Build FaceDetection objects from photo + embeddings data."""
    face_ids = photo_data.get("face_ids", [])
    path = photo_data.get("path", "")
    filename = Path(path).name

    # Build confirmed face map
    confirmed_faces = {}
    for iid, identity in identities.get("identities", {}).items():
        if identity.get("state") == "CONFIRMED":
            name = identity.get("name", "Unknown")
            for fid in identity.get("anchor_ids", []):
                confirmed_faces[fid] = name

    # Match face_ids to embeddings by filename
    face_embs = [e for e in embeddings if e.get("filename", "") == filename]

    faces = []
    for i, face_id in enumerate(face_ids):
        bbox = None
        det_score = 0.0
        quality = 0.0

        # Try explicit face_id match first
        for emb in embeddings:
            if emb.get("face_id") == face_id:
                bbox_raw = emb.get("bbox", [0, 0, 0, 0])
                bbox = [int(b) for b in bbox_raw]
                det_score = float(emb.get("det_score", 0))
                quality = float(emb.get("quality", 0))
                break

        # Fallback: match by filename index
        if bbox is None and i < len(face_embs):
            emb = face_embs[i]
            bbox_raw = emb.get("bbox", [0, 0, 0, 0])
            bbox = [int(b) for b in bbox_raw]
            det_score = float(emb.get("det_score", 0))
            quality = float(emb.get("quality", 0))

        if bbox is None:
            continue

        identity_name = confirmed_faces.get(face_id)
        faces.append(FaceDetection(
            face_id=face_id,
            bbox=bbox,
            face_index=i,
            det_score=det_score,
            quality=quality,
            identity_name=identity_name,
        ))

    return faces


def build_gedcom_context(photo_id: str, faces: list[FaceDetection],
                         identities: dict, gedcom_data: dict | None) -> str:
    """Build GEDCOM context string for a photo's identified faces.

    Returns empty string if no GEDCOM data or no identified faces.
    """
    if not gedcom_data:
        return ""

    parsed_gedcom = gedcom_data.get("parsed_gedcom")
    face_links = gedcom_data.get("face_links", {})
    if not parsed_gedcom or not face_links:
        return ""

    # Get face_ids that have confirmed identities
    identified_face_ids = [f.face_id for f in faces if f.identity_name]
    if not identified_face_ids:
        return ""

    try:
        from rhodesli_ml.gedcom_context import build_photo_context
    except ImportError as e:
        logger.warning(f"GEDCOM context module not available: {e}")
        return ""

    # build_photo_context expects the inner identities dict, not the
    # full JSON envelope with schema_version/history keys
    inner_identities = identities
    if "identities" in identities and "schema_version" in identities:
        inner_identities = identities["identities"]

    context = build_photo_context(
        photo_id=photo_id,
        identified_faces=identified_face_ids,
        parsed_gedcom=parsed_gedcom,
        gedcom_face_links=face_links,
        identities=inner_identities,
        variant="first_order",
    )

    if context:
        from rhodesli_ml.gedcom_context import estimate_context_tokens
        token_count = estimate_context_tokens(context)
        enrichment_level = "full" if token_count >= 400 else "partial" if token_count >= 100 else "thin"
        logger.info(f"Photo {photo_id}: GEDCOM context {token_count} tokens ({enrichment_level})")

    return context


def load_gedcom_data() -> dict | None:
    """Load GEDCOM data for context injection.

    Tries Supabase first, falls back to local files.
    Returns dict with 'parsed_gedcom' and 'face_links', or None.
    """
    try:
        from app.supabase_data import get_supabase_client
        sb = get_supabase_client()
        if not sb:
            return None

        def _load_all_rows(preferred_table: str, fallback_table: str | None = None) -> list[dict]:
            rows = []
            table_name = preferred_table
            page_size = 1000
            offset = 0
            while True:
                try:
                    resp = sb.table(table_name).select("*").range(offset, offset + page_size - 1).execute()
                except Exception:
                    if not fallback_table or table_name == fallback_table:
                        raise
                    table_name = fallback_table
                    rows = []
                    offset = 0
                    continue
                if not resp or not resp.data:
                    break
                rows.extend(resp.data)
                if len(resp.data) < page_size:
                    break
                offset += page_size
            return rows

        def _load_redirect_map() -> dict[str, str]:
            try:
                rows = _load_all_rows("gedcom_entity_redirects")
            except Exception as exc:
                msg = str(exc)
                if "gedcom_entity_redirects" in msg or "PGRST205" in msg or "relation" in msg:
                    return {}
                raise

            redirect_map = {}
            for row in rows:
                if (row.get("entity_type") or "individual") != "individual":
                    continue
                old_key = row.get("old_key")
                new_key = row.get("new_key")
                if old_key and new_key:
                    redirect_map[old_key] = new_key
            return redirect_map

        # Load face links
        links_resp = sb.table("gedcom_face_links").select("*").execute()
        redirect_map = _load_redirect_map()
        face_links = {}
        if links_resp and links_resp.data:
            for row in links_resp.data:
                face_links[row["identity_id"]] = resolve_redirect_chain(row["gedcom_id"], redirect_map)

        if not face_links:
            return None

        all_individuals = _load_all_rows("current_gedcom_individuals", "gedcom_individuals")

        if not all_individuals:
            return None

        all_families = []
        all_relationships = []
        all_events = []
        try:
            all_families = _load_all_rows("current_gedcom_families")
        except Exception:
            all_families = []

        has_rich_events = any(row.get("events_json") for row in all_individuals)
        if not has_rich_events:
            try:
                all_events = _load_all_rows("current_gedcom_events", "gedcom_events")
            except Exception:
                all_events = []

        if not all_families:
            try:
                all_relationships = _load_all_rows("current_gedcom_relationships", "gedcom_relationships")
            except Exception:
                all_relationships = []

        # Build a minimal parsed gedcom from Supabase data
        # This is a lightweight wrapper — full GEDCOM file not needed
        logger.info(
            "Loaded %s GEDCOM face links, %s individuals, %s families, %s relationships",
            len(face_links),
            len(all_individuals),
            len(all_families),
            len(all_relationships),
        )
        return {
            "face_links": face_links,
            "parsed_gedcom": _build_parsed_gedcom_from_supabase(
                all_individuals,
                families_data=all_families,
                relationships_data=all_relationships,
                events_data=all_events,
            ),
        }
    except _SUPABASE_ERRORS as e:
        logger.warning(f"GEDCOM data unavailable (network/API): {e}")
        return None


def _build_parsed_gedcom_from_supabase(individuals_data, families_data=None, relationships_data=None, events_data=None):
    """Build a ParsedGedcom object from Supabase table data.

    Reconstructs the full object graph (individuals + families + relationships)
    from flat Supabase rows so that build_photo_context() can call methods like
    get_parents(), get_spouses(), get_children(), get_siblings(), get_marriages().

    Args:
        individuals_data: List of dicts from gedcom_individuals table.

    Returns:
        ParsedGedcom object, or None on failure.
    """
    if not individuals_data:
        return None

    from rhodesli_ml.importers.gedcom_parser import (
        GedcomEvent,
        GedcomFamily,
        GedcomIndividual,
        ParsedGedcom,
        parse_gedcom_date,
    )
    from rhodesli_ml.importers.gedcom_snapshot import (
        inflate_citation,
        inflate_event,
        inflate_media_ref,
        inflate_name,
    )

    # 1. Build individuals dict from individuals_data
    individuals = {}
    for row in individuals_data:
        xref = row["gedcom_id"]
        birth_event = inflate_event(row.get("birth_event_json"))
        if birth_event is None and (row.get("birth_date") or row.get("birth_place")):
            birth_event = GedcomEvent(
                event_type="birth",
                date=parse_gedcom_date(row.get("birth_date", "")),
                place=row.get("birth_place"),
                raw_date=row.get("birth_date", ""),
            )
        death_event = inflate_event(row.get("death_event_json"))
        if death_event is None and (row.get("death_date") or row.get("death_place")):
            death_event = GedcomEvent(
                event_type="death",
                date=parse_gedcom_date(row.get("death_date", "")),
                place=row.get("death_place"),
                raw_date=row.get("death_date", ""),
            )
        individuals[xref] = GedcomIndividual(
            xref_id=xref,
            given_name=row.get("given_name", ""),
            surname=row.get("surname", ""),
            full_name=row.get("name", ""),
            gender=row.get("gender", "U"),
            birth=birth_event,
            death=death_event,
            events=[inflate_event(event) for event in row.get("events_json") or [] if inflate_event(event)],
            family_as_spouse=list(row.get("family_as_spouse_json") or []),
            family_as_child=list(row.get("family_as_child_json") or []),
            names=[inflate_name(name) for name in row.get("names_json") or []],
            notes=list(row.get("notes_json") or []),
            citations=[inflate_citation(citation) for citation in row.get("citations_json") or []],
            media_refs=[inflate_media_ref(media_ref) for media_ref in row.get("media_refs_json") or []],
            custom_tags=row.get("custom_tags_json") or {},
        )

    # 2. Legacy event fallback when rows do not yet carry events_json.
    if events_data:
        for ev_row in events_data:
            indi_xref = ev_row.get("gedcom_individual_id")
            if indi_xref not in individuals:
                continue
            etype = ev_row.get("event_type", "")
            if etype in ("birth", "death"):
                continue
            event = GedcomEvent(
                event_type=etype,
                date=parse_gedcom_date(ev_row.get("raw_date", "") or ev_row.get("date", "")),
                place=ev_row.get("place"),
                raw_date=ev_row.get("raw_date", "") or ev_row.get("date", ""),
            )
            individuals[indi_xref].events.append(event)

    # 3. Reconstruct families either from rich family rows or legacy relationships.
    families = {}
    if families_data:
        for row in families_data:
            fam_xref = row.get("family_gedcom_id")
            if not fam_xref:
                continue
            fam = GedcomFamily(
                xref_id=fam_xref,
                husband_xref=row.get("husband_xref"),
                wife_xref=row.get("wife_xref"),
                children_xrefs=list(row.get("children_xrefs_json") or []),
                marriage=inflate_event(row.get("marriage_event_json")),
                events=[inflate_event(event) for event in row.get("events_json") or [] if inflate_event(event)],
                notes=list(row.get("notes_json") or []),
                citations=[inflate_citation(citation) for citation in row.get("citations_json") or []],
                media_refs=[inflate_media_ref(media_ref) for media_ref in row.get("media_refs_json") or []],
                custom_tags=row.get("custom_tags_json") or {},
            )
            families[fam_xref] = fam

            for spouse_xref in [fam.husband_xref, fam.wife_xref]:
                if spouse_xref in individuals and fam_xref not in individuals[spouse_xref].family_as_spouse:
                    individuals[spouse_xref].family_as_spouse.append(fam_xref)
            for child_xref in fam.children_xrefs:
                if child_xref in individuals and fam_xref not in individuals[child_xref].family_as_child:
                    individuals[child_xref].family_as_child.append(fam_xref)
    elif relationships_data:
        for rel in relationships_data:
            indi_xref = rel["individual_gedcom_id"]
            related_xref = rel["related_gedcom_id"]
            rel_type = rel["relationship_type"]
            fam_xref = rel.get("family_gedcom_id", "")

            if not fam_xref:
                continue

            if fam_xref not in families:
                families[fam_xref] = GedcomFamily(xref_id=fam_xref)

            fam = families[fam_xref]

            if rel_type == "spouse":
                if indi_xref in individuals:
                    indi = individuals[indi_xref]
                    if fam_xref not in indi.family_as_spouse:
                        indi.family_as_spouse.append(fam_xref)
                    gender = indi.gender
                    if gender == "M" and not fam.husband_xref:
                        fam.husband_xref = indi_xref
                    elif gender == "F" and not fam.wife_xref:
                        fam.wife_xref = indi_xref
                    elif not fam.husband_xref:
                        fam.husband_xref = indi_xref
                    elif not fam.wife_xref:
                        fam.wife_xref = indi_xref

            elif rel_type == "child":
                if indi_xref in individuals:
                    indi = individuals[indi_xref]
                    if fam_xref not in indi.family_as_child:
                        indi.family_as_child.append(fam_xref)
                    if indi_xref not in fam.children_xrefs:
                        fam.children_xrefs.append(indi_xref)

            elif rel_type == "parent":
                if indi_xref in individuals:
                    indi = individuals[indi_xref]
                    if fam_xref not in indi.family_as_spouse:
                        indi.family_as_spouse.append(fam_xref)
                    gender = indi.gender
                    if gender == "M" and not fam.husband_xref:
                        fam.husband_xref = indi_xref
                    elif gender == "F" and not fam.wife_xref:
                        fam.wife_xref = indi_xref
                    elif not fam.husband_xref:
                        fam.husband_xref = indi_xref
                    elif not fam.wife_xref:
                        fam.wife_xref = indi_xref
                if related_xref in individuals:
                    child = individuals[related_xref]
                    if fam_xref not in child.family_as_child:
                        child.family_as_child.append(fam_xref)
                    if related_xref not in fam.children_xrefs:
                        fam.children_xrefs.append(related_xref)

    logger.info(f"Built ParsedGedcom from Supabase: {len(individuals)} individuals, {len(families)} families")
    return ParsedGedcom(
        individuals=individuals,
        families=families,
        source_file="supabase",
    )


async def process_photo(photo_id: str, photo_data: dict, identities: dict,
                        embeddings, model: str, batch_id: str,
                        gedcom_data: dict | None = None) -> dict:
    """Process a single photo through the combined pipeline."""
    # Build faces
    faces = build_faces_for_photo(photo_data, identities, embeddings)
    if not faces:
        return {"photo_id": photo_id, "status": "skipped", "reason": "no faces with bboxes"}

    # Load image bytes
    image_bytes = load_photo_bytes(photo_data.get("path", ""))
    if not image_bytes:
        return {"photo_id": photo_id, "status": "skipped", "reason": "could not load image"}

    # Build GEDCOM context (if available)
    additional_context = build_gedcom_context(photo_id, faces, identities, gedcom_data)
    has_gedcom = bool(additional_context)

    # Calculate enrichment metrics for logging
    gedcom_token_count = 0
    enrichment_level = "none"
    if has_gedcom:
        from rhodesli_ml.gedcom_context import estimate_context_tokens
        gedcom_token_count = estimate_context_tokens(additional_context)
        enrichment_level = "full" if gedcom_token_count >= 400 else "partial" if gedcom_token_count >= 100 else "thin"

    # Run alignment with GEDCOM context
    start = time.time()
    try:
        result = await run_face_alignment(
            photo_id=photo_id,
            image_bytes=image_bytes,
            faces=faces,
            model=model,
            additional_context=additional_context,
            call_type="combined" if has_gedcom else "alignment",
            batch_id=batch_id,
            gedcom_token_count=gedcom_token_count,
            enrichment_level=enrichment_level,
        )
    except Exception as e:
        # Keep broad here: Gemini API can throw many error types.
        # The narrowing is in the data-loading functions above.
        return {"photo_id": photo_id, "status": "error", "reason": str(e)}

    elapsed = time.time() - start

    if result.error:
        return {"photo_id": photo_id, "status": "error", "reason": result.error}

    # Save result (Supabase-first, JSON fallback)
    save_alignment(result, output_dir=PROJECT_ROOT / "data")

    # Estimate cost from centralized pricing
    pricing = get_model_pricing(model)
    cost = (result.input_tokens * pricing["input"] / 1_000_000) + (result.output_tokens * pricing["output"] / 1_000_000)

    return {
        "photo_id": photo_id,
        "status": "success",
        "faces_detected": result.faces_detected,
        "faces_described": result.faces_described,
        "elapsed": round(elapsed, 1),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost": round(cost, 4),
        "has_gedcom": has_gedcom,
    }


def dry_run_photo(photo_id: str, photo_data: dict, identities: dict,
                   embeddings, gedcom_data: dict | None = None) -> dict:
    """Build prompt for a photo without calling Gemini API.

    Returns prompt text, token counts, and enrichment metadata.
    """
    from app.face_alignment import build_alignment_prompt

    faces = build_faces_for_photo(photo_data, identities, embeddings)
    if not faces:
        return {"photo_id": photo_id, "status": "skipped", "reason": "no faces with bboxes"}

    additional_context = build_gedcom_context(photo_id, faces, identities, gedcom_data)
    has_gedcom = bool(additional_context)

    gedcom_token_count = 0
    enrichment_level = "none"
    if has_gedcom:
        from rhodesli_ml.gedcom_context import estimate_context_tokens
        gedcom_token_count = estimate_context_tokens(additional_context)
        enrichment_level = "full" if gedcom_token_count >= 400 else "partial" if gedcom_token_count >= 100 else "thin"

    prompt = build_alignment_prompt(faces, additional_context)
    prompt_token_count = len(prompt) // 4  # rough estimate

    # Get identity names for faces
    face_names = []
    for f in faces:
        if f.identity_name:
            face_names.append(f"{f.face_id} -> {f.identity_name}")

    return {
        "photo_id": photo_id,
        "status": "dry_run",
        "faces_count": len(faces),
        "has_gedcom": has_gedcom,
        "gedcom_token_count": gedcom_token_count,
        "enrichment_level": enrichment_level,
        "prompt_token_count": prompt_token_count,
        "prompt_text": prompt,
        "gedcom_context": additional_context,
        "identified_faces": face_names,
        "photo_path": photo_data.get("path", ""),
    }


def get_failed_photo_ids(results_file: Path) -> list[str]:
    """Extract photo IDs that failed from a previous batch result."""
    if not results_file.exists():
        return []
    with open(results_file) as f:
        data = json.load(f)
    return [r["photo_id"] for r in data.get("results", []) if r["status"] == "error"]


async def main():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    parser = argparse.ArgumentParser(description="Combined Gemini photo processing pipeline")
    parser.add_argument('--limit', type=int, default=5, help='Max photos to process (default: 5 validation)')
    parser.add_argument('--execute', action='store_true', help='Process all eligible photos')
    parser.add_argument('--model', default=GEMINI_MODEL)
    parser.add_argument('--delay', type=float, default=2.0, help='Delay between API calls (seconds)')
    parser.add_argument('--skip-aligned', action='store_true', help='Skip already aligned photos')
    parser.add_argument('--retry-failed', type=str, help='Path to previous results JSON to retry failures')
    parser.add_argument('--photo-ids', nargs='+', help='Specific photo IDs to process')
    parser.add_argument('--gedcom', action='store_true', default=True, help='Include GEDCOM context (default: on)')
    parser.add_argument('--no-gedcom', action='store_true', help='Disable GEDCOM context')
    parser.add_argument('--dry-run', action='store_true', help='Build prompts and log token counts without calling Gemini API')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Check API key (not needed for dry-run)
    if not args.dry_run:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            logger.error("GEMINI_API_KEY not set")
            sys.exit(1)

    # Load data
    with open(PROJECT_ROOT / "data" / "photo_index.json") as f:
        photo_index = json.load(f)
    with open(PROJECT_ROOT / "data" / "identities.json") as f:
        identities = json.load(f)

    embeddings = np.load(str(PROJECT_ROOT / "data" / "embeddings.npy"), allow_pickle=True)

    photos = photo_index.get("photos", {})
    logger.info(f"Total photos: {len(photos)}")

    # Filter to photos with faces
    eligible = {pid: p for pid, p in photos.items() if p.get("face_ids")}
    logger.info(f"Photos with faces: {len(eligible)}")

    # Apply photo ID filter
    if args.photo_ids:
        eligible = {pid: p for pid, p in eligible.items() if pid in args.photo_ids}
        logger.info(f"Filtered to specific IDs: {len(eligible)}")
    elif args.retry_failed:
        failed_ids = get_failed_photo_ids(Path(args.retry_failed))
        eligible = {pid: p for pid, p in eligible.items() if pid in failed_ids}
        logger.info(f"Retrying {len(eligible)} failed photos from {args.retry_failed}")

    # Skip already aligned if requested
    if args.skip_aligned:
        from app.face_alignment import load_alignments_from_file
        existing = load_alignments_from_file(PROJECT_ROOT / "data")
        before = len(eligible)
        eligible = {pid: p for pid, p in eligible.items() if pid not in existing}
        logger.info(f"After skipping aligned: {len(eligible)} (skipped {before - len(eligible)})")

    # Apply limit
    limit = len(eligible) if args.execute or args.retry_failed or args.photo_ids else args.limit
    photo_list = list(eligible.items())[:limit]

    # Load GEDCOM data
    gedcom_data = None
    if not args.no_gedcom:
        gedcom_data = load_gedcom_data()
        if gedcom_data:
            logger.info(f"GEDCOM context enabled ({len(gedcom_data.get('face_links', {}))} linked identities)")
        else:
            logger.info("GEDCOM context: not available (alignment-only mode)")

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    logger.info(f"Processing {len(photo_list)} photos with {args.model} ({mode})")

    # Generate batch ID
    prefix = "batch_dryrun" if args.dry_run else "batch_combined"
    batch_id = f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Batch ID: {batch_id}")

    # Process
    results = []
    total_cost = 0.0
    success = 0
    errors = 0
    skipped = 0
    gedcom_enriched = 0

    for i, (pid, pdata) in enumerate(photo_list):
        logger.info(f"[{i+1}/{len(photo_list)}] {pid} ({len(pdata.get('face_ids', []))} faces)")

        if args.dry_run:
            result = dry_run_photo(pid, pdata, identities, embeddings,
                                   gedcom_data=gedcom_data)
        else:
            result = await process_photo(pid, pdata, identities, embeddings, args.model,
                                         batch_id=batch_id, gedcom_data=gedcom_data)

        results.append(result)

        if result["status"] == "dry_run":
            success += 1
            gedcom_flag = " +GEDCOM" if result.get("has_gedcom") else ""
            if result.get("has_gedcom"):
                gedcom_enriched += 1
            logger.info(f"  PROMPT: {result['prompt_token_count']} tokens, "
                        f"GEDCOM: {result['gedcom_token_count']} tokens "
                        f"({result['enrichment_level']}){gedcom_flag}")
            if result.get("identified_faces"):
                for fn in result["identified_faces"]:
                    logger.info(f"    {fn}")
        elif result["status"] == "success":
            success += 1
            total_cost += result.get("cost", 0)
            gedcom_flag = " +GEDCOM" if result.get("has_gedcom") else ""
            if result.get("has_gedcom"):
                gedcom_enriched += 1
            logger.info(f"  OK {result['faces_described']}/{result['faces_detected']} faces, "
                        f"${result['cost']:.4f}, {result['elapsed']}s{gedcom_flag}")
        elif result["status"] == "skipped":
            skipped += 1
            logger.info(f"  -- Skipped: {result['reason']}")
        else:
            errors += 1
            logger.error(f"  !! Error: {result['reason']}")

        # Rate limit (only for live calls)
        if not args.dry_run and i < len(photo_list) - 1:
            await asyncio.sleep(args.delay)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH COMPLETE ({mode}) — {batch_id}")
    logger.info(f"{'='*60}")
    logger.info(f"Success: {success}/{len(photo_list)}")
    logger.info(f"Errors: {errors}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"GEDCOM-enriched: {gedcom_enriched}")
    if not args.dry_run:
        logger.info(f"Total cost: ${total_cost:.4f}")

    # Save results (strip prompt_text for non-dry-run to keep file size down)
    output_dir = PROJECT_ROOT / "results"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / f"{batch_id}.json"

    save_results = results
    if args.dry_run:
        # For dry-run, save prompts to separate file and keep summary in main
        prompts_output = output_dir / f"{batch_id}_prompts.json"
        prompts_data = {}
        for r in results:
            if r.get("prompt_text"):
                prompts_data[r["photo_id"]] = {
                    "prompt_text": r["prompt_text"],
                    "gedcom_context": r.get("gedcom_context", ""),
                }
        with open(prompts_output, "w") as f:
            json.dump(prompts_data, f, indent=2)
        logger.info(f"Prompts saved to {prompts_output}")

        # Strip large text from summary results
        save_results = []
        for r in results:
            summary = {k: v for k, v in r.items() if k not in ("prompt_text", "gedcom_context")}
            save_results.append(summary)

    with open(output, "w") as f:
        json.dump({
            "batch_id": batch_id,
            "model": args.model,
            "mode": mode.lower(),
            "total_photos": len(photo_list),
            "success": success,
            "errors": errors,
            "skipped": skipped,
            "gedcom_enriched": gedcom_enriched,
            "total_cost": round(total_cost, 4) if not args.dry_run else 0,
            "results": save_results,
        }, f, indent=2)
    logger.info(f"Results saved to {output}")


if __name__ == '__main__':
    asyncio.run(main())
