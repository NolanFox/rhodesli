"""
Natural Language Archive Query — Intent Parsing.

Rule-based query parser for the Rhodesli photo archive.
Extracts intent and entities from natural language questions.

See: docs/prds/032_nl_archive_query.md

Phase 1: Rule-based pattern matching (no LLM dependency).
Phase 2 (future): Gemini-assisted parsing for complex queries.
"""

import re
from typing import Any


MAX_QUERY_LEN = 512

# Relationship keywords mapped to relationship types
_RELATIONSHIP_WORDS = {
    "child": "child",
    "children": "child",
    "son": "child",
    "daughter": "child",
    "parent": "parent",
    "parents": "parent",
    "father": "parent",
    "mother": "parent",
    "spouse": "spouse",
    "wife": "spouse",
    "husband": "spouse",
    "sibling": "sibling",
    "siblings": "sibling",
    "brother": "sibling",
    "sister": "sibling",
}

# Decade patterns
_DECADE_PATTERN = re.compile(r"\b(1[89]\d0)s?\b")

# Year range pattern
_YEAR_RANGE_PATTERN = re.compile(r"\b(1[89]\d{2})\s*[-\u2013to]+\s*(1[89]\d{2}|20[0-2]\d)\b")

# Single year pattern
_YEAR_PATTERN = re.compile(r"\b(1[89]\d{2}|20[0-2]\d)\b")

# Aggregation words
_AGGREGATE_WORDS = {"how many", "count", "total", "number of"}

# Location keywords (common Rhodesli locations)
_LOCATION_WORDS = {
    "rhodes",
    "new york",
    "nyc",
    "miami",
    "tampa",
    "jerusalem",
    "israel",
    "turkey",
    "greece",
    "seattle",
    "los angeles",
    "atlanta",
    "congo",
    "zimbabwe",
    "rhodesia",
    "asheville",
}

# Photo type keywords
_PHOTO_TYPE_WORDS = {
    "wedding": "wedding",
    "portrait": "portrait",
    "group": "group",
    "family": "family",
    "newspaper": "newspaper",
    "immigration": "immigration",
}


def parse_query_intent(query: str) -> dict[str, Any]:
    """
    Parse a natural language query into structured intent + entities.

    Returns a dict with:
      - intent: one of person_search, relationship, photo_filter,
                aggregate, location, temporal, unknown
      - Plus intent-specific fields (entities, filters, etc.)

    Examples:
      >>> parse_query_intent("Find Nace Capeluto")
      {"intent": "person_search", "entities": {"name": "Nace Capeluto"}}

      >>> parse_query_intent("Photos from the 1940s")
      {"intent": "photo_filter", "filters": {"decade": "1940s"}}
    """
    if not query or not query.strip():
        return {"intent": "unknown", "raw_query": query or ""}

    if len(query) > MAX_QUERY_LEN:
        return {"intent": "unknown", "raw_query": query[:MAX_QUERY_LEN]}

    q = query.strip()
    q_lower = q.lower()

    # Check for aggregation intent
    for agg_word in _AGGREGATE_WORDS:
        if agg_word in q_lower:
            return _parse_aggregate(q, q_lower)

    # Check for relationship intent
    rel_result = _parse_relationship(q, q_lower)
    if rel_result:
        return rel_result

    # Check for temporal intent (decade/year references)
    temporal_result = _parse_temporal(q, q_lower)
    if temporal_result:
        return temporal_result

    # Check for location intent
    location_result = _parse_location(q, q_lower)
    if location_result:
        return location_result

    # Check for photo type filter
    photo_type_result = _parse_photo_type(q, q_lower)
    if photo_type_result:
        return photo_type_result

    # Check for person search (name-like patterns)
    person_result = _parse_person_search(q, q_lower)
    if person_result:
        return person_result

    # Fallback: unknown intent
    return {"intent": "unknown", "raw_query": q}


def _parse_person_search(query: str, q_lower: str) -> dict[str, Any] | None:
    """Extract person name from search-like queries."""
    # "Find X", "Search for X", "Who is X", "Show me X"
    patterns = [
        r"(?:find|search\s+for|look\s+up|show\s+me|who\s+is|who\s+was)\s+(.{1,256})",
        r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)$",  # Capitalized multi-word (likely a name)
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            name = match.group(1).strip().rstrip("?.")
            if name:
                return {"intent": "person_search", "entities": {"name": name}}
    return None


def _parse_relationship(query: str, q_lower: str) -> dict[str, Any] | None:
    """Extract relationship queries like 'children of X'."""
    for word, rel_type in _RELATIONSHIP_WORDS.items():
        # "children of X", "X's children"
        pattern1 = rf"\b{word}\s+of\s+(.{{1,256}}?)(?:\?|$)"
        match = re.search(pattern1, q_lower)
        if match:
            name = _extract_name(match.group(1), query)
            return {
                "intent": "relationship",
                "relationship_type": rel_type,
                "entities": {"name": name},
            }

        pattern2 = rf"(.{{1,256}}?)(?:'s|s')\s+{word}"
        match = re.search(pattern2, q_lower)
        if match:
            name = _extract_name(match.group(1), query)
            return {
                "intent": "relationship",
                "relationship_type": rel_type,
                "entities": {"name": name},
            }

        # "who are the children of X"
        pattern3 = rf"who\s+(?:are|were)\s+(?:the\s+)?{word}\s+of\s+(.{{1,256}}?)(?:\?|$)"
        match = re.search(pattern3, q_lower)
        if match:
            name = _extract_name(match.group(1), query)
            return {
                "intent": "relationship",
                "relationship_type": rel_type,
                "entities": {"name": name},
            }

    return None


def _parse_temporal(query: str, q_lower: str) -> dict[str, Any] | None:
    """Extract temporal filters (decades, years, ranges)."""
    filters: dict[str, Any] = {}

    # Check for decade
    decade_match = _DECADE_PATTERN.search(q_lower)
    if decade_match:
        filters["decade"] = decade_match.group(1) + "s"

    # Check for year range
    range_match = _YEAR_RANGE_PATTERN.search(q_lower)
    if range_match:
        filters["year_start"] = int(range_match.group(1))
        filters["year_end"] = int(range_match.group(2))
    elif not decade_match:
        # Check for single year
        year_match = _YEAR_PATTERN.search(q_lower)
        if year_match:
            filters["year"] = int(year_match.group(1))

    if filters:
        # Check for "before" / "after" modifiers
        if "before" in q_lower and "year" in filters:
            filters["year_end"] = filters.pop("year")
        elif "after" in q_lower and "year" in filters:
            filters["year_start"] = filters.pop("year")

        return {"intent": "photo_filter", "filters": filters}

    return None


def _parse_location(query: str, q_lower: str) -> dict[str, Any] | None:
    """Extract location-based filters."""
    for location in _LOCATION_WORDS:
        if location in q_lower:
            return {
                "intent": "photo_filter",
                "filters": {"location": location},
            }
    return None


def _parse_photo_type(query: str, q_lower: str) -> dict[str, Any] | None:
    """Extract photo type filters (wedding, portrait, etc.)."""
    for keyword, photo_type in _PHOTO_TYPE_WORDS.items():
        if keyword in q_lower:
            return {
                "intent": "photo_filter",
                "filters": {"photo_type": photo_type},
            }
    return None


def _parse_aggregate(query: str, q_lower: str) -> dict[str, Any]:
    """Parse aggregation queries."""
    return {
        "intent": "aggregate",
        "raw_query": query,
    }


def _extract_name(matched_text: str, original_query: str) -> str:
    """Clean up a name extracted from a regex match."""
    name = matched_text.strip().rstrip("?.!,")
    # Try to get original casing from the query
    name_lower = name.lower()
    idx = original_query.lower().find(name_lower)
    if idx >= 0:
        name = original_query[idx : idx + len(name)]
    return name
