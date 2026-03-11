"""Write-only calibration hooks for admin review decisions.

These hooks fire after merge, reject, and confirm actions to record
calibration labels with enough lineage for later replay and rollback.
They intentionally do not fit or refresh models in production.

Session: 63, 97 | AD-149, AD-217, AD-218
"""

import logging
from typing import Optional

import numpy as np

from core.config import DATA_DIR
from core.embeddings_io import load_face_data
from rhodesli_ml.calibration_lineage import (
    LABEL_TYPE_EXPLICIT_NEGATIVE,
    LABEL_TYPE_EXPLICIT_POSITIVE,
    LABEL_TYPE_IMPLICIT_NEGATIVE,
    build_calibration_pair_row,
    record_calibration_pair,
)

logger = logging.getLogger(__name__)

_EMBEDDINGS_CACHE: dict[str, np.ndarray] | None = None
_EMBEDDINGS_CACHE_MTIME: float | None = None


def _get_embedding(face_id: str, embeddings_path: str = "data/embeddings.npy") -> Optional[np.ndarray]:
    """Get embedding vector for a face_id."""
    from pathlib import Path

    global _EMBEDDINGS_CACHE
    global _EMBEDDINGS_CACHE_MTIME

    emb_path = Path(embeddings_path)
    if embeddings_path == "data/embeddings.npy":
        emb_path = Path(DATA_DIR) / "embeddings.npy"
    if not emb_path.exists():
        return None

    mtime = emb_path.stat().st_mtime
    if _EMBEDDINGS_CACHE is None or _EMBEDDINGS_CACHE_MTIME != mtime:
        face_data = load_face_data(emb_path)
        _EMBEDDINGS_CACHE = {fid: row["mu"] for fid, row in face_data.items() if row.get("mu") is not None}
        _EMBEDDINGS_CACHE_MTIME = mtime

    if _EMBEDDINGS_CACHE is None:
        return None
    return _EMBEDDINGS_CACHE.get(face_id)


def _compute_similarity(emb_a: np.ndarray, emb_b: np.ndarray) -> float:
    """Cosine similarity between two embedding vectors."""
    dot = np.dot(emb_a, emb_b)
    norm_a = np.linalg.norm(emb_a)
    norm_b = np.linalg.norm(emb_b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _insert_pair(
    supabase_client,
    face_id_a: str,
    face_id_b: str,
    similarity: float,
    is_match: bool,
    source: str,
    *,
    label_type: str,
    state_event_action: str,
    actor_id: str,
    source_surface: str,
    weight: float | None = None,
    metadata: dict | None = None,
):
    """Insert one lineage-rich calibration pair into Supabase."""
    row = build_calibration_pair_row(
        face_id_a,
        face_id_b,
        similarity_score=similarity,
        is_match=is_match,
        source=source,
        label_type=label_type,
        weight=weight,
        state_event_action=state_event_action,
        actor_id=actor_id,
        source_surface=source_surface,
        metadata=metadata,
    )
    try:
        saved = record_calibration_pair(
            supabase_client,
            row,
            source_surface=source_surface,
            actor_id=actor_id,
            action=state_event_action,
        )
        logger.info(
            "Calibration pair: %s sim=%.3f match=%s label_type=%s source=%s",
            saved["pair_key"],
            similarity,
            is_match,
            saved["label_type"],
            source,
        )
    except Exception as e:
        logger.warning(f"Failed to insert calibration pair: {e}")


async def on_face_merge(face_id_a: str, face_id_b: str,
                        merged_by: str = "admin",
                        supabase_client=None,
                        source_surface: str = "app.engagement_routes._fire_recalibration_hook"):
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
        _insert_pair(
            supabase_client,
            face_id_a,
            face_id_b,
            similarity,
            is_match=True,
            source=f"merge_{merged_by}",
            label_type=LABEL_TYPE_EXPLICIT_POSITIVE,
            state_event_action="merge",
            actor_id=merged_by,
            source_surface=source_surface,
        )


async def on_match_reject(face_id_a: str, face_id_b: str,
                          rejected_by: str = "admin",
                          supabase_client=None,
                          source_surface: str = "app.engagement_routes._fire_recalibration_hook"):
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
        _insert_pair(
            supabase_client,
            face_id_a,
            face_id_b,
            similarity,
            is_match=False,
            source=f"reject_{rejected_by}",
            label_type=LABEL_TYPE_EXPLICIT_NEGATIVE,
            state_event_action="reject",
            actor_id=rejected_by,
            source_surface=source_surface,
            weight=1.5,
        )


async def on_identity_confirm(identity_id: str, anchor_face_ids: list[str],
                              confirmed_by: str = "admin",
                              supabase_client=None,
                              max_negative_samples: int = 10,
                              source_surface: str = "app.engagement_routes._fire_recalibration_hook"):
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
                    _insert_pair(
                        supabase_client,
                        fid,
                        other_fid,
                        similarity,
                        is_match=False,
                        source=f"implicit_confirm_{confirmed_by}",
                        label_type=LABEL_TYPE_IMPLICIT_NEGATIVE,
                        state_event_action="confirm",
                        actor_id=confirmed_by,
                        source_surface=source_surface,
                        metadata={"identity_id": identity_id},
                    )
            break  # One face from this identity is enough
