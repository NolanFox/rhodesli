"""
Natural Language Query Executor — runs parsed intents against Supabase.

Takes the output of rhodesli_ml.nl_query.parse_query_intent() and
executes the appropriate queries against Supabase tables.

All queries use parameterized Supabase client methods (ilike, gte, lte)
— no string interpolation for SQL.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
        .ilike("name", f"%{name}%")
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
    """Filter photos by decade, year, location, or type."""
    filters = intent_result.get("filters", {})

    query = sb.table("photos").select("photo_id, path, source, collection, date_estimate, upload_date")

    query_desc_parts = []

    # Temporal filters
    if "decade" in filters:
        decade_str = filters["decade"]  # e.g. "1940s"
        decade_start = int(decade_str.rstrip("s"))
        decade_end = decade_start + 9
        query = query.gte("date_estimate", decade_start).lte("date_estimate", decade_end)
        query_desc_parts.append(f"from the {decade_str}")

    if "year" in filters:
        year = filters["year"]
        query = query.eq("date_estimate", year)
        query_desc_parts.append(f"from {year}")

    if "year_start" in filters:
        query = query.gte("date_estimate", filters["year_start"])
        query_desc_parts.append(f"after {filters['year_start']}")

    if "year_end" in filters:
        query = query.lte("date_estimate", filters["year_end"])
        query_desc_parts.append(f"before {filters['year_end']}")

    # Location filter
    if "location" in filters:
        loc = filters["location"]
        query = query.or_(f"source.ilike.%{loc}%,collection.ilike.%{loc}%")
        query_desc_parts.append(f"from {loc}")

    # Photo type filter
    if "photo_type" in filters:
        ptype = filters["photo_type"]
        query = query.or_(f"source.ilike.%{ptype}%,collection.ilike.%{ptype}%")
        query_desc_parts.append(f"{ptype} photos")

    result = query.limit(50).execute()

    items = []
    for row in result.data or []:
        items.append(
            {
                "photo_id": row["photo_id"],
                "path": row.get("path", ""),
                "source": row.get("source", ""),
                "collection": row.get("collection", ""),
                "date_estimate": row.get("date_estimate"),
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
