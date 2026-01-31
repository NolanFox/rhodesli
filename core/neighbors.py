import numpy as np
from typing import List, Dict, Any

# --- INSTRUMENTATION IMPORT ---
from core.event_recorder import get_event_recorder

# Constants
SIMILARITY_THRESHOLD = 0.6  # Standard threshold for "High" confidence

def calculate_distance(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """
    Calculate Euclidean distance between two embeddings.
    Lower is better (0.0 is identical).
    """
    diff = emb1 - emb2
    dist = np.sum(diff * diff)
    return float(dist)

def find_nearest_neighbors(
    identity_id: str, 
    registry: Any, 
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Find the nearest identities to a specific identity.
    
    Algorithm:
    1. Get the target identity's embedding (centroid of its anchors).
    2. Compare against ALL other identity embeddings in the system.
    3. Filter out rejected pairs (hard negative constraints).
    4. Sort by distance (ascending).
    5. Log the 'Raw Intelligence' (Top 20) for analysis.
    6. Return the UI-facing list (Top 5).
    """
    
    # 1. Get source embedding
    target_identity = registry.get_identity(identity_id)
    
    # We need the embedding vector. 
    # In a real app, this might come from a separate store or be cached on the identity.
    # Assuming registry or a helper provides access to the embedding matrix.
    # For this implementation, we assume we can load it or it's passed via registry/helper.
    # NOTE: Adapting to your architecture where embeddings are likely stored in .npy
    # and managed alongside the registry.
    
    import os
    
    # Load embeddings (optimization: this should be cached in memory in production)
    embeddings_path = os.path.join("data", "embeddings.npy")
    if not os.path.exists(embeddings_path):
        return []
        
    try:
        # Load the dictionary of {face_id: embedding}
        # Note: In your specific architecture, this might be handled differently.
        # This implementation assumes standard numpy loading for context.
        face_embeddings = np.load(embeddings_path, allow_pickle=True).item()
    except Exception as e:
        print(f"Error loading embeddings: {e}")
        return []

    # Calculate Target Centroid
    # Get all anchor face IDs for the target identity
    target_face_ids = registry.get_anchor_face_ids(identity_id)
    if not target_face_ids:
        return []
        
    target_vectors = [face_embeddings[fid] for fid in target_face_ids if fid in face_embeddings]
    if not target_vectors:
        return []
        
    target_embedding = np.mean(target_vectors, axis=0)

    # 2. Score against all other identities
    results = []
    
    # Get all active identities
    all_identities = registry.list_identities()
    
    for candidate in all_identities:
        cand_id = candidate["identity_id"]
        
        # Skip self
        if cand_id == identity_id:
            continue
            
        # Skip merged identities (ghosts)
        if candidate.get("merged_into"):
            continue
            
        # 3. Filter Rejected (Hard Negative Constraint)
        if registry.is_identity_rejected(identity_id, cand_id):
            continue
            
        # Calculate Candidate Centroid
        cand_face_ids = registry.get_anchor_face_ids(cand_id)
        if not cand_face_ids:
            continue
            
        cand_vectors = [face_embeddings[fid] for fid in cand_face_ids if fid in face_embeddings]
        if not cand_vectors:
            continue
            
        cand_embedding = np.mean(cand_vectors, axis=0)
        
        # Calculate Distance
        score = calculate_distance(target_embedding, cand_embedding)
        
        results.append({
            "id": cand_id,
            "name": candidate.get("name"),
            "score": score,
            "face_count": len(cand_face_ids)
        })

    # 4. Sort by score (ascending distance = descending similarity)
    results.sort(key=lambda x: x["score"])

    # --- INSTRUMENTATION HOOK (The Magnet Observer) ---
    # We log the top 20 results BEFORE truncating to 'limit'.
    # This captures the "invisible" ranking shifts that happen when you merge.
    top_k_snapshot = [
        {
            "id": r["id"], 
            "score": float(r["score"]), 
            "rank": i + 1,
            "name": r.get("name") # Helpful for debugging logs
        }
        for i, r in enumerate(results[:20]) # Capture deeper than UI limit
    ]
    
    get_event_recorder().record("SEARCH", {
        "identity_id": identity_id,
        "candidate_count": len(results),
        "top_k": top_k_snapshot,
        "threshold": SIMILARITY_THRESHOLD,
        "ui_limit": limit
    }, actor="system")
    # --------------------------------------------------

    # 6. Return Top-K for UI
    return results[:limit]