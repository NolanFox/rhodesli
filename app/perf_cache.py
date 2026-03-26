"""
Precomputed embedding matrices for identity distance computation.
- Confirmed matrix: CONFIRMED identities only (for suggestions/matching)
- Global matrix: ALL active identities (for neighbors/similar sidebar)
Enables vectorized cosine distance computation (O(1) matrix multiply vs O(N) loop).
Session 111f + 135b performance optimization.
"""

import logging
import threading

import numpy as np

logger = logging.getLogger(__name__)

# Global state — confirmed identities only
_confirmed_matrix = None  # shape (num_faces, 512), L2-normalized
_confirmed_face_map = None  # list of (identity_id, face_id) tuples, parallel to rows
_confirmed_identity_ids = None  # set of identity IDs in the matrix
_confirmed_metadata = None  # dict of identity_id -> {"name": str, "face_count": int}
_confirmed_dirty = True
_lock = threading.Lock()

# Global state — ALL active identities (for neighbors endpoint)
_global_matrix = None  # shape (num_faces, 512), L2-normalized
_global_face_map = None  # list of (identity_id, face_id) tuples
_global_identity_map = None  # numpy array, parallel to rows — maps face row to identity index
_global_identity_info = None  # list of (identity_id, name, face_ids_list, face_count)
_global_identity_photos = None  # dict of identity_id -> set of photo_ids
_global_identity_info_by_id = None  # dict of identity_id -> (identity_id, name, face_ids, face_count)
_global_dirty = True
_global_lock = threading.Lock()


def mark_confirmed_dirty():
    """Mark the confirmed matrix as needing rebuild. Called on confirm/merge only."""
    global _confirmed_dirty
    _confirmed_dirty = True


def mark_global_dirty():
    """Mark the global matrix as needing rebuild. Called on any identity mutation."""
    global _global_dirty
    _global_dirty = True


def _rebuild_matrix():
    """Rebuild the confirmed identity embedding matrix from current registry state."""
    global _confirmed_matrix, _confirmed_face_map, _confirmed_identity_ids, _confirmed_metadata, _confirmed_dirty

    import app.main as _main_mod

    try:
        registry = _main_mod.load_registry()
        face_data = _main_mod.get_face_data()
    except Exception as e:
        logger.warning(f"perf_cache: cannot rebuild matrix: {e}")
        _confirmed_matrix = np.array([]).reshape(0, 512)
        _confirmed_face_map = []
        _confirmed_identity_ids = set()
        _confirmed_metadata = {}
        _confirmed_dirty = False
        return

    identities = registry._identities if hasattr(registry, "_identities") else {}

    face_map = []
    embeddings = []
    identity_ids = set()
    metadata = {}  # identity_id -> {"name": str, "face_count": int}

    for iid, idata in identities.items():
        if idata.get("merged_into"):
            continue
        if idata.get("state") != "CONFIRMED":
            continue

        identity_ids.add(iid)

        # Get all face IDs (anchors + candidates)
        all_face_entries = list(idata.get("anchor_ids", [])) + list(idata.get("candidate_ids", []))

        # Cache metadata for get_confirmed_distances() to avoid redundant load_registry()
        face_ids_for_meta = []
        for entry in all_face_entries:
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if fid:
                face_ids_for_meta.append(fid)
        metadata[iid] = {
            "name": idata.get("name", "Unknown"),
            "face_count": len(face_ids_for_meta),
        }

        for entry in all_face_entries:
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if not fid:
                continue
            fd = face_data.get(fid)
            if fd and ("mu" in fd or "embeddings" in fd):
                emb = fd.get("mu", fd.get("embeddings"))
                if hasattr(emb, "__len__") and len(emb) > 0:
                    embeddings.append(np.array(emb).flatten())
                    face_map.append((iid, fid))

    if embeddings:
        matrix = np.vstack(embeddings).astype(np.float32)
        # L2-normalize for cosine distance via dot product
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # avoid division by zero
        matrix = matrix / norms
        _confirmed_matrix = matrix
    else:
        _confirmed_matrix = np.array([]).reshape(0, 512).astype(np.float32)

    _confirmed_face_map = face_map
    _confirmed_identity_ids = identity_ids
    _confirmed_metadata = metadata
    _confirmed_dirty = False

    logger.info(
        f"perf_cache: rebuilt confirmed matrix — {len(face_map)} faces "
        f"from {len(identity_ids)} identities, "
        f"{_confirmed_matrix.nbytes / 1024:.0f}KB"
    )


def get_confirmed_distances(target_embedding, community_slug=None):
    """Return sorted list of dicts with identity_id, name, face_count, best_face_id, distance.

    Uses vectorized np.dot instead of per-face cdist loops.
    Cosine distance = 1 - dot(normalized_target, normalized_corpus).

    Args:
        target_embedding: 1D numpy array (raw, not normalized)
        community_slug: optional, for community-scoped sorting

    Returns:
        List of dicts sorted by distance (same-community first if community_slug provided)
    """
    global _confirmed_dirty

    with _lock:
        if _confirmed_dirty or _confirmed_matrix is None:
            _rebuild_matrix()

    if _confirmed_matrix is None or _confirmed_matrix.shape[0] == 0:
        return []

    # Normalize target
    target = np.array(target_embedding).flatten().astype(np.float32)
    norm = np.linalg.norm(target)
    if norm == 0:
        return []
    target = target / norm

    # Vectorized cosine distance: 1 - dot(target, matrix.T)
    similarities = _confirmed_matrix @ target  # shape (num_faces,)
    distances = 1.0 - similarities

    # Group by identity: find min distance per identity
    identity_best = {}  # identity_id -> (min_distance, best_face_id)
    for idx, (iid, fid) in enumerate(_confirmed_face_map):
        d = float(distances[idx])
        if iid not in identity_best or d < identity_best[iid][0]:
            identity_best[iid] = (d, fid)

    # Build result list with cached metadata (avoids redundant load_registry())
    results = []
    for iid, (dist, best_fid) in identity_best.items():
        meta = (_confirmed_metadata or {}).get(iid, {})
        results.append(
            {
                "identity_id": iid,
                "name": meta.get("name", "Unknown"),
                "face_count": meta.get("face_count", 0),
                "best_face_id": best_fid,
                "distance": dist,
            }
        )

    # Community scoping
    if community_slug:
        try:
            import app.main as _main_mod
            from app.supabase_data import load_communities

            communities = load_communities()
            comm_ids = None
            for comm in communities or []:
                if comm.get("slug") == community_slug:
                    comm_ids = _main_mod._get_community_identity_ids(comm)
                    break

            if comm_ids is not None:
                same = [s for s in results if s["identity_id"] in comm_ids]
                cross = [s for s in results if s["identity_id"] not in comm_ids]
                same.sort(key=lambda s: s["distance"])
                cross.sort(key=lambda s: s["distance"])
                return same + cross
        except Exception:
            pass

    results.sort(key=lambda s: s["distance"])
    return results


# ---- Global (all identities) embedding matrix ----


def _rebuild_global_matrix():
    """Rebuild the global embedding matrix from ALL active (non-merged) identities."""
    global _global_matrix, _global_face_map, _global_identity_map, _global_identity_info
    global _global_identity_photos, _global_identity_info_by_id, _global_dirty

    import app.main as _main_mod

    try:
        registry = _main_mod.load_registry()
        face_data = _main_mod.get_face_data()
        photo_registry = _main_mod.load_photo_registry()
    except Exception as e:
        logger.warning(f"perf_cache: cannot rebuild global matrix: {e}")
        _global_matrix = np.array([]).reshape(0, 512).astype(np.float32)
        _global_face_map = []
        _global_identity_map = np.array([], dtype=np.int32)
        _global_identity_info = []
        _global_identity_photos = {}
        _global_identity_info_by_id = {}
        _global_dirty = False
        return

    identities = registry._identities if hasattr(registry, "_identities") else {}

    face_map = []
    embeddings = []
    identity_indices = []
    identity_info = []
    identity_photos = {}

    for iid, idata in identities.items():
        if idata.get("merged_into"):
            continue

        all_face_entries = list(idata.get("anchor_ids", [])) + list(idata.get("candidate_ids", []))
        face_ids = []
        for entry in all_face_entries:
            fid = entry if isinstance(entry, str) else entry.get("face_id")
            if fid:
                face_ids.append(fid)

        if not face_ids:
            continue

        cand_idx = len(identity_info)
        identity_info.append(
            (
                iid,
                idata.get("name", f"Identity {iid[:8]}..."),
                face_ids,
                len(face_ids),
            )
        )

        # Cache photo IDs for co-occurrence check
        identity_photos[iid] = photo_registry.get_photos_for_faces(face_ids)

        for fid in face_ids:
            fd = face_data.get(fid)
            if fd and ("mu" in fd or "embeddings" in fd):
                emb = fd.get("mu", fd.get("embeddings"))
                if hasattr(emb, "__len__") and len(emb) > 0:
                    embeddings.append(np.array(emb).flatten())
                    face_map.append((iid, fid))
                    identity_indices.append(cand_idx)

    if embeddings:
        matrix = np.vstack(embeddings).astype(np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms
        _global_matrix = matrix
    else:
        _global_matrix = np.array([]).reshape(0, 512).astype(np.float32)

    _global_face_map = face_map
    _global_identity_map = np.array(identity_indices, dtype=np.int32)
    _global_identity_info = identity_info
    _global_identity_info_by_id = {item[0]: item for item in identity_info}
    _global_identity_photos = identity_photos
    _global_dirty = False

    logger.info(
        f"perf_cache: rebuilt global matrix — {len(face_map)} faces "
        f"from {len(identity_info)} identities, "
        f"{_global_matrix.nbytes / 1024:.0f}KB"
    )


def get_all_neighbors(target_id, registry=None, limit=20):
    """Return sorted neighbors for target_id using precomputed global matrix.

    Much faster than find_nearest_neighbors_fast() because the embedding matrix
    is precomputed and cached, eliminating the 100-200ms matrix construction.

    Returns list of dicts with: identity_id, name, distance, face_count, can_merge,
    merge_blocked_reason.
    """
    global _global_dirty

    with _global_lock:
        if _global_dirty or _global_matrix is None:
            _rebuild_global_matrix()

    if _global_matrix is None or _global_matrix.shape[0] == 0:
        return []

    # Find target identity's face embeddings in the global matrix
    target_rows = [i for i, (iid, _) in enumerate(_global_face_map) if iid == target_id]
    if not target_rows:
        return []

    # Get target embeddings (already L2-normalized)
    target_embs = _global_matrix[target_rows]  # shape (n_target_faces, 512)

    # Compute distances: min across target faces for each corpus face
    # Using euclidean distance to match find_nearest_neighbors_fast
    similarities = _global_matrix @ target_embs.T  # shape (corpus, n_target_faces)
    # Cosine distance = 1 - similarity; take min across target faces
    distances = 1.0 - np.max(similarities, axis=1)

    # Get target's photos for co-occurrence check
    target_photos = (_global_identity_photos or {}).get(target_id, set())

    # Group by identity: find min distance per identity
    identity_best = {}
    for idx in range(len(_global_face_map)):
        iid = _global_face_map[idx][0]
        if iid == target_id:
            continue
        d = float(distances[idx])
        if iid not in identity_best or d < identity_best[iid]:
            identity_best[iid] = d

    # Build result list
    candidates = []
    for iid, dist in identity_best.items():
        # O(1) dict lookup instead of O(N) linear scan (Session 139 E1)
        info = _global_identity_info_by_id.get(iid) if _global_identity_info_by_id else None
        if info is None:
            continue

        _, name, face_ids, face_count = info

        # Co-occurrence check
        cand_photos = (_global_identity_photos or {}).get(iid, set())
        co_occurrence = not target_photos.isdisjoint(cand_photos)

        candidates.append(
            {
                "identity_id": iid,
                "name": name,
                "distance": dist,
                "face_count": face_count,
                "can_merge": not co_occurrence,
                "merge_blocked_reason": "co_occurrence" if co_occurrence else None,
            }
        )

    candidates.sort(key=lambda c: c["distance"])
    return candidates[:limit]
