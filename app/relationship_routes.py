"""
Relationship and GEDCOM routes extracted from app/main.py.

Relationship CRUD, GEDCOM individual search/link/unlink,
GEDCOM cache helpers, and date confirmation.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from fasthtml.common import *
from starlette.responses import Response

from core.registry import IdentityState
from core.ui_safety import ensure_utf8_display

from app.main import rt
from rhodesli_ml.importers.gedcom_matching import resolve_redirect_chain

import app.main as _main_mod

logger = logging.getLogger(__name__)


_gedcom_matches_cache = None
_gedcom_tree_relationships_cache = None

_GEDCOM_THIN_FIELDS = "gedcom_id,name,given_name,surname,gender,birth_date,birth_place,death_date,death_place"
_GEDCOM_RICH_FIELDS = (
    "gedcom_id,name,given_name,surname,gender,birth_date,birth_place,death_date,death_place,"
    "birth_event_json,death_event_json,events_json,names_json,notes_json,citations_json,"
    "media_refs_json,custom_tags_json,source_file"
)


_gedcom_matches_cache_ts: float = 0.0
_GEDCOM_MATCHES_CACHE_TTL: float = 300.0


def _load_gedcom_matches():
    """Load GEDCOM match proposals.

    When DATA_SOURCE=postgres (default), reads from Supabase gedcom_matches table.
    When DATA_SOURCE=json (rollback), reads from gedcom_matches.json.
    Uses a 300-second TTL cache — GEDCOM links change only during manual linking.
    PRD-051 Phase 2, Session 114.
    """
    global _gedcom_matches_cache, _gedcom_matches_cache_ts
    import time as _time

    now = _time.time()
    if _gedcom_matches_cache is not None and (now - _gedcom_matches_cache_ts) < _GEDCOM_MATCHES_CACHE_TTL:
        return _gedcom_matches_cache

    default = {"schema_version": 1, "matches": [], "source_file": ""}

    if _main_mod.DATA_SOURCE == "postgres":
        try:
            from app.supabase_data import get_supabase_client

            sb = get_supabase_client()
            if sb:
                resp = sb.table("gedcom_matches").select("data").execute()
                rows = resp.data or []
                matches = [r["data"] for r in rows if r.get("data")]
                result = {"schema_version": 1, "matches": matches, "source_file": "supabase"}
                _gedcom_matches_cache = result
                _gedcom_matches_cache_ts = now
                logging.debug("gedcom_matches_cache_populated source=postgres count=%d", len(matches))
                return result
        except Exception as e:
            logging.error("gedcom_matches: Supabase read failed, returning empty (no JSON fallback — AD-232): %s", e)
        _gedcom_matches_cache = default
        _gedcom_matches_cache_ts = now
        return _gedcom_matches_cache

    # JSON mode (DATA_SOURCE=json) — rollback escape hatch only
    matches_path = _main_mod.data_path / "gedcom_matches.json"
    if not matches_path.exists():
        _gedcom_matches_cache = default
        _gedcom_matches_cache_ts = now
        return _gedcom_matches_cache

    try:
        _gedcom_matches_cache = json.loads(matches_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        _gedcom_matches_cache = default
    _gedcom_matches_cache_ts = now
    return _gedcom_matches_cache


def invalidate_gedcom_matches_cache():
    """Clear GEDCOM matches cache after writes."""
    global _gedcom_matches_cache, _gedcom_matches_cache_ts
    _gedcom_matches_cache = None
    _gedcom_matches_cache_ts = 0.0


_relationship_graph_cache = None
_relationship_graph_cache_ts: float = 0.0
_RELATIONSHIP_GRAPH_CACHE_TTL: float = 300.0


def _load_relationship_graph():
    """Load relationship graph.

    When DATA_SOURCE=postgres (default), reads from Supabase relationships table.
    When DATA_SOURCE=json (rollback), reads from relationships.json.
    Uses a 300-second TTL cache — relationships change only on GEDCOM import.
    PRD-051 Phase 2, Session 114.
    """
    global _relationship_graph_cache, _relationship_graph_cache_ts
    import time as _time

    now = _time.time()
    if _relationship_graph_cache is not None and (now - _relationship_graph_cache_ts) < _RELATIONSHIP_GRAPH_CACHE_TTL:
        return _relationship_graph_cache

    default = {"schema_version": 1, "relationships": [], "gedcom_imports": []}

    if _main_mod.DATA_SOURCE == "postgres":
        try:
            from app.supabase_data import get_supabase_client

            sb = get_supabase_client()
            if sb:
                resp = sb.table("relationships").select("data").execute()
                rows = resp.data or []
                relationships = [r["data"] for r in rows if r.get("data")]
                result = {"schema_version": 1, "relationships": relationships, "gedcom_imports": []}
                _relationship_graph_cache = result
                _relationship_graph_cache_ts = now
                logging.debug("relationship_graph_cache_populated source=postgres count=%d", len(relationships))
                return result
        except Exception as e:
            logging.error("relationships: Supabase read failed, returning empty (no JSON fallback — AD-232): %s", e)
        _relationship_graph_cache = default
        _relationship_graph_cache_ts = now
        return _relationship_graph_cache

    # JSON mode (DATA_SOURCE=json) — rollback escape hatch only
    rel_path = _main_mod.data_path / "relationships.json"
    if not rel_path.exists():
        _relationship_graph_cache = default
        _relationship_graph_cache_ts = now
        return _relationship_graph_cache
    try:
        _relationship_graph_cache = json.loads(rel_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        _relationship_graph_cache = default
    _relationship_graph_cache_ts = now
    return _relationship_graph_cache


def invalidate_relationship_cache():
    """Clear relationship cache after writes."""
    global _relationship_graph_cache, _relationship_graph_cache_ts
    _relationship_graph_cache = None
    _relationship_graph_cache_ts = 0.0


def _save_relationship_graph(graph: dict):
    """Save relationship graph to data/relationships.json + sync to Supabase (AD-135)."""
    rel_path = _main_mod.data_path / "relationships.json"
    rel_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    # Sync relationships to Supabase
    try:
        from app.supabase_data import sync_relationships

        sync_relationships(graph.get("relationships", []))
    except Exception as e:
        logging.warning(f"Supabase relationship sync failed (degraded mode): {e}")
    # Invalidate cache after write (PRD-051 Session 114)
    invalidate_relationship_cache()


@rt("/api/relationship/add")
def post(person_a: str, person_b: str, type: str, confidence: str = "confirmed", label: str = "", sess=None):
    """Add a relationship between two people (admin only)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    from rhodesli_ml.graph.relationship_graph import add_relationship as _add_rel

    graph = _main_mod._load_relationship_graph()
    graph = _add_rel(graph, person_a, person_b, type, "manual", confidence, label=label or None)
    _main_mod._save_relationship_graph(graph)
    return Response("OK", status_code=200)


@rt("/api/relationship/update")
def post(person_a: str, person_b: str, type: str, confidence: str, sess=None):
    """Update relationship confidence (admin only)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    from rhodesli_ml.graph.relationship_graph import update_relationship_confidence as _update_conf

    graph = _main_mod._load_relationship_graph()
    graph = _update_conf(graph, person_a, person_b, type, confidence)
    _main_mod._save_relationship_graph(graph)
    return Response("OK", status_code=200)


@rt("/api/relationship/remove")
def post(person_a: str, person_b: str, type: str, sess=None):
    """Remove a relationship (admin only, non-destructive)."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied
    from rhodesli_ml.graph.relationship_graph import remove_relationship as _remove_rel

    graph = _main_mod._load_relationship_graph()
    graph = _remove_rel(graph, person_a, person_b, type)
    _main_mod._save_relationship_graph(graph)
    return Response("OK", status_code=200)


_gedcom_individuals_cache = None
_gedcom_face_links_cache = None
_gedcom_redirects_cache = None
_gedcom_tree_relationships_cache_loaded_at = 0.0
_gedcom_tree_relationships_cache_failed_at = 0.0
_gedcom_individuals_cache_loaded_at = 0.0
_gedcom_individuals_cache_failed_at = 0.0
_gedcom_face_links_cache_loaded_at = 0.0
_gedcom_face_links_cache_failed_at = 0.0
_gedcom_redirects_cache_loaded_at = 0.0
_gedcom_redirects_cache_failed_at = 0.0
_GEDCOM_CACHE_TTL_SECONDS = 300
_GEDCOM_FAILURE_BACKOFF_SECONDS = 30


def _is_ttl_cache_fresh(loaded_at: float, ttl_seconds: int) -> bool:
    return bool(loaded_at) and (time.monotonic() - loaded_at) < ttl_seconds


def _failure_backoff_active(failed_at: float, backoff_seconds: int) -> bool:
    return bool(failed_at) and (time.monotonic() - failed_at) < backoff_seconds


def _is_retryable_gedcom_error(exc: Exception) -> bool:
    msg = str(exc)
    retryable_markers = (
        "ConnectionTerminated",
        "RemoteProtocolError",
        "Server disconnected",
        "timeout",
        "Timeout",
        "503",
        "504",
    )
    return any(marker in msg for marker in retryable_markers)


def _run_gedcom_query(query_fn, label: str):
    """Retry a transient GEDCOM/Supabase failure once after resetting the client."""
    last_error = None
    for attempt in range(1, 3):
        try:
            return query_fn()
        except Exception as exc:
            last_error = exc
            if attempt >= 2 or not _is_retryable_gedcom_error(exc):
                raise
            logging.warning(f"{label} failed ({exc}); retrying once with a fresh Supabase client")
            try:
                from app.supabase_data import reset_client

                reset_client()
            except Exception:
                pass
            time.sleep(0.2 * attempt)
    raise last_error


def _load_gedcom_rows(
    sb,
    table_name: str,
    select_fields: str,
    order_by: str | None = None,
    filters: dict | None = None,
) -> list[dict]:
    rows = []
    page_size = 1000
    offset = 0
    while True:
        query = sb.table(table_name).select(select_fields)
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        if order_by:
            query = query.order(order_by)
        resp = query.range(offset, offset + page_size - 1).execute()
        if not resp or not resp.data:
            break
        rows.extend(resp.data)
        if len(resp.data) < page_size:
            break
        offset += page_size
    return rows


def _load_gedcom_individuals():
    """Load GEDCOM individuals from Supabase into memory cache.

    Returns list of dicts with keys: gedcom_id, name, given_name, surname,
    gender, birth_date, birth_place, death_date, death_place.
    Caches in memory — call _main_mod._invalidate_gedcom_cache() to refresh.
    """
    global _gedcom_individuals_cache, _gedcom_individuals_cache_loaded_at, _gedcom_individuals_cache_failed_at
    if _gedcom_individuals_cache is not None and _is_ttl_cache_fresh(
        _gedcom_individuals_cache_loaded_at, _GEDCOM_CACHE_TTL_SECONDS
    ):
        return _gedcom_individuals_cache
    if _failure_backoff_active(_gedcom_individuals_cache_failed_at, _GEDCOM_FAILURE_BACKOFF_SECONDS):
        return _gedcom_individuals_cache or []

    try:
        from app.supabase_data import get_supabase_client

        def _query():
            sb = get_supabase_client()
            if not sb:
                return []

            try:
                # PRD-063 Day 3 (Session 158b): prefer the v2 view first.
                return _load_gedcom_rows(sb, "current_gedcom_individuals_v2", _GEDCOM_THIN_FIELDS)
            except Exception as exc_v2:
                msg_v2 = str(exc_v2)
                if "current_gedcom_individuals_v2" not in msg_v2 and "PGRST205" not in msg_v2 and "relation" not in msg_v2:
                    raise
                logging.info("current_gedcom_individuals_v2 unavailable; falling back to v1 view")
            try:
                # AD-163: legacy v1 view fallback (pre-Phase 158b-4 deploys).
                return _load_gedcom_rows(sb, "current_gedcom_individuals", _GEDCOM_THIN_FIELDS)
            except Exception as exc:
                msg = str(exc)
                if "current_gedcom_individuals" not in msg and "PGRST205" not in msg and "relation" not in msg:
                    raise
                logging.info("current_gedcom_individuals unavailable; falling back to gedcom_individuals")
                return _load_gedcom_rows(sb, "gedcom_individuals", _GEDCOM_THIN_FIELDS)

        all_rows = _run_gedcom_query(_query, "GEDCOM individuals load")

        _gedcom_individuals_cache = all_rows
        _gedcom_individuals_cache_loaded_at = time.monotonic()
        _gedcom_individuals_cache_failed_at = 0.0
        logging.info(f"Loaded {len(all_rows)} GEDCOM individuals into cache")
    except Exception as e:
        _gedcom_individuals_cache_failed_at = time.monotonic()
        logging.warning(f"Failed to load GEDCOM individuals: {e}")
        return _gedcom_individuals_cache or []

    return _gedcom_individuals_cache


def _load_gedcom_individual(gedcom_id: str, include_rich: bool = False) -> dict | None:
    """Load one GEDCOM individual by xref.

    Broad search/list routes should use the thin bulk loader. Exact-link routes
    should fetch one row to avoid reloading the full GEDCOM mirror.

    Session 157b PRD-063 dual-read: prefer gedcom_individuals_v2 over v1.
    Falls back to v1 (current_gedcom_individuals view, then gedcom_individuals
    table) when the row isn't yet in v2 or v2 isn't deployed.
    """
    if not gedcom_id:
        return None

    try:
        from app.gedcom_dual_read import get_individual as _dual_get_individual

        def _query():
            return _dual_get_individual(gedcom_id, include_rich=include_rich)

        row = _run_gedcom_query(_query, "GEDCOM individual load (dual-read)")
        if row is not None:
            return row
    except Exception as e:
        logging.warning(f"Failed to load GEDCOM individual {gedcom_id}: {e}")

    for row in _load_gedcom_individuals():
        if row.get("gedcom_id") == gedcom_id:
            return row
    return None


def _load_gedcom_face_links():
    """Load GEDCOM face links from Supabase. Returns dict: identity_id -> gedcom_id."""
    global _gedcom_face_links_cache, _gedcom_face_links_cache_loaded_at, _gedcom_face_links_cache_failed_at
    if _gedcom_face_links_cache is not None and _is_ttl_cache_fresh(
        _gedcom_face_links_cache_loaded_at, _GEDCOM_CACHE_TTL_SECONDS
    ):
        return _gedcom_face_links_cache
    if _failure_backoff_active(_gedcom_face_links_cache_failed_at, _GEDCOM_FAILURE_BACKOFF_SECONDS):
        return _gedcom_face_links_cache or {}

    try:
        from app.supabase_data import get_supabase_client

        def _query():
            sb = get_supabase_client()
            if not sb:
                return {}
            resp = sb.table("gedcom_face_links").select("identity_id,gedcom_id,confidence,linked_by").execute()
            redirects = _load_gedcom_entity_redirects()
            links = {}
            if resp and resp.data:
                for row in resp.data:
                    original_gedcom_id = row.get("gedcom_id")
                    resolved_gedcom_id = (
                        resolve_redirect_chain(original_gedcom_id or "", redirects) if original_gedcom_id else ""
                    )
                    link_row = {
                        **row,
                        "gedcom_id": resolved_gedcom_id or original_gedcom_id,
                    }
                    if resolved_gedcom_id and resolved_gedcom_id != original_gedcom_id:
                        link_row["original_gedcom_id"] = original_gedcom_id
                        link_row["redirected_from"] = original_gedcom_id
                    links[row["identity_id"]] = link_row
            return links

        links = _run_gedcom_query(_query, "GEDCOM face links load")
        _gedcom_face_links_cache = links
        _gedcom_face_links_cache_loaded_at = time.monotonic()
        _gedcom_face_links_cache_failed_at = 0.0
    except Exception as e:
        _gedcom_face_links_cache_failed_at = time.monotonic()
        logging.warning(f"Failed to load GEDCOM face links: {e}")
        return _gedcom_face_links_cache or {}

    return _gedcom_face_links_cache


def _load_gedcom_entity_redirects(entity_type: str = "individual", community_id: str = "rhodesli"):
    """Load GEDCOM redirect mappings for rekeyed or merged entities."""
    global _gedcom_redirects_cache, _gedcom_redirects_cache_loaded_at, _gedcom_redirects_cache_failed_at
    if _gedcom_redirects_cache is not None and _is_ttl_cache_fresh(
        _gedcom_redirects_cache_loaded_at, _GEDCOM_CACHE_TTL_SECONDS
    ):
        return _gedcom_redirects_cache.get((community_id, entity_type), {})
    if _failure_backoff_active(_gedcom_redirects_cache_failed_at, _GEDCOM_FAILURE_BACKOFF_SECONDS):
        return (_gedcom_redirects_cache or {}).get((community_id, entity_type), {})

    try:
        from app.supabase_data import get_supabase_client

        def _query():
            sb = get_supabase_client()
            if not sb:
                return {}
            try:
                rows = _load_gedcom_rows(
                    sb,
                    "gedcom_entity_redirects",
                    "community_id,entity_type,old_key,new_key",
                    order_by="old_key",
                )
            except Exception as exc:
                msg = str(exc)
                if "gedcom_entity_redirects" in msg or "PGRST205" in msg or "relation" in msg:
                    return {}
                raise

            grouped: dict[tuple[str, str], dict[str, str]] = {}
            for row in rows:
                row_community = row.get("community_id") or "rhodesli"
                row_entity_type = row.get("entity_type") or "individual"
                old_key = row.get("old_key")
                new_key = row.get("new_key")
                if not old_key or not new_key:
                    continue
                grouped.setdefault((row_community, row_entity_type), {})[old_key] = new_key
            return grouped

        redirect_groups = _run_gedcom_query(_query, "GEDCOM redirects load")
        _gedcom_redirects_cache = redirect_groups
        _gedcom_redirects_cache_loaded_at = time.monotonic()
        _gedcom_redirects_cache_failed_at = 0.0
    except Exception as e:
        _gedcom_redirects_cache_failed_at = time.monotonic()
        logging.warning(f"Failed to load GEDCOM redirects: {e}")
        return (_gedcom_redirects_cache or {}).get((community_id, entity_type), {})

    return _gedcom_redirects_cache.get((community_id, entity_type), {})


def _load_current_gedcom_relationship_edges():
    """Load current GEDCOM parent/spouse edges for tree rendering.

    The JSON relationship graph now acts as a manual overlay. Current GEDCOM
    relationships should come from Supabase so tree rendering follows the
    latest imported family structure.
    """
    global _gedcom_tree_relationships_cache
    global _gedcom_tree_relationships_cache_loaded_at, _gedcom_tree_relationships_cache_failed_at
    if _gedcom_tree_relationships_cache is not None and _is_ttl_cache_fresh(
        _gedcom_tree_relationships_cache_loaded_at, _GEDCOM_CACHE_TTL_SECONDS
    ):
        return _gedcom_tree_relationships_cache
    if _failure_backoff_active(_gedcom_tree_relationships_cache_failed_at, _GEDCOM_FAILURE_BACKOFF_SECONDS):
        return _gedcom_tree_relationships_cache or []

    try:
        from app.supabase_data import get_supabase_client

        def _query():
            sb = get_supabase_client()
            if not sb:
                return []
            select_fields = "individual_gedcom_id,related_gedcom_id,relationship_type,family_gedcom_id"
            try:
                rows = _load_gedcom_rows(sb, "current_gedcom_relationships", select_fields)
            except Exception as exc:
                msg = str(exc)
                if "current_gedcom_relationships" not in msg and "PGRST205" not in msg and "relation" not in msg:
                    raise
                # Session 162 (Codex P1.4): fallback to raw table MUST filter is_current
                # to avoid scanning 700k+ historical rows during the PostgREST flake window.
                rows = _load_gedcom_rows(
                    sb, "gedcom_relationships", select_fields, filters={"is_current": True}
                )
            edges = []
            seen_spouses = set()
            for row in rows:
                rel_type = row.get("relationship_type")
                person_a = row.get("individual_gedcom_id")
                person_b = row.get("related_gedcom_id")
                if not person_a or not person_b:
                    continue
                if rel_type == "parent":
                    edges.append(
                        {
                            "person_a": person_a,
                            "person_b": person_b,
                            "type": "parent_child",
                            "source": "gedcom_current",
                            "gedcom_family_id": row.get("family_gedcom_id"),
                        }
                    )
                elif rel_type == "spouse":
                    pair = tuple(sorted((person_a, person_b)))
                    if pair in seen_spouses:
                        continue
                    seen_spouses.add(pair)
                    edges.append(
                        {
                            "person_a": person_a,
                            "person_b": person_b,
                            "type": "spouse",
                            "source": "gedcom_current",
                            "gedcom_family_id": row.get("family_gedcom_id"),
                        }
                    )
            return edges

        edges = _run_gedcom_query(_query, "GEDCOM tree relationships load")
        _gedcom_tree_relationships_cache = edges
        _gedcom_tree_relationships_cache_loaded_at = time.monotonic()
        _gedcom_tree_relationships_cache_failed_at = 0.0
    except Exception as e:
        _gedcom_tree_relationships_cache_failed_at = time.monotonic()
        logging.warning(f"Failed to load current GEDCOM tree relationships: {e}")
        return _gedcom_tree_relationships_cache or []

    return _gedcom_tree_relationships_cache


def _normalize_gedcom_tree_edges(rows: list[dict]) -> list[dict]:
    """Normalize GEDCOM relationship rows into tree edges."""
    edges = []
    seen_spouses = set()
    for row in rows:
        rel_type = row.get("relationship_type")
        person_a = row.get("individual_gedcom_id")
        person_b = row.get("related_gedcom_id")
        if not person_a or not person_b:
            continue
        if rel_type == "parent":
            edges.append(
                {
                    "person_a": person_a,
                    "person_b": person_b,
                    "type": "parent_child",
                    "source": "gedcom_current",
                    "gedcom_family_id": row.get("family_gedcom_id"),
                }
            )
        elif rel_type == "spouse":
            pair = tuple(sorted((person_a, person_b)))
            if pair in seen_spouses:
                continue
            seen_spouses.add(pair)
            edges.append(
                {
                    "person_a": person_a,
                    "person_b": person_b,
                    "type": "spouse",
                    "source": "gedcom_current",
                    "gedcom_family_id": row.get("family_gedcom_id"),
                }
            )
    return edges


def _load_gedcom_relationship_edges_for_ids(gedcom_ids: list[str] | set[str] | tuple[str, ...]) -> list[dict]:
    """Load only the GEDCOM relationship edges touching the requested IDs."""
    ids = sorted({gid for gid in (gedcom_ids or []) if gid})
    if not ids:
        return []
    if _gedcom_tree_relationships_cache is not None and _is_ttl_cache_fresh(
        _gedcom_tree_relationships_cache_loaded_at, _GEDCOM_CACHE_TTL_SECONDS
    ):
        id_set = set(ids)
        return [
            edge
            for edge in _gedcom_tree_relationships_cache
            if edge.get("person_a") in id_set or edge.get("person_b") in id_set
        ]

    try:
        from app.supabase_data import get_supabase_client

        def _query():
            sb = get_supabase_client()
            if not sb:
                return []
            select_fields = "individual_gedcom_id,related_gedcom_id,relationship_type,family_gedcom_id"
            rows = []
            for i in range(0, len(ids), 25):
                chunk = ids[i : i + 25]
                filter_expr = ",".join(
                    f"{column}.eq.{gid}" for gid in chunk for column in ("individual_gedcom_id", "related_gedcom_id")
                )
                try:
                    resp = sb.table("current_gedcom_relationships").select(select_fields).or_(filter_expr).execute()
                except Exception as exc:
                    msg = str(exc)
                    if "current_gedcom_relationships" not in msg and "PGRST205" not in msg and "relation" not in msg:
                        raise
                    # Session 162 (Codex P1.4): same is_current filter requirement on the
                    # targeted-edges path. Without this filter we pull historical rows
                    # too and burn the IO we just stopped burning on the main path.
                    resp = (
                        sb.table("gedcom_relationships")
                        .select(select_fields)
                        .eq("is_current", True)
                        .or_(filter_expr)
                        .execute()
                    )
                if resp and resp.data:
                    rows.extend(resp.data)
            return _normalize_gedcom_tree_edges(rows)

        return _run_gedcom_query(_query, "GEDCOM tree targeted relationships load")
    except Exception as e:
        logging.warning(f"Failed to load targeted GEDCOM tree relationships: {e}")
        return []


def _load_gedcom_individuals_by_ids(
    gedcom_ids: list[str] | set[str] | tuple[str, ...], include_rich: bool = False
) -> list[dict]:
    """Load only the GEDCOM individuals needed for a targeted tree slice."""
    ids = sorted({gid for gid in (gedcom_ids or []) if gid})
    if not ids:
        return []
    if _gedcom_individuals_cache is not None and _is_ttl_cache_fresh(
        _gedcom_individuals_cache_loaded_at, _GEDCOM_CACHE_TTL_SECONDS
    ):
        id_set = set(ids)
        return [row for row in _gedcom_individuals_cache if row.get("gedcom_id") in id_set]

    select_fields = _GEDCOM_RICH_FIELDS if include_rich else _GEDCOM_THIN_FIELDS
    try:
        from app.supabase_data import get_supabase_client

        def _query():
            sb = get_supabase_client()
            if not sb:
                return []
            rows = []
            for i in range(0, len(ids), 100):
                chunk = ids[i : i + 100]
                # PRD-063 Day 3 (Session 158b): prefer v2 view, then v1 view, then v1 table
                resp = None
                try:
                    resp = (
                        sb.table("current_gedcom_individuals_v2").select(select_fields).in_("gedcom_id", chunk).execute()
                    )
                except Exception as exc_v2:
                    msg_v2 = str(exc_v2)
                    if "current_gedcom_individuals_v2" not in msg_v2 and "PGRST205" not in msg_v2 and "relation" not in msg_v2:
                        raise
                if resp is None:
                    try:
                        resp = (
                            sb.table("current_gedcom_individuals").select(select_fields).in_("gedcom_id", chunk).execute()
                        )
                    except Exception as exc:
                        msg = str(exc)
                        if "current_gedcom_individuals" not in msg and "PGRST205" not in msg and "relation" not in msg:
                            raise
                        resp = sb.table("gedcom_individuals").select(select_fields).in_("gedcom_id", chunk).execute()
                if resp and resp.data:
                    rows.extend(resp.data)
            return rows

        return _run_gedcom_query(_query, "GEDCOM targeted individuals load")
    except Exception as e:
        logging.warning(f"Failed to load targeted GEDCOM individuals: {e}")
        return []


def _invalidate_gedcom_cache():
    """Invalidate GEDCOM caches after link/unlink operations."""
    global _gedcom_individuals_cache_loaded_at, _gedcom_individuals_cache_failed_at
    global _gedcom_face_links_cache, _gedcom_face_links_cache_loaded_at, _gedcom_face_links_cache_failed_at
    global _gedcom_redirects_cache, _gedcom_redirects_cache_loaded_at, _gedcom_redirects_cache_failed_at
    global _gedcom_tree_relationships_cache, _gedcom_tree_relationships_cache_loaded_at
    global _gedcom_tree_relationships_cache_failed_at
    _gedcom_individuals_cache_loaded_at = 0.0
    _gedcom_individuals_cache_failed_at = 0.0
    _gedcom_face_links_cache = None
    _gedcom_face_links_cache_loaded_at = 0.0
    _gedcom_face_links_cache_failed_at = 0.0
    _gedcom_redirects_cache = None
    _gedcom_redirects_cache_loaded_at = 0.0
    _gedcom_redirects_cache_failed_at = 0.0
    _gedcom_tree_relationships_cache = None
    _gedcom_tree_relationships_cache_loaded_at = 0.0
    _gedcom_tree_relationships_cache_failed_at = 0.0


def _load_gedcom_versions():
    """Load GEDCOM version history from Supabase. Returns list of version dicts, newest first."""
    try:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return []
        resp = sb.table("gedcom_versions").select("*").order("version_number", desc=True).execute()
        return resp.data if resp and resp.data else []
    except Exception as e:
        logging.warning(f"Failed to load GEDCOM versions: {e}")
        return []


def _load_gedcom_enrichment_queue_count():
    """Load count of pending GEDCOM re-enrichment items from Supabase."""
    try:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return 0
        resp = sb.table("gedcom_enrichment_queue").select("id", count="exact").eq("status", "pending").execute()
        return (
            resp.count
            if resp and hasattr(resp, "count") and resp.count
            else len(resp.data)
            if resp and resp.data
            else 0
        )
    except Exception as e:
        logging.warning(f"Failed to load enrichment queue count: {e}")
        return 0


# Temporary storage for versioned GEDCOM upload preview (diff before apply)
_gedcom_upload_preview = None


def _search_gedcom_individuals(query: str, limit: int = 20, offset: int = 0) -> tuple:
    """Search GEDCOM individuals by name. Fuzzy, case-insensitive.

    Returns (results_page, total_count) where results_page is a list of dicts
    with match info, sorted by relevance.
    """
    if not query or len(query.strip()) < 3:
        return [], 0

    import time as _time

    _t0 = _time.monotonic()
    individuals = _query_gedcom_search_candidates(query)
    if not individuals:
        individuals = _main_mod._load_gedcom_individuals()
    if not individuals:
        logger.info("gedcom_search", gedcom_search_ms=0, query=query.strip(), result_count=0, source="empty")
        return [], 0

    query_lower = query.strip().lower()
    query_parts = query_lower.split()

    # Sephardic surname variants (common in Rhodes community)
    SURNAME_VARIANTS = {
        "capeluto": {"capelluto", "capelouto", "capuano", "capouano", "capueto"},
        "capelluto": {"capeluto", "capelouto", "capuano", "capouano", "capueto"},
        "capuano": {"capeluto", "capelluto", "capelouto", "capouano", "capueto"},
        "capouano": {"capeluto", "capelluto", "capelouto", "capuano", "capueto"},
        "israel": {"yisrael"},
        "yisrael": {"israel"},
        "moussafer": {"mosafir", "musafir"},
        "mosafir": {"moussafer", "musafir"},
        "sedikaro": {"sedicaro"},
        "sedicaro": {"sedikaro"},
        "pizante": {"pizanti"},
        "pizanti": {"pizante"},
        "benveniste": {"benvenisti"},
        "benvenisti": {"benveniste"},
    }

    import difflib

    results_by_xref = {}
    for row in individuals:
        name = (row.get("name") or "").lower()
        given = (row.get("given_name") or "").lower()
        surname = (row.get("surname") or "").lower()

        score = 0.0

        # Exact full name match
        if query_lower == name:
            score = 1.0
        # All query parts found in name
        elif all(p in name for p in query_parts):
            score = 0.85
        # Fuzzy match and surname variations handling
        else:
            # Check surname direct or variant match
            surname_match = False
            q_surname = query_parts[-1] if len(query_parts) >= 2 else query_parts[0]
            if (
                q_surname == surname
                or q_surname in SURNAME_VARIANTS.get(surname, set())
                or surname in SURNAME_VARIANTS.get(q_surname, set())
            ):
                surname_match = True

            # Use SequenceMatcher for given name or full string comparison
            if surname_match and len(query_parts) >= 2:
                q_given = query_parts[0]
                given_ratio = difflib.SequenceMatcher(None, q_given, given).ratio()
                if given_ratio > 0.8:
                    score = 0.9
                elif given_ratio > 0.6:
                    score = 0.7
                else:
                    score = 0.4
            else:
                # Fallback to general fuzzy ratio against the whole name
                ratio = difflib.SequenceMatcher(None, query_lower, name).ratio()
                if ratio > 0.7:
                    score = ratio

        if score < 0.3:
            import difflib

            sim = difflib.SequenceMatcher(None, query_lower, name).ratio()
            if sim > 0.6:
                score = sim * 0.8
            else:
                continue

        # Extract birth/death years
        birth_year = None
        death_year = None
        bd = row.get("birth_date") or ""
        dd = row.get("death_date") or ""
        for s in [bd]:
            for part in s.split():
                if part.isdigit() and 1400 < int(part) < 2100:
                    birth_year = int(part)
                    break
        for s in [dd]:
            for part in s.split():
                if part.isdigit() and 1400 < int(part) < 2100:
                    death_year = int(part)
                    break

        # Bonus scoring: people with dates are more useful (B1)
        if birth_year or death_year:
            score += 0.05
        # Bonus: Rhodes connection
        bp = (row.get("birth_place") or "").lower()
        dp = (row.get("death_place") or "").lower()
        if "rhodes" in bp or "rhodes" in dp or "rodi" in bp or "rodi" in dp:
            score += 0.05

        xref_id = row.get("gedcom_id")
        if not xref_id:
            continue
        candidate = {
            "xref_id": xref_id,
            "full_name": row.get("name") or "Unknown",
            "birth_year": birth_year,
            "death_year": death_year,
            "birth_place": row.get("birth_place"),
            "death_place": row.get("death_place"),
            "score": score,
        }
        existing = results_by_xref.get(xref_id)
        if existing is None or candidate["score"] > existing["score"]:
            results_by_xref[xref_id] = candidate

    results = list(results_by_xref.values())

    # Sort by score descending, then by name
    results.sort(key=lambda x: (-x["score"], x["full_name"]))
    total = len(results)
    _elapsed_ms = round((_time.monotonic() - _t0) * 1000, 1)
    logger.info(
        "gedcom_search",
        gedcom_search_ms=_elapsed_ms,
        query=query.strip(),
        result_count=total,
        candidates_scanned=len(individuals),
    )
    return results[offset : offset + limit], total


def _query_gedcom_search_candidates(query: str, candidate_limit: int = 500) -> list[dict]:
    """Prefilter GEDCOM candidates in Supabase before fuzzy scoring in Python."""
    if not query or len(query.strip()) < 3:
        return []

    query_lower = query.strip().lower()
    query_parts = [part for part in query_lower.split() if part]
    if not query_parts:
        return []

    # Sephardic surname variants (common in Rhodes community)
    surname_variants = {
        "capeluto": {"capelluto", "capelouto", "capuano", "capouano", "capueto"},
        "capelluto": {"capeluto", "capelouto", "capuano", "capouano", "capueto"},
        "capuano": {"capeluto", "capelluto", "capelouto", "capouano", "capueto"},
        "capouano": {"capeluto", "capelluto", "capelouto", "capuano", "capueto"},
        "israel": {"yisrael"},
        "yisrael": {"israel"},
        "moussafer": {"mosafir", "musafir"},
        "mosafir": {"moussafer", "musafir"},
        "sedikaro": {"sedicaro"},
        "sedicaro": {"sedikaro"},
        "pizante": {"pizanti"},
        "pizanti": {"pizante"},
        "benveniste": {"benvenisti"},
        "benvenisti": {"benveniste"},
    }

    terms = {query_lower}
    if len(query_parts) >= 2:
        surname_term = query_parts[-1]
        terms.add(surname_term)
        terms.update(surname_variants.get(surname_term, set()))
    else:
        only_term = query_parts[0]
        terms.add(only_term)
        terms.update(surname_variants.get(only_term, set()))

    filters = []
    for term in sorted({t for t in terms if t}):
        escaped = term.replace(",", r"\,")
        filters.extend(
            [
                f"name.ilike.%{escaped}%",
                f"given_name.ilike.%{escaped}%",
                f"surname.ilike.%{escaped}%",
            ]
        )

    try:
        from app.supabase_data import get_supabase_client

        def _query():
            sb = get_supabase_client()
            if not sb:
                return []
            filter_expr = ",".join(dict.fromkeys(filters))
            # PRD-063 Day 3 (Session 158b): prefer v2 view, then v1 view, then v1 table
            resp = None
            try:
                resp = (
                    sb.table("current_gedcom_individuals_v2")
                    .select(_GEDCOM_THIN_FIELDS)
                    .or_(filter_expr)
                    .order("gedcom_id")
                    .range(0, candidate_limit - 1)
                    .execute()
                )
            except Exception as exc_v2:
                msg_v2 = str(exc_v2)
                if "current_gedcom_individuals_v2" not in msg_v2 and "PGRST205" not in msg_v2 and "relation" not in msg_v2:
                    raise
            if resp is None:
                try:
                    resp = (
                        sb.table("current_gedcom_individuals")
                        .select(_GEDCOM_THIN_FIELDS)
                        .or_(filter_expr)
                        .order("gedcom_id")
                        .range(0, candidate_limit - 1)
                        .execute()
                    )
                except Exception as exc:
                    msg = str(exc)
                    if "current_gedcom_individuals" not in msg and "PGRST205" not in msg and "relation" not in msg:
                        raise
                    resp = (
                        sb.table("gedcom_individuals")
                        .select(_GEDCOM_THIN_FIELDS)
                        .or_(filter_expr)
                        .order("gedcom_id")
                        .range(0, candidate_limit - 1)
                        .execute()
                    )
            return resp.data if resp and resp.data else []

        return _run_gedcom_query(_query, "GEDCOM search prefilter")
    except Exception as e:
        logging.warning(f"GEDCOM search prefilter failed, falling back to in-memory scan: {e}")
        return []


def _person_gedcom_link_section(person_id: str, display_name: str, is_admin: bool):
    """Render GEDCOM link info on person page. Shows current link or link panel for admins."""
    if not is_admin:
        return None

    existing_links = _main_mod._load_gedcom_face_links()
    link = existing_links.get(person_id)

    if link:
        # Already linked — show linked GEDCOM individual with unlink option
        gedcom_id = link.get("gedcom_id", "")
        # Look up the GEDCOM person's name for display
        _gedcom_display_name = None
        if gedcom_id:
            try:
                _gedcom_rows = _load_gedcom_individuals_by_ids([gedcom_id])
                if _gedcom_rows:
                    _gedcom_display_name = _gedcom_rows[0].get("display_name") or _gedcom_rows[0].get("name")
            except Exception:
                pass
        _gedcom_label = _gedcom_display_name or gedcom_id or "Unknown"
        return Div(
            H3("Family Tree Link", cls="text-lg font-serif font-semibold text-slate-300 mb-4"),
            Div(
                Div(
                    Span("Linked GEDCOM record: ", cls="text-slate-400 text-sm"),
                    Span(_gedcom_label, cls="text-white font-medium text-sm"),
                    Span(f" ({gedcom_id})", cls="text-slate-500 text-xs ml-1") if _gedcom_display_name else None,
                    cls="flex items-baseline flex-wrap gap-1",
                ),
                P(
                    f"Link auto-resolved from retired GEDCOM id {link.get('redirected_from')}",
                    cls="text-xs text-amber-300 mt-1",
                )
                if link.get("redirected_from")
                else None,
                P(
                    "Use Family Tree or Connect to inspect linked family context without blocking the person page.",
                    cls="text-xs text-slate-500 mt-1",
                ),
                Button(
                    "Unlink",
                    cls="mt-2 px-3 py-1 text-xs text-red-400 hover:text-red-300 border border-red-800 "
                    "hover:border-red-600 rounded transition-colors",
                    hx_post="/api/gedcom/unlink",
                    hx_vals=json.dumps({"identity_id": person_id, "gedcom_id": gedcom_id}),
                    hx_target=f"#gedcom-link-panel-{person_id}",
                    hx_swap="outerHTML",
                    hx_confirm="Unlink this person from the family tree?",
                ),
                id=f"gedcom-link-panel-{person_id}",
                cls="p-3 bg-emerald-900/20 border border-emerald-700/30 rounded-lg",
            ),
            id="gedcom",
            cls="mt-10 pt-8 border-t border-slate-800 scroll-mt-20",
            data_testid="gedcom-link-section",
        )
    else:
        # Not linked — show link search panel
        return Div(
            H3("Family Tree Link", cls="text-lg font-serif font-semibold text-slate-300 mb-4"),
            _main_mod._gedcom_link_panel(person_id, display_name),
            id="gedcom",
            cls="mt-10 pt-8 border-t border-slate-800 scroll-mt-20",
            data_testid="gedcom-link-section",
        )


def _gedcom_link_panel(identity_id: str, identity_name: str) -> Div:
    """Render the 'Link to Family Tree' panel for post-confirm GEDCOM linking."""
    if not identity_name:
        try:
            identity = _main_mod.load_registry().get_identity(identity_id)
            identity_name = identity.get("name", "")
        except Exception:
            identity_name = ""
    return Div(
        Div(
            H3("Link to Family Tree", cls="text-base font-semibold text-white"),
            P(f"Connect {identity_name} to their genealogical record.", cls="text-sm text-slate-400 mt-1"),
            cls="mb-3",
        ),
        # Search input
        Div(
            Input(
                type="text",
                name="q",
                value=identity_name,
                placeholder="Search by name...",
                cls="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm",
                hx_get=f"/api/gedcom/search?identity_id={identity_id}",
                hx_trigger="input changed delay:300ms",
                minlength="3",
                hx_target=f"#gedcom-results-{identity_id}",
                hx_include="this",
            ),
            cls="mb-3",
        ),
        # Results container (populated by HTMX)
        Div(id=f"gedcom-results-{identity_id}", cls="max-h-60 overflow-y-auto"),
        # Skip button
        Div(
            Button(
                "No match — skip",
                cls="px-4 py-2 text-sm text-slate-400 hover:text-white border border-slate-600 "
                "hover:border-slate-500 rounded transition-colors",
                data_action="gedcom-link-skip",
                data_identity_id=identity_id,
            ),
            cls="mt-3 text-center",
        ),
        # Script for skip (dismiss panel)
        Script("""
            document.addEventListener('click', function(e) {
                var btn = e.target.closest('[data-action="gedcom-link-skip"]');
                if (btn) {
                    var panel = btn.closest('.gedcom-link-panel');
                    if (panel) panel.remove();
                }
            });
        """),
        id=f"gedcom-link-panel-{identity_id}",
        cls="gedcom-link-panel mt-4 p-4 bg-slate-800/50 border border-slate-700 rounded-lg",
    )


@rt("/api/gedcom/search")
def get(q: str = "", identity_id: str = "", offset: int = 0, sess=None):
    """Search GEDCOM individuals by name. Admin only.

    Returns HTMX fragment with selectable results. Supports pagination
    via offset parameter with "Show more" button (B1).
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    page_size = 10
    results, total = _main_mod._search_gedcom_individuals(q, limit=page_size, offset=offset)

    if not results:
        if offset == 0:
            return Div(
                P("No matches found.", cls="text-slate-500 text-sm py-2"),
            )
        else:
            return Div(
                P("No more results.", cls="text-slate-500 text-sm py-2"),
            )

    # Check which individuals are already linked to this identity
    existing_links = _main_mod._load_gedcom_face_links()
    current_link = existing_links.get(identity_id, {})
    current_xref = current_link.get("gedcom_id") if current_link else None

    items = []
    for r in results:
        xref = r["xref_id"]
        is_linked = xref == current_xref

        # Build display info — label locations explicitly to avoid ambiguity
        life_span = []
        birth_parts = []
        if r.get("birth_year"):
            birth_parts.append(f"b. {r['birth_year']}")
        if r.get("birth_place"):
            # Prefix with "b." if place-only (no year) to avoid ambiguity
            if not r.get("birth_year"):
                birth_parts.append(f"b. {r['birth_place']}")
            else:
                birth_parts.append(r["birth_place"])
        if birth_parts:
            life_span.append(", ".join(birth_parts))
        death_parts = []
        if r.get("death_year"):
            death_parts.append(f"d. {r['death_year']}")
        if r.get("death_place"):
            if not r.get("death_year"):
                death_parts.append(f"d. {r['death_place']}")
            else:
                death_parts.append(r["death_place"])
        if death_parts:
            life_span.append(", ".join(death_parts))

        # Match strength indicator (B1)
        score = r.get("score", 0)
        if score >= 0.9:
            match_cls = "text-emerald-400"
            match_label = "Strong"
        elif score >= 0.7:
            match_cls = "text-amber-400"
            match_label = "Good"
        else:
            match_cls = "text-slate-500"
            match_label = "Partial"

        item = Div(
            Div(
                Div(
                    Span(r["full_name"], cls="text-white font-medium text-sm"),
                    Span(match_label, cls=f"text-[10px] {match_cls} ml-1.5 font-medium"),
                    cls="flex items-center",
                ),
                Span(" · ".join(life_span) if life_span else "No dates", cls="text-slate-400 text-xs"),
                cls="flex flex-col gap-0.5",
            ),
            Button(
                "Linked" if is_linked else "Link",
                cls=(
                    "px-3 py-1 text-xs rounded font-medium shrink-0 "
                    + (
                        "bg-emerald-600/30 text-emerald-400 cursor-default"
                        if is_linked
                        else "bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer"
                    )
                ),
                hx_post="/api/gedcom/link",
                hx_vals=json.dumps({"identity_id": identity_id, "gedcom_id": xref}),
                hx_target=f"#gedcom-link-panel-{identity_id}",
                hx_swap="outerHTML",
                disabled=is_linked,
            )
            if not is_linked
            else Span(
                "Linked", cls="px-3 py-1 text-xs rounded font-medium bg-emerald-600/30 text-emerald-400 shrink-0"
            ),
            cls="flex items-center justify-between py-2 px-3 hover:bg-slate-700/50 rounded transition-colors",
        )
        items.append(item)

    # Show result count header
    count_header = (
        P(
            f'{total} result{"s" if total != 1 else ""} for "{q}"',
            cls="text-xs text-slate-500 px-3 pb-1 mb-1 border-b border-slate-700/50",
        )
        if total > 0
        else None
    )

    # Proper Pagination Controls
    pagination_controls = []

    if total > page_size:
        prev_offset = max(0, offset - page_size)
        next_offset = offset + page_size
        current_page = (offset // page_size) + 1
        total_pages = (total + page_size - 1) // page_size

        btn_cls = "px-3 py-1.5 text-xs font-medium rounded transition-colors"
        btn_active = "text-indigo-400 bg-slate-800 hover:bg-slate-700"
        btn_disabled = "text-slate-600 bg-slate-800/50 cursor-not-allowed"

        # Prev Button
        prev_btn = Button(
            "← Prev",
            cls=f"{btn_cls} {btn_active if offset > 0 else btn_disabled}",
            disabled=(offset == 0),
            **(
                {
                    "hx_get": f"/api/gedcom/search?q={quote(q)}&identity_id={identity_id}&offset={prev_offset}",
                    "hx_target": f"#gedcom-results-{identity_id}",
                    "hx_swap": "innerHTML",
                }
                if offset > 0
                else {}
            ),
        )

        # Next Button
        next_btn = Button(
            "Next →",
            cls=f"{btn_cls} {btn_active if next_offset < total else btn_disabled}",
            disabled=(next_offset >= total),
            **(
                {
                    "hx_get": f"/api/gedcom/search?q={quote(q)}&identity_id={identity_id}&offset={next_offset}",
                    "hx_target": f"#gedcom-results-{identity_id}",
                    "hx_swap": "innerHTML",
                }
                if next_offset < total
                else {}
            ),
        )

        pagination_controls = [
            Div(
                prev_btn,
                Span(f"Page {current_page} of {total_pages}", cls="text-xs text-slate-500"),
                next_btn,
                cls="flex items-center justify-between mt-3 pt-3 border-t border-slate-700/50 w-full",
            )
        ]

    return Div(count_header, Div(*items, cls="space-y-0.5"), *pagination_controls)


@rt("/api/gedcom/link")
def post(identity_id: str = "", gedcom_id: str = "", sess=None):
    """Link an identity to a GEDCOM individual. Admin only.

    Saves to gedcom_face_links table in Supabase.
    Returns success confirmation that replaces the link panel.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not identity_id or not gedcom_id:
        return Response("Missing identity_id or gedcom_id", status_code=400)

    # Look up the GEDCOM individual for display
    gedcom_row = _main_mod._load_gedcom_individual(gedcom_id)
    gedcom_name = "Unknown"
    birth_year = None
    death_year = None
    if gedcom_row:
        gedcom_name = gedcom_row.get("name") or "Unknown"
        bd = gedcom_row.get("birth_date") or ""
        dd = gedcom_row.get("death_date") or ""
        for part in bd.split():
            if part.isdigit() and 1400 < int(part) < 2100:
                birth_year = int(part)
                break
        for part in dd.split():
            if part.isdigit() and 1400 < int(part) < 2100:
                death_year = int(part)
                break

    # Save to Supabase
    try:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return Response("Supabase unavailable", status_code=503)

        user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
        linked_by = (user.id if user else "admin") if _main_mod.is_auth_enabled() else "admin"

        sb.table("gedcom_face_links").upsert(
            {
                "identity_id": identity_id,
                "gedcom_id": gedcom_id,
                "confidence": 1.0,
                "linked_by": f"admin-web:{linked_by}",
            },
            on_conflict="identity_id,gedcom_id",
        ).execute()

        # Also enrich the identity with birth/death data and name from GEDCOM
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id) if identity_id else None
        current_name = identity.get("name", "") if identity else ""
        auto_named = current_name.startswith("Unidentified Person") or not current_name.strip()

        # Auto-rename to GEDCOM name if identity still has auto-generated name
        if auto_named and gedcom_name and gedcom_name != "Unknown":
            try:
                registry.rename_identity(identity_id, gedcom_name, user_source="gedcom-link")
            except (KeyError, ValueError):
                pass

        updates = {}
        if birth_year:
            updates["birth_year"] = birth_year
        if death_year:
            updates["death_year"] = death_year
        if updates:
            registry.set_metadata(identity_id, updates, user_source="gedcom-link")
        if auto_named or updates:
            _main_mod.save_registry(registry, changed_ids={identity_id})

        _main_mod._invalidate_gedcom_cache()
    except Exception as e:
        logging.error(f"GEDCOM link failed: {e}")
        return Response(f"Link failed: {e}", status_code=500)

    # Build lifespan string
    life_parts = []
    if birth_year:
        life_parts.append(f"b. {birth_year}")
    if death_year:
        life_parts.append(f"d. {death_year}")
    life_str = f" ({' — '.join(life_parts)})" if life_parts else ""

    # Determine final display name (GEDCOM name if auto-renamed, else current name)
    final_name = gedcom_name if (auto_named and gedcom_name and gedcom_name != "Unknown") else current_name
    name_saved_note = f" — Named: {final_name}" if auto_named and gedcom_name and gedcom_name != "Unknown" else ""

    link_panel = Div(
        Div(
            Span(f"Linked to Family Tree{name_saved_note}", cls="text-emerald-400 font-medium text-sm"),
            cls="mb-1",
        ),
        Div(
            Span(f"{gedcom_name}{life_str}", cls="text-white text-sm"),
            cls="mb-2",
        ),
        Button(
            "Unlink",
            cls="px-3 py-1 text-xs text-red-400 hover:text-red-300 border border-red-800 "
            "hover:border-red-600 rounded transition-colors",
            hx_post="/api/gedcom/unlink",
            hx_vals=json.dumps({"identity_id": identity_id, "gedcom_id": gedcom_id}),
            hx_target=f"#gedcom-link-panel-{identity_id}",
            hx_swap="outerHTML",
            hx_confirm="Unlink this person from the family tree?",
        ),
        id=f"gedcom-link-panel-{identity_id}",
        cls="mt-4 p-4 bg-emerald-900/20 border border-emerald-700/30 rounded-lg",
    )

    # OOB swap: update name input with GEDCOM name if auto-renamed
    if auto_named and gedcom_name and gedcom_name != "Unknown":
        name_oob = Input(
            type="text",
            name="new_name",
            value=final_name,
            cls="flex-1 px-4 py-2 bg-slate-800 border border-emerald-600 rounded-lg text-white "
            "placeholder-slate-400 focus:outline-none focus:border-purple-500",
            id="enrichment-name-input",
            hx_swap_oob="true",
        )
        return link_panel, name_oob

    return link_panel


@rt("/api/gedcom/unlink")
def post(identity_id: str = "", gedcom_id: str = "", sess=None):
    """Unlink an identity from a GEDCOM individual. Admin only.

    Soft-deletes by removing the row from gedcom_face_links.
    Returns the link panel so the admin can re-link if needed.
    """
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    if not identity_id:
        return Response("Missing identity_id", status_code=400)

    try:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return Response("Supabase unavailable", status_code=503)

        sb.table("gedcom_face_links").delete().eq("identity_id", identity_id).execute()
        _main_mod._invalidate_gedcom_cache()
    except Exception as e:
        logging.error(f"GEDCOM unlink failed: {e}")
        return Response(f"Unlink failed: {e}", status_code=500)

    # Get identity name for the re-link panel
    try:
        registry = _main_mod.load_registry()
        identity = registry.get_identity(identity_id)
        identity_name = ensure_utf8_display(identity.get("name", "Unknown"))
    except KeyError:
        identity_name = "Unknown"

    return _main_mod._gedcom_link_panel(identity_id, identity_name)


# --- Admin Review Queue (Feature 5: Active Learning Priority Queue) ---


@rt("/api/photo/{photo_id}/confirm-date")
async def post(photo_id: str, sess=None):
    """Confirm AI date estimate — sets source to 'human' without changing the value."""
    denied = _main_mod._check_admin(sess)
    if denied:
        return denied

    labels = _main_mod._load_date_labels()
    label = labels.get(photo_id)
    if not label:
        return Div(Span("Label not found", cls="text-red-400"), id=f"review-{photo_id[:8]}")

    # Log confirmation
    import uuid
    from datetime import datetime, timezone

    user = _main_mod.get_current_user(sess or {}) if _main_mod.is_auth_enabled() else None
    correction_entry = {
        "id": f"corr_{uuid.uuid4().hex[:12]}",
        "photo_id": photo_id,
        "field": "estimated_decade",
        "old_value": {"decade": label.get("estimated_decade"), "year": label.get("best_year_estimate")},
        "new_value": {"decade": label.get("estimated_decade"), "year": label.get("best_year_estimate")},
        "old_source": label.get("source", "gemini"),
        "new_source": "human",
        "contributor_email": user.email if user else "local",
        "contributor_type": "admin",
        "status": "confirmed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    log = _main_mod._load_corrections_log()
    log["corrections"].append(correction_entry)
    _main_mod._save_corrections_log(log)

    # Update in-memory label
    label["source"] = "human"

    return Div(
        Span("\u2713 Confirmed", cls="text-emerald-400 text-sm"),
        cls="p-3 bg-emerald-950/30 rounded-lg border border-emerald-700/30 text-center",
        id=f"review-{photo_id[:8]}",
    )
