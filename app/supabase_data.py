"""Supabase data layer for user-entered data persistence.

Architecture (AD-135):
- Supabase = source of truth for user decisions
- JSON files = read cache (not modified directly by end-users)
- All user writes go through save_registry() → this module
- If Supabase is unavailable, app continues from JSON (degraded mode)

Tables:
- identities: sole source of truth for all identity data (Session 130)
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
    global _supabase_client, _supabase_available, _GEMINI_API_CALLS_COLUMNS
    _supabase_client = None
    _supabase_available = None
    # Discovered schema is per-project; clear it so a swapped client re-discovers
    # (avoids cross-test/cross-client column-set poisoning — Codex P2-4).
    _GEMINI_API_CALLS_COLUMNS = None


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
    """DEPRECATED: identity_overrides removed in Session 130.

    This function is a no-op. The identities table in Supabase is the sole
    source of truth. Kept as a stub so tests that mock it don't break.
    """
    pass


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

    # --- identity_overrides REMOVED (Session 130) ---
    # identity_overrides was a stale data layer that silently overwrote correct
    # identity data with snapshots from days ago. Caused 36 faces to disappear
    # (9th occurrence of split-brain pattern, Lesson 153). The identities table
    # in Supabase is now the sole source of truth — no override/shadow layer.

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


_GEMINI_API_CALLS_COLUMNS: set | None = None


def _gemini_api_calls_columns(sb) -> set | None:
    """Discover (and cache) the live column set of gemini_api_calls.

    Used to filter out columns the code knows about but the live table does
    not (schema drift, Lesson 105/152). Returns None if discovery fails, in
    which case the caller inserts the full row (best-effort, original behavior).
    """
    global _GEMINI_API_CALLS_COLUMNS
    if _GEMINI_API_CALLS_COLUMNS is not None:
        return _GEMINI_API_CALLS_COLUMNS
    try:
        probe = sb.table("gemini_api_calls").select("*").limit(1).execute()
        if probe.data:
            _GEMINI_API_CALLS_COLUMNS = set(probe.data[0].keys())
            return _GEMINI_API_CALLS_COLUMNS
    except Exception as e:  # noqa: BLE001 - discovery is best-effort
        logger.debug(f"gemini_api_calls column discovery failed: {e}")
    return None


def log_gemini_call(photo_id, model_used, call_type, **kwargs):
    """Log a Gemini API call to Supabase for analysis.

    Args:
        photo_id: Photo being analyzed
        model_used: Gemini model string
        call_type: 'alignment', 'enrichment', 'combined', 'date_estimation'
        **kwargs: Optional fields: prompt_tokens, completion_tokens, total_tokens,
                  cost_usd, latency_ms, status, error_message, rate_limit_type,
                  response_summary, gemini_config, batch_id,
                  prompt_text, full_response, gedcom_context,
                  prompt_manifest_id, prompt_family, prompt_version,
                  prompt_variant, prompt_contract_version, prompt_hash,
                  full_response_hash, experiment_id, shadow_run_id,
                  request_surface, request_mode, related_state_event_id,
                  contract_valid

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
        "prompt_manifest_id",
        "prompt_family",
        "prompt_version",
        "prompt_variant",
        "prompt_contract_version",
        "prompt_hash",
        "full_response_hash",
        "experiment_id",
        "shadow_run_id",
        "request_surface",
        "request_mode",
        "related_state_event_id",
        "contract_valid",
    ]:
        if field in kwargs and kwargs[field] is not None:
            row[field] = kwargs[field]

    # Schema-drift guard (Lesson 105/152): the code may pass prompt-lineage
    # columns (contract_valid, prompt_manifest_id, request_surface, ...) that
    # don't exist in the live gemini_api_calls table. PostgREST rejects the
    # ENTIRE insert on an unknown column (PGRST204), so a single drifted column
    # silently drops the whole API-call log. Filter the row to columns that
    # actually exist in the live table before inserting. Lineage data that has
    # no dedicated column is preserved inside the gemini_config JSONB.
    valid_cols = _gemini_api_calls_columns(sb)
    if valid_cols:
        dropped = [k for k in row if k not in valid_cols]
        if dropped:
            import copy as _copy

            # Deep-copy so we never mutate the caller's gemini_config (or a
            # nested _lineage dict it may own) — Codex P3-6.
            cfg = _copy.deepcopy(row.get("gemini_config") or {})
            lineage = cfg.setdefault("_lineage", {})
            for k in dropped:
                lineage[k] = row[k]
            row["gemini_config"] = cfg
            row = {k: v for k, v in row.items() if k in valid_cols}
            logger.debug(f"gemini_api_calls: dropped non-existent columns {dropped} (preserved in gemini_config._lineage)")

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


def shadow_write_photo(photo_data: dict, strict: bool = False) -> None:
    """Shadow-write photo metadata to Supabase.

    Args:
        photo_data: Photo metadata dict with photo_id, path, etc.
        strict: If True, re-raise exceptions instead of swallowing them.
                Use strict=True when DATA_SOURCE=postgres (Session 105).
    """
    try:
        client = get_supabase_client()
        if not client:
            if strict:
                raise ConnectionError("Supabase client not available for strict shadow write")
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
        logger.error(f"Shadow write photo failed: {e}")
        try:
            import sentry_sdk

            sentry_sdk.add_breadcrumb(category="shadow_write", message=f"photo write failed: {e}", level="error")
        except ImportError:
            pass
        if strict:
            raise


def _ensure_list_for_supabase(val):
    """Ensure value is a proper list for Supabase JSONB columns.

    Prevents writing JSON-encoded strings like '["face_id"]' instead of
    proper arrays ["face_id"]. Root cause of face tagging bug (Session 104b).
    """
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return []


def shadow_write_identity(identity_data: dict, strict: bool = False) -> None:
    """Shadow-write identity to Supabase.

    Args:
        identity_data: Identity dict with identity_id, name, state, etc.
        strict: If True, re-raise exceptions instead of swallowing them.
                Use strict=True when DATA_SOURCE=postgres (Session 105).
    """
    try:
        client = get_supabase_client()
        if not client:
            if strict:
                raise ConnectionError("Supabase client not available for strict shadow write")
            return
        # Embed top-level notes inside metadata (Session 156)
        metadata_in = identity_data.get("metadata") or {}
        if not isinstance(metadata_in, dict):
            metadata_in = {}
        top_level_notes = identity_data.get("notes")
        if isinstance(top_level_notes, list):
            metadata_in = {**metadata_in, "notes": top_level_notes}

        row = {
            "identity_id": identity_data.get("identity_id", ""),
            "name": identity_data.get("name", ""),
            "display_name": identity_data.get("display_name"),
            "state": identity_data.get("state", "INBOX"),
            "anchor_ids": _ensure_list_for_supabase(identity_data.get("anchor_ids", [])),
            "candidate_ids": _ensure_list_for_supabase(identity_data.get("candidate_ids", [])),
            "negative_ids": _ensure_list_for_supabase(identity_data.get("negative_ids", [])),
            "metadata": metadata_in,
            "version_id": identity_data.get("version_id", 1),
            "merged_into": identity_data.get("merged_into"),
            "created_at": identity_data.get("created_at"),
            "updated_at": identity_data.get("updated_at"),
        }
        client.table("identities").upsert(row).execute()
    except Exception as e:
        logger.error(f"Shadow write identity failed: {e}")
        try:
            import sentry_sdk

            sentry_sdk.add_breadcrumb(category="shadow_write", message=f"identity write failed: {e}", level="error")
        except ImportError:
            pass
        if strict:
            raise


def shadow_write_photos_batch(photos_list: list[dict], strict: bool = False) -> int:
    """Shadow-write a batch of photos to Supabase. Returns count written.

    Args:
        photos_list: List of photo dicts with photo_id, path, etc.
        strict: If True, re-raise exceptions instead of swallowing them.
    """
    client = get_supabase_client()
    if not client:
        if strict:
            raise ConnectionError("Supabase client not available for strict shadow write")
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
            logger.error(f"Shadow write photos batch failed: {e}")
            if strict:
                raise
    return written


def shadow_write_photo_faces_batch(photos_with_faces: list[dict], strict: bool = False) -> int:
    """Write photo_faces rows to Supabase. Session 105b.

    Closes the critical gap where load_from_postgres() reads photo_faces
    but no write path ever populated it after the initial migration.

    Args:
        photos_with_faces: List of dicts with photo_id and face_ids keys.
            Each dict should have at minimum: {"photo_id": str, "face_ids": list[str]}
        strict: If True, re-raise exceptions.
    Returns:
        Count of face rows written.
    """
    client = get_supabase_client()
    if not client:
        if strict:
            raise ConnectionError("Supabase client not available for photo_faces write")
        return 0

    written = 0
    batch_size = 200
    rows = []
    for photo in photos_with_faces:
        photo_id = photo.get("photo_id", "")
        face_ids = photo.get("face_ids", [])
        if not photo_id or not face_ids:
            continue
        for fid in face_ids:
            rows.append({"face_id": fid, "photo_id": photo_id})

    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            client.table("photo_faces").upsert(batch).execute()
            written += len(batch)
        except Exception as e:
            logger.error(f"Shadow write photo_faces batch failed: {e}")
            if strict:
                raise
    return written


def shadow_write_identities_batch(identities_list: list[dict], strict: bool = False) -> int:
    """Shadow-write a batch of identities to Supabase. Returns count written.

    DATA-020: Never overwrite a meaningful Postgres name with an auto-generated
    local name (e.g. "Unidentified Person NNN"). When the local name is
    auto-generated but Postgres has a real name, the name field is skipped.
    """
    client = get_supabase_client()
    if not client:
        if strict:
            raise ConnectionError("Supabase client not available for strict shadow write")
        return 0

    # DATA-020 + Session 132 race condition fix: Pre-fetch existing Postgres
    # names AND version_ids. Version check prevents stale writes from
    # overwriting merge results (optimistic concurrency control).
    all_ids = [ident.get("identity_id", "") for ident in identities_list if ident.get("identity_id")]
    postgres_names = {}
    postgres_versions = {}
    if all_ids:
        try:
            # Fetch in batches of 200 to stay within URL limits
            for batch_start in range(0, len(all_ids), 200):
                id_batch = all_ids[batch_start : batch_start + 200]
                result = (
                    client.table("identities")
                    .select("identity_id,name,version_id")
                    .in_("identity_id", id_batch)
                    .execute()
                )
                if result.data:
                    for row in result.data:
                        postgres_names[row["identity_id"]] = row.get("name", "")
                        postgres_versions[row["identity_id"]] = row.get("version_id", 0)
        except Exception as e:
            logger.warning(f"DATA-020 name prefetch failed (proceeding without protection): {e}")

    written = 0
    skipped_stale = 0
    name_protected = 0
    batch_size = 100
    for i in range(0, len(identities_list), batch_size):
        batch = identities_list[i : i + batch_size]
        rows = []
        for ident in batch:
            identity_id = ident.get("identity_id", "")
            incoming_version = ident.get("version_id", 1)

            # Session 132: Optimistic concurrency — skip rows where Supabase
            # already has a higher version_id (merge won the race).
            pg_version = postgres_versions.get(identity_id, 0)
            if pg_version > incoming_version:
                skipped_stale += 1
                logger.warning(
                    "stale_write_skipped",
                    extra={
                        "identity_id": identity_id,
                        "incoming_version": incoming_version,
                        "postgres_version": pg_version,
                    },
                )
                continue

            local_name = ident.get("name") or f"Unidentified Person {identity_id[:8]}"

            # DATA-020: Never overwrite a real Postgres name with an auto-generated local name
            pg_name = postgres_names.get(identity_id, "")
            skip_name = False
            if local_name.startswith("Unidentified Person") and pg_name and not pg_name.startswith("Unidentified"):
                skip_name = True
                name_protected += 1
                logger.warning(
                    "name_protection_fired",
                    extra={
                        "identity_id": identity_id,
                        "local_name": local_name,
                        "postgres_name": pg_name,
                    },
                )

            # Embed top-level notes inside metadata so they persist via
            # the metadata JSONB column (Session 156).
            metadata_in = ident.get("metadata") or {}
            if not isinstance(metadata_in, dict):
                metadata_in = {}
            top_level_notes = ident.get("notes")
            if isinstance(top_level_notes, list):
                metadata_in = {**metadata_in, "notes": top_level_notes}

            row = {
                "identity_id": identity_id,
                "display_name": ident.get("display_name"),
                "state": ident.get("state", "INBOX"),
                "anchor_ids": _ensure_list_for_supabase(ident.get("anchor_ids", [])),
                "candidate_ids": _ensure_list_for_supabase(ident.get("candidate_ids", [])),
                "negative_ids": _ensure_list_for_supabase(ident.get("negative_ids", [])),
                "metadata": metadata_in,
                "version_id": incoming_version,
                "merged_into": ident.get("merged_into"),
                "created_at": ident.get("created_at"),
                "updated_at": ident.get("updated_at"),
            }
            # Session 141: Include primary_face_id when set (column may not exist yet)
            if ident.get("primary_face_id"):
                row["primary_face_id"] = ident["primary_face_id"]
            if not skip_name:
                row["name"] = local_name

            rows.append(row)
        if not rows:
            continue
        try:
            client.table("identities").upsert(rows).execute()
            written += len(rows)
        except Exception as e:
            logger.error(f"Shadow write identities batch failed: {e}")
            if strict:
                raise

    if name_protected:
        logger.info(f"DATA-020: Protected {name_protected} Postgres names from auto-generated overwrite")
    if skipped_stale:
        logger.info(f"Session 132: Skipped {skipped_stale} stale writes (Supabase had higher version_id)")
    return written


# =========================================================================
# DATE LABELS SYNC (JSON → Supabase)
# =========================================================================


def sync_date_label(photo_id: str, label_data: dict) -> None:
    """Upsert a single date label to Supabase. Fire-and-forget.

    Table columns: id, photo_id, estimated_decade, best_year_estimate, confidence,
    year_range_start, year_range_end, scene_description, tags, evidence, model,
    prompt_version, reanalyzed_at, location_evidence, visible_text,
    gemini_raw_location, full_data, created_at, updated_at, data
    """
    try:
        client = get_supabase_client()
        if not client:
            return
        prob_range = label_data.get("probable_range", [])
        row = {
            "photo_id": photo_id,
            "data": label_data,
            "estimated_decade": label_data.get("estimated_decade"),
            "best_year_estimate": label_data.get("best_year_estimate"),
            "confidence": label_data.get("confidence"),
            "year_range_start": prob_range[0] if len(prob_range) >= 2 else None,
            "year_range_end": prob_range[1] if len(prob_range) >= 2 else None,
            "scene_description": label_data.get("scene_description"),
            "model": label_data.get("model"),
            "prompt_version": label_data.get("prompt_version"),
            "reanalyzed_at": label_data.get("reanalyzed_at"),
            "location_evidence": label_data.get("location_estimate"),
            "gemini_raw_location": label_data.get("gemini_raw_location"),
        }
        client.table("date_labels").upsert(row, on_conflict="photo_id").execute()
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
            prob_range = label.get("probable_range", [])
            rows.append(
                {
                    "photo_id": photo_id,
                    "data": label,
                    "estimated_decade": label.get("estimated_decade"),
                    "best_year_estimate": label.get("best_year_estimate"),
                    "confidence": label.get("confidence"),
                    "year_range_start": prob_range[0] if len(prob_range) >= 2 else None,
                    "year_range_end": prob_range[1] if len(prob_range) >= 2 else None,
                    "scene_description": label.get("scene_description"),
                    "model": label.get("model"),
                    "prompt_version": label.get("prompt_version"),
                    "reanalyzed_at": label.get("reanalyzed_at"),
                    "location_evidence": label.get("location_estimate"),
                    "gemini_raw_location": label.get("gemini_raw_location"),
                }
            )
        try:
            client.table("date_labels").upsert(rows, on_conflict="photo_id").execute()
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
            "location_name": location_data.get("location_name", ""),
            "location_estimate": location_data.get("location_estimate", ""),
            "confidence": location_data.get("confidence"),
            "lat": location_data.get("lat"),
            "lng": location_data.get("lng"),
            "region": location_data.get("region", ""),
            "biographical_evidence": location_data.get("biographical_evidence"),
            "gemini_raw_location": location_data.get("gemini_raw_location"),
        }
        client.table("photo_locations").upsert(row, on_conflict="photo_id").execute()
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
                "location_name": loc.get("location_name", ""),
                "location_estimate": loc.get("location_estimate", ""),
                "confidence": loc.get("confidence"),
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
                "region": loc.get("region", ""),
                "biographical_evidence": loc.get("biographical_evidence"),
                "gemini_raw_location": loc.get("gemini_raw_location"),
            }
        )

    batch_size = 100
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        try:
            client.table("photo_locations").upsert(batch, on_conflict="photo_id").execute()
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


def sync_audit_log_entry(
    action: str,
    target_id: str,
    actor: str = "admin",
    entry_data: dict = None,
    target_type: str = "annotation",
) -> None:
    """Insert an audit log entry to Supabase. Fire-and-forget."""
    try:
        client = get_supabase_client()
        if not client:
            return
        row = {
            "action": action,
            "target_id": target_id,
            "target_type": target_type,
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


def sync_identity_history_event(event: dict) -> None:
    """Insert an identity registry event into Supabase audit_log."""
    if not isinstance(event, dict):
        return

    identity_id = event.get("identity_id")
    if not identity_id:
        return

    sync_audit_log_entry(
        action=event.get("action", "unknown"),
        target_id=identity_id,
        actor=event.get("user_source", "system"),
        entry_data=event,
        target_type="identity_event",
    )


def _is_missing_column_error(exc: Exception, column_name: str) -> bool:
    """Return True when PostgREST reports a missing column for a legacy schema."""
    if getattr(exc, "code", None) == "42703":
        return True
    return f"column {column_name} does not exist" in str(exc)


def _looks_like_identity_history_event(event: dict) -> bool:
    """Heuristic fallback for legacy audit_log schemas without target_type."""
    if not isinstance(event, dict):
        return False
    required_keys = {"event_id", "identity_id", "action", "timestamp", "previous_version_id"}
    return required_keys.issubset(event.keys())


def load_identity_history_from_supabase() -> list[dict] | None:
    """Load append-only identity registry events from Supabase audit_log."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        all_rows = []
        page_size = 1000
        offset = 0
        use_shape_filter = False
        while True:
            try:
                query = (
                    sb.table("audit_log")
                    .select("*")
                    .eq("target_type", "identity_event")
                    .range(offset, offset + page_size - 1)
                )
                result = query.execute()
            except _SUPABASE_ERRORS as e:
                if not _is_missing_column_error(e, "audit_log.target_type"):
                    raise
                logger.info(
                    "Supabase audit_log.target_type missing; falling back to shape-filtered identity history sync"
                )
                use_shape_filter = True
                all_rows = []
                offset = 0
                break

            batch = result.data or []
            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size

        if use_shape_filter:
            while True:
                result = sb.table("audit_log").select("*").range(offset, offset + page_size - 1).execute()
                batch = result.data or []
                if not batch:
                    break
                all_rows.extend(batch)
                if len(batch) < page_size:
                    break
                offset += page_size

        events = []
        seen_event_ids = set()
        for row in all_rows:
            event = row.get("data") or {}
            if not isinstance(event, dict):
                continue
            if use_shape_filter and not _looks_like_identity_history_event(event):
                continue
            event_id = event.get("event_id")
            if not event_id or event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            events.append(event)

        events.sort(key=lambda e: e.get("timestamp", ""))
        return events
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase identity history load failed: {e}")
        return None


def load_identity_overrides_from_supabase() -> dict[str, dict] | None:
    """DEPRECATED: identity_overrides removed in Session 130.

    Returns None (no overrides). Kept as a stub so tests that mock it don't break.
    """
    return None


# =========================================================================
# PENDING UPLOADS SYNC
# =========================================================================


def sync_pending_upload(job_id: str, upload_data: dict) -> None:
    """Upsert a pending upload to Supabase. Fire-and-forget.

    Resilient to schema mismatches: if the 'data' jsonb column doesn't exist,
    retries without it (Lesson 105 — mock tests don't catch column mismatches).
    """
    try:
        client = get_supabase_client()
        if not client:
            return

        # Derive uploader email from multiple possible keys
        uploader = (
            upload_data.get("uploader_email")
            or upload_data.get("user_id")
            or upload_data.get("uploaded_by")
            or upload_data.get("submitted_by")
        )
        # Derive filename from multiple possible keys
        filename = (
            upload_data.get("filename")
            or upload_data.get("original_filename")
            or (upload_data.get("files", [None])[0] if upload_data.get("files") else None)
        )

        row = {
            "job_id": job_id,
            "user_id": uploader,
            "status": upload_data.get("status", "pending"),
            "filename": filename,
            "data": upload_data,
            # Rejection metadata — included when status=="rejected"
            "reviewed_at": upload_data.get("reviewed_at"),
            "reviewed_by": upload_data.get("reviewed_by"),
            "rejection_reason": upload_data.get("rejection_reason"),
        }
        # Drop None values to avoid schema errors on columns that may not exist
        row = {k: v for k, v in row.items() if v is not None}
        try:
            client.table("pending_uploads").upsert(row).execute()
        except _SUPABASE_ERRORS as e:
            # Retry without optional columns that may not exist in the schema
            err_lower = str(e).lower()
            if "column" in err_lower:
                optional_cols = {"data", "reviewed_at", "reviewed_by", "rejection_reason"}
                # Remove optional cols one by one until it succeeds
                pruned = {k: v for k, v in row.items() if k not in optional_cols}
                if "data" in err_lower:
                    logger.info(f"Retrying pending upload sync without optional columns for {job_id}")
                client.table("pending_uploads").upsert(pruned).execute()
            else:
                raise
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


# =========================================================================
# COMMUNITY SYNC (PRD-035)
# =========================================================================

# In-memory cache for community lookups (avoids hitting Supabase on every request)
_community_cache: dict = {}  # slug -> community dict
_community_cache_ts: float = 0.0
_COMMUNITY_CACHE_TTL: float = 300.0  # 5 minutes


def _invalidate_community_cache():
    """Clear community cache (after create/update)."""
    global _community_cache, _community_cache_ts
    _community_cache = {}
    _community_cache_ts = 0.0


def _default_rhodes_community() -> dict:
    """Return a hardcoded Rhodes community dict for when Supabase is unavailable."""
    return {
        "id": "00000000-0000-0000-0000-000000000001",
        "slug": "rhodes",
        "name": "Jewish Community of Rhodes",
        "landing_title": "Jewish Community of Rhodes",
        "landing_subtitle": "Heritage photo archive for the Sephardic Jewish community of Rhodes",
        "is_default": True,
    }


def load_communities() -> list | None:
    """Load all communities from Supabase. Returns list of dicts or None."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        result = sb.table("communities").select("*").order("created_at").execute()
        return result.data or []
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase communities load failed: {e}")
        return None


def get_community_by_slug(slug: str) -> dict | None:
    """Fetch a community by slug, with caching. Returns dict or None."""
    import time

    global _community_cache, _community_cache_ts

    now = time.time()
    if now - _community_cache_ts < _COMMUNITY_CACHE_TTL and slug in _community_cache:
        return _community_cache[slug]

    sb = get_supabase_client()
    if not sb:
        if slug == "rhodes":
            community = _default_rhodes_community()
            _community_cache[slug] = community
            _community_cache_ts = now
            return community
        _community_cache[slug] = None
        _community_cache_ts = now
        return None

    try:
        result = sb.table("communities").select("*").eq("slug", slug).limit(1).execute()
        if result.data:
            community = result.data[0]
            _community_cache[slug] = community
            _community_cache_ts = now
            return community
        _community_cache[slug] = None
        _community_cache_ts = now
        return None
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase community lookup failed for '{slug}': {e}")
        if slug == "rhodes":
            community = _default_rhodes_community()
            _community_cache[slug] = community
            _community_cache_ts = now
            return community
        return None


def load_photos_for_community(community_id: str) -> list | None:
    """Load photo IDs belonging to a community via photo_communities table."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        all_rows = []
        page_size = 1000
        offset = 0
        while True:
            result = (
                sb.table("photo_communities")
                .select("photo_id")
                .eq("community_id", community_id)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not result.data:
                break
            all_rows.extend(result.data)
            if len(result.data) < page_size:
                break
            offset += page_size

        photo_ids = [r["photo_id"] for r in all_rows]
        logger.info(f"Loaded {len(photo_ids)} photo IDs for community {community_id}")
        return photo_ids
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase photo_communities load failed: {e}")
        return None


def load_identities_for_community(community_id: str) -> list | None:
    """Load identity IDs belonging to a community via identity_communities table."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        all_rows = []
        page_size = 1000
        offset = 0
        while True:
            result = (
                sb.table("identity_communities")
                .select("identity_id, is_primary")
                .eq("community_id", community_id)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not result.data:
                break
            all_rows.extend(result.data)
            if len(result.data) < page_size:
                break
            offset += page_size

        logger.info(f"Loaded {len(all_rows)} identity IDs for community {community_id}")
        return all_rows
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase identity_communities load failed: {e}")
        return None


def create_community(data: dict) -> dict | None:
    """Create a new community. Returns the created row or None."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        result = sb.table("communities").insert(data).execute()
        if result.data:
            logger.info(f"Created community: {data.get('slug')}")
            _invalidate_community_cache()
            return result.data[0]
        return None
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase community create failed: {e}")
        return None


def create_personal_archive(user_id: str, email: str) -> dict | None:
    """Create a personal community archive for a new user.

    Returns the created community dict, or None if creation fails.
    Idempotent: if personal archive already exists, returns it.
    """
    sb = get_supabase_client()
    if not sb:
        return None

    # Extract display name from email
    name_part = email.split("@")[0].replace(".", " ").replace("_", " ").title()
    slug = f"personal-{user_id[:8]}"

    try:
        # Idempotency check
        existing = sb.table("communities").select("*").eq("owner_id", user_id).eq("is_personal", True).execute()
        if existing.data:
            return existing.data[0]

        # Create personal archive
        result = (
            sb.table("communities")
            .insert(
                {
                    "slug": slug,
                    "name": f"{name_part}'s Archive",
                    "description": "Personal photo archive",
                    "admin_emails": [email],
                    "r2_prefix": f"personal/{user_id[:8]}",
                    "owner_id": user_id,
                    "is_personal": True,
                    "privacy": "private",
                    "config": {"auto_created": True, "workspace_version": 1},
                }
            )
            .execute()
        )

        if result.data:
            _invalidate_community_cache()
            return result.data[0]
        return None
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Failed to create personal archive for {email}: {e}")
        return None


def update_community(community_id: str, data: dict) -> dict | None:
    """Update a community by ID. Returns updated row or None."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        result = sb.table("communities").update(data).eq("id", community_id).execute()
        if result.data:
            logger.info(f"Updated community: {community_id}")
            _invalidate_community_cache()
            return result.data[0]
        return None
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase community update failed: {e}")
        return None


def create_upload_batch(data: dict) -> dict | None:
    """Create an upload batch record. Returns the created row or None."""
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        result = sb.table("upload_batches").insert(data).execute()
        if result.data:
            return result.data[0]
        return None
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase upload batch create failed: {e}")
        return None


def add_photo_to_community(photo_id: str, community_id: str) -> bool:
    """Add a photo to a community (photo_communities table). Returns success."""
    sb = get_supabase_client()
    if not sb:
        return False

    try:
        sb.table("photo_communities").upsert({"photo_id": photo_id, "community_id": community_id}).execute()
        return True
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase add_photo_to_community failed: {e}")
        return False


def add_identity_to_community(identity_id: str, community_id: str, is_primary: bool = False) -> bool:
    """Add an identity to a community (identity_communities table). Returns success."""
    sb = get_supabase_client()
    if not sb:
        return False

    try:
        sb.table("identity_communities").upsert(
            {
                "identity_id": identity_id,
                "community_id": community_id,
                "is_primary": is_primary,
            }
        ).execute()
        return True
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase add_identity_to_community failed: {e}")
        return False


def log_identification_investigation(data: dict) -> bool:
    """Log an identification investigation to Supabase.

    Args:
        data: Dict with keys matching identification_investigations table columns.
              Required: investigation_name, session_id, target_name.
              Optional: all other columns (community_id, candidates, etc.)

    Returns True on success, False on failure.
    """
    sb = get_supabase_client()
    if not sb:
        return False

    # Required fields
    row = {}
    for field in ["investigation_name", "session_id", "target_name"]:
        if field not in data:
            logger.warning(f"log_identification_investigation missing required field: {field}")
            return False
        row[field] = data[field]

    # Optional fields
    for field in [
        "community_id",
        "collection_id",
        "target_birth_year",
        "target_death_year",
        "target_relationship",
        "target_gedcom_id",
        "target_spouse",
        "target_geography",
        "known_references",
        "methodology_steps",
        "candidates",
        "clusters",
        "outcome",
        "confirmed_identity_id",
        "confirmed_face_ids",
        "confidence_overall",
        "signals_used",
        "also_identified",
        "feature_ideas",
        "investigator",
    ]:
        if field in data and data[field] is not None:
            row[field] = data[field]

    try:
        sb.table("identification_investigations").insert(row).execute()
        logger.debug(f"Logged investigation: {data.get('investigation_name')} (session {data.get('session_id')})")
        return True
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase investigation log failed: {e}")
        return False


def get_investigations_for_family(target_name: str, community_id: str = None) -> list:
    """Retrieve past investigations by target name (case-insensitive).

    Args:
        target_name: Name to search for (uses ilike for case-insensitive match).
        community_id: Optional community filter.

    Returns list of investigation dicts, or empty list on failure.
    """
    sb = get_supabase_client()
    if not sb:
        return []

    try:
        query = sb.table("identification_investigations").select("*")
        query = query.ilike("target_name", f"%{target_name}%")
        if community_id:
            query = query.eq("community_id", community_id)
        query = query.order("created_at", desc=True)
        result = query.execute()
        return result.data or []
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase investigation family search failed: {e}")
        return []


def get_investigation(investigation_id: str) -> dict | None:
    """Retrieve a single investigation by ID.

    Args:
        investigation_id: UUID string of the investigation.

    Returns investigation dict, or None if not found or on failure.
    """
    sb = get_supabase_client()
    if not sb:
        return None

    try:
        result = sb.table("identification_investigations").select("*").eq("id", investigation_id).limit(1).execute()
        if result.data:
            return result.data[0]
        return None
    except _SUPABASE_ERRORS as e:
        logger.warning(f"Supabase investigation lookup failed: {e}")
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
