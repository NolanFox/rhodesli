"""GEDCOM dual-read helper — Session 157b Track B2 (PRD-063 Day 2).

Reads GEDCOM individual/family records, preferring v2 (gedcom_individuals_v2,
gedcom_families_v2) over v1 (gedcom_individuals, gedcom_families). v2 row
counts are ~18× / ~14× smaller than v1, so reads are faster and the canonical
fields are identical.

This is the dual-read window: Sessions 157-158. Session 158 will cut over to
v2-only and drop v1 (after VACUUM FULL). Until then, v1 remains a fallback
for any record not yet in v2 — though by Session 157b the Day 1 + Day 2
backfills should mean v2 is a complete superset of v1's is_current=TRUE rows.

Out of scope (Sessions 157+158): events, relationships, records — these
v2 tables don't exist yet, so any code path that needs them MUST keep
reading from v1.

Usage:
    from app.gedcom_dual_read import get_individual, get_family

    indiv = get_individual("@I1@")
    fam = get_family("@F4@")

Both return a dict (with v2 columns when available) or None if the gedcom_id
is not found in either v2 or v1.
"""

from __future__ import annotations

import logging
from typing import Optional

# Canonical fields shared by v1 and v2 individual rows. Ordered to match
# AD-244 schema. names_json/events_json/family_as_*_json/notes_json/
# citations_json are also in both but we don't always select them.
INDIVIDUAL_THIN_FIELDS = (
    "gedcom_id,name,given_name,surname,gender,"
    "birth_date,birth_place,death_date,death_place"
)
INDIVIDUAL_RICH_FIELDS = (
    INDIVIDUAL_THIN_FIELDS
    + ",names_json,events_json,family_as_spouse_json,family_as_child_json"
    + ",notes_json,citations_json"
)

# Family canonical fields. v1 may have additional columns; v2 mirrors the
# subset we need for app reads.
FAMILY_THIN_FIELDS = "family_gedcom_id,husband_xref,wife_xref"


def _v2_read_individual(sb, gedcom_id: str, select_fields: str) -> Optional[dict]:
    """Try gedcom_individuals_v2 first. Returns row dict or None."""
    try:
        resp = (
            sb.table("gedcom_individuals_v2")
            .select(select_fields)
            .eq("gedcom_id", gedcom_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        msg = str(exc)
        # PGRST205 / "relation does not exist" → v2 not deployed yet → fall through
        if "PGRST205" in msg or "gedcom_individuals_v2" in msg or "relation" in msg:
            logging.debug(f"v2 individual read unavailable: {exc}")
            return None
        raise
    rows = resp.data if resp and resp.data else []
    return rows[0] if rows else None


def _v1_read_individual(sb, gedcom_id: str, select_fields: str) -> Optional[dict]:
    """Fallback to gedcom_individuals (preferring current_gedcom_individuals view)."""
    try:
        resp = (
            sb.table("current_gedcom_individuals")
            .select(select_fields)
            .eq("gedcom_id", gedcom_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        msg = str(exc)
        if "current_gedcom_individuals" not in msg and "PGRST205" not in msg and "relation" not in msg:
            raise
        resp = (
            sb.table("gedcom_individuals")
            .select(select_fields)
            .eq("gedcom_id", gedcom_id)
            .limit(1)
            .execute()
        )
    rows = resp.data if resp and resp.data else []
    return rows[0] if rows else None


def get_individual(gedcom_id: str, *, include_rich: bool = False, sb=None) -> Optional[dict]:
    """Read a GEDCOM individual, preferring v2 over v1.

    Returns None if not found in either table.

    During the dual-read window (Sessions 157-158), v1 remains authoritative
    for fields not yet in v2 (events, relationships, records). For canonical
    fields (name, birth/death dates+places, gender) v2 is preferred — its
    row count is ~18× smaller and queries are faster.
    """
    if not gedcom_id:
        return None
    select_fields = INDIVIDUAL_RICH_FIELDS if include_rich else INDIVIDUAL_THIN_FIELDS
    if sb is None:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return None
    try:
        v2_row = _v2_read_individual(sb, gedcom_id, select_fields)
    except Exception as exc:
        logging.warning(f"v2 individual read failed for {gedcom_id}: {exc}")
        v2_row = None
    if v2_row is not None:
        return v2_row
    try:
        return _v1_read_individual(sb, gedcom_id, select_fields)
    except Exception as exc:
        logging.warning(f"v1 individual fallback failed for {gedcom_id}: {exc}")
        return None


def _v2_read_family(sb, family_gedcom_id: str, select_fields: str) -> Optional[dict]:
    try:
        resp = (
            sb.table("gedcom_families_v2")
            .select(select_fields)
            .eq("family_gedcom_id", family_gedcom_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        msg = str(exc)
        if "PGRST205" in msg or "gedcom_families_v2" in msg or "relation" in msg:
            logging.debug(f"v2 family read unavailable: {exc}")
            return None
        raise
    rows = resp.data if resp and resp.data else []
    return rows[0] if rows else None


def _v1_read_family(sb, family_gedcom_id: str, select_fields: str) -> Optional[dict]:
    resp = (
        sb.table("gedcom_families")
        .select(select_fields)
        .eq("family_gedcom_id", family_gedcom_id)
        .limit(1)
        .execute()
    )
    rows = resp.data if resp and resp.data else []
    return rows[0] if rows else None


def get_family(family_gedcom_id: str, *, sb=None) -> Optional[dict]:
    """Read a GEDCOM family, preferring v2 over v1.

    Returns None if not found in either table.

    Note: gedcom_families_v2 is canonical-fields only (family_gedcom_id +
    husband_xref + wife_xref). For events_family_json or children_xrefs_json
    callers must continue to read v1 directly.
    """
    if not family_gedcom_id:
        return None
    if sb is None:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return None
    try:
        v2_row = _v2_read_family(sb, family_gedcom_id, FAMILY_THIN_FIELDS)
    except Exception as exc:
        logging.warning(f"v2 family read failed for {family_gedcom_id}: {exc}")
        v2_row = None
    if v2_row is not None:
        return v2_row
    try:
        return _v1_read_family(sb, family_gedcom_id, FAMILY_THIN_FIELDS)
    except Exception as exc:
        logging.warning(f"v1 family fallback failed for {family_gedcom_id}: {exc}")
        return None
