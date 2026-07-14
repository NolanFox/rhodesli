"""Assemble a deterministic, read-only evidence packet for one identity."""

from __future__ import annotations

import hashlib
import json
import math
from itertools import combinations
from typing import Any

import numpy as np


def _pairwise_l2(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine-derived L2 distance for two L2-normalized vectors."""
    cosine = float(np.dot(np.asarray(a, dtype=float), np.asarray(b, dtype=float)))
    return math.sqrt(max(0.0, 2.0 - 2.0 * max(-1.0, min(1.0, cosine))))


def _rank_external_matches(anchor_mu, emb_map, face_to_identity, top_n):
    """Rank non-anchor faces by their minimum distance to any subject anchor."""
    anchors = anchor_mu if isinstance(anchor_mu, dict) else {"anchor": anchor_mu}
    anchor_ids = set(anchors)
    matches = []
    for face_id, mu in emb_map.items():
        if face_id in anchor_ids or not anchors:
            continue
        distance = min(_pairwise_l2(anchor, mu) for anchor in anchors.values())
        identity = face_to_identity.get(face_id)
        if isinstance(identity, dict):
            identity_id = identity.get("identity_id")
            name = identity.get("name")
            state = identity.get("state")
        else:
            identity_id, name, state = identity, None, None
        matches.append(
            {
                "face_id": face_id,
                "l2": distance,
                "identity_id": identity_id,
                "name": name,
                "state": state,
            }
        )
    matches.sort(key=lambda item: (item["l2"], item["face_id"]))
    matches = matches[: max(0, top_n)]
    nearest_l2 = matches[0]["l2"] if matches else None
    return {
        "matches": matches,
        "nearest_l2": nearest_l2,
        "no_confident_match": nearest_l2 is None or nearest_l2 >= 1.05,
    }


def _rows(response) -> list[dict]:
    return list(getattr(response, "data", None) or [])


def _select(sb, table, fields, *, equals=None, contains=None, paged=False):
    """Execute a Supabase select, optionally paging in 1,000-row windows."""
    offset = 0
    output = []
    while True:
        query = sb.table(table).select(fields)
        for column, value in (equals or {}).items():
            query = query.eq(column, value)
        for column, values in (contains or {}).items():
            query = query.in_(column, list(values))
        if paged:
            query = query.range(offset, offset + 999)
        page = _rows(query.execute())
        output.extend(page)
        if not paged or len(page) < 1000:
            return output
        offset += 1000


def _face_id(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("face_id")
    return value if isinstance(value, str) else None


def _embedding_map(path: str) -> dict[str, np.ndarray]:
    result = {}
    for raw in np.load(path, allow_pickle=True):
        if isinstance(raw, np.ndarray) and raw.shape == ():
            raw = raw.item()
        if isinstance(raw, np.void) and raw.dtype.names:
            raw = {key: raw[key] for key in raw.dtype.names}
        if not isinstance(raw, dict):
            continue
        face_id, mu = raw.get("face_id"), raw.get("mu")
        if isinstance(face_id, bytes):
            face_id = face_id.decode("utf-8")
        if not face_id or mu is None:
            continue
        vector = np.asarray(mu, dtype=float).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if norm and np.isfinite(norm) and np.all(np.isfinite(vector)):
            result[str(face_id)] = vector / norm
    return result


def _empty_packet(case_ref, error=None):
    packet = {
        "case_ref": case_ref,
        "subject": {},
        "anchor_faces": [],
        "internal_consistency": {"pairs": [], "l2": None, "same_person": None},
        "external_match": {"matches": [], "nearest_l2": None, "no_confident_match": True},
        "co_occurrence": [],
        "gedcom_context": [],
        "date_location": [],
        "provenance": [],
        "candidates_on_file": [],
    }
    if error:
        packet["error"] = error
    return packet


def _seal(packet):
    canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    packet["manifest"] = {
        "assembled_utc": None,
        "packet_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    return packet


def _date_range(data):
    for key in ("range", "probable_range", "date_range", "year_range"):
        if key in data:
            return data[key]
    earliest = data.get("earliest_year")
    latest = data.get("latest_year")
    return [earliest, latest] if earliest is not None or latest is not None else None


def _as_dict(data):
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        try:
            value = json.loads(data)
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def assemble_evidence_packet(
    case_ref,
    *,
    community_id=None,
    top_n=20,
    sb=None,
    embeddings_path="data/embeddings.npy",
) -> dict:
    """Read evidence for ``case_ref`` without modifying any persistent state."""
    if sb is None:
        from app.supabase_data import get_supabase_client

        sb = get_supabase_client()
    if sb is None:
        return _seal(_empty_packet(case_ref, "no supabase"))

    # reserved; identities/photos are not community-scoped by column (see identity_communities)
    identity_filters = {}
    identities = _select(
        sb,
        "identities",
        "identity_id,name,state,anchor_ids,candidate_ids",
        equals=identity_filters,
        paged=True,
    )
    identity_by_id = {row.get("identity_id"): row for row in identities}
    subject_row = identity_by_id.get(case_ref, {})
    anchor_ids = [face_id for value in subject_row.get("anchor_ids", []) if (face_id := _face_id(value))]
    packet = _empty_packet(case_ref)
    packet["subject"] = {
        "identity_id": subject_row.get("identity_id", case_ref),
        "name": subject_row.get("name"),
        "state": subject_row.get("state"),
        "anchor_ids": anchor_ids,
    }

    face_to_identity = {}
    for identity in identities:
        summary = {key: identity.get(key) for key in ("identity_id", "name", "state")}
        for value in identity.get("anchor_ids", []) + identity.get("candidate_ids", []):
            if face_id := _face_id(value):
                face_to_identity[face_id] = summary

    photo_faces = _select(sb, "photo_faces", "face_id,photo_id", paged=True)
    photo_by_face = {row.get("face_id"): row.get("photo_id") for row in photo_faces}
    packet["anchor_faces"] = [
        {"face_id": face_id, "photo_id": photo_by_face.get(face_id)} for face_id in anchor_ids
    ]

    emb_map = _embedding_map(embeddings_path)
    anchor_mu = {face_id: emb_map[face_id] for face_id in anchor_ids if face_id in emb_map}
    pairs = [
        {"face_id_a": left, "face_id_b": right, "l2": _pairwise_l2(anchor_mu[left], anchor_mu[right])}
        for left, right in combinations(anchor_mu, 2)
    ]
    packet["internal_consistency"] = {
        "pairs": pairs,
        "l2": pairs[0]["l2"] if len(pairs) == 1 else None,
        "same_person": all(pair["l2"] < 0.85 for pair in pairs) if pairs else None,
    }
    packet["external_match"] = _rank_external_matches(anchor_mu, emb_map, face_to_identity, top_n)

    anchor_photos = sorted({photo_by_face[face_id] for face_id in anchor_ids if photo_by_face.get(face_id)})
    cooccurring_identity_ids = set()
    for photo_id in anchor_photos:
        others = []
        for row in photo_faces:
            face_id = row.get("face_id")
            if row.get("photo_id") != photo_id or face_id in anchor_ids:
                continue
            identity = face_to_identity.get(face_id) or {}
            others.append({"face_id": face_id, **{k: identity.get(k) for k in ("identity_id", "name", "state")}})
            if identity.get("state") == "CONFIRMED" and identity.get("identity_id"):
                cooccurring_identity_ids.add(identity["identity_id"])
        packet["co_occurrence"].append({"photo_id": photo_id, "other_faces": others})

    subject_links = _select(
        sb,
        "gedcom_face_links",
        "identity_id,gedcom_id,confidence",
        equals={"identity_id": case_ref},
    )
    packet["candidates_on_file"] = [
        {"gedcom_id": row.get("gedcom_id"), "confidence": row.get("confidence")} for row in subject_links
    ]
    co_links = (
        _select(
            sb,
            "gedcom_face_links",
            "identity_id,gedcom_id,confidence",
            contains={"identity_id": sorted(cooccurring_identity_ids)},
        )
        if cooccurring_identity_ids
        else []
    )
    from app.relationship_routes import _load_gedcom_individual

    seen_gedcom = set()
    for link in subject_links + co_links:
        gedcom_id = link.get("gedcom_id")
        if not gedcom_id or gedcom_id in seen_gedcom:
            continue
        seen_gedcom.add(gedcom_id)
        individual = _load_gedcom_individual(gedcom_id) or {}
        packet["gedcom_context"].append(
            {
                "gedcom_id": gedcom_id,
                "name": individual.get("name"),
                "birth_date": individual.get("birth_date"),
                "death_date": individual.get("death_date"),
                "confidence": link.get("confidence"),
            }
        )

    photo_filters = {}
    photos = _select(
        sb,
        "photos",
        "photo_id,source,collection,source_url",
        equals=photo_filters,
        contains={"photo_id": anchor_photos},
    ) if anchor_photos else []
    photos_by_id = {row.get("photo_id"): row for row in photos}
    dates = _select(sb, "date_labels", "photo_id,data", contains={"photo_id": anchor_photos}) if anchor_photos else []
    locations = (
        _select(sb, "photo_locations", "photo_id,data", contains={"photo_id": anchor_photos})
        if anchor_photos
        else []
    )
    dates_by_id = {row.get("photo_id"): _as_dict(row.get("data")) for row in dates}
    locations_by_id = {row.get("photo_id"): _as_dict(row.get("data")) for row in locations}
    for photo_id in anchor_photos:
        date = dates_by_id.get(photo_id, {})
        location = locations_by_id.get(photo_id, {})
        confidence = location.get("confidence")
        packet["date_location"].append(
            {
                "photo_id": photo_id,
                "reasoning": date.get("reasoning"),
                "range": _date_range(date),
                "location": {
                    "name": location.get("name") or location.get("location_name") or location.get("location"),
                    "confidence": confidence,
                },
                "location_low_confidence": confidence in ("low", "medium"),
            }
        )
        photo = photos_by_id.get(photo_id, {})
        packet["provenance"].append(
            {"photo_id": photo_id, **{key: photo.get(key) for key in ("source", "collection", "source_url")}}
        )
    return _seal(packet)
