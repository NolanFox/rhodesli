"""Photo co-occurrence graph builder.

Builds a graph of which people appear together in photos.
This uses EXISTING photo data — no GEDCOM required.

For every photo with 2+ identified people, creates edges
between all pairs of people in that photo.

AD-075: Co-occurrence graph schema
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Optional


def build_co_occurrence_graph(
    identities: dict,
    photo_index: dict,
    date_labels: Optional[dict] = None,
) -> dict:
    """Build co-occurrence graph from photo data.

    For each photo with 2+ confirmed/proposed identities,
    create edges between all pairs of people.

    Args:
        identities: Dict from identities.json (identity_id -> record)
        photo_index: Dict from photo_index.json
        date_labels: Optional dict of photo_id -> {estimated_year: int} for date context

    Returns: Co-occurrence graph dict matching data/co_occurrence_graph.json schema.
    """
    photos = photo_index.get("photos", {})
    face_to_photo = photo_index.get("face_to_photo", {})

    # Build face_id -> identity_id lookup (only confirmed/proposed)
    face_to_identity = {}
    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue
        state = ident.get("state", "")
        if state not in ("CONFIRMED", "PROPOSED"):
            continue

        for anchor in ident.get("anchor_ids", []):
            face_id = anchor if isinstance(anchor, str) else anchor.get("face_id", "")
            if face_id:
                face_to_identity[face_id] = iid

    # Build photo_id -> set of identity_ids
    photo_people = defaultdict(set)
    for face_id, iid in face_to_identity.items():
        photo_id = face_to_photo.get(face_id)
        if photo_id:
            photo_people[photo_id].add(iid)

    # Build edges: for each photo with 2+ people, create pairs
    edge_data = defaultdict(lambda: {"shared_photos": [], "count": 0})

    for photo_id, people_set in photo_people.items():
        if len(people_set) < 2:
            continue

        for person_a, person_b in combinations(sorted(people_set), 2):
            key = (person_a, person_b)
            edge_data[key]["shared_photos"].append(photo_id)
            edge_data[key]["count"] += 1

    # Build edge list
    edges = []
    for (person_a, person_b), data in edge_data.items():
        edge = {
            "person_a": person_a,
            "person_b": person_b,
            "shared_photos": data["shared_photos"],
            "count": data["count"],
        }
        edges.append(edge)

    # Sort by count (most co-occurrences first)
    edges.sort(key=lambda e: e["count"], reverse=True)

    return {
        "schema_version": 1,
        "edges": edges,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "total_edges": len(edges),
            "total_photos_with_pairs": len([p for p in photo_people.values() if len(p) >= 2]),
            "max_co_occurrences": edges[0]["count"] if edges else 0,
        },
    }


def save_co_occurrence_graph(graph: dict, path: Optional[str] = None):
    """Save co-occurrence graph to JSON file."""
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "co_occurrence_graph.json"
    else:
        path = Path(path)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(graph, f, indent=2)


def load_co_occurrence_graph(path: Optional[str] = None) -> dict:
    """Load co-occurrence graph from JSON file."""
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "co_occurrence_graph.json"
    else:
        path = Path(path)

    if not path.exists():
        return {"schema_version": 1, "edges": [], "generated_at": None, "stats": {}}

    with open(path) as f:
        return json.load(f)


def get_co_occurrences_for_person(graph: dict, identity_id: str) -> list:
    """Get all people who appear in photos with a given person.

    Returns: List of dicts with person_id, shared_photos, count.
    Sorted by count (most co-occurrences first).
    """
    results = []
    for edge in graph.get("edges", []):
        if edge["person_a"] == identity_id:
            results.append({
                "person_id": edge["person_b"],
                "shared_photos": edge["shared_photos"],
                "count": edge["count"],
            })
        elif edge["person_b"] == identity_id:
            results.append({
                "person_id": edge["person_a"],
                "shared_photos": edge["shared_photos"],
                "count": edge["count"],
            })

    results.sort(key=lambda r: r["count"], reverse=True)
    return results
