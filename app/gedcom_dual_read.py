"""GEDCOM current-state reader — Session 164 (PRD-064 Option B-plus).

Single, clean reader over the canonical current-state tables ``gedcom_individuals``
and ``gedcom_families`` (one row per entity, community-scoped composite PK). The
old Session 157b/158 dual-read (v1/v2 fallback chains) is gone — the v1 tables
were dropped in 158e and the v2 tables are dropped + replaced by the canonical
tables in the Session 164 migration.

History no longer lives in the DB (the canonical tables hold ONLY current state).
``get_individual_history`` therefore reads the R2 history artifacts via
``gedcom_history`` + ``gedcom_versions.artifact_prefix``; if R2 is unavailable it
returns ``[]`` (Codex P2-6).

The module name (``gedcom_dual_read``) and the public field-name constants are
kept for backward compatibility with existing callers — only the implementation
collapsed.

Usage:
    from app.gedcom_dual_read import get_individual, get_family

    indiv = get_individual("@I1@")
    fam = get_family("@F4@")

Both return a dict (canonical columns) or None if not found.
"""

from __future__ import annotations

import logging
from typing import Optional

DEFAULT_COMMUNITY = "rhodesli"

# Canonical individual fields (back-compat constant names). Thin = the fast
# columns most readers need; Rich adds the JSONB columns.
INDIVIDUAL_THIN_FIELDS = (
    "gedcom_id,name,given_name,surname,gender,"
    "birth_date,birth_place,death_date,death_place"
)
INDIVIDUAL_RICH_FIELDS = (
    INDIVIDUAL_THIN_FIELDS
    + ",names_json,events_json,family_as_spouse_json,family_as_child_json"
    + ",notes_json,citations_json"
)

# Family canonical fields.
FAMILY_THIN_FIELDS = "family_gedcom_id,husband_xref,wife_xref"


def get_individual(
    gedcom_id: str,
    *,
    include_rich: bool = False,
    community_id: str = DEFAULT_COMMUNITY,
    sb=None,
) -> Optional[dict]:
    """Read one GEDCOM individual from the canonical ``gedcom_individuals`` table.

    Filtered by (community_id, gedcom_id). Returns the row dict or None.
    """
    if not gedcom_id:
        return None
    select_fields = INDIVIDUAL_RICH_FIELDS if include_rich else INDIVIDUAL_THIN_FIELDS
    if sb is None:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return None
    resp = (
        sb.table("gedcom_individuals")
        .select(select_fields)
        .eq("community_id", community_id)
        .eq("gedcom_id", gedcom_id)
        .limit(1)
        .execute()
    )
    rows = resp.data if resp and resp.data else []
    return rows[0] if rows else None


def get_family(
    family_gedcom_id: str,
    *,
    community_id: str = DEFAULT_COMMUNITY,
    sb=None,
) -> Optional[dict]:
    """Read one GEDCOM family from the canonical ``gedcom_families`` table.

    Filtered by (community_id, family_gedcom_id). Returns the row dict or None.
    """
    if not family_gedcom_id:
        return None
    if sb is None:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return None
    resp = (
        sb.table("gedcom_families")
        .select(FAMILY_THIN_FIELDS)
        .eq("community_id", community_id)
        .eq("family_gedcom_id", family_gedcom_id)
        .limit(1)
        .execute()
    )
    rows = resp.data if resp and resp.data else []
    return rows[0] if rows else None


# --- History reader (Session 164: reads R2 artifacts, not the DB) ---

# Kept for back-compat with callers/tests that import the constant. The canonical
# DB no longer carries per-version rows, so history comes from R2 diffs which
# carry the full per-entity payloads.
INDIVIDUAL_HISTORY_FIELDS = INDIVIDUAL_RICH_FIELDS


def get_individual_history(
    gedcom_id: str,
    *,
    community_id: str = DEFAULT_COMMUNITY,
    sb=None,
    r2_client=None,
) -> list[dict]:
    """Return the change timeline for a gedcom_id, reconstructed from R2 history.

    Each element is a per-version change record for this entity::

        {"version_number", "change_type", "before", "after",
         "before_hash", "after_hash"}

    sorted by version_number ascending (oldest first). Built by scanning each
    applied version's ``diff.json.gz`` in R2 for entries matching this gedcom_id.

    The canonical current-state DB tables hold ONLY the latest state, so DB
    history is impossible — R2 is the lossless source of truth (Codex P2-6).
    If R2 is unavailable (or no artifacts exist yet), returns ``[]``.
    """
    if not gedcom_id:
        return []
    if sb is None:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return []

    # Load applied versions (newest first is fine; we re-sort at the end).
    try:
        resp = (
            sb.table("gedcom_versions")
            .select("version_number,artifact_prefix,artifact_format,status")
            .eq("status", "applied")
            .order("version_number", desc=False)
            .execute()
        )
        versions = resp.data if resp and resp.data else []
    except Exception as exc:
        logging.debug(f"gedcom_versions read for history unavailable: {exc}")
        return []

    versions = [
        v for v in versions
        if v.get("artifact_prefix") and v.get("artifact_format") == "v1"
    ]
    if not versions:
        return []

    if r2_client is None:
        try:
            import scripts.import_gedcom_version as imp

            r2_client = imp.default_r2_factory()
        except Exception as exc:
            logging.debug(f"R2 client unavailable for individual history: {exc}")
            return []

    from rhodesli_ml.importers import gedcom_history as gh
    import os

    bucket = os.environ.get("R2_BUCKET_NAME", "rhodesli-photos")
    timeline: list[dict] = []
    for v in versions:
        prefix = v["artifact_prefix"]
        try:
            diff_doc = gh.download_diff(r2_client, bucket, prefix)
        except Exception as exc:
            logging.debug(f"diff download failed for {prefix}: {exc}")
            continue
        ind_diff = (diff_doc.get("entities") or {}).get("individuals") or {}
        for bucket_name in ("added", "modified", "removed"):
            for item in ind_diff.get(bucket_name, []) or []:
                if item.get("entity_id") == gedcom_id:
                    timeline.append(
                        {
                            "version_number": v["version_number"],
                            "change_type": item.get("change_type", bucket_name),
                            "before": item.get("before"),
                            "after": item.get("after"),
                            "before_hash": item.get("before_hash"),
                            "after_hash": item.get("after_hash"),
                        }
                    )

    timeline.sort(key=lambda r: r["version_number"])
    return timeline
