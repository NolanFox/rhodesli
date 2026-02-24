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
        variant="curated",
    )
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

        # Load face links
        links_resp = sb.table("gedcom_face_links").select("*").execute()
        face_links = {}
        if links_resp and links_resp.data:
            for row in links_resp.data:
                face_links[row["identity_id"]] = row["gedcom_id"]

        if not face_links:
            return None

        # Load ALL individuals (Supabase default limit is 1000, we have 21,809)
        all_individuals = []
        page_size = 1000
        offset = 0
        while True:
            indis_resp = sb.table("gedcom_individuals").select("*").range(offset, offset + page_size - 1).execute()
            if not indis_resp or not indis_resp.data:
                break
            all_individuals.extend(indis_resp.data)
            if len(indis_resp.data) < page_size:
                break
            offset += page_size

        if not all_individuals:
            return None

        # Build a minimal parsed gedcom from Supabase data
        # This is a lightweight wrapper — full GEDCOM file not needed
        logger.info(f"Loaded {len(face_links)} GEDCOM face links, {len(all_individuals)} individuals")
        return {
            "face_links": face_links,
            "parsed_gedcom": _build_parsed_gedcom_from_supabase(all_individuals),
        }
    except _SUPABASE_ERRORS as e:
        logger.warning(f"GEDCOM data unavailable (network/API): {e}")
        return None


def _build_parsed_gedcom_from_supabase(individuals_data):
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
    from app.supabase_data import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return None

    # 1. Build individuals dict from individuals_data
    individuals = {}
    for row in individuals_data:
        xref = row["gedcom_id"]
        birth_event = None
        if row.get("birth_date") or row.get("birth_place"):
            birth_event = GedcomEvent(
                event_type="birth",
                date=parse_gedcom_date(row.get("birth_date", "")),
                place=row.get("birth_place"),
                raw_date=row.get("birth_date", ""),
            )
        death_event = None
        if row.get("death_date") or row.get("death_place"):
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
            events=[],
            family_as_spouse=[],
            family_as_child=[],
        )

    # 2. Load events and attach to individuals (paginated)
    try:
        all_events = []
        offset = 0
        while True:
            events_resp = sb.table("gedcom_events").select("*").range(offset, offset + 999).execute()
            if not events_resp or not events_resp.data:
                break
            all_events.extend(events_resp.data)
            if len(events_resp.data) < 1000:
                break
            offset += 1000
        for ev_row in all_events:
                indi_xref = ev_row.get("gedcom_individual_id")
                if indi_xref not in individuals:
                    continue
                # Skip birth/death — already handled above
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
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Failed to load GEDCOM events (network/API): {e}")

    # 3. Load relationships and reconstruct families (paginated)
    families = {}
    try:
        all_rels = []
        offset = 0
        while True:
            rels_resp = sb.table("gedcom_relationships").select("*").range(offset, offset + 999).execute()
            if not rels_resp or not rels_resp.data:
                break
            all_rels.extend(rels_resp.data)
            if len(rels_resp.data) < 1000:
                break
            offset += 1000
        for rel in all_rels:
                indi_xref = rel["individual_gedcom_id"]
                related_xref = rel["related_gedcom_id"]
                rel_type = rel["relationship_type"]
                fam_xref = rel.get("family_gedcom_id", "")

                if not fam_xref:
                    continue

                # Ensure family exists
                if fam_xref not in families:
                    families[fam_xref] = GedcomFamily(xref_id=fam_xref)

                fam = families[fam_xref]

                if rel_type == "spouse":
                    # indi_xref is a spouse in this family
                    if indi_xref in individuals:
                        indi = individuals[indi_xref]
                        if fam_xref not in indi.family_as_spouse:
                            indi.family_as_spouse.append(fam_xref)
                        # Assign husband/wife based on gender
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
                    # indi_xref is child, related_xref is parent
                    if indi_xref in individuals:
                        indi = individuals[indi_xref]
                        if fam_xref not in indi.family_as_child:
                            indi.family_as_child.append(fam_xref)
                        if indi_xref not in fam.children_xrefs:
                            fam.children_xrefs.append(indi_xref)

                elif rel_type == "parent":
                    # indi_xref is parent, related_xref is child
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

    except _SUPABASE_ERRORS as e:
        logger.warning(f"Failed to load GEDCOM relationships (network/API): {e}")

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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Check API key
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

    logger.info(f"Processing {len(photo_list)} photos with {args.model}")

    # Generate batch ID
    batch_id = f"batch_combined_{time.strftime('%Y%m%d_%H%M%S')}"
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
        result = await process_photo(pid, pdata, identities, embeddings, args.model,
                                     batch_id=batch_id, gedcom_data=gedcom_data)
        results.append(result)

        if result["status"] == "success":
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

        # Rate limit
        if i < len(photo_list) - 1:
            await asyncio.sleep(args.delay)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"BATCH COMPLETE — {batch_id}")
    logger.info(f"{'='*60}")
    logger.info(f"Success: {success}/{len(photo_list)}")
    logger.info(f"Errors: {errors}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"GEDCOM-enriched: {gedcom_enriched}")
    logger.info(f"Total cost: ${total_cost:.4f}")

    # Save results
    output_dir = PROJECT_ROOT / "results"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / f"{batch_id}.json"
    with open(output, "w") as f:
        json.dump({
            "batch_id": batch_id,
            "model": args.model,
            "total_photos": len(photo_list),
            "success": success,
            "errors": errors,
            "skipped": skipped,
            "gedcom_enriched": gedcom_enriched,
            "total_cost": round(total_cost, 4),
            "results": results,
        }, f, indent=2)
    logger.info(f"Results saved to {output}")


if __name__ == '__main__':
    asyncio.run(main())
