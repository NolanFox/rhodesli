"""
Nearest Neighbor Discovery (Instance-First).

This module is intentionally pessimistic and stateless.
It performs face-to-face matching and only *projects*
results up to the identity level for UI display.

Design goals:
- Avoid centroid poisoning (averaging faces destroys distinct features)
- Preserve explainability (match A->B, not Mean(A)->Mean(B))
- Favor recall during discovery (if one face matches, show it)
"""

import numpy as np
from scipy.spatial.distance import cdist

def get_identity_embeddings(identity_id, registry, face_data):
    """
    Get all embeddings for an identity (anchors + candidates).
    Returns: (face_ids, matrix_of_embeddings)
    """
    identity = registry.get_identity(identity_id)
    if not identity:
        return [], np.array([])

    all_entries = identity.get("anchor_ids", []) + identity.get("candidate_ids", [])
    face_ids = []
    embeddings = []

    for entry in all_entries:
        # Handle both string and dict anchor formats
        fid = entry if isinstance(entry, str) else entry.get("face_id")
        if fid in face_data:
            face_ids.append(fid)
            embeddings.append(face_data[fid]["mu"])

    if not embeddings:
        return [], np.array([])

    return face_ids, np.vstack(embeddings)

def find_nearest_neighbors(target_id, registry, photo_registry, face_data, limit=5):
    """
    Find nearest neighbors using 'Single Linkage' (Best-Linkage) strategy.
    
    Instead of comparing centroids (averages), we find the closest PAIR of faces
    between the target and the candidate. 
    
    Algorithm:
    1. Get all embeddings for Target Identity (Set A)
    2. Get all embeddings for Candidate Identity (Set B)
    3. Calculate distances between ALL pairs (A x B)
    4. The score is the MINIMUM distance found (Best single match)
    """
    # 1. Get Target Data
    target_fids, target_embs = get_identity_embeddings(target_id, registry, face_data)
    if target_embs.size == 0:
        return []

    target_identity = registry.get_identity(target_id)
    # Get set of rejected IDs to exclude
    negative_ids = set(target_identity.get("negative_ids", []))
    
    # Pre-calculate photo sets for co-occurrence check
    target_photos = photo_registry.get_photos_for_faces(target_fids)

    # 2. Candidate Filtering
    candidates = []
    all_identities = registry.list_identities()

    for cand in all_identities:
        cand_id = cand["identity_id"]
        
        # Skip self
        if cand_id == target_id:
            continue
            
        # Skip if explicitly rejected (Not Same Person)
        if f"identity:{cand_id}" in negative_ids:
            continue

        # Get Candidate Data
        cand_fids, cand_embs = get_identity_embeddings(cand_id, registry, face_data)
        if cand_embs.size == 0:
            continue

        # 3. Compute Distance (Single Linkage / Min-Dist)
        # cdist computes distance between every row in A and every row in B
        dists = cdist(target_embs, cand_embs, metric='euclidean')
        
        # Find the absolute best match between any face in A and any face in B
        min_dist = np.min(dists)

        # 4. Check Co-occurrence (Blocking constraint)
        cand_photos = photo_registry.get_photos_for_faces(cand_fids)
        co_occurrence = not target_photos.isdisjoint(cand_photos)

        candidates.append({
            "identity_id": cand_id,
            "name": cand.get("name", f"Identity {cand_id[:8]}..."),
            "mls_score": -min_dist * 100,  # Negative distance for compatibility
            "dist": min_dist,              # Raw distance for sorting
            "face_count": len(cand_fids),
            "can_merge": not co_occurrence,
            "merge_blocked_reason": "co_occurrence" if co_occurrence else None
        })

    # 5. Sort by raw distance (smallest distance = best match)
    candidates.sort(key=lambda x: x["dist"])

    return candidates[:limit]

def sort_faces_by_outlier_score(identity_id, registry, face_data):
    """
    Sort faces in an identity by how far they are from the identity's centroid.
    Useful for finding 'impostors' in a cluster.
    """
    fids, embs = get_identity_embeddings(identity_id, registry, face_data)
    if embs.size == 0:
        return []

    # Calculate centroid (simple mean)
    centroid = np.mean(embs, axis=0)
    
    # Calculate distance of each face to centroid
    dists = cdist([centroid], embs, metric='euclidean').flatten()
    
    # Pair FIDs with distances
    scored_faces = list(zip(fids, dists))
    
    # Sort descending (furthest first)
    scored_faces.sort(key=lambda x: x[1], reverse=True)
    
    return scored_faces