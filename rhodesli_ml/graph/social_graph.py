"""Unified social graph — merges GEDCOM relationships + photo co-occurrence.

Provides BFS pathfinding ("six degrees"), proximity scoring,
and graph export for D3.js visualization.

AD-077: Social graph architecture
"""

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional


# Edge type labels for display
EDGE_LABELS = {
    "parent_child": "parent of",
    "child_of": "child of",
    "spouse_of": "spouse of",
    "sibling_of": "sibling of",
    "photographed_with": "photographed with",
}

# Weights for proximity scoring
RELATIONSHIP_WEIGHTS = {
    "parent_child": 1.0,
    "child_of": 1.0,
    "spouse_of": 1.0,
    "sibling_of": 1.0,
    "photographed_with_5plus": 0.8,
    "photographed_with_2to4": 0.5,
    "photographed_with_1": 0.3,
}


def build_social_graph(relationship_graph: dict, co_occurrence_graph: dict) -> dict:
    """Merge relationship graph + co-occurrence graph into unified social graph.

    Args:
        relationship_graph: From data/relationships.json
        co_occurrence_graph: From data/co_occurrence_graph.json

    Returns: Unified graph dict with nodes and edges.
    """
    nodes = set()
    edges = []

    # Add familial edges from relationship graph
    for rel in relationship_graph.get("relationships", []):
        person_a = rel["person_a"]
        person_b = rel["person_b"]
        nodes.add(person_a)
        nodes.add(person_b)

        rel_type = rel["type"]
        if rel_type == "parent_child":
            # person_a is parent, person_b is child
            edges.append({
                "source": person_a,
                "target": person_b,
                "type": "parent_child",
                "label": "parent of",
                "category": "family",
                "weight": 1.0,
            })
            edges.append({
                "source": person_b,
                "target": person_a,
                "type": "child_of",
                "label": "child of",
                "category": "family",
                "weight": 1.0,
            })
        elif rel_type == "spouse":
            edges.append({
                "source": person_a,
                "target": person_b,
                "type": "spouse_of",
                "label": "spouse of",
                "category": "family",
                "weight": 1.0,
            })
            edges.append({
                "source": person_b,
                "target": person_a,
                "type": "spouse_of",
                "label": "spouse of",
                "category": "family",
                "weight": 1.0,
            })

    # Derive sibling edges from shared parents
    parent_to_children = defaultdict(set)
    for rel in relationship_graph.get("relationships", []):
        if rel["type"] == "parent_child":
            parent_to_children[rel["person_a"]].add(rel["person_b"])

    sibling_pairs = set()
    for _parent, children in parent_to_children.items():
        children_list = sorted(children)
        for i in range(len(children_list)):
            for j in range(i + 1, len(children_list)):
                pair = (children_list[i], children_list[j])
                if pair not in sibling_pairs:
                    sibling_pairs.add(pair)
                    edges.append({
                        "source": pair[0],
                        "target": pair[1],
                        "type": "sibling_of",
                        "label": "sibling of",
                        "category": "family",
                        "weight": 1.0,
                    })
                    edges.append({
                        "source": pair[1],
                        "target": pair[0],
                        "type": "sibling_of",
                        "label": "sibling of",
                        "category": "family",
                        "weight": 1.0,
                    })

    # Add photographic edges from co-occurrence graph
    for edge in co_occurrence_graph.get("edges", []):
        person_a = edge["person_a"]
        person_b = edge["person_b"]
        count = edge.get("count", 1)
        shared_photos = edge.get("shared_photos", [])
        nodes.add(person_a)
        nodes.add(person_b)

        if count >= 5:
            weight = RELATIONSHIP_WEIGHTS["photographed_with_5plus"]
        elif count >= 2:
            weight = RELATIONSHIP_WEIGHTS["photographed_with_2to4"]
        else:
            weight = RELATIONSHIP_WEIGHTS["photographed_with_1"]

        photo_label = f"in {count} photo{'s' if count != 1 else ''}"
        edges.append({
            "source": person_a,
            "target": person_b,
            "type": "photographed_with",
            "label": f"photographed with ({photo_label})",
            "category": "photo",
            "weight": weight,
            "photo_count": count,
            "shared_photos": shared_photos,
        })
        edges.append({
            "source": person_b,
            "target": person_a,
            "type": "photographed_with",
            "label": f"photographed with ({photo_label})",
            "category": "photo",
            "weight": weight,
            "photo_count": count,
            "shared_photos": shared_photos,
        })

    return {
        "nodes": sorted(nodes),
        "edges": edges,
    }


def _build_adjacency(graph: dict, category_filter: Optional[str] = None) -> dict:
    """Build adjacency list from social graph.

    Args:
        graph: Unified social graph
        category_filter: "family", "photo", or None (all)

    Returns: {node_id: [(neighbor_id, edge_data), ...]}
    """
    adj = defaultdict(list)
    for edge in graph["edges"]:
        if category_filter and edge.get("category") != category_filter:
            continue
        adj[edge["source"]].append((edge["target"], edge))
    return adj


def find_shortest_path(graph: dict, person_a: str, person_b: str,
                       category_filter: Optional[str] = None) -> Optional[list]:
    """BFS to find shortest path between two people.

    Args:
        graph: Unified social graph
        person_a: Start identity ID
        person_b: End identity ID
        category_filter: "family", "photo", or None (all)

    Returns: List of path steps [{from, to, edge}] or None if no path.
    """
    if person_a == person_b:
        return []

    if person_a not in graph["nodes"] or person_b not in graph["nodes"]:
        return None

    adj = _build_adjacency(graph, category_filter)

    # BFS
    visited = {person_a}
    queue = deque([(person_a, [])])

    while queue:
        current, path = queue.popleft()

        for neighbor, edge in adj.get(current, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)

            new_path = path + [{
                "from": current,
                "to": neighbor,
                "edge": edge,
            }]

            if neighbor == person_b:
                return new_path

            queue.append((neighbor, new_path))

    return None


def find_all_paths(graph: dict, person_a: str, person_b: str,
                   max_depth: int = 6) -> dict:
    """Find shortest paths using all edges, family-only, and photo-only.

    Returns: {
        "any": path or None,
        "family": path or None,
        "photo": path or None,
    }
    """
    return {
        "any": find_shortest_path(graph, person_a, person_b),
        "family": find_shortest_path(graph, person_a, person_b, "family"),
        "photo": find_shortest_path(graph, person_a, person_b, "photo"),
    }


def compute_proximity(graph: dict, person_a: str, person_b: str) -> float:
    """Compute proximity score between two people.

    proximity = (1 / path_length) * average_edge_weight

    Returns: Score (0.0 if no connection, higher = closer).
    """
    path = find_shortest_path(graph, person_a, person_b)
    if path is None or len(path) == 0:
        return 0.0

    total_weight = sum(step["edge"]["weight"] for step in path)
    avg_weight = total_weight / len(path)
    return (1.0 / len(path)) * avg_weight


def get_closest_connections(graph: dict, person_id: str, n: int = 5) -> list:
    """Get the N closest connections for a person.

    Returns: List of dicts [{person_id, proximity, path_length, edge_type}, ...]
    sorted by proximity descending.
    """
    if person_id not in graph["nodes"]:
        return []

    connections = []
    for other in graph["nodes"]:
        if other == person_id:
            continue
        path = find_shortest_path(graph, person_id, other)
        if path is None:
            continue
        proximity = compute_proximity(graph, person_id, other)
        # Determine primary edge type for the direct connection
        if len(path) == 1:
            edge_type = path[0]["edge"]["type"]
        else:
            edge_type = "indirect"

        connections.append({
            "person_id": other,
            "proximity": round(proximity, 3),
            "path_length": len(path),
            "edge_type": edge_type,
        })

    connections.sort(key=lambda c: c["proximity"], reverse=True)
    return connections[:n]


def export_for_d3(graph: dict, identities: dict, photo_counts: Optional[dict] = None) -> dict:
    """Export graph in D3.js force-directed format.

    Args:
        graph: Unified social graph
        identities: Dict of identity_id -> identity record (for names)
        photo_counts: Optional dict of identity_id -> photo count

    Returns: {
        "nodes": [{"id": uuid, "name": str, "photo_count": int, "generation": int}, ...],
        "links": [{"source": uuid, "target": uuid, "type": str, "category": str}, ...],
    }
    """
    # Build node data
    d3_nodes = []
    for node_id in graph["nodes"]:
        identity = identities.get(node_id, {})
        name = identity.get("name", "Unknown")
        count = photo_counts.get(node_id, 0) if photo_counts else 0
        d3_nodes.append({
            "id": node_id,
            "name": name,
            "photo_count": count,
        })

    # Build link data — deduplicate bidirectional edges
    seen_links = set()
    d3_links = []
    for edge in graph["edges"]:
        pair = tuple(sorted([edge["source"], edge["target"]]))
        link_key = (pair[0], pair[1], edge["type"])
        if link_key in seen_links:
            continue
        seen_links.add(link_key)

        d3_links.append({
            "source": edge["source"],
            "target": edge["target"],
            "type": edge["type"],
            "category": edge.get("category", "unknown"),
            "label": edge.get("label", ""),
            "weight": edge.get("weight", 1.0),
            "photo_count": edge.get("photo_count"),
        })

    return {
        "nodes": d3_nodes,
        "links": d3_links,
    }


def compute_all_proximities(graph: dict) -> dict:
    """Compute proximity scores for all connected pairs.

    Returns: Dict of (person_a, person_b) -> proximity score
    """
    proximities = {}
    nodes = graph["nodes"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            score = compute_proximity(graph, nodes[i], nodes[j])
            if score > 0:
                proximities[(nodes[i], nodes[j])] = round(score, 3)
    return proximities
