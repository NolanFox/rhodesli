"""
Face grouping for ingestion-time clustering.

Groups similar faces together so that uploading 10 photos of the same person
creates 1 inbox identity (with 10 faces) instead of 10 separate identities.

Design principles:
- Conservative: Under-grouping is better than over-grouping
- Simple: Union-Find with pairwise Euclidean distance (no clustering libraries)
- Advisory: Groups go to inbox for user confirmation, not auto-merged

See docs/adr_008_ingestion_grouping.md for design rationale.
"""

import numpy as np
from scipy.spatial.distance import cdist

from core.config import GROUPING_THRESHOLD


def group_faces(faces: list[dict]) -> list[list[dict]]:
    """
    Group faces by embedding similarity using union-find.

    Faces with Euclidean distance < GROUPING_THRESHOLD are grouped together.
    Grouping is transitive: if A~B and B~C, then A,B,C are in the same group.

    Args:
        faces: List of face dicts, each containing:
            - face_id: Unique identifier
            - mu: 512-dimensional embedding vector (np.ndarray)

    Returns:
        List of groups, where each group is a list of face dicts.
        Original face dicts are preserved (not copies).

    Example:
        >>> faces = [{"face_id": "f1", "mu": emb1}, {"face_id": "f2", "mu": emb2}]
        >>> groups = group_faces(faces)
        >>> # If emb1 and emb2 are similar: [[face1, face2]]
        >>> # If different: [[face1], [face2]]
    """
    n = len(faces)

    if n == 0:
        return []

    if n == 1:
        return [faces]

    # Extract embeddings into matrix for efficient distance computation
    embeddings = np.array([f["mu"] for f in faces])

    # Compute all pairwise Euclidean distances
    # distances[i][j] = distance between face i and face j
    distances = cdist(embeddings, embeddings, metric="euclidean")

    # Union-Find data structure for transitive grouping
    parent = list(range(n))

    def find(x: int) -> int:
        """Find root with path compression."""
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        """Union two sets."""
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Group faces below threshold
    for i in range(n):
        for j in range(i + 1, n):
            if distances[i][j] < GROUPING_THRESHOLD:
                union(i, j)

    # Collect groups by root
    groups_by_root: dict[int, list[dict]] = {}
    for i in range(n):
        root = find(i)
        if root not in groups_by_root:
            groups_by_root[root] = []
        groups_by_root[root].append(faces[i])

    return list(groups_by_root.values())
