"""Supabase data layer for user-entered data persistence.

Architecture (AD-135):
- Supabase = source of truth for user decisions
- JSON files = read cache (not modified directly by end-users)
- All user writes go through save_registry() → this module
- If Supabase is unavailable, app continues from JSON (degraded mode)

Tables:
- identity_overrides: complete identity records for user-modified identities
- annotations: community annotations (name suggestions, bios, etc.)
- relationships: person-to-person relationships
- gedcom_matches: GEDCOM individual → identity match decisions
"""

import json
import logging
import os

# Narrow exception types for Supabase operations.
# Schema bugs (KeyError, AttributeError) intentionally NOT caught.
try:
    import httpx
    from postgrest.exceptions import APIError as PostgRESTError

    _SUPABASE_ERRORS = (httpx.HTTPError, PostgRESTError, ConnectionError, TimeoutError, OSError)
except ImportError:
    _SUPABASE_ERRORS = (ConnectionError, TimeoutError, OSError)

logger = logging.getLogger(__name__)

# Module-level client cache
_supabase_client = None
_supabase_available = None  # None = not tested, True/False = tested


def get_supabase_client():
    """Get Supabase client using service role key. Returns None if not configured."""
    global _supabase_client, _supabase_available

    if _supabase_available is False:
        return None
    if _supabase_client is not None:
        return _supabase_client

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        _supabase_available = False
        logger.info("Supabase not configured (no SERVICE_ROLE_KEY) — JSON-only mode")
        return None

    try:
        from supabase import ClientOptions, create_client

        try:
            timeout_s = float(os.environ.get("SUPABASE_POSTGREST_TIMEOUT_SECONDS", "10"))
        except ValueError:
            timeout_s = 10.0

        _supabase_client = create_client(
            url,
            key,
            options=ClientOptions(postgrest_client_timeout=max(timeout_s, 1.0)),
        )
        _supabase_available = True
        logger.info("Supabase client initialized")
        return _supabase_client
    except Exception as e:
        _supabase_available = False
        logger.warning(f"Supabase client init failed: {e}")
        return None


def reset_client():
    """Reset client cache (for testing)."""
    global _supabase_client, _supabase_available
    _supabase_client = None
    _supabase_available = None


def _is_user_modified_identity(data):
    """Check if an identity has been modified by users.

    User-modified means state was changed from ML-default, or has
    user-entered metadata, or has been merged, or has face rejections.
    """
    state = data.get("state", "INBOX")
    if state in ("CONFIRMED", "CONTESTED", "SKIPPED"):
        return True
    if data.get("merged_into") is not None:
        return True
    if len(data.get("negative_ids", [])) > 0:
        return True
    metadata = data.get("metadata", {})
    user_fields = [
        "birth_year",
        "death_year",
        "birth_place",
        "death_place",
        "maiden_name",
        "generation_qualifier",
        "relationship_notes",
        "bio",
        "gedcom_xref",
        "ancestry_url",
    ]
    if any(metadata.get(f) for f in user_fields):
        return True
    return False


# =========================================================================
# IDENTITY SYNC
# =========================================================================


def sync_identity_overrides(identities_dict):
    """Upsert all user-modified identities to Supabase.

    Called after every save_registry(). Syncs the full state of each
    user-modified identity so Supabase stays current.

    Args:
        identities_dict: dict of {identity_id: identity_data} from the registry
    """
    sb = get_supabase_client()
    if not sb:
        return

    rows = []
    for identity_id, data in identities_dict.items():
        if _is_user_modified_identity(data):
            rows.append(
                {
                    "identity_id": identity_id,
                    "state": data.get("state", "INBOX"),
                    "name": data.get("name"),
                    "merged_into": data.get("merged_into"),
                    "data": data,
                    "updated_by": "admin",
                    "updated_at": data.get("updated_at"),
                }
            )

    if not rows:
        return

    try:
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            sb.table("identity_overrides").upsert(batch).execute()
        logger.debug(f"Synced {len(rows)} identity overrides to Supabase")
    except Exception as e:
        logger.warning(f"Supabase identity sync failed (degraded mode): {e}")


# =========================================================================
# ANNOTATION SYNC
# =========================================================================


def sync_annotations(annotations_dict):
    """Upsert all annotations to Supabase.

    Called after every _save_annotations(). Syncs the full annotations dict.

    Args:
        annotations_dict: dict of {annotation_id: annotation_data}
    """
    sb = get_supabase_client()
    if not sb:
        return

    rows = []
    for ann_id, ann in annotations_dict.items():
        rows.append(
            {
                "annotation_id": ann_id,
                "identity_id": ann.get("target_id") if ann.get("target_type") == "identity" else None,
                "photo_id": ann.get("target_id") if ann.get("target_type") == "photo" else None,
                "type": ann.get("type"),
                "status": ann.get("status", "pending"),
                "data": ann,
                "updated_at": ann.get("reviewed_at") or ann.get("submitted_at"),
            }
        )

    if not rows:
        return

    try:
        sb.table("annotations").upsert(rows).execute()
        logger.debug(f"Synced {len(rows)} annotations to Supabase")
    except Exception as e:
        logger.warning(f"Supabase annotation sync failed (degraded mode): {e}")


# =========================================================================
# RELATIONSHIP SYNC
# =========================================================================


def sync_relationships(relationships_list):
    """Sync relationships to Supabase.

    Uses delete-all + batched insert. Batching prevents request size limits
    for large relationship sets (1000+ rows).

    Args:
        relationships_list: list of relationship dicts from relationships.json
    """
    sb = get_supabase_client()
    if not sb:
        return

    try:
        # Delete all existing and re-insert (relationships don't have stable IDs)
        sb.table("relationships").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

        if not relationships_list:
            return

        rows = []
        for r in relationships_list:
            rows.append(
                {
                    "person_a": r.get("person_a"),
                    "person_b": r.get("person_b"),
                    "relationship_type": r.get("type"),
                    "source": r.get("source", "human"),
                    "data": r,
                    "updated_at": r.get("created_at"),
                }
            )

        # Batch insert to avoid request size limits
        batch_size = 200
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            sb.table("relationships").insert(batch).execute()
        logger.debug(f"Synced {len(rows)} relationships to Supabase")
    except Exception as e:
        logger.warning(f"Supabase relationship sync failed (degraded mode): {e}")


# =========================================================================
# GEDCOM SYNC
# =========================================================================


def sync_gedcom_matches(matches_list):
    """Sync GEDCOM matches to Supabase.

    Args:
        matches_list: list of match dicts from gedcom_matches.json
    """
    sb = get_supabase_client()
    if not sb:
        return

    rows = []
    for m in matches_list:
        rows.append(
            {
                "xref_id": m.get("gedcom_xref"),
                "identity_id": m.get("identity_id"),
                "decision": m.get("status", "pending"),
                "data": m,
                "updated_at": m.get("updated_at"),
            }
        )

    if not rows:
        return

    try:
        sb.table("gedcom_matches").upsert(rows).execute()
        logger.debug(f"Synced {len(rows)} GEDCOM matches to Supabase")
    except Exception as e:
        logger.warning(f"Supabase GEDCOM sync failed (degraded mode): {e}")


# =========================================================================
# STARTUP SYNC (Supabase → JSON)
# =========================================================================


def sync_from_supabase_on_startup(data_path):
    """Rebuild JSON cache from Supabase source of truth.

    Runs on every deploy/restart. Ensures JSON files reflect the latest
    Supabase state, even if a deploy bundled stale JSON files.

    This is what makes deploys data-safe: the bundled JSON gets merged
    with Supabase truth on startup.

    Args:
        data_path: Path to the data directory (e.g., /app/storage/data/)
    """
    sb = get_supabase_client()
    if not sb:
        logger.warning("Supabase unavailable on startup — using existing JSON cache")
        return False

    from pathlib import Path
    import portalocker

    data_path = Path(data_path)
    changes_made = False

    # --- Sync identity overrides ---
    try:
        result = sb.table("identity_overrides").select("identity_id, data").execute()
        overrides = {row["identity_id"]: row["data"] for row in result.data}

        if overrides:
            ids_path = data_path / "identities.json"
            if ids_path.exists():
                with open(ids_path) as f:
                    ids_data = json.load(f)

                identities = ids_data.get("identities", {})
                applied = 0
                for identity_id, override_data in overrides.items():
                    identities[identity_id] = override_data
                    applied += 1

                ids_data["identities"] = identities

                # Atomic write with lock
                tmp_path = ids_path.with_suffix(".tmp")
                with open(tmp_path, "w") as f:
                    portalocker.lock(f, portalocker.LOCK_EX)
                    json.dump(ids_data, f, indent=2)
                tmp_path.replace(ids_path)

                logger.info(f"Startup sync: applied {applied} identity overrides from Supabase")
                changes_made = True
    except Exception as e:
        logger.error(f"Startup sync failed for identities: {e}")

    # --- Sync annotations ---
    try:
        result = sb.table("annotations").select("annotation_id, data").execute()
        if result.data:
            ann_path = data_path / "annotations.json"
            ann_data = {"schema_version": 1, "annotations": {}}
            if ann_path.exists():
                with open(ann_path) as f:
                    ann_data = json.load(f)

            for row in result.data:
                ann_data.setdefault("annotations", {})[row["annotation_id"]] = row["data"]

            tmp_path = ann_path.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                json.dump(ann_data, f, indent=2)
            tmp_path.replace(ann_path)

            logger.info(f"Startup sync: applied {len(result.data)} annotations from Supabase")
            changes_made = True
    except Exception as e:
        logger.error(f"Startup sync failed for annotations: {e}")

    # --- Sync relationships ---
    try:
        # Paginate to handle >1000 relationships (Supabase default limit)
        all_rel_rows = []
        page_size = 1000
        offset = 0
        while True:
            result = sb.table("relationships").select("data").range(offset, offset + page_size - 1).execute()
            if not result.data:
                break
            all_rel_rows.extend(result.data)
            if len(result.data) < page_size:
                break
            offset += page_size

        if all_rel_rows:
            rel_path = data_path / "relationships.json"
            rel_data = {
                "relationships": [row["data"] for row in all_rel_rows],
                "metadata": {},
            }

            tmp_path = rel_path.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                json.dump(rel_data, f, indent=2)
            tmp_path.replace(rel_path)

            logger.info(f"Startup sync: applied {len(all_rel_rows)} relationships from Supabase")
            changes_made = True
    except Exception as e:
        logger.error(f"Startup sync failed for relationships: {e}")

    # --- Sync GEDCOM matches ---
    try:
        result = sb.table("gedcom_matches").select("data").execute()
        if result.data:
            gm_path = data_path / "gedcom_matches.json"
            gm_data = {"schema_version": 1, "matches": []}
            if gm_path.exists():
                with open(gm_path) as f:
                    gm_data = json.load(f)

            # Replace matches list with Supabase data
            gm_data["matches"] = [row["data"] for row in result.data]

            tmp_path = gm_path.with_suffix(".tmp")
            with open(tmp_path, "w") as f:
                portalocker.lock(f, portalocker.LOCK_EX)
                json.dump(gm_data, f, indent=2)
            tmp_path.replace(gm_path)

            logger.info(f"Startup sync: applied {len(result.data)} GEDCOM matches from Supabase")
            changes_made = True
    except Exception as e:
        logger.error(f"Startup sync failed for GEDCOM matches: {e}")

    if changes_made:
        logger.info("Startup sync from Supabase complete — JSON cache updated")
    else:
        logger.info("Startup sync: no changes from Supabase")

    return changes_made


# =========================================================================
# FACE ALIGNMENT SYNC (AD-152: JSON → Supabase migration)
# =========================================================================


def save_face_alignment_to_supabase(photo_id, alignment_data, model_used=None, cost=None, tokens=None):
    """Save face alignment result to Supabase.

    Primary store for face alignment data (AD-152).
    Returns True on success, False on failure (caller falls back to JSON).
    """
    sb = get_supabase_client()
    if not sb:
        return False

    row = {
        "photo_id": photo_id,
        "alignment_data": alignment_data,
        "model_used": model_used,
        "cost": cost,
        "tokens_used": tokens,
    }
    # Remove None values so defaults apply
    row = {k: v for k, v in row.items() if v is not None}

    try:
        sb.table("face_gemini_alignments").upsert(row, on_conflict="photo_id").execute()
        logger.debug(f"Saved face alignment for {photo_id} to Supabase")
        return True
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase face alignment save failed for {photo_id}: {e}")
        return False


def load_face_alignment_from_supabase(photo_id):
    """Load face alignment for a single photo from Supabase.

    Returns alignment_data dict or None.
    """
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        result = (
            sb.table("face_gemini_alignments")
            .select("alignment_data, model_used, cost, tokens_used")
            .eq("photo_id", photo_id)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return result.data[0].get("alignment_data")
        return None
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase face alignment load failed for {photo_id}: {e}")
        return None


def load_all_face_alignments_from_supabase():
    """Load all face alignment results from Supabase.

    Returns dict of {photo_id: alignment_data} or None on failure.
    """
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        result = sb.table("face_gemini_alignments").select("photo_id, alignment_data").execute()
        if result.data:
            return {row["photo_id"]: row["alignment_data"] for row in result.data if row.get("alignment_data")}
        return {}
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase face alignment bulk load failed: {e}")
        return None


def count_face_alignments_in_supabase():
    """Count face alignment records in Supabase. Returns int or None on failure."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        result = sb.table("face_gemini_alignments").select("photo_id", count="exact").execute()
        return result.count
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase face alignment count failed: {e}")
        return None


# =========================================================================
# GEMINI API CALL LOGGING (AD-152)
# =========================================================================


def log_gemini_call(photo_id, model_used, call_type, **kwargs):
    """Log a Gemini API call to Supabase for analysis.

    Args:
        photo_id: Photo being analyzed
        model_used: Gemini model string
        call_type: 'alignment', 'enrichment', 'combined', 'date_estimation'
        **kwargs: Optional fields: prompt_tokens, completion_tokens, total_tokens,
                  cost_usd, latency_ms, status, error_message, rate_limit_type,
                  response_summary, gemini_config, batch_id,
                  prompt_text, full_response, gedcom_context

    Returns True on success, False on failure.
    """
    sb = get_supabase_client()
    if not sb:
        return False

    row = {
        "photo_id": photo_id,
        "model_used": model_used,
        "call_type": call_type,
        "status": kwargs.get("status", "success"),
    }
    # Add optional fields
    for field in [
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cost_usd",
        "latency_ms",
        "error_message",
        "rate_limit_type",
        "response_summary",
        "gemini_config",
        "batch_id",
        "prompt_text",
        "full_response",
        "gedcom_context",
    ]:
        if field in kwargs and kwargs[field] is not None:
            row[field] = kwargs[field]

    try:
        sb.table("gemini_api_calls").insert(row).execute()
        logger.debug(f"Logged Gemini call: {photo_id} ({call_type}, {model_used})")
        return True
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase Gemini call log failed: {e}")
        return False


def get_gemini_call_summary(batch_id=None):
    """Get summary of Gemini API calls. Returns dict or None."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        query = sb.table("gemini_api_calls").select("*")
        if batch_id:
            query = query.eq("batch_id", batch_id)
        result = query.execute()

        if not result.data:
            return {"total_calls": 0, "total_cost": 0}

        total_cost = sum(float(r.get("cost_usd", 0) or 0) for r in result.data)
        by_status = {}
        for r in result.data:
            s = r.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1

        return {
            "total_calls": len(result.data),
            "total_cost_usd": round(total_cost, 4),
            "by_status": by_status,
        }
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase Gemini call summary failed: {e}")
        return None


# =========================================================================
# SHADOW WRITES — Core data mirroring to Supabase (Session 90b)
# =========================================================================
# These functions write core data (photos, identities) to Supabase
# alongside the existing JSON files. They are fire-and-forget: failures
# log a warning but never raise. This enables eventual migration from
# JSON to Supabase as the primary data store.


def shadow_write_photo(photo_data: dict) -> None:
    """Shadow-write photo metadata to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "photo_id": photo_data.get("photo_id", ""),
            "path": photo_data.get("path", ""),
            "source": photo_data.get("source", ""),
            "collection": photo_data.get("collection", ""),
            "source_url": photo_data.get("source_url", ""),
            "upload_date": photo_data.get("upload_date"),
            "width": photo_data.get("width"),
            "height": photo_data.get("height"),
            "face_count": len(photo_data.get("face_ids", [])),
            "uploaded_by": photo_data.get("uploaded_by"),
            "job_id": photo_data.get("job_id"),
        }
        client.table("photos").upsert(row).execute()
    except Exception as e:
        logger.warning(f"Shadow write photo failed: {e}")


def shadow_write_identity(identity_data: dict) -> None:
    """Shadow-write identity to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "identity_id": identity_data.get("identity_id", ""),
            "name": identity_data.get("name", ""),
            "display_name": identity_data.get("display_name"),
            "state": identity_data.get("state", "INBOX"),
            "anchor_ids": identity_data.get("anchor_ids", []),
            "candidate_ids": identity_data.get("candidate_ids", []),
            "negative_ids": identity_data.get("negative_ids", []),
            "version_id": identity_data.get("version_id", 1),
            "merged_into": identity_data.get("merged_into"),
        }
        client.table("identities").upsert(row).execute()
    except Exception as e:
        logger.warning(f"Shadow write identity failed: {e}")


def shadow_write_photos_batch(photos_list: list[dict]) -> int:
    """Shadow-write a batch of photos to Supabase. Returns count written."""
    client = get_supabase_client()
    if not client:
        return 0

    written = 0
    batch_size = 100
    for i in range(0, len(photos_list), batch_size):
        batch = photos_list[i : i + batch_size]
        rows = []
        for p in batch:
            rows.append(
                {
                    "photo_id": p.get("photo_id", ""),
                    "path": p.get("path", ""),
                    "source": p.get("source", ""),
                    "collection": p.get("collection", ""),
                    "source_url": p.get("source_url", ""),
                    "upload_date": p.get("upload_date"),
                    "width": p.get("width"),
                    "height": p.get("height"),
                    "face_count": len(p.get("face_ids", [])),
                    "uploaded_by": p.get("uploaded_by"),
                    "job_id": p.get("job_id"),
                }
            )
        try:
            client.table("photos").upsert(rows).execute()
            written += len(rows)
        except Exception as e:
            logger.warning(f"Shadow write photos batch failed: {e}")
    return written


def shadow_write_identities_batch(identities_list: list[dict]) -> int:
    """Shadow-write a batch of identities to Supabase. Returns count written."""
    client = get_supabase_client()
    if not client:
        return 0

    written = 0
    batch_size = 100
    for i in range(0, len(identities_list), batch_size):
        batch = identities_list[i : i + batch_size]
        rows = []
        for ident in batch:
            rows.append(
                {
                    "identity_id": ident.get("identity_id", ""),
                    "name": ident.get("name", ""),
                    "display_name": ident.get("display_name"),
                    "state": ident.get("state", "INBOX"),
                    "anchor_ids": ident.get("anchor_ids", []),
                    "candidate_ids": ident.get("candidate_ids", []),
                    "negative_ids": ident.get("negative_ids", []),
                    "version_id": ident.get("version_id", 1),
                    "merged_into": ident.get("merged_into"),
                }
            )
        try:
            client.table("identities").upsert(rows).execute()
            written += len(rows)
        except Exception as e:
            logger.warning(f"Shadow write identities batch failed: {e}")
    return written


# =========================================================================
# DATE LABELS SYNC (JSON → Supabase)
# =========================================================================


def sync_date_label(photo_id: str, label_data: dict) -> None:
    """Upsert a single date label to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "photo_id": photo_id,
            "data": label_data,
            "estimated_year": label_data.get("best_year_estimate"),
            "confidence": label_data.get("confidence"),
            "scene_description": label_data.get("scene_description"),
            "reanalyzed_at": label_data.get("reanalyzed_at"),
        }
        client.table("date_labels").upsert(row).execute()
        logger.debug(f"Synced date label for {photo_id}")
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase date label sync failed for {photo_id}: {e}")


def sync_date_labels_batch(labels_list: list) -> int:
    """Upsert a batch of date labels. Returns count written."""
    client = get_supabase_client()
    if not client:
        return 0

    written = 0
    batch_size = 100
    for i in range(0, len(labels_list), batch_size):
        batch = labels_list[i : i + batch_size]
        rows = []
        for label in batch:
            photo_id = label.get("photo_id")
            if not photo_id:
                continue
            rows.append(
                {
                    "photo_id": photo_id,
                    "data": label,
                    "estimated_year": label.get("best_year_estimate"),
                    "confidence": label.get("confidence"),
                    "scene_description": label.get("scene_description"),
                    "reanalyzed_at": label.get("reanalyzed_at"),
                }
            )
        try:
            client.table("date_labels").upsert(rows).execute()
            written += len(rows)
        except _SUPABASE_ERRORS as e:
            logger.warning(f"Supabase date labels batch sync failed: {e}")
    return written


def load_date_labels_from_supabase() -> dict | None:
    """Load all date labels from Supabase. Returns dict keyed by photo_id or None."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        all_rows = []
        page_size = 1000
        offset = 0
        while True:
            result = sb.table("date_labels").select("photo_id, data").range(offset, offset + page_size - 1).execute()
            if not result.data:
                break
            all_rows.extend(result.data)
            if len(result.data) < page_size:
                break
            offset += page_size

        return {row["photo_id"]: row["data"] for row in all_rows if row.get("data")}
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase date labels load failed: {e}")
        return None


# =========================================================================
# PHOTO LOCATIONS SYNC (JSON → Supabase)
# =========================================================================


def sync_photo_location(photo_id: str, location_data: dict) -> None:
    """Upsert a single photo location to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "photo_id": photo_id,
            "data": location_data,
            "place": location_data.get("location_name", ""),
            "confidence": location_data.get("confidence"),
            "latitude": location_data.get("lat"),
            "longitude": location_data.get("lng"),
        }
        client.table("photo_locations").upsert(row).execute()
        logger.debug(f"Synced photo location for {photo_id}")
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase photo location sync failed for {photo_id}: {e}")


def sync_photo_locations_batch(locations_dict: dict) -> int:
    """Upsert a batch of photo locations. Returns count written."""
    client = get_supabase_client()
    if not client:
        return 0

    written = 0
    rows = []
    for photo_id, loc in locations_dict.items():
        rows.append(
            {
                "photo_id": photo_id,
                "data": loc,
                "place": loc.get("location_name", ""),
                "confidence": loc.get("confidence"),
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
            }
        )

    batch_size = 100
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            client.table("photo_locations").upsert(batch).execute()
            written += len(batch)
        except _SUPABASE_ERRORS as e:
            logger.warning(f"Supabase photo locations batch sync failed: {e}")
    return written


def load_photo_locations_from_supabase() -> dict | None:
    """Load all photo locations from Supabase. Returns dict keyed by photo_id or None."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        all_rows = []
        page_size = 1000
        offset = 0
        while True:
            result = (
                sb.table("photo_locations").select("photo_id, data").range(offset, offset + page_size - 1).execute()
            )
            if not result.data:
                break
            all_rows.extend(result.data)
            if len(result.data) < page_size:
                break
            offset += page_size

        return {row["photo_id"]: row["data"] for row in all_rows if row.get("data")}
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase photo locations load failed: {e}")
        return None


# =========================================================================
# DISCOVERY LOG SYNC
# =========================================================================


def sync_discovery_log_entry(face_id: str, target_identity_id: str, decision: str, entry_data: dict = None) -> None:
    """Insert a discovery log entry to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "face_id": face_id,
            "target_identity_id": target_identity_id,
            "decision": decision,
            "decided_by": "admin",
            "data": entry_data or {},
        }
        client.table("discovery_log").insert(row).execute()
        logger.debug(f"Synced discovery log: {face_id} -> {target_identity_id} ({decision})")
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase discovery log sync failed: {e}")


# =========================================================================
# AUDIT LOG SYNC
# =========================================================================


def sync_audit_log_entry(action: str, target_id: str, actor: str = "admin", entry_data: dict = None) -> None:
    """Insert an audit log entry to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "action": action,
            "target_id": target_id,
            "target_type": "annotation",
            "actor": actor,
            "data": entry_data or {},
        }
        client.table("audit_log").insert(row).execute()
        logger.debug(f"Synced audit log: {action} on {target_id}")
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase audit log sync failed: {e}")


def load_audit_log_from_supabase(limit: int = 100) -> list | None:
    """Load recent audit log entries from Supabase. Returns list or None."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        result = sb.table("audit_log").select("*").order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase audit log load failed: {e}")
        return None


# =========================================================================
# PENDING UPLOADS SYNC
# =========================================================================


def sync_pending_upload(job_id: str, upload_data: dict) -> None:
    """Upsert a pending upload to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "job_id": job_id,
            "user_id": upload_data.get("user_id") or upload_data.get("uploaded_by"),
            "status": upload_data.get("status", "pending"),
            "filename": upload_data.get("filename") or upload_data.get("original_filename"),
            "data": upload_data,
        }
        client.table("pending_uploads").upsert(row).execute()
        logger.debug(f"Synced pending upload {job_id}")
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase pending upload sync failed for {job_id}: {e}")


# =========================================================================
# COMPARISON RESULTS SYNC
# =========================================================================


def sync_comparison_result(result_id: str, result_data: dict) -> None:
    """Upsert a comparison result to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "result_id": result_id,
            "data": result_data,
        }
        client.table("comparison_results").upsert(row).execute()
        logger.debug(f"Synced comparison result {result_id}")
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase comparison result sync failed for {result_id}: {e}")


# =========================================================================
# BIRTH YEAR ESTIMATES SYNC
# =========================================================================


def sync_birth_year_estimate(identity_id: str, estimate_data: dict) -> None:
    """Upsert a birth year estimate to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "identity_id": identity_id,
            "estimated_year": estimate_data.get("birth_year_estimate"),
            "confidence": estimate_data.get("birth_year_confidence"),
            "data": estimate_data,
        }
        client.table("birth_year_estimates").upsert(row).execute()
        logger.debug(f"Synced birth year estimate for {identity_id}")
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase birth year estimate sync failed for {identity_id}: {e}")


# =========================================================================
# CORRECTIONS LOG SYNC
# =========================================================================


def sync_corrections_log_entry(correction_data: dict) -> None:
    """Insert a corrections log entry to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "photo_id": correction_data.get("photo_id"),
            "identity_id": correction_data.get("identity_id"),
            "correction_type": correction_data.get("type") or correction_data.get("correction_type", "date"),
            "data": correction_data,
        }
        client.table("corrections_log").insert(row).execute()
        logger.debug("Synced corrections log entry")
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase corrections log sync failed: {e}")


# =========================================================================
# PERSON COMMENTS SYNC
# =========================================================================


def sync_person_comment(identity_id: str, comment: str, author: str = "admin") -> None:
    """Insert a person comment to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "identity_id": identity_id,
            "comment": comment,
            "author": author,
        }
        client.table("person_comments").insert(row).execute()
        logger.debug(f"Synced person comment for {identity_id}")
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase person comment sync failed: {e}")


def load_annotations_from_supabase() -> dict | None:
    """Load all annotations from Supabase.

    Returns dict with schema_version and annotations dict keyed by annotation_id,
    matching the JSON file format. Returns None on failure.
    """
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        all_rows = []
        page_size = 1000
        offset = 0
        while True:
            result = (
                sb.table("annotations").select("annotation_id, data").range(offset, offset + page_size - 1).execute()
            )
            if not result.data:
                break
            all_rows.extend(result.data)
            if len(result.data) < page_size:
                break
            offset += page_size

        annotations = {}
        for row in all_rows:
            if row.get("data"):
                annotations[row["annotation_id"]] = row["data"]

        logger.info(f"Loaded {len(annotations)} annotations from Supabase")
        return {"schema_version": 1, "annotations": annotations}
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase annotations load failed: {e}")
        return None


def load_birth_year_estimates_from_supabase() -> dict | None:
    """Load all birth year estimates from Supabase.

    Returns dict keyed by identity_id, matching the in-memory format
    used by _load_birth_year_estimates(). Returns None on failure.
    """
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        all_rows = []
        page_size = 1000
        offset = 0
        while True:
            result = (
                sb.table("birth_year_estimates")
                .select("identity_id, data")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not result.data:
                break
            all_rows.extend(result.data)
            if len(result.data) < page_size:
                break
            offset += page_size

        estimates = {}
        for row in all_rows:
            iid = row.get("identity_id")
            data = row.get("data")
            if iid and data:
                estimates[iid] = data

        logger.info(f"Loaded {len(estimates)} birth year estimates from Supabase")
        return estimates
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase birth year estimates load failed: {e}")
        return None


def load_person_comments_from_supabase(identity_id: str = None) -> list | None:
    """Load person comments from Supabase. Returns list or None."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        query = sb.table("person_comments").select("*").order("created_at", desc=True)
        if identity_id:
            query = query.eq("identity_id", identity_id)
        result = query.limit(500).execute()
        return result.data or []
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase person comments load failed: {e}")
        return None
