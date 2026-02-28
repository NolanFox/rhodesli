"""Relationship graph builder from GEDCOM data.

Builds a family relationship graph (parent-child, spouse) from
GEDCOM data cross-referenced with confirmed archive identity matches.

AD-075: Relationship graph schema
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rhodesli_ml.importers.gedcom_parser import ParsedGedcom
from rhodesli_ml.importers.identity_matcher import MatchProposal


def parse_gedcom_year(date_str: str | None) -> str | None:
    """Extract year from GEDCOM date string.

    Handles: "1887", "21 SEP 1887", "ABT 1900", "AFT 1930",
    "BEF 1920", "BET 1890 AND 1900", None, ""

    AD-175: Replaces broken [:4] slice that produced "21 S" for day-first dates.
    """
    if not date_str or not isinstance(date_str, str):
        return None
    date_str = date_str.strip()
    if not date_str:
        return None

    upper = date_str.upper()

    # BET...AND... → range
    bet_match = re.match(r'BET\w*\s+.*?(\d{4}).*AND.*?(\d{4})', upper)
    if bet_match:
        return f"{bet_match.group(1)}\u2013{bet_match.group(2)}"

    # Find any 4-digit year
    year_match = re.search(r'\b(\d{4})\b', date_str)
    if not year_match:
        return None
    year = year_match.group(1)

    # Qualifiers
    if upper.startswith(('ABT', 'ABOUT')):
        return f"~{year}"
    if upper.startswith(('AFT', 'AFTER')):
        return f"aft. {year}"
    if upper.startswith(('BEF', 'BEFORE')):
        return f"bef. {year}"

    return year


def format_lifespan(birth_date: str | None, death_date: str | None) -> str:
    """Format birth/death into display string like '1887–1944'."""
    b = parse_gedcom_year(birth_date)
    d = parse_gedcom_year(death_date)
    if b and d:
        return f"{b}\u2013{d}"
    if b:
        return f"{b}\u2013"
    if d:
        return f"\u2013{d}"
    return ""


def build_relationship_graph(
    parsed_gedcom: ParsedGedcom,
    confirmed_matches: list,
    existing_graph: Optional[dict] = None,
) -> dict:
    """Build a relationship graph from GEDCOM data and confirmed matches.

    Creates relationships for all family members in the GEDCOM data.
    Matched individuals use their archive identity_id; unmatched individuals
    retain their raw GEDCOM xref_id (e.g., '@I1@'). This preserves the full
    family tree structure for visualization even when not all members are
    matched to archive identities.

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
            parent_id = xref_to_identity.get(parent_xref, parent_xref)

            for child_xref in fam.children_xrefs:
                child_id = xref_to_identity.get(child_xref, child_xref)

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
            husband_id = xref_to_identity.get(fam.husband_xref, fam.husband_xref)
            wife_id = xref_to_identity.get(fam.wife_xref, fam.wife_xref)
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
    """Build a family tree in the flat array format required by family-chart.

    If root_person is provided, traverses bidirectionally (ancestors + descendants)
    to include their full family context. Otherwise, returns all individuals.

    Output format per node (family-chart CardHtml compatible):
    {
        "id": str,
        "data": {
            "first name": str, "last name": str, "gender": "M"|"F"|"U",
            "birthday": str, "lifespan": str, "avatar": str
        },
        "rels": {
            "father": str|None, "mother": str|None,
            "spouses": [str], "children": [str]
        }
    }

    AD-175: Uses parse_gedcom_year() for all dates. Populates children
    bidirectionally so siblings render correctly.
    """
    relationships = graph.get("relationships", [])
    if not relationships:
        return []

    parent_to_children: dict[str, set] = {}
    child_to_parents: dict[str, set] = {}
    person_to_spouses: dict[str, set] = {}

    for rel in relationships:
        if rel.get("removed"):
            continue
        if rel["type"] == "parent_child":
            parent_to_children.setdefault(rel["person_a"], set()).add(rel["person_b"])
            child_to_parents.setdefault(rel["person_b"], set()).add(rel["person_a"])
        elif rel["type"] == "spouse":
            person_to_spouses.setdefault(rel["person_a"], set()).add(rel["person_b"])
            person_to_spouses.setdefault(rel["person_b"], set()).add(rel["person_a"])

    # Determine which people to include
    included_ids: set = set()

    if root_person:
        queue = [root_person]
        while queue:
            curr = queue.pop(0)
            if curr in included_ids:
                continue
            included_ids.add(curr)
            for p in child_to_parents.get(curr, []):
                if p not in included_ids:
                    queue.append(p)
            for c in parent_to_children.get(curr, []):
                if c not in included_ids:
                    queue.append(c)
            for s in person_to_spouses.get(curr, []):
                if s not in included_ids:
                    queue.append(s)
    else:
        for rel in relationships:
            if not rel.get("removed"):
                included_ids.add(rel["person_a"])
                included_ids.add(rel["person_b"])

    nodes = []
    for pid in included_ids:
        ident = identities.get(pid, {})
        name = ident.get("name", "Unknown")
        meta = ident.get("metadata", {})
        gender = meta.get("gender", "U")

        # Split name into first/last
        name_parts = name.rsplit(" ", 1) if name and name != "Unknown" else ["Unknown", ""]
        first_name = name_parts[0] if len(name_parts) >= 1 else "Unknown"
        last_name = name_parts[1] if len(name_parts) >= 2 else ""

        # Override with explicit first_name/last_name if available
        if ident.get("first_name"):
            first_name = ident["first_name"]
        if ident.get("last_name"):
            last_name = ident["last_name"]

        # Dates — use parse_gedcom_year for GEDCOM dates, fall back to metadata
        birth_raw = meta.get("birth_date") or meta.get("birth_year") or meta.get("birth_year_estimate") or ""
        death_raw = meta.get("death_date") or meta.get("death_year") or ""
        birthday = parse_gedcom_year(str(birth_raw)) if birth_raw else ""
        lifespan = format_lifespan(str(birth_raw) if birth_raw else None,
                                   str(death_raw) if death_raw else None)

        # Avatar URL (populated by app/main.py after calling this function)
        avatar = ident.get("avatar_url", "")

        # Assign father/mother from parents
        parents = list(child_to_parents.get(pid, []))
        father = None
        mother = None
        for p in parents:
            p_ident = identities.get(p, {})
            p_gender = p_ident.get("metadata", {}).get("gender", "U")
            if p_gender == "M" and not father:
                father = p
            elif p_gender == "F" and not mother:
                mother = p
            else:
                if not father:
                    father = p
                elif not mother:
                    mother = p

        # Build rels
        rels: dict = {}
        if father:
            rels["father"] = father
        if mother:
            rels["mother"] = mother

        spouses = list(person_to_spouses.get(pid, []))
        if spouses:
            rels["spouses"] = spouses

        children = list(parent_to_children.get(pid, []))
        if children:
            rels["children"] = children

        nodes.append({
            "id": pid,
            "data": {
                "first name": first_name,
                "last name": last_name,
                "gender": gender,
                "birthday": birthday or "",
                "lifespan": lifespan,
                "avatar": avatar,
            },
            "rels": rels,
        })

    return nodes


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
