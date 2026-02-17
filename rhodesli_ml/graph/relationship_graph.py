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


def find_root_couples(graph: dict) -> list:
    """Find root couples — parents with no parents of their own in the graph.

    Returns: List of tuples [(person_a, person_b), ...] where each tuple is
    a couple that has children but neither member appears as a child.
    Single parents (no spouse) are returned as (person_id, None).
    """
    relationships = graph.get("relationships", [])
    if not relationships:
        return []

    # Build sets of all parents and all children
    all_parents = set()
    all_children = set()
    spouse_map = {}  # person -> spouse

    for rel in relationships:
        if rel.get("removed"):
            continue
        if rel["type"] == "parent_child":
            all_parents.add(rel["person_a"])
            all_children.add(rel["person_b"])
        elif rel["type"] == "spouse":
            spouse_map[rel["person_a"]] = rel["person_b"]
            spouse_map[rel["person_b"]] = rel["person_a"]

    # Root parents: parents who are NOT children of anyone
    root_parents = all_parents - all_children

    # Group root parents into couples
    seen = set()
    couples = []
    for person in sorted(root_parents):  # Sort for deterministic ordering
        if person in seen:
            continue
        seen.add(person)
        spouse = spouse_map.get(person)
        if spouse and spouse in root_parents:
            seen.add(spouse)
            couples.append((person, spouse))
        else:
            couples.append((person, None))

    return couples


def build_family_tree(
    graph: dict,
    identities: dict,
    root_person: Optional[str] = None,
) -> list:
    """Build a hierarchical family tree from a relationship graph.

    AD-081: Uses hierarchical tree structure with couple-based nodes.
    AD-082: Each family unit (married couple + children) is a logical node.

    Args:
        graph: Relationship graph dict (from relationships.json)
        identities: Dict of identity_id -> identity record
        root_person: If set, center the tree on this person's family

    Returns: List of tree root nodes. Each node is either:
        - {"type": "couple", "members": [{id, name, ...}, ...], "children": [...]}
        - {"type": "single", "id": str, "name": str, ..., "children": [...]}
    """
    relationships = graph.get("relationships", [])
    if not relationships:
        return []

    # Build adjacency maps
    parent_to_children = {}  # parent_id -> [child_id, ...]
    child_to_parents = {}    # child_id -> [parent_id, ...]
    spouse_map = {}          # person -> spouse

    for rel in relationships:
        if rel.get("removed"):
            continue
        if rel["type"] == "parent_child":
            parent_to_children.setdefault(rel["person_a"], []).append(rel["person_b"])
            child_to_parents.setdefault(rel["person_b"], []).append(rel["person_a"])
        elif rel["type"] == "spouse":
            spouse_map[rel["person_a"]] = rel["person_b"]
            spouse_map[rel["person_b"]] = rel["person_a"]

    visited = set()

    def _enrich_person(person_id: str) -> dict:
        """Build person metadata from identity record."""
        ident = identities.get(person_id, {})
        return {
            "id": person_id,
            "name": ident.get("name", "Unknown"),
            "birth_year": ident.get("metadata", {}).get("birth_year")
                          or ident.get("metadata", {}).get("birth_year_estimate"),
            "death_year": ident.get("metadata", {}).get("death_year"),
            "gender": ident.get("metadata", {}).get("gender"),
        }

    def _build_subtree(person_id: str, spouse_id: Optional[str] = None) -> dict:
        """Recursively build a subtree starting from a person (and their spouse)."""
        visited.add(person_id)
        if spouse_id:
            visited.add(spouse_id)

        # Collect children of this person (and spouse if present)
        children_ids = set(parent_to_children.get(person_id, []))
        if spouse_id:
            children_ids |= set(parent_to_children.get(spouse_id, []))

        # Build child subtrees
        child_nodes = []
        for child_id in sorted(children_ids):
            if child_id in visited:
                continue
            child_spouse = spouse_map.get(child_id)
            if child_spouse and child_spouse in visited:
                child_spouse = None
            child_nodes.append(_build_subtree(child_id, child_spouse))

        if spouse_id:
            return {
                "type": "couple",
                "members": [_enrich_person(person_id), _enrich_person(spouse_id)],
                "children": child_nodes,
            }
        else:
            node = _enrich_person(person_id)
            node["type"] = "single"
            node["children"] = child_nodes
            return node

    # If root_person specified, build subtree from that person
    if root_person:
        spouse = spouse_map.get(root_person)
        tree = [_build_subtree(root_person, spouse)]
        return tree

    # Otherwise, find all root couples and build from each
    root_couples = find_root_couples(graph)
    trees = []
    for couple in root_couples:
        person_a, person_b = couple
        if person_a in visited:
            continue
        trees.append(_build_subtree(person_a, person_b))

    return trees


def add_relationship(
    graph: dict,
    person_a: str,
    person_b: str,
    rel_type: str,
    source: str = "manual",
    confidence: str = "confirmed",
    label: Optional[str] = None,
) -> dict:
    """Add a relationship to the graph, deduplicating.

    AD-083: Supports FAN types (fan_friend, fan_associate, fan_neighbor)
    plus standard types (parent_child, spouse).
    """
    # Check for existing (non-removed) relationship of same type between same people
    for rel in graph.get("relationships", []):
        if rel.get("removed"):
            continue
        if rel["type"] == rel_type and rel["person_a"] == person_a and rel["person_b"] == person_b:
            return graph  # Already exists

    entry = {
        "person_a": person_a,
        "person_b": person_b,
        "type": rel_type,
        "source": source,
        "confidence": confidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if label:
        entry["label"] = label

    graph.setdefault("relationships", []).append(entry)
    return graph


def update_relationship_confidence(
    graph: dict,
    person_a: str,
    person_b: str,
    rel_type: str,
    confidence: str,
) -> dict:
    """Update the confidence level of an existing relationship."""
    for rel in graph.get("relationships", []):
        if (rel["type"] == rel_type and
                rel["person_a"] == person_a and rel["person_b"] == person_b):
            rel["confidence"] = confidence
            break
    return graph


def remove_relationship(
    graph: dict,
    person_a: str,
    person_b: str,
    rel_type: str,
) -> dict:
    """Mark a relationship as removed (non-destructive)."""
    for rel in graph.get("relationships", []):
        if (rel["type"] == rel_type and
                rel["person_a"] == person_a and rel["person_b"] == person_b):
            rel["removed"] = True
            break
    return graph


def get_relationships_for_person(
    graph: dict,
    identity_id: str,
    include_theory: bool = True,
) -> dict:
    """Get all relationships for a specific person.

    Args:
        graph: Relationship graph dict
        identity_id: Person to look up
        include_theory: If False, exclude relationships with confidence="theory"

    Returns: {
        "parents": [identity_id, ...],
        "children": [identity_id, ...],
        "spouses": [identity_id, ...],
        "siblings": [identity_id, ...],
        "fan": [{"id": identity_id, "type": fan_type, "label": ...}, ...],
    }
    """
    parents = []
    children = []
    spouses = []
    fan = []

    for rel in graph.get("relationships", []):
        if rel.get("removed"):
            continue
        if not include_theory and rel.get("confidence") == "theory":
            continue

        rel_type = rel["type"]

        if rel_type == "parent_child":
            if rel["person_a"] == identity_id:
                children.append(rel["person_b"])
            elif rel["person_b"] == identity_id:
                parents.append(rel["person_a"])
        elif rel_type == "spouse":
            if rel["person_a"] == identity_id:
                spouses.append(rel["person_b"])
            elif rel["person_b"] == identity_id:
                spouses.append(rel["person_a"])
        elif rel_type.startswith("fan_"):
            other = None
            if rel["person_a"] == identity_id:
                other = rel["person_b"]
            elif rel["person_b"] == identity_id:
                other = rel["person_a"]
            if other:
                fan.append({
                    "id": other,
                    "type": rel_type,
                    "label": rel.get("label"),
                    "confidence": rel.get("confidence", "confirmed"),
                })

    # Compute siblings: other children of the same parents (respecting filters)
    siblings = set()
    for parent_id in parents:
        for rel in graph.get("relationships", []):
            if rel.get("removed"):
                continue
            if not include_theory and rel.get("confidence") == "theory":
                continue
            if rel["type"] == "parent_child" and rel["person_a"] == parent_id:
                if rel["person_b"] != identity_id:
                    siblings.add(rel["person_b"])

    return {
        "parents": parents,
        "children": children,
        "spouses": spouses,
        "siblings": list(siblings),
        "fan": fan,
    }
