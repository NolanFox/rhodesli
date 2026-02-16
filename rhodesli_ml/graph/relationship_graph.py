"""Relationship graph builder from GEDCOM data.

Builds a family relationship graph (parent-child, spouse) from
GEDCOM data cross-referenced with confirmed archive identity matches.

AD-075: Relationship graph schema
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rhodesli_ml.importers.gedcom_parser import ParsedGedcom
from rhodesli_ml.importers.identity_matcher import MatchProposal


def build_relationship_graph(
    parsed_gedcom: ParsedGedcom,
    confirmed_matches: list,
    existing_graph: Optional[dict] = None,
) -> dict:
    """Build a relationship graph from GEDCOM data and confirmed matches.

    Only creates relationships between individuals that have been
    matched to archive identities (both endpoints must be matched).

    Args:
        parsed_gedcom: Parsed GEDCOM data
        confirmed_matches: List of confirmed MatchProposal objects
        existing_graph: Existing graph to merge into (optional)

    Returns: Relationship graph dict matching data/relationships.json schema.
    """
    # Build xref -> identity_id lookup from confirmed matches
    xref_to_identity = {}
    for match in confirmed_matches:
        if match.status == "confirmed":
            xref_to_identity[match.gedcom_individual.xref_id] = match.identity_id

    relationships = []
    seen_pairs = set()  # Avoid duplicates

    for fam_xref, fam in parsed_gedcom.families.items():
        # Parent-child relationships
        parent_xrefs = []
        if fam.husband_xref:
            parent_xrefs.append(fam.husband_xref)
        if fam.wife_xref:
            parent_xrefs.append(fam.wife_xref)

        for parent_xref in parent_xrefs:
            if parent_xref not in xref_to_identity:
                continue
            parent_id = xref_to_identity[parent_xref]

            for child_xref in fam.children_xrefs:
                if child_xref not in xref_to_identity:
                    continue
                child_id = xref_to_identity[child_xref]

                pair_key = ("parent_child", parent_id, child_id)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                relationships.append({
                    "person_a": parent_id,
                    "person_b": child_id,
                    "type": "parent_child",
                    "source": "gedcom",
                    "gedcom_family_id": fam_xref,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

        # Spouse relationship
        if fam.husband_xref and fam.wife_xref:
            if fam.husband_xref in xref_to_identity and fam.wife_xref in xref_to_identity:
                husband_id = xref_to_identity[fam.husband_xref]
                wife_id = xref_to_identity[fam.wife_xref]
                # Normalize pair order for dedup
                pair = tuple(sorted([husband_id, wife_id]))
                pair_key = ("spouse", pair[0], pair[1])
                if pair_key not in seen_pairs:
                    seen_pairs.add(pair_key)
                    relationships.append({
                        "person_a": husband_id,
                        "person_b": wife_id,
                        "type": "spouse",
                        "source": "gedcom",
                        "gedcom_family_id": fam_xref,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })

    # Merge with existing graph
    graph = existing_graph or {
        "schema_version": 1,
        "relationships": [],
        "gedcom_imports": [],
    }

    # Add new relationships (avoiding duplicates with existing)
    existing_keys = set()
    for rel in graph.get("relationships", []):
        key = (rel["type"], rel["person_a"], rel["person_b"])
        existing_keys.add(key)

    for rel in relationships:
        key = (rel["type"], rel["person_a"], rel["person_b"])
        if key not in existing_keys:
            graph["relationships"].append(rel)
            existing_keys.add(key)

    # Record the import
    graph.setdefault("gedcom_imports", []).append({
        "filename": parsed_gedcom.source_file,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "individuals_count": parsed_gedcom.individual_count,
        "families_count": parsed_gedcom.family_count,
        "matches_confirmed": len([m for m in confirmed_matches if m.status == "confirmed"]),
        "relationships_added": len(relationships),
    })

    return graph


def save_relationship_graph(graph: dict, path: Optional[str] = None):
    """Save relationship graph to JSON file."""
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "relationships.json"
    else:
        path = Path(path)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(graph, f, indent=2)


def load_relationship_graph(path: Optional[str] = None) -> dict:
    """Load relationship graph from JSON file."""
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "relationships.json"
    else:
        path = Path(path)

    if not path.exists():
        return {"schema_version": 1, "relationships": [], "gedcom_imports": []}

    with open(path) as f:
        return json.load(f)


def get_relationships_for_person(graph: dict, identity_id: str) -> dict:
    """Get all relationships for a specific person.

    Returns: {
        "parents": [identity_id, ...],
        "children": [identity_id, ...],
        "spouses": [identity_id, ...],
        "siblings": [identity_id, ...],  # computed from shared parents
    }
    """
    parents = []
    children = []
    spouses = []

    for rel in graph.get("relationships", []):
        if rel["type"] == "parent_child":
            if rel["person_a"] == identity_id:
                children.append(rel["person_b"])
            elif rel["person_b"] == identity_id:
                parents.append(rel["person_a"])
        elif rel["type"] == "spouse":
            if rel["person_a"] == identity_id:
                spouses.append(rel["person_b"])
            elif rel["person_b"] == identity_id:
                spouses.append(rel["person_a"])

    # Compute siblings: other children of the same parents
    siblings = set()
    for parent_id in parents:
        for rel in graph.get("relationships", []):
            if rel["type"] == "parent_child" and rel["person_a"] == parent_id:
                if rel["person_b"] != identity_id:
                    siblings.add(rel["person_b"])

    return {
        "parents": parents,
        "children": children,
        "spouses": spouses,
        "siblings": list(siblings),
    }
