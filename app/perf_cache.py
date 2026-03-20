"""
Precomputed embedding matrix for confirmed identities.
Enables vectorized cosine distance computation (O(1) matrix multiply vs O(N) loop).
Session 111f performance optimization.
"""

import logging
import threading

import numpy as np

logger = logging.getLogger(__name__)

# Global state
_confirmed_matrix = None  # shape (num_faces, 512), L2-normalized
_confirmed_face_map = None  # list of (identity_id, face_id) tuples, parallel to rows
_confirmed_identity_ids = None  # set of identity IDs in the matrix
_confirmed_metadata = None  # dict of identity_id -> {"name": str, "face_count": int}
_confirmed_dirty = True
_lock = threading.Lock()


def mark_confirmed_dirty():
    """Mark the confirmed matrix as needing rebuild. Called on confirm/merge only."""
    global _confirmed_dirty
    _confirmed_dirty = True


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
            if fd and "embeddings" in fd:
                emb = fd["embeddings"]
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
