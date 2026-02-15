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

def batch_best_neighbor_distances(identity_ids, registry, face_data):
    """Compute the best-neighbor distance for a batch of identities.

    Returns a dict mapping identity_id -> (best_distance, best_neighbor_id, best_neighbor_name).
    Uses vectorized numpy operations for efficiency — O(n*m) total, not O(n^2*m).
    """
    if not identity_ids:
        return {}

    # Build a lookup of identity_id -> representative embedding (first available face)
    query_data = {}  # id -> (embedding_vector,)
    for iid in identity_ids:
        fids, embs = get_identity_embeddings(iid, registry, face_data)
        if embs.size > 0:
            query_data[iid] = embs

    if not query_data:
        return {}

    # Build candidate pool: all identities NOT in the query set
    query_set = set(identity_ids)
    all_identities = registry.list_identities()
    candidate_data = {}  # id -> (name, embeddings)
    for cand in all_identities:
        cid = cand["identity_id"]
        if cid in query_set:
            continue
        if cand.get("merged_into"):
            continue
        fids, embs = get_identity_embeddings(cid, registry, face_data)
        if embs.size > 0:
            candidate_data[cid] = (cand.get("name", "Unknown"), embs)

    if not candidate_data:
        return {iid: (999.0, None, None) for iid in identity_ids}

    # Stack all candidate embeddings into one matrix for vectorized distance
    cand_ids = list(candidate_data.keys())
    cand_names = [candidate_data[cid][0] for cid in cand_ids]
    cand_emb_list = [candidate_data[cid][1] for cid in cand_ids]
    # Track which rows belong to which candidate
    cand_row_to_idx = []
    cand_all_embs = []
    for idx, embs in enumerate(cand_emb_list):
        for row in embs:
            cand_all_embs.append(row)
            cand_row_to_idx.append(idx)
    cand_matrix = np.vstack(cand_all_embs)  # shape: (total_cand_faces, 512)
    cand_row_to_idx = np.array(cand_row_to_idx)

    results = {}
    for iid, q_embs in query_data.items():
        # Compute distances from all query faces to all candidate faces
        dists = cdist(q_embs, cand_matrix, metric='euclidean')
        # For each candidate, find the minimum distance across all face pairs
        min_per_row = np.min(dists, axis=0)  # min across query faces for each candidate face
        # Group by candidate identity and find overall min
        best_dist = 999.0
        best_idx = -1
        for cidx in range(len(cand_ids)):
            mask = cand_row_to_idx == cidx
            if mask.any():
                cand_min = float(np.min(min_per_row[mask]))
                if cand_min < best_dist:
                    best_dist = cand_min
                    best_idx = cidx
        if best_idx >= 0:
            results[iid] = (best_dist, cand_ids[best_idx], cand_names[best_idx])
        else:
            results[iid] = (999.0, None, None)

    # Fill in identities that had no embeddings
    for iid in identity_ids:
        if iid not in results:
            results[iid] = (999.0, None, None)

    return results


def find_similar_faces(query_embedding, face_data, registry=None, limit=20, exclude_face_ids=None):
    """
    Find the most similar faces to a query embedding across the entire archive.

    Unlike find_nearest_neighbors() which operates at the identity level,
    this works at the individual face level — returning each face with its
    distance, identity info, and photo context.

    Args:
        query_embedding: 512-dim numpy array (the face to compare)
        face_data: dict mapping face_id -> {"mu": embedding, ...}
        registry: IdentityRegistry (optional, for name lookup)
        limit: max results to return
        exclude_face_ids: set of face_ids to exclude from results

    Returns:
        list of dicts with: face_id, distance, identity_id, identity_name, state
    """
    if query_embedding is None or len(face_data) == 0:
        return []

    exclude = exclude_face_ids or set()
    query = np.array(query_embedding).reshape(1, -1)

    # Build candidate matrix
    candidate_ids = []
    candidate_embs = []
    for fid, fdata in face_data.items():
        if fid in exclude:
            continue
        if "mu" in fdata:
            candidate_ids.append(fid)
            candidate_embs.append(fdata["mu"])

    if not candidate_embs:
        return []

    candidate_matrix = np.vstack(candidate_embs)
    dists = cdist(query, candidate_matrix, metric='euclidean').flatten()

    # Sort by distance
    sorted_indices = np.argsort(dists)

    # Build identity lookup if registry provided
    face_to_identity = {}
    if registry:
        for ident in registry.list_identities():
            if ident.get("merged_into"):
                continue
            iid = ident["identity_id"]
            name = ident.get("name", "Unknown")
            state = ident.get("state", "INBOX")
            for entry in ident.get("anchor_ids", []) + ident.get("candidate_ids", []):
                fid = entry if isinstance(entry, str) else entry.get("face_id", "")
                face_to_identity[fid] = {"identity_id": iid, "name": name, "state": state}

    results = []
    for idx in sorted_indices[:limit]:
        fid = candidate_ids[idx]
        dist = float(dists[idx])
        ident_info = face_to_identity.get(fid, {})

        # Confidence tier
        if dist < 0.80:
            confidence = "VERY HIGH"
        elif dist < 1.00:
            confidence = "HIGH"
        elif dist < 1.20:
            confidence = "MODERATE"
        else:
            confidence = "LOW"

        results.append({
            "face_id": fid,
            "distance": dist,
            "confidence": confidence,
            "identity_id": ident_info.get("identity_id", ""),
            "identity_name": ident_info.get("name", "Unknown"),
            "state": ident_info.get("state", "INBOX"),
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