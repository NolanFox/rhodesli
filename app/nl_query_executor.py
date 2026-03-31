"""
Natural Language Query Executor — runs parsed intents against Supabase.

Takes the output of rhodesli_ml.nl_query.parse_query_intent() and
executes the appropriate queries against Supabase tables.

All queries use parameterized Supabase client methods (ilike, gte, lte)
— no string interpolation for SQL.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def _sanitize_postgrest_value(value: str) -> str:
    """Strip PostgREST metacharacters to prevent filter injection via .or_().

    Security audit Finding 1 (Session 134): .or_() takes raw PostgREST filter
    strings. Commas, periods, and parens in values can alter filter logic.
    """
    return re.sub(r"[^a-zA-Z0-9 '\-]", "", value)


def _escape_ilike(value: str) -> str:
    """Escape ILIKE special characters (%, _) in user-provided search terms.

    Security audit Finding 2 (Session 134): unescaped % matches all rows,
    _ matches any single character.
    """
    return value.replace("%", r"\%").replace("_", r"\_")


def execute_query(intent_result: dict[str, Any], supabase_client=None) -> dict[str, Any]:
    """
    Execute a parsed NL query intent against Supabase.

    Args:
        intent_result: Output from parse_query_intent()
        supabase_client: Supabase client (from get_supabase_client())

    Returns:
        dict with:
          - result_type: one of "persons", "photos", "aggregate", "message"
          - items: list of result dicts (for persons/photos)
          - message: str (for message/aggregate types)
          - query_summary: human-readable description of what was searched
    """
    intent = intent_result.get("intent", "unknown")

    if supabase_client is None:
        return {
            "result_type": "message",
            "items": [],
            "message": "Search is temporarily unavailable (database not connected).",
            "query_summary": "Database unavailable",
        }

    try:
        if intent == "person_search":
            return _execute_person_search(intent_result, supabase_client)
        elif intent == "photo_filter":
            return _execute_photo_filter(intent_result, supabase_client)
        elif intent == "aggregate":
            return _execute_aggregate(intent_result, supabase_client)
        elif intent == "relationship":
            return _execute_relationship(intent_result)
        else:
            return _execute_unknown(intent_result)
    except Exception:
        logger.exception("NL query execution failed for intent=%s", intent)
        return {
            "result_type": "message",
            "items": [],
            "message": "Something went wrong executing your search. Please try again.",
            "query_summary": "Error",
        }


def _execute_person_search(intent_result: dict, sb) -> dict[str, Any]:
    """Search identities by name using ILIKE."""
    name = intent_result.get("entities", {}).get("name", "")
    if not name:
        return {
            "result_type": "message",
            "items": [],
            "message": "Please provide a name to search for.",
            "query_summary": "Empty name search",
        }

    result = (
        sb.table("identities")
        .select("identity_id, name, state, anchor_ids")
        .ilike("name", f"%{_escape_ilike(name)}%")
        .neq("state", "MERGED")
        .limit(50)
        .execute()
    )

    items = []
    for row in result.data or []:
        anchor_ids = row.get("anchor_ids") or []
        if isinstance(anchor_ids, str):
            import json

            try:
                anchor_ids = json.loads(anchor_ids)
            except (json.JSONDecodeError, TypeError):
                anchor_ids = []
        items.append(
            {
                "identity_id": row["identity_id"],
                "name": row.get("name", "Unknown"),
                "state": row.get("state", "INBOX"),
                "face_count": len(anchor_ids),
            }
        )

    return {
        "result_type": "persons",
        "items": items,
        "message": f'Found {len(items)} {"person" if len(items) == 1 else "people"} matching "{name}"',
        "query_summary": f'People matching "{name}"',
    }


def _execute_photo_filter(intent_result: dict, sb) -> dict[str, Any]:
    """Filter photos by decade, year, location, or type.

    Temporal filters query the date_labels table (not photos — photos has no
    date_estimate column). Non-temporal filters query photos directly.
    """
    filters = intent_result.get("filters", {})

    has_temporal = any(k in filters for k in ("decade", "year", "year_start", "year_end"))
    query_desc_parts = []
    temporal_photo_ids = None

    if has_temporal:
        # Step 1: Get matching photo_ids from date_labels (no FK to photos)
        dl_query = sb.table("date_labels").select("photo_id, best_year_estimate")

        if "decade" in filters:
            decade_str = filters["decade"]  # e.g. "1940s"
            decade_start = int(decade_str.rstrip("s"))
            decade_end = decade_start + 9
            dl_query = dl_query.gte("best_year_estimate", decade_start).lte("best_year_estimate", decade_end)
            query_desc_parts.append(f"from the {decade_str}")

        if "year" in filters:
            year = filters["year"]
            dl_query = dl_query.eq("best_year_estimate", year)
            query_desc_parts.append(f"from {year}")

        if "year_start" in filters:
            dl_query = dl_query.gte("best_year_estimate", filters["year_start"])
            query_desc_parts.append(f"after {filters['year_start']}")

        if "year_end" in filters:
            dl_query = dl_query.lte("best_year_estimate", filters["year_end"])
            query_desc_parts.append(f"before {filters['year_end']}")

        dl_result = dl_query.limit(100).execute()
        temporal_photo_ids = {row["photo_id"]: row.get("best_year_estimate") for row in (dl_result.data or [])}

        if not temporal_photo_ids:
            return {
                "result_type": "photos",
                "items": [],
                "message": f"No photos found {', '.join(query_desc_parts)}",
                "query_summary": "Photos " + ", ".join(query_desc_parts),
            }

        # Step 2: Get photo details for matching IDs
        query = (
            sb.table("photos")
            .select("photo_id, path, source, collection, upload_date")
            .in_("photo_id", list(temporal_photo_ids.keys())[:50])
        )
    else:
        query = sb.table("photos").select("photo_id, path, source, collection, upload_date")

    # Location and photo_type filters only work on non-temporal queries (direct photos table).
    # For temporal queries (date_labels join), these would need PostgREST nested filters
    # which aren't supported yet — skip gracefully.
    if not has_temporal:
        # Location filter — SEC-001: sanitize + escape before .or_()
        if "location" in filters:
            loc = _escape_ilike(_sanitize_postgrest_value(filters["location"]))
            query = query.or_(f"source.ilike.%{loc}%,collection.ilike.%{loc}%")
            query_desc_parts.append(f"from {filters['location']}")

        # Photo type filter — SEC-001: sanitize + escape before .or_()
        if "photo_type" in filters:
            ptype = _escape_ilike(_sanitize_postgrest_value(filters["photo_type"]))
            query = query.or_(f"source.ilike.%{ptype}%,collection.ilike.%{ptype}%")
            query_desc_parts.append(f"{filters['photo_type']} photos")

    result = query.limit(50).execute()

    items = []
    for row in result.data or []:
        date_est = temporal_photo_ids.get(row["photo_id"]) if temporal_photo_ids else None
        items.append(
            {
                "photo_id": row["photo_id"],
                "path": row.get("path", ""),
                "source": row.get("source", ""),
                "collection": row.get("collection", ""),
                "date_estimate": date_est,
            }
        )

    query_summary = "Photos " + ", ".join(query_desc_parts) if query_desc_parts else "Photos"

    return {
        "result_type": "photos",
        "items": items,
        "message": f"Found {len(items)} photo{'s' if len(items) != 1 else ''} {', '.join(query_desc_parts)}",
        "query_summary": query_summary,
    }


def _execute_aggregate(intent_result: dict, sb) -> dict[str, Any]:
    """Return archive-wide counts."""
    photo_result = sb.table("photos").select("photo_id", count="exact").execute()
    identity_result = sb.table("identities").select("identity_id", count="exact").neq("state", "MERGED").execute()

    photo_count = photo_result.count if photo_result.count is not None else 0
    identity_count = identity_result.count if identity_result.count is not None else 0

    message = f"The archive contains {photo_count} photos and {identity_count} identified people."

    return {
        "result_type": "aggregate",
        "items": [],
        "message": message,
        "query_summary": "Archive statistics",
        "counts": {
            "photos": photo_count,
            "identities": identity_count,
        },
    }


def _execute_relationship(intent_result: dict) -> dict[str, Any]:
    """Placeholder for relationship queries."""
    name = intent_result.get("entities", {}).get("name", "someone")
    rel_type = intent_result.get("relationship_type", "relative")
    return {
        "result_type": "message",
        "items": [],
        "message": (
            f"Relationship queries are coming soon. "
            f"We're working on connecting family relationships in the archive. "
            f'Try searching for "{name}" by name instead.'
        ),
        "query_summary": f"{rel_type.title()} of {name}",
    }


def _execute_unknown(intent_result: dict) -> dict[str, Any]:
    """Return helpful suggestions for unrecognized queries."""
    return {
        "result_type": "message",
        "items": [],
        "message": (
            "I'm not sure what you're looking for. Try:\n"
            '- A person\'s name (e.g., "Nace Capeluto")\n'
            '- A time period (e.g., "Photos from the 1940s")\n'
            '- A location (e.g., "Photos from Rhodes")\n'
            '- A question (e.g., "How many photos are in the archive?")'
        ),
        "query_summary": "Suggestions",
    }
