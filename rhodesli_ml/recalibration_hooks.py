"""
Recalibration Hooks: Auto-update calibration pairs on admin actions.

These hooks fire after face merges, rejections, and identity confirmations
to keep the calibration model current. They insert new pairs into the
calibration_pairs table and check if recalibration is needed.

Designed to handle the future "reject" UX non-match spike gracefully:
- Rate limit: max 1 recalibration per hour
- Drift detection: threshold shift > 0.1 → flag for review
- Weight explicit rejections 1.5x (more informative than implicit)
- Never retroactively change past merge decisions

Session: 63 | AD-149
"""

import logging
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


def _get_embedding(face_id: str, embeddings_path: str = "data/embeddings.npy") -> Optional[np.ndarray]:
    """Get embedding vector for a face_id."""
    from pathlib import Path

    emb_path = Path(embeddings_path)
    if not emb_path.exists():
        return None

    embeddings = np.load(str(emb_path), allow_pickle=True)
    filename_groups = {}

    for emb in embeddings:
        # Explicit face_id match
        if emb.get("face_id") == face_id:
            mu = emb.get("mu")
            if mu is not None:
                return np.array(mu, dtype=np.float32)

        # Build filename index for legacy face_ids
        fn = emb.get("filename", "")
        if fn:
            filename_groups.setdefault(fn, []).append(emb)

    # Try legacy face_id format: "filename:faceN"
    if ":" in face_id:
        parts = face_id.rsplit(":", 1)
        stem = parts[0]
        idx_str = parts[1].replace("face", "")
        try:
            idx = int(idx_str)
            for fn, entries in filename_groups.items():
                if Path(fn).stem == stem and idx < len(entries):
                    mu = entries[idx].get("mu")
                    if mu is not None:
                        return np.array(mu, dtype=np.float32)
        except ValueError:
            pass

    return None


def _compute_similarity(emb_a: np.ndarray, emb_b: np.ndarray) -> float:
    """Cosine similarity between two embedding vectors."""
    dot = np.dot(emb_a, emb_b)
    norm_a = np.linalg.norm(emb_a)
    norm_b = np.linalg.norm(emb_b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _insert_pair(supabase_client, face_id_a: str, face_id_b: str,
                 similarity: float, is_match: bool, source: str,
                 weight: float = 1.0):
    """Insert a calibration pair into Supabase (upsert on conflict)."""
    # Canonical ordering
    a, b = (min(face_id_a, face_id_b), max(face_id_a, face_id_b))
    row = {
        "face_id_a": a,
        "face_id_b": b,
        "similarity_score": round(similarity, 6),
        "is_match": is_match,
        "source": source,
        "weight": weight,
    }
    try:
        supabase_client.table('calibration_pairs').upsert(
            row, on_conflict='face_id_a,face_id_b'
        ).execute()
        logger.info(f"Calibration pair: {a[:20]}..↔{b[:20]}.. sim={similarity:.3f} match={is_match} source={source}")
    except Exception as e:
        logger.warning(f"Failed to insert calibration pair: {e}")


async def on_face_merge(face_id_a: str, face_id_b: str,
                        merged_by: str = "admin",
                        supabase_client=None):
    """
    Hook: called when two faces are confirmed as the same person.

    Creates a match pair and checks recalibration trigger.
    """
    emb_a = _get_embedding(face_id_a)
    emb_b = _get_embedding(face_id_b)

    if emb_a is None or emb_b is None:
        logger.warning(f"on_face_merge: missing embedding for {face_id_a} or {face_id_b}")
        return

    similarity = _compute_similarity(emb_a, emb_b)

    if supabase_client:
        _insert_pair(supabase_client, face_id_a, face_id_b,
                     similarity, is_match=True, source=f"merge_{merged_by}")

        # Check recalibration
        _check_recalibration(supabase_client)


async def on_match_reject(face_id_a: str, face_id_b: str,
                          rejected_by: str = "admin",
                          supabase_client=None):
    """
    Hook: called when a proposed match is rejected ("not same person").

    Creates a non-match pair with weight=1.5 (explicit rejections are
    more informative than implicit non-matches). Ready for future
    "reject" UX — will handle the non-match spike gracefully.
    """
    emb_a = _get_embedding(face_id_a)
    emb_b = _get_embedding(face_id_b)

    if emb_a is None or emb_b is None:
        logger.warning(f"on_match_reject: missing embedding for {face_id_a} or {face_id_b}")
        return

    similarity = _compute_similarity(emb_a, emb_b)

    if supabase_client:
        # Weight 1.5x for explicit rejections (more informative)
        _insert_pair(supabase_client, face_id_a, face_id_b,
                     similarity, is_match=False, source=f"reject_{rejected_by}",
                     weight=1.5)

        _check_recalibration(supabase_client)


async def on_identity_confirm(identity_id: str, anchor_face_ids: list[str],
                              confirmed_by: str = "admin",
                              supabase_client=None,
                              max_negative_samples: int = 10):
    """
    Hook: called when an identity is confirmed.

    Generates implicit non-match pairs with other confirmed identities.
    Samples to avoid generating too many pairs for large identity sets.
    """
    import json
    import random
    from pathlib import Path

    # Load identities to find other confirmed people
    with open(Path("data/identities.json")) as f:
        identities = json.load(f)

    other_faces = []
    for iid, ident in identities.get("identities", {}).items():
        if iid == identity_id:
            continue
        if ident.get("state") != "CONFIRMED":
            continue
        for fid in ident.get("anchor_ids", []):
            emb = _get_embedding(fid)
            if emb is not None:
                other_faces.append((fid, emb))
                break  # One face per other identity

    if not other_faces:
        return

    # Sample if too many
    if len(other_faces) > max_negative_samples:
        other_faces = random.sample(other_faces, max_negative_samples)

    # Get embedding for this identity's face
    for fid in anchor_face_ids:
        emb = _get_embedding(fid)
        if emb is not None:
            for other_fid, other_emb in other_faces:
                similarity = _compute_similarity(emb, other_emb)
                if supabase_client:
                    _insert_pair(supabase_client, fid, other_fid,
                                 similarity, is_match=False,
                                 source=f"implicit_confirm_{confirmed_by}")
            break  # One face from this identity is enough

    if supabase_client:
        _check_recalibration(supabase_client)


def _check_recalibration(supabase_client):
    """Check if recalibration is needed and trigger if so."""
    try:
        from rhodesli_ml.similarity_calibration import SimilarityCalibrator
        cal = SimilarityCalibrator(supabase_client=supabase_client)
        recalibrated, warning = cal.recalibrate_if_needed()
        if recalibrated:
            logger.info(f"Auto-recalibrated calibration model")
            if warning:
                logger.warning(warning)
    except Exception as e:
        logger.warning(f"Recalibration check failed: {e}")
