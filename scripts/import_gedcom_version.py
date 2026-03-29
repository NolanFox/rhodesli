#!/usr/bin/env python3
"""Import a new GEDCOM version with rich, non-destructive tracking.

The importer mirrors top-level GEDCOM entities instead of flattening only the
basic individual fields. It supports:

- legacy-baseline diffing against the current thin tables
- richer entity snapshots for individuals, events, families, sources, media,
  relationships, and raw records
- versioned Supabase writes with `is_current` / `superseded_by`
- field-level change logging for Claude-auditable review
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from rhodesli_ml.importers.gedcom_snapshot import (  # noqa: E402
    LEGACY_COMPARE_FIELDS,
    GedcomSnapshotBundle,
    canonical_json_dumps,
    build_snapshot_bundle,
    diff_entity_maps,
)
from rhodesli_ml.importers.gedcom_matching import (  # noqa: E402
    detect_individual_redirects,
)

logger = logging.getLogger(__name__)

INDIVIDUAL_COMPARE_FIELDS = LEGACY_COMPARE_FIELDS["individuals"]

ENTITY_CONFIG = {
    "individuals": {
        "table": "gedcom_individuals",
        "key_field": "gedcom_id",
    },
    "events": {
        "table": "gedcom_events",
        "key_field": "event_key",
    },
    "families": {
        "table": "gedcom_families",
        "key_field": "family_gedcom_id",
    },
    "sources": {
        "table": "gedcom_sources",
        "key_field": "source_xref",
    },
    "media_objects": {
        "table": "gedcom_media_objects",
        "key_field": "media_xref",
    },
    "relationships": {
        "table": "gedcom_relationships",
        "key_field": "edge_key",
    },
    "records": {
        "table": "gedcom_records",
        "key_field": "record_key",
    },
}

RICH_ENTITY_TYPES = {"families", "sources", "media_objects", "records"}
REDIRECT_TABLE = "gedcom_entity_redirects"


def get_supabase_client():
    """Get Supabase client with service role key."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    from supabase import create_client

    return create_client(url, key)


def hash_file(filepath: Path) -> str:
    """SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_next_version_number(sb, community_id: str = "rhodesli") -> int:
    """Get the next version number for a community."""
    result = (
        sb.table("gedcom_versions")
        .select("version_number")
        .eq("community_id", community_id)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["version_number"] + 1
    return 1


def check_duplicate_hash(sb, source_hash: str, community_id: str = "rhodesli") -> dict | None:
    """Check if this exact file was already imported successfully.

    Failed or rolled-back attempts stay in lineage but must not block a retry.
    """
    result = (
        sb.table("gedcom_versions")
        .select("*")
        .eq("source_hash", source_hash)
        .eq("community_id", community_id)
        .execute()
    )
    for row in result.data or []:
        status = row.get("status") or "applied"
        if status not in {"failed", "rolled_back"}:
            return row
    return None


def load_current_individuals(sb) -> dict[str, dict[str, Any]]:
    """Backward-compatible helper kept for tests and thin legacy callers."""
    return _load_current_entity_map(sb, "individuals", baseline_mode=True)["rows"]


def diff_individual(old: dict, new_data: dict) -> list[dict]:
    """Compare an old individual row to new parsed data. Returns field-level changes."""
    changes = []
    for field in INDIVIDUAL_COMPARE_FIELDS:
        old_val = old.get(field) or ""
        new_val = new_data.get(field) or ""
        if str(old_val).strip() != str(new_val).strip():
            changes.append(
                {
                    "field_name": field,
                    "old_value": str(old_val) if old_val else None,
                    "new_value": str(new_val) if new_val else None,
                }
            )
    return changes


def build_individual_row(xref_id: str, indi, source_file: str) -> dict:
    """Build a thin legacy row dict from a parsed GEDCOM individual."""
    return {
        "gedcom_id": xref_id,
        "name": indi.full_name or "Unknown",
        "given_name": indi.given_name or None,
        "surname": indi.surname or None,
        "gender": indi.gender or "U",
        "birth_date": indi.birth.raw_date if indi.birth else None,
        "birth_place": indi.birth_place,
        "death_date": indi.death.raw_date if indi.death else None,
        "death_place": indi.death_place,
        "source_file": source_file,
    }


def _relation_missing_error(exc: Exception) -> bool:
    msg = str(exc)
    return "relation" in msg or "PGRST205" in msg or "Could not find the table" in msg


def _fetch_current_rows(sb, table_name: str) -> tuple[list[dict[str, Any]], bool]:
    conn = _get_direct_db_swap_connection()
    if conn is not None:
        try:
            try:
                from psycopg2.extras import RealDictCursor
            except Exception:
                RealDictCursor = None

            with conn:
                cursor_factory = RealDictCursor if RealDictCursor is not None else None
                with conn.cursor(cursor_factory=cursor_factory) as cur:
                    cur.execute(f"select * from {table_name} where is_current = true")
                    rows = cur.fetchall()
            return [dict(row) for row in rows], False
        except Exception as exc:
            if _relation_missing_error(exc):
                return [], True
            raise
        finally:
            conn.close()

    rows: list[dict[str, Any]] = []
    offset = 0
    page_size = 1000
    try:
        while True:
            result = (
                sb.table(table_name)
                .select("*")
                .or_("is_current.eq.true,is_current.is.null")
                .order("id")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            page = result.data or []
            rows.extend(page)
            if len(page) < page_size:
                break
            offset += page_size
        return rows, False
    except Exception as exc:
        if _relation_missing_error(exc):
            return [], True
        raise


def _table_exists(sb, table_name: str) -> bool:
    try:
        sb.table(table_name).select("id").limit(1).execute()
        return True
    except Exception as exc:
        if _relation_missing_error(exc):
            return False
        raise


def _build_event_key_from_row(row: dict[str, Any], ordinal: int) -> str:
    return f"{row.get('gedcom_individual_id', '')}|{row.get('event_type', '')}|{ordinal}"


def _build_relationship_key_from_row(row: dict[str, Any]) -> str:
    return (
        f"{row.get('relationship_type', '')}|{row.get('family_gedcom_id', '')}|"
        f"{row.get('individual_gedcom_id', '')}|{row.get('related_gedcom_id', '')}"
    )


def _normalize_current_rows(entity_type: str, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    config = ENTITY_CONFIG[entity_type]
    key_field = config["key_field"]

    if entity_type == "events":
        grouped: dict[tuple[str, str], int] = {}
        normalized = {}
        for row in rows:
            if row.get("event_key"):
                normalized[row["event_key"]] = row
                continue
            group_key = (row.get("gedcom_individual_id", ""), row.get("event_type", ""))
            ordinal = grouped.get(group_key, 0)
            grouped[group_key] = ordinal + 1
            normalized[_build_event_key_from_row(row, ordinal)] = row
        return normalized

    if entity_type == "relationships":
        normalized = {}
        for row in rows:
            edge_key = row.get("edge_key") or _build_relationship_key_from_row(row)
            normalized[edge_key] = row
        return normalized

    normalized = {}
    for row in rows:
        key = row.get(key_field)
        if key:
            normalized[key] = row
    return normalized


def _load_current_entity_map(sb, entity_type: str, baseline_mode: bool) -> dict[str, Any]:
    if baseline_mode and entity_type in {"families", "sources", "media_objects", "records"}:
        table_name = ENTITY_CONFIG[entity_type]["table"]
        return {"rows": {}, "missing_table": not _table_exists(sb, table_name)}

    if baseline_mode and entity_type == "events":
        return {"rows": {}, "missing_table": False}

    table_name = ENTITY_CONFIG[entity_type]["table"]
    rows, missing_table = _fetch_current_rows(sb, table_name)
    return {
        "rows": _normalize_current_rows(entity_type, rows),
        "missing_table": missing_table,
    }


def _load_bootstrap_supersede_rows(sb, entity_type: str) -> list[dict[str, Any]]:
    if entity_type not in {"individuals", "events", "relationships"}:
        return []
    table_name = ENTITY_CONFIG[entity_type]["table"]
    rows, missing_table = _fetch_current_rows(sb, table_name)
    if missing_table:
        return []
    return rows


def _bundle_entity_map(bundle: GedcomSnapshotBundle, entity_type: str) -> dict[str, dict[str, Any]]:
    return getattr(bundle, entity_type)


def _versions_exist(sb, community_id: str) -> bool:
    result = sb.table("gedcom_versions").select("id,status").eq("community_id", community_id).execute()
    for row in result.data or []:
        status = row.get("status") or "applied"
        if status not in {"failed", "rolled_back"}:
            return True
    return False


def _stringify_change_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return canonical_json_dumps(value)
    return str(value)


def _flatten_change_log_entries(version_id: str, entity_type: str, diff_result: dict[str, Any]) -> list[dict[str, Any]]:
    return list(_iter_change_log_entries(version_id, entity_type, diff_result))


def _iter_change_log_entries(version_id: str, entity_type: str, diff_result: dict[str, Any]):
    for item in diff_result["added"]:
        yield {
            "version_id": version_id,
            "change_type": "added",
            "entity_type": entity_type.rstrip("s"),
            "xref_id": item["entity_id"],
            "field_name": None,
            "old_value": None,
            "new_value": None,
        }
    for item in diff_result["removed"]:
        yield {
            "version_id": version_id,
            "change_type": "removed",
            "entity_type": entity_type.rstrip("s"),
            "xref_id": item["entity_id"],
            "field_name": None,
            "old_value": None,
            "new_value": None,
        }
    for item in diff_result["modified"]:
        for change in item["changes"]:
            yield {
                "version_id": version_id,
                "change_type": "modified",
                "entity_type": entity_type.rstrip("s"),
                "xref_id": item["entity_id"],
                "field_name": change["path"],
                "old_value": _stringify_change_value(change["old_value"]),
                "new_value": _stringify_change_value(change["new_value"]),
            }


def _iter_redirect_change_log_entries(version_id: str, redirects: list[dict[str, Any]]):
    for row in redirects:
        yield {
            "version_id": version_id,
            "change_type": "redirected",
            "entity_type": row["entity_type"],
            "xref_id": row["old_key"],
            "field_name": "redirected_to",
            "old_value": row["old_key"],
            "new_value": row["new_key"],
        }


def _write_change_log(
    sb,
    version_id: str,
    diff_by_entity: dict[str, dict[str, Any]],
    redirects: list[dict[str, Any]],
    *,
    batch_size: int = 500,
) -> None:
    buffer: list[dict[str, Any]] = []

    def flush() -> None:
        if buffer:
            _write_rows(sb, "gedcom_change_log", list(buffer), batch_size=batch_size)
            buffer.clear()

    for entity_type, diff_result in diff_by_entity.items():
        for entry in _iter_change_log_entries(version_id, entity_type, diff_result):
            buffer.append(entry)
            if len(buffer) >= batch_size:
                flush()
    for entry in _iter_redirect_change_log_entries(version_id, redirects):
        buffer.append(entry)
        if len(buffer) >= batch_size:
            flush()
    flush()


def _sample_changes(diff_by_entity: dict[str, dict[str, Any]], limit: int = 25) -> list[dict[str, Any]]:
    sample: list[dict[str, Any]] = []
    for entity_type, diff_result in diff_by_entity.items():
        for item in diff_result["modified"][:5]:
            sample.append(
                {
                    "entity_type": entity_type,
                    "entity_id": item["entity_id"],
                    "changes": item["changes"][:5],
                }
            )
            if len(sample) >= limit:
                return sample
    return sample


def _build_redirect_summary(redirects: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "detected": len(redirects),
        "sample": [
            {
                "entity_type": row["entity_type"],
                "old_key": row["old_key"],
                "new_key": row["new_key"],
                "redirect_type": row["redirect_type"],
                "match_score": row["match_score"],
                "reasons": row["match_basis"].get("reasons", [])[:5],
            }
            for row in redirects[:10]
        ],
    }


def _build_summary(
    bundle: GedcomSnapshotBundle,
    diff_by_entity: dict[str, dict[str, Any]],
    baseline_mode: bool,
    redirects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entity_summaries = {entity_type: diff_result["summary"] for entity_type, diff_result in diff_by_entity.items()}
    individual_summary = entity_summaries["individuals"]
    total_changes = sum(
        summary["added"] + summary["modified"] + summary["removed"] for summary in entity_summaries.values()
    )
    return {
        "added": individual_summary["added"],
        "modified": individual_summary["modified"],
        "removed": individual_summary["removed"],
        "unchanged": individual_summary["unchanged"],
        "total_changes": total_changes,
        "entity_summaries": entity_summaries,
        "counts": bundle.counts,
        "baseline_mode": "legacy_bootstrap" if baseline_mode else "versioned",
        "sample_changes": _sample_changes(diff_by_entity),
        "redirects": _build_redirect_summary(redirects or []),
    }


def _insert_rows(sb, table_name: str, rows: list[dict[str, Any]], batch_size: int = 250) -> dict[str, dict[str, Any]]:
    inserted_by_key: dict[str, dict[str, Any]] = {}
    if not rows:
        return inserted_by_key

    direct_rows = _insert_rows_direct_db(table_name, rows, batch_size=batch_size)
    if direct_rows is not None:
        for row in direct_rows:
            for key_field in (
                "gedcom_id",
                "event_key",
                "family_gedcom_id",
                "source_xref",
                "media_xref",
                "edge_key",
                "record_key",
            ):
                if row.get(key_field):
                    inserted_by_key[row[key_field]] = row
                    break
        return inserted_by_key

    for index in range(0, len(rows), batch_size):
        chunk = rows[index : index + batch_size]
        result = sb.table(table_name).insert(chunk).execute()
        for row in result.data or []:
            for key_field in (
                "gedcom_id",
                "event_key",
                "family_gedcom_id",
                "source_xref",
                "media_xref",
                "edge_key",
                "record_key",
            ):
                if row.get(key_field):
                    inserted_by_key[row[key_field]] = row
                    break
    return inserted_by_key


def _batched_ids(rows: list[dict[str, Any]], batch_size: int = 500) -> list[list[str]]:
    ids = [row.get("id") for row in rows if row.get("id")]
    return [ids[index : index + batch_size] for index in range(0, len(ids), batch_size)]


def _batched_values(values: list[str], batch_size: int = 1000) -> list[list[str]]:
    return [values[index : index + batch_size] for index in range(0, len(values), batch_size)]


def _adapt_db_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        from psycopg2.extras import Json

        return Json(value)
    return value


def _insert_rows_direct_db(
    table_name: str,
    rows: list[dict[str, Any]],
    *,
    batch_size: int = 250,
    returning: bool = True,
) -> list[dict[str, Any]] | None:
    conn = _get_direct_db_swap_connection()
    if conn is None:
        return None

    if not rows:
        return []

    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor, execute_values

    inserted_rows: list[dict[str, Any]] = []
    columns = sorted({key for row in rows for key in row.keys()})

    try:
        with conn:
            cursor_factory = RealDictCursor if returning else None
            with conn.cursor(cursor_factory=cursor_factory) as cur:
                base_query = sql.SQL("insert into {} ({}) values %s").format(
                    sql.Identifier(table_name),
                    sql.SQL(", ").join(sql.Identifier(column) for column in columns),
                )
                if returning:
                    base_query += sql.SQL(" returning *")
                query = base_query.as_string(cur)

                for index in range(0, len(rows), batch_size):
                    chunk = rows[index : index + batch_size]
                    values = [[_adapt_db_value(row.get(column)) for column in columns] for row in chunk]
                    result = execute_values(
                        cur,
                        query,
                        values,
                        page_size=len(chunk),
                        fetch=returning,
                    )
                    if returning and result:
                        inserted_rows.extend(dict(row) for row in result)
        return inserted_rows
    finally:
        conn.close()


def _write_rows(sb, table_name: str, rows: list[dict[str, Any]], batch_size: int = 500) -> None:
    if not rows:
        return

    direct_rows = _insert_rows_direct_db(
        table_name,
        rows,
        batch_size=batch_size,
        returning=False,
    )
    if direct_rows is not None:
        return

    for index in range(0, len(rows), batch_size):
        sb.table(table_name).insert(rows[index : index + batch_size]).execute()


def _get_direct_db_swap_connection():
    pooler_host = os.environ.get("SUPABASE_DB_POOLER_HOST")
    db_password = os.environ.get("SUPABASE_DB_PASSWORD")
    supabase_url = os.environ.get("SUPABASE_URL", "")
    if not pooler_host or not db_password or not supabase_url:
        return None

    project_ref = supabase_url.split("//", 1)[-1].split(".", 1)[0]
    db_user = os.environ.get("SUPABASE_DB_USER") or f"postgres.{project_ref}"
    db_port = int(os.environ.get("SUPABASE_DB_POOLER_PORT", "6543"))
    db_name = os.environ.get("SUPABASE_DB_NAME", "postgres")

    try:
        import psycopg2
    except Exception:
        return None

    return psycopg2.connect(
        host=pooler_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_password,
        sslmode="require",
    )


def _swap_current_rows_with_cursor(
    cur,
    table_name: str,
    supersede_rows: list[dict[str, Any]],
    inserted_rows: list[dict[str, Any]],
    *,
    baseline_mode: bool = False,
    version_id: str | None = None,
) -> None:
    if baseline_mode and version_id:
        cur.execute(f"update {table_name} set is_current = false where is_current = true")
        cur.execute(
            f"update {table_name} set is_current = true where version_id = %s",
            (version_id,),
        )
        return

    supersede_ids = [str(row["id"]) for row in supersede_rows if row.get("id")]
    inserted_ids = [str(row["id"]) for row in inserted_rows if row.get("id")]

    for chunk in _batched_values(supersede_ids):
        cur.execute(
            f"update {table_name} set is_current = false where id = any(%s::uuid[])",
            (chunk,),
        )
    for chunk in _batched_values(inserted_ids):
        cur.execute(
            f"update {table_name} set is_current = true where id = any(%s::uuid[])",
            (chunk,),
        )


def _swap_current_rows_direct_db(
    table_name: str,
    supersede_rows: list[dict[str, Any]],
    inserted_rows: list[dict[str, Any]],
    *,
    baseline_mode: bool = False,
    version_id: str | None = None,
) -> bool:
    conn = _get_direct_db_swap_connection()
    if conn is None:
        return False

    try:
        with conn:
            with conn.cursor() as cur:
                _swap_current_rows_with_cursor(
                    cur,
                    table_name,
                    supersede_rows,
                    inserted_rows,
                    baseline_mode=baseline_mode,
                    version_id=version_id,
                )
        return True
    finally:
        conn.close()


def _activate_rows(sb, table_name: str, rows: list[dict[str, Any]]) -> None:
    for chunk in _batched_ids(rows):
        sb.table(table_name).update({"is_current": True}).in_("id", chunk).execute()


def _supersede_rows(
    sb, table_name: str, rows: list[dict[str, Any]], inserted_by_key: dict[str, dict[str, Any]], key_field: str
) -> None:
    del inserted_by_key, key_field
    if not rows:
        return
    for chunk in _batched_ids(rows):
        sb.table(table_name).update({"is_current": False}).in_("id", chunk).execute()


def _apply_entity_diff(
    sb,
    entity_type: str,
    diff_result: dict[str, Any],
    baseline_mode: bool,
    version_id: str,
    new_map: dict[str, dict[str, Any]],
    bootstrap_supersede_rows: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    config = ENTITY_CONFIG[entity_type]
    table_name = config["table"]

    insert_rows: list[dict[str, Any]]

    if baseline_mode:
        insert_rows = [{**row, "version_id": version_id, "is_current": False} for row in new_map.values()]
    else:
        insert_rows = []
        for item in diff_result["added"]:
            insert_rows.append({**item["new_payload"], "version_id": version_id, "is_current": False})
        for item in diff_result["modified"]:
            insert_rows.append({**item["new_payload"], "version_id": version_id, "is_current": False})

    return _insert_rows(sb, table_name, insert_rows)


def _build_current_swap_plan(
    entity_type: str,
    diff_result: dict[str, Any],
    *,
    baseline_mode: bool,
    bootstrap_supersede_rows: list[dict[str, Any]] | None,
    inserted_by_key: dict[str, dict[str, Any]],
    version_id: str,
) -> dict[str, Any]:
    config = ENTITY_CONFIG[entity_type]
    if baseline_mode:
        supersede_rows = list(bootstrap_supersede_rows or [])
    else:
        supersede_rows = [item["old_payload"] for item in diff_result["modified"]] + [
            item["old_payload"] for item in diff_result["removed"]
        ]

    return {
        "table_name": config["table"],
        "key_field": config["key_field"],
        "supersede_rows": supersede_rows,
        "inserted_rows": list(inserted_by_key.values()),
        "inserted_by_key": inserted_by_key,
        "baseline_mode": baseline_mode,
        "version_id": version_id,
    }


def _finalize_current_state_direct_db(current_swap_plans: list[dict[str, Any]]) -> bool:
    conn = _get_direct_db_swap_connection()
    if conn is None:
        return False

    try:
        with conn:
            with conn.cursor() as cur:
                for plan in current_swap_plans:
                    _swap_current_rows_with_cursor(
                        cur,
                        plan["table_name"],
                        plan["supersede_rows"],
                        plan["inserted_rows"],
                        baseline_mode=plan["baseline_mode"],
                        version_id=plan["version_id"],
                    )
        return True
    finally:
        conn.close()


def _finalize_current_state_via_api(sb, current_swap_plans: list[dict[str, Any]]) -> None:
    for plan in current_swap_plans:
        _supersede_rows(
            sb,
            plan["table_name"],
            plan["supersede_rows"],
            plan["inserted_by_key"],
            plan["key_field"],
        )
        _activate_rows(sb, plan["table_name"], plan["inserted_rows"])


def _finalize_current_state(sb, current_swap_plans: list[dict[str, Any]]) -> None:
    if _finalize_current_state_direct_db(current_swap_plans):
        return
    _finalize_current_state_via_api(sb, current_swap_plans)


def _queue_enrichments(sb, version_id: str, individual_diff: dict[str, Any]) -> None:
    """Queue photos for re-enrichment when linked GEDCOM individuals changed."""
    affected_xrefs = {item["entity_id"] for item in individual_diff["modified"]} | {
        item["entity_id"] for item in individual_diff["removed"]
    }
    if not affected_xrefs:
        return

    links_result = sb.table("gedcom_face_links").select("*").execute()
    face_links = {row["gedcom_id"]: row for row in links_result.data or [] if row.get("gedcom_id")}

    queue_rows = []
    modified_xrefs = {item["entity_id"] for item in individual_diff["modified"]}
    for xref_id in sorted(affected_xrefs):
        link = face_links.get(xref_id)
        if not link or not link.get("identity_id"):
            continue
        change_type = "modified" if xref_id in modified_xrefs else "removed"
        queue_rows.append(
            {
                "photo_id": f"lookup:{link['identity_id']}",
                "identity_id": link["identity_id"],
                "gedcom_id": xref_id,
                "trigger": "gedcom_update",
                "reason": f"GEDCOM {change_type}: {xref_id}",
                "version_id": version_id,
                "status": "pending",
            }
        )

    if queue_rows:
        _write_rows(sb, "gedcom_enrichment_queue", queue_rows, batch_size=500)
        logger.info("Queued %s re-enrichment items", len(queue_rows))


def _redirect_table_exists(sb, community_id: str) -> bool:
    try:
        (sb.table(REDIRECT_TABLE).select("id").eq("community_id", community_id).limit(1).execute())
        return True
    except Exception as exc:
        if _relation_missing_error(exc):
            return False
        raise


def _required_schema_tables(diff_by_entity: dict[str, dict[str, Any]], missing_tables: list[str]) -> list[str]:
    del diff_by_entity  # rich-table requirement is now driven by actual table visibility checks
    return sorted(set(missing_tables))


def _redirect_change_log_entries(version_id: str, redirects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return list(_iter_redirect_change_log_entries(version_id, redirects))


def _set_version_status(
    sb,
    version_id: str,
    *,
    status: str,
    summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    payload: dict[str, Any] = {"status": status}
    if summary is not None:
        # Round-trip through JSON to convert datetime objects to strings
        payload["summary"] = json.loads(json.dumps(summary, default=str))
    if error_message:
        payload["notes"] = error_message
    sb.table("gedcom_versions").update(payload).eq("id", version_id).execute()


def _write_redirect_rows(
    sb,
    version_id: str,
    community_id: str,
    redirects: list[dict[str, Any]],
    inserted_maps: dict[str, dict[str, dict[str, Any]]],
    current_maps: dict[str, dict[str, dict[str, Any]]],
) -> None:
    if not redirects:
        return

    redirect_rows = []
    target_updates: list[tuple[str, str]] = []
    individual_current = current_maps.get("individuals", {})
    individual_inserted = inserted_maps.get("individuals", {})

    for row in redirects:
        target_row = individual_inserted.get(row["new_key"]) or individual_current.get(row["new_key"])
        if row.get("old_row_id") and target_row and target_row.get("id"):
            target_updates.append((row["old_row_id"], target_row["id"]))

        redirect_rows.append(
            {
                "community_id": community_id,
                "entity_type": row["entity_type"],
                "old_key": row["old_key"],
                "new_key": row["new_key"],
                "version_id": version_id,
                "redirect_type": row["redirect_type"],
                "match_score": row["match_score"],
                "match_basis_json": row["match_basis"],
            }
        )

    _write_rows(sb, REDIRECT_TABLE, redirect_rows, batch_size=500)

    for old_row_id, target_row_id in target_updates:
        sb.table("gedcom_individuals").update({"superseded_by": target_row_id}).eq("id", old_row_id).execute()


def import_versioned(
    sb,
    parsed,
    source_file: str,
    source_hash: str,
    community_id: str = "rhodesli",
    notes: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Import a new GEDCOM version with full change tracking."""
    existing = check_duplicate_hash(sb, source_hash, community_id) if sb else None
    if existing:
        logger.warning(
            "This exact file was already imported as version %s on %s. Skipping.",
            existing["version_number"],
            existing["imported_at"],
        )
        return {
            "skipped": True,
            "reason": "duplicate_hash",
            "existing_version": existing["version_number"],
        }

    version_number = get_next_version_number(sb, community_id) if sb else 1
    baseline_mode = not _versions_exist(sb, community_id) if sb else True
    bundle = build_snapshot_bundle(parsed, source_file=source_file)

    current_maps = {}
    missing_tables = []
    bootstrap_supersede_rows = {}
    for entity_type in ENTITY_CONFIG:
        current_result = (
            _load_current_entity_map(sb, entity_type, baseline_mode=baseline_mode)
            if sb
            else {"rows": {}, "missing_table": False}
        )
        current_maps[entity_type] = current_result["rows"]
        if current_result["missing_table"]:
            missing_tables.append(ENTITY_CONFIG[entity_type]["table"])
        if sb and baseline_mode:
            bootstrap_supersede_rows[entity_type] = _load_bootstrap_supersede_rows(sb, entity_type)
        else:
            bootstrap_supersede_rows[entity_type] = []

    diff_by_entity = {}
    for entity_type in ENTITY_CONFIG:
        diff_by_entity[entity_type] = diff_entity_maps(
            entity_type,
            current_maps[entity_type],
            _bundle_entity_map(bundle, entity_type),
        )

    redirects: list[dict[str, Any]] = []
    redirect_table_exists = _redirect_table_exists(sb, community_id) if sb else False
    if current_maps["individuals"]:
        redirects = detect_individual_redirects(
            diff_by_entity["individuals"]["removed"],
            bundle.individuals,
            old_map=current_maps["individuals"],
        )

    summary = _build_summary(bundle, diff_by_entity, baseline_mode=baseline_mode, redirects=redirects)
    required_tables = _required_schema_tables(diff_by_entity, missing_tables)
    if redirects and not redirect_table_exists:
        required_tables = sorted(set(required_tables) | {REDIRECT_TABLE})
    summary["schema_ready"] = not required_tables
    summary["missing_tables"] = required_tables
    summary["version_number"] = version_number

    if dry_run:
        return {"dry_run": True, **summary}

    if required_tables:
        raise RuntimeError(
            "GEDCOM rich-schema tables are missing; apply the migration before import: " + ", ".join(required_tables)
        )

    # Round-trip through JSON to convert datetime objects to strings
    summary_json = json.loads(json.dumps(summary, default=str))
    version_result = (
        sb.table("gedcom_versions")
        .insert(
            {
                "version_number": version_number,
                "community_id": community_id,
                "source_file": source_file,
                "source_hash": source_hash,
                "individual_count": bundle.counts["individuals"],
                "family_count": bundle.counts["families"],
                "source_count": bundle.counts["sources"],
                "media_count": bundle.counts["media_objects"],
                "record_count": bundle.counts["records"],
                "summary": summary_json,
                "notes": notes,
                "status": "applying",
            }
        )
        .execute()
    )
    version_id = version_result.data[0]["id"]
    logger.info("Created version %s (id: %s)", version_number, version_id)
    try:
        inserted_maps: dict[str, dict[str, dict[str, Any]]] = {}
        current_swap_plans: list[dict[str, Any]] = []
        for entity_type in ENTITY_CONFIG:
            inserted_by_key = _apply_entity_diff(
                sb,
                entity_type,
                diff_by_entity[entity_type],
                baseline_mode=baseline_mode,
                version_id=version_id,
                new_map=_bundle_entity_map(bundle, entity_type),
                bootstrap_supersede_rows=bootstrap_supersede_rows.get(entity_type, []),
            )
            inserted_maps[entity_type] = inserted_by_key
            current_swap_plans.append(
                _build_current_swap_plan(
                    entity_type,
                    diff_by_entity[entity_type],
                    baseline_mode=baseline_mode,
                    bootstrap_supersede_rows=bootstrap_supersede_rows.get(entity_type, []),
                    inserted_by_key=inserted_by_key,
                    version_id=version_id,
                )
            )

        _write_redirect_rows(
            sb,
            version_id=version_id,
            community_id=community_id,
            redirects=redirects,
            inserted_maps=inserted_maps,
            current_maps=current_maps,
        )

        # Change log is non-critical — don't let it block import
        try:
            _write_change_log(
                sb,
                version_id,
                diff_by_entity,
                redirects,
                batch_size=500,
            )
        except Exception as cl_exc:
            logger.warning("Change log write failed (non-fatal): %s", cl_exc)

        _queue_enrichments(sb, version_id, diff_by_entity["individuals"])
        _finalize_current_state(sb, current_swap_plans)
    except Exception as exc:
        failed_summary = {**summary, "status": "failed", "error": str(exc)}
        try:
            _set_version_status(
                sb,
                version_id,
                status="failed",
                summary=failed_summary,
                error_message=f"FAILED: {exc}",
            )
        except Exception as status_exc:
            logger.error("Failed to set version status: %s", status_exc)
        raise

    applied_summary = {**summary, "status": "applied"}
    _set_version_status(sb, version_id, status="applied", summary=applied_summary)

    return {
        "version_id": version_id,
        "version_number": version_number,
        **applied_summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Import versioned GEDCOM into Supabase")
    parser.add_argument("--file", required=True, help="Path to GEDCOM file")
    parser.add_argument("--execute", action="store_true", help="Actually import (default: dry-run)")
    parser.add_argument("--community", default="rhodesli", help="Community ID")
    parser.add_argument("--notes", default=None, help="Notes for this version")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    dry_run = not args.execute
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    filepath = Path(args.file).expanduser()
    if not filepath.exists():
        logger.error("GEDCOM file not found: %s", filepath)
        sys.exit(1)

    source_hash = hash_file(filepath)
    logger.info("File: %s (SHA256: %s...)", filepath.name, source_hash[:16])

    logger.info("Parsing GEDCOM: %s", filepath.name)
    from rhodesli_ml.importers.gedcom_parser import parse_gedcom

    parsed = parse_gedcom(str(filepath))
    logger.info(
        "Parsed: %s individuals, %s families, %s sources, %s media",
        parsed.individual_count,
        parsed.family_count,
        parsed.source_count,
        parsed.media_count,
    )

    from dotenv import load_dotenv

    load_dotenv()
    sb = get_supabase_client()
    logger.info("Connected to Supabase")

    result = import_versioned(
        sb,
        parsed,
        filepath.name,
        source_hash,
        community_id=args.community,
        notes=args.notes,
        dry_run=dry_run,
    )

    if result.get("skipped"):
        logger.info("Import skipped: %s", result["reason"])
        return

    logger.info("\n%s", json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
