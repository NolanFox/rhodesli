"""
Nearest Neighbor Discovery (Instance-First).

This module is intentionally pessimistic and stateless.
It performs face-to-face matching and only *projects*
results up to the identity level for UI display.

Design goals:
- Avoid centroid poisoning (averaging faces destroys distinct features)
- Preserve explainability (match A->B, not Mean(A)->Mean(B))
- Favor recall during discovery (if one face matches, show it)
- Provide statistical context (rank/percentile) not just raw distance
"""

import numpy as np
from scipy.spatial.distance import cdist
from core.event_recorder import get_event_recorder

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
    
    Returns raw distances and statistical rank, NOT UI-scaled scores.
    """
    # 1. Get Target Data
    target_fids, target_embs = get_identity_embeddings(target_id, registry, face_data)
    if target_embs.size == 0:
        return []

    target_identity = registry.get_identity(target_id)
    negative_ids = set(target_identity.get("negative_ids", []))
    
    target_photos = photo_registry.get_photos_for_faces(target_fids)

    # 2. Candidate Filtering & Scoring
    candidates = []
    all_identities = registry.list_identities()

    for cand in all_identities:
        cand_id = cand["identity_id"]
        
        if cand_id == target_id: continue
        if f"identity:{cand_id}" in negative_ids: continue

        cand_fids, cand_embs = get_identity_embeddings(cand_id, registry, face_data)
        if cand_embs.size == 0: continue

        # Best-Linkage Math: Min dist between any pair
        dists = cdist(target_embs, cand_embs, metric='euclidean')
        min_dist = float(np.min(dists))

        # Check Co-occurrence
        cand_photos = photo_registry.get_photos_for_faces(cand_fids)
        co_occurrence = not target_photos.isdisjoint(cand_photos)

        candidates.append({
            "identity_id": cand_id,
            "name": cand.get("name", f"Identity {cand_id[:8]}..."),
            "distance": min_dist,          # Raw Euclidean distance
            "face_count": len(cand_fids),
            "can_merge": not co_occurrence,
            "merge_blocked_reason": "co_occurrence" if co_occurrence else None
        })

    # 3. Sort & Rank
    candidates.sort(key=lambda x: x["distance"])

    total = len(candidates)
    for idx, c in enumerate(candidates):
        c["rank"] = idx + 1
        c["percentile"] = (idx + 1) / total if total > 0 else 1.0

    # 4. Confidence Gap: how much closer is #1 vs #2?
    # margin = (dist_2nd - dist_1st) / dist_1st
    # Higher margin = more distinctive match = easier for humans to adjudicate
    if len(candidates) >= 2:
        d1 = candidates[0]["distance"]
        d2 = candidates[1]["distance"]
        if d1 > 0:
            candidates[0]["confidence_gap"] = round((d2 - d1) / d1 * 100, 1)
        else:
            candidates[0]["confidence_gap"] = 100.0
        # For non-top candidates, gap is vs the next one
        for i in range(1, len(candidates)):
            if i + 1 < len(candidates):
                di = candidates[i]["distance"]
                di_next = candidates[i + 1]["distance"]
                if di > 0:
                    candidates[i]["confidence_gap"] = round((di_next - di) / di * 100, 1)
                else:
                    candidates[i]["confidence_gap"] = 0.0
            else:
                candidates[i]["confidence_gap"] = 0.0
    elif len(candidates) == 1:
        candidates[0]["confidence_gap"] = 100.0

    results = candidates[:limit]

    # 4. Instrumentation
    get_event_recorder().record("FIND_SIMILAR", {
        "target_id": target_id,
        "total_candidates": total,
        "top_k": [
            {
                "identity_id": r["identity_id"],
                "distance": round(r["distance"], 4),
                "rank": r["rank"],
                "percentile": round(r["percentile"], 4)
            }
            for r in results
        ]
    })

    return results

def sort_faces_by_outlier_score(identity_id, registry, face_data):
    """
    Sort faces by distance from the identity's ad-hoc centroid.
    """
    fids, embs = get_identity_embeddings(identity_id, registry, face_data)
    if embs.size == 0:
        return []

    centroid = np.mean(embs, axis=0)
    dists = cdist([centroid], embs, metric='euclidean').flatten()
    
    scored_faces = list(zip(fids, dists))
    scored_faces.sort(key=lambda x: x[1], reverse=True)
    
    return scored_faces