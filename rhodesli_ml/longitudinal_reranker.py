"""Prototype-bank longitudinal reranker for offline identity matching."""

from __future__ import annotations

import json
import math
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from joblib import dump, load
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

from core.identity_scoring import build_identity_embedding_index, extract_face_ids, get_photo_id

FEATURE_SETS = {
    "distance_only": [
        "baseline_distance",
        "baseline_rank",
        "distance_gap_to_best",
        "distance_gap_to_competitor",
    ],
    "temporal": [
        "baseline_distance",
        "baseline_rank",
        "distance_gap_to_best",
        "distance_gap_to_competitor",
        "query_quality",
        "candidate_quality_max",
        "candidate_quality_mean",
        "candidate_face_count",
        "prototype_count",
        "identity_dispersion",
        "nearest_year_gap",
        "year_span_gap",
        "age_at_query_year",
        "age_out_of_bounds",
        "same_collection",
        "cross_collection",
    ],
    "full": [
        "baseline_distance",
        "baseline_rank",
        "distance_gap_to_best",
        "distance_gap_to_competitor",
        "query_quality",
        "candidate_quality_max",
        "candidate_quality_mean",
        "candidate_face_count",
        "prototype_count",
        "identity_dispersion",
        "nearest_year_gap",
        "year_span_gap",
        "age_at_query_year",
        "age_out_of_bounds",
        "same_collection",
        "cross_collection",
        "kinship_is_parent_child",
        "kinship_is_sibling",
        "kinship_is_skip_generation",
        "kinship_temporal_overlap",
        "kinship_age_delta",
    ],
}


@dataclass
class LongitudinalRuntimeContext:
    """Runtime metadata needed for shadow reranking."""

    photo_metadata: dict[str, dict]
    face_to_photo_id: dict[str, str]
    birth_years: dict[str, int]
    relationship_graph: dict[str, dict]
    prototype_bank: dict[str, dict]


def resolve_git_commit() -> str | None:
    """Return the current git commit when available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def face_quality_score(face: dict) -> float:
    """Estimate one comparable face quality score from available metadata."""
    det_score = float(face.get("det_score") or 0.5)
    quality = face.get("quality")
    try:
        quality_val = float(quality) if quality is not None else 1.0
    except (TypeError, ValueError):
        quality_val = 1.0
    mu = np.asarray(face.get("mu"), dtype=np.float32)
    emb_norm = float(np.linalg.norm(mu)) if mu.size else 0.0
    norm_component = min(max(emb_norm / 25.0, 0.4), 1.4)
    return float(np.clip((det_score * 0.6) + (quality_val * 0.2) + (norm_component * 0.2), 0.0, 2.0))


def load_photo_metadata(data_path: Path) -> dict[str, dict]:
    """Load photo-year and collection metadata keyed by photo_id."""
    photo_index = json.load(open(data_path / "photo_index.json"))
    photos = photo_index.get("photos", {})
    labels_path = data_path / "date_labels.json"
    labels = {}
    if labels_path.exists():
        loaded = json.load(open(labels_path))
        for item in loaded.get("labels", []):
            photo_id = item.get("photo_id")
            if photo_id:
                labels[photo_id] = item

    metadata = {}
    for photo_id, photo in photos.items():
        label = labels.get(photo_id, {})
        year = label.get("best_year_estimate")
        if year is None:
            year = label.get("estimated_year")
        metadata[photo_id] = {
            "photo_id": photo_id,
            "collection": photo.get("collection") or photo.get("source") or "",
            "source": photo.get("source") or "",
            "year": year,
        }
    return metadata


def load_face_to_photo_lookup(data_path: Path) -> dict[str, str]:
    """Load canonical face_id -> photo_id mappings from photo_index.json."""
    photo_index = json.load(open(data_path / "photo_index.json"))
    photos = photo_index.get("photos", {})
    lookup = {}
    for photo_id, photo in photos.items():
        for face_id in photo.get("face_ids", []):
            lookup[face_id] = photo_id
    return lookup


def resolve_photo_id(face_id: str, runtime: LongitudinalRuntimeContext | None = None) -> str | None:
    """Resolve one face_id to the canonical photo_id when possible."""
    if runtime is not None:
        photo_id = runtime.face_to_photo_id.get(face_id)
        if photo_id:
            return photo_id
    return get_photo_id(face_id)


def load_birth_years(data_path: Path, identities_data: dict) -> dict[str, int]:
    """Load canonical or ML-estimated birth years keyed by identity_id."""
    birth_years = {}
    for identity_id, identity in identities_data.get("identities", {}).items():
        metadata = identity.get("metadata") or {}
        birth_year = metadata.get("birth_year")
        if birth_year is not None:
            try:
                birth_years[identity_id] = int(birth_year)
            except (TypeError, ValueError):
                continue

    for candidate in [
        Path("rhodesli_ml/data/birth_year_estimates.json"),
        data_path / "birth_year_estimates.json",
    ]:
        if not candidate.exists():
            continue
        estimates = json.load(open(candidate))
        for item in estimates.get("estimates", []):
            identity_id = item.get("identity_id")
            birth_year = item.get("birth_year_estimate")
            if identity_id and birth_year is not None and identity_id not in birth_years:
                birth_years[identity_id] = int(birth_year)
        break
    return birth_years


def load_relationship_graph(data_path: Path) -> dict[str, dict]:
    """Load a lightweight parent/child graph for kinship-risk features."""
    graph = {"parents": defaultdict(set), "children": defaultdict(set)}
    path = data_path / "relationships.json"
    if not path.exists():
        return graph

    data = json.load(open(path))
    for relationship in data.get("relationships", []):
        if relationship.get("type") != "parent_child":
            continue
        parent = relationship.get("person_a")
        child = relationship.get("person_b")
        if parent and child:
            graph["children"][parent].add(child)
            graph["parents"][child].add(parent)
    return graph


def derive_kinship_category(identity_a: str, identity_b: str, relationship_graph: dict[str, dict]) -> str:
    """Return a compact kinship category between two candidate identities."""
    if not identity_a or not identity_b or identity_a == identity_b:
        return "none"

    parents = relationship_graph["parents"]
    children = relationship_graph["children"]

    if identity_b in parents[identity_a] or identity_a in parents[identity_b]:
        return "parent_child"
    if parents[identity_a] & parents[identity_b]:
        return "sibling"

    grandparents_a = {grandparent for parent in parents[identity_a] for grandparent in parents[parent]}
    grandparents_b = {grandparent for parent in parents[identity_b] for grandparent in parents[parent]}
    if identity_b in grandparents_a or identity_a in grandparents_b:
        return "skip_generation"
    if grandparents_a & grandparents_b:
        return "skip_generation"
    if any(child in children[identity_b] for child in children[identity_a]):
        return "skip_generation"

    return "none"


def build_prototype_bank(
    identities_data: dict,
    face_data: dict,
    photo_metadata: dict[str, dict],
    *,
    max_prototypes: int = 5,
    face_to_photo_id: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Select a small, quality-aware prototype bank per confirmed identity."""
    prototype_bank = {}

    for identity_id, identity in identities_data.get("identities", {}).items():
        if identity.get("state") != "CONFIRMED" or identity.get("merged_into"):
            continue

        candidates = []
        for face_id in extract_face_ids(identity):
            face = face_data.get(face_id)
            if face is None or face.get("mu") is None:
                continue
            photo_id = face_to_photo_id.get(face_id) if face_to_photo_id else get_photo_id(face_id)
            meta = photo_metadata.get(photo_id, {})
            candidates.append(
                {
                    "face_id": face_id,
                    "mu": np.asarray(face["mu"], dtype=np.float32),
                    "quality": face_quality_score(face),
                    "year": meta.get("year"),
                    "collection": meta.get("collection") or "",
                }
            )

        if not candidates:
            continue

        candidates.sort(key=lambda item: item["quality"], reverse=True)
        selected = [candidates[0]]
        while len(selected) < min(max_prototypes, len(candidates)):
            best_candidate = None
            best_score = -math.inf
            for candidate in candidates:
                if any(candidate["face_id"] == existing["face_id"] for existing in selected):
                    continue
                year_bonus = 0.2
                year_values = [entry["year"] for entry in selected if entry["year"] is not None]
                if candidate["year"] is not None and year_values:
                    min_gap = min(abs(candidate["year"] - year) for year in year_values)
                    year_bonus = min(min_gap / 20.0, 1.0)
                elif candidate["year"] is not None:
                    year_bonus = 0.5
                dispersion_bonus = min(
                    float(np.mean([np.linalg.norm(candidate["mu"] - entry["mu"]) for entry in selected])) / 1.5,
                    1.0,
                )
                score = (candidate["quality"] * 0.65) + (year_bonus * 0.25) + (dispersion_bonus * 0.10)
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            if best_candidate is None:
                break
            selected.append(best_candidate)

        vectors = [entry["mu"] for entry in selected]
        if len(vectors) > 1:
            pairwise = []
            for index, vec_a in enumerate(vectors):
                for vec_b in vectors[index + 1 :]:
                    pairwise.append(float(np.linalg.norm(vec_a - vec_b)))
            dispersion = float(np.mean(pairwise)) if pairwise else 0.0
        else:
            dispersion = 0.0

        years = [entry["year"] for entry in selected if entry["year"] is not None]
        prototype_bank[identity_id] = {
            "prototype_face_ids": [entry["face_id"] for entry in selected],
            "prototype_count": len(selected),
            "candidate_face_count": len(candidates),
            "quality_max": round(max(entry["quality"] for entry in selected), 4),
            "quality_mean": round(float(np.mean([entry["quality"] for entry in selected])), 4),
            "identity_dispersion": round(dispersion, 4),
            "year_min": min(years) if years else None,
            "year_max": max(years) if years else None,
            "collections": sorted({entry["collection"] for entry in selected if entry["collection"]}),
            "prototype_years": {entry["face_id"]: entry["year"] for entry in selected},
        }
    return prototype_bank


def _score_query_candidates(
    query_face_id: str,
    query_face: dict,
    true_identity_id: str,
    identity_index: dict[str, dict],
    *,
    excluded_photo_ids: set[str],
    top_k: int,
) -> list[dict]:
    """Score candidate identities while holding the query face out of its true identity."""
    candidates = []
    for identity_id, identity_info in identity_index.items():
        embeddings = identity_info["embeddings"]
        if identity_id == true_identity_id:
            keep_indices = [index for index, face_id in enumerate(identity_info["face_ids"]) if face_id != query_face_id]
            if not keep_indices:
                continue
            embeddings = embeddings[keep_indices]
        if excluded_photo_ids.intersection(identity_info.get("photo_ids", set())):
            continue

        query_mu = np.asarray(query_face["mu"], dtype=np.float32).reshape(1, -1)
        distances = np.linalg.norm(embeddings - query_mu, axis=1)
        candidates.append(
            {
                "identity_id": identity_id,
                "distance": float(np.min(distances)),
                "baseline_rank": None,
            }
        )

    candidates.sort(key=lambda item: item["distance"])
    for index, candidate in enumerate(candidates, start=1):
        candidate["baseline_rank"] = index
    return candidates[:top_k]


def _encode_kinship_features(category: str) -> tuple[float, float, float]:
    return (
        1.0 if category == "parent_child" else 0.0,
        1.0 if category == "sibling" else 0.0,
        1.0 if category == "skip_generation" else 0.0,
    )


def build_candidate_feature_row(
    query_face_id: str,
    query_face: dict,
    candidate: dict,
    candidate_rows: list[dict],
    identity_index: dict[str, dict],
    runtime: LongitudinalRuntimeContext,
) -> dict[str, Any]:
    """Build one numeric feature row for a query face and one candidate identity."""
    query_photo_id = resolve_photo_id(query_face_id, runtime)
    query_meta = runtime.photo_metadata.get(query_photo_id, {})
    query_year = query_meta.get("year")
    query_collection = query_meta.get("collection") or ""

    candidate_id = candidate["identity_id"]
    prototype = runtime.prototype_bank[candidate_id]

    distances = []
    for prototype_face_id in prototype["prototype_face_ids"]:
        proto_vec = identity_index[candidate_id]["embeddings"][
            identity_index[candidate_id]["face_ids"].index(prototype_face_id)
        ]
        distances.append(float(np.linalg.norm(np.asarray(query_face["mu"], dtype=np.float32) - proto_vec)))
    nearest_prototype_distance = min(distances) if distances else candidate["distance"]

    prototype_years = [year for year in prototype["prototype_years"].values() if year is not None]
    if query_year is not None and prototype_years:
        nearest_year_gap = min(abs(query_year - year) for year in prototype_years)
        year_min = min(prototype_years)
        year_max = max(prototype_years)
        if year_min <= query_year <= year_max:
            year_span_gap = 0.0
        else:
            year_span_gap = float(min(abs(query_year - year_min), abs(query_year - year_max)))
    else:
        nearest_year_gap = np.nan
        year_span_gap = np.nan

    birth_year = runtime.birth_years.get(candidate_id)
    age_at_query_year = float(query_year - birth_year) if query_year is not None and birth_year is not None else np.nan
    age_out_of_bounds = float(
        not np.isnan(age_at_query_year) and (age_at_query_year < -5 or age_at_query_year > 110)
    )

    competitor = next((row for row in candidate_rows if row["identity_id"] != candidate_id), None)
    if competitor is None:
        competitor = candidate
    competitor_id = competitor["identity_id"]
    kinship_category = derive_kinship_category(candidate_id, competitor_id, runtime.relationship_graph)
    kin_parent_child, kin_sibling, kin_skip_generation = _encode_kinship_features(kinship_category)

    competitor_birth_year = runtime.birth_years.get(competitor_id)
    kinship_age_delta = (
        float(abs(birth_year - competitor_birth_year))
        if birth_year is not None and competitor_birth_year is not None
        else np.nan
    )
    if query_year is not None and birth_year is not None and competitor_birth_year is not None:
        overlap = (
            0 <= query_year - birth_year <= 110
            and 0 <= query_year - competitor_birth_year <= 110
        )
        kinship_temporal_overlap = float(overlap)
    else:
        kinship_temporal_overlap = 0.0

    best_distance = candidate_rows[0]["distance"]
    competitor_distance = competitor["distance"]
    candidate_collections = prototype["collections"]

    return {
        "baseline_distance": float(candidate["distance"]),
        "baseline_rank": float(candidate["baseline_rank"]),
        "distance_gap_to_best": float(candidate["distance"] - best_distance),
        "distance_gap_to_competitor": float(candidate["distance"] - competitor_distance),
        "query_quality": face_quality_score(query_face),
        "candidate_quality_max": float(prototype["quality_max"]),
        "candidate_quality_mean": float(prototype["quality_mean"]),
        "candidate_face_count": float(prototype["candidate_face_count"]),
        "prototype_count": float(prototype["prototype_count"]),
        "identity_dispersion": float(prototype["identity_dispersion"]),
        "nearest_prototype_distance": nearest_prototype_distance,
        "nearest_year_gap": float(nearest_year_gap) if not np.isnan(nearest_year_gap) else np.nan,
        "year_span_gap": float(year_span_gap) if not np.isnan(year_span_gap) else np.nan,
        "age_at_query_year": float(age_at_query_year) if not np.isnan(age_at_query_year) else np.nan,
        "age_out_of_bounds": age_out_of_bounds,
        "same_collection": float(query_collection in candidate_collections and bool(query_collection)),
        "cross_collection": float(bool(query_collection) and query_collection not in candidate_collections),
        "kinship_is_parent_child": kin_parent_child,
        "kinship_is_sibling": kin_sibling,
        "kinship_is_skip_generation": kin_skip_generation,
        "kinship_temporal_overlap": kinship_temporal_overlap,
        "kinship_age_delta": float(kinship_age_delta) if not np.isnan(kinship_age_delta) else np.nan,
    }


def build_shadow_dataset(
    identities_data: dict,
    face_data: dict,
    data_path: Path,
    *,
    top_k: int = 5,
    max_prototypes: int = 5,
) -> tuple[list[dict], LongitudinalRuntimeContext, dict[str, Any]]:
    """Build candidate-level training rows and query-level slice metadata."""
    identity_index = build_identity_embedding_index(identities_data, face_data, states=("CONFIRMED",))
    photo_metadata = load_photo_metadata(data_path)
    face_to_photo_id = load_face_to_photo_lookup(data_path)
    birth_years = load_birth_years(data_path, identities_data)
    relationship_graph = load_relationship_graph(data_path)
    prototype_bank = build_prototype_bank(
        identities_data,
        face_data,
        photo_metadata,
        max_prototypes=max_prototypes,
        face_to_photo_id=face_to_photo_id,
    )
    runtime = LongitudinalRuntimeContext(
        photo_metadata=photo_metadata,
        face_to_photo_id=face_to_photo_id,
        birth_years=birth_years,
        relationship_graph=relationship_graph,
        prototype_bank=prototype_bank,
    )

    confirmed_counts = {
        identity_id: len(info["face_ids"])
        for identity_id, info in identity_index.items()
        if len(info["face_ids"]) >= 2
    }
    dominant_ids = {identity_id for identity_id, _count in Counter(confirmed_counts).most_common(3)}
    sorted_counts = sorted(confirmed_counts.items(), key=lambda item: item[1])
    tail_ids = {identity_id for identity_id, _count in sorted_counts[: max(1, len(sorted_counts) // 2)]}

    rows = []
    query_summary = {}
    for identity_id, identity_info in identity_index.items():
        if len(identity_info["face_ids"]) < 2 or identity_id not in prototype_bank:
            continue

        for query_face_id in identity_info["face_ids"]:
            query_face = face_data.get(query_face_id)
            if query_face is None or query_face.get("mu") is None:
                continue

            query_photo_id = resolve_photo_id(query_face_id, runtime)
            shortlist = _score_query_candidates(
                query_face_id,
                query_face,
                identity_id,
                identity_index,
                excluded_photo_ids={query_photo_id} if query_photo_id else set(),
                top_k=top_k,
            )
            if not shortlist or not any(candidate["identity_id"] == identity_id for candidate in shortlist):
                continue

            other_face_years = []
            query_year = runtime.photo_metadata.get(query_photo_id, {}).get("year")
            for other_face_id in identity_info["face_ids"]:
                if other_face_id == query_face_id:
                    continue
                other_photo_id = resolve_photo_id(other_face_id, runtime)
                other_year = runtime.photo_metadata.get(other_photo_id, {}).get("year")
                if other_year is not None and query_year is not None:
                    other_face_years.append(abs(query_year - other_year))
            min_query_gap = min(other_face_years) if other_face_years else None

            query_key = f"{identity_id}:{query_face_id}"
            query_summary[query_key] = {
                "query_face_id": query_face_id,
                "true_identity_id": identity_id,
                "year_gap": min_query_gap,
                "is_dominant": identity_id in dominant_ids,
                "is_tail": identity_id in tail_ids,
            }

            for candidate in shortlist:
                feature_row = build_candidate_feature_row(
                    query_face_id,
                    query_face,
                    candidate,
                    shortlist,
                    identity_index,
                    runtime,
                )
                feature_row.update(
                    {
                        "query_key": query_key,
                        "query_face_id": query_face_id,
                        "true_identity_id": identity_id,
                        "target_identity_id": candidate["identity_id"],
                        "label": int(candidate["identity_id"] == identity_id),
                    }
                )
                rows.append(feature_row)

    dataset_meta = {
        "dominant_identity_ids": sorted(dominant_ids),
        "tail_identity_ids": sorted(tail_ids),
        "query_summary": query_summary,
    }
    return rows, runtime, dataset_meta


def _matrix_from_rows(rows: list[dict], feature_names: list[str]) -> np.ndarray:
    matrix = []
    for row in rows:
        matrix.append([row.get(name, np.nan) for name in feature_names])
    return np.asarray(matrix, dtype=np.float32)


def _sample_weights(rows: list[dict]) -> np.ndarray:
    counts = Counter(row["true_identity_id"] for row in rows)
    return np.asarray([1.0 / counts[row["true_identity_id"]] for row in rows], dtype=np.float32)


def _group_split(rows: list[dict], *, random_state: int = 42) -> tuple[list[dict], list[dict]]:
    queries = sorted({row["query_key"] for row in rows})
    groups = [query.split(":", 1)[0] for query in queries]
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=random_state)
    train_idx, test_idx = next(splitter.split(queries, groups=groups))
    train_queries = {queries[index] for index in train_idx}
    test_queries = {queries[index] for index in test_idx}
    train_rows = [row for row in rows if row["query_key"] in train_queries]
    test_rows = [row for row in rows if row["query_key"] in test_queries]
    return train_rows, test_rows


def _score_rows(model, rows: list[dict], feature_names: list[str]) -> list[dict]:
    scores = model.predict_proba(_matrix_from_rows(rows, feature_names))[:, 1]
    scored_rows = []
    for row, score in zip(rows, scores):
        updated = dict(row)
        updated["reranker_score"] = float(score)
        scored_rows.append(updated)
    return scored_rows


def _auc(labels: list[int], scores: list[float]) -> float | None:
    if not labels or len(set(labels)) < 2:
        return None
    return float(roc_auc_score(labels, scores))


def evaluate_candidate_rows(scored_rows: list[dict], dataset_meta: dict[str, Any]) -> dict[str, Any]:
    """Compute query-level and slice-level metrics from scored candidate rows."""
    grouped = defaultdict(list)
    for row in scored_rows:
        grouped[row["query_key"]].append(row)

    baseline_top1 = []
    reranker_top1 = []
    baseline_top3 = []
    reranker_top3 = []
    age20_baseline = []
    age20_reranker = []
    age30_baseline = []
    age30_reranker = []
    kinship_fp_baseline = 0
    kinship_fp_reranker = 0
    kinship_queries = 0
    tail_baseline_hits = 0
    tail_reranker_hits = 0
    tail_total = 0

    all_labels = []
    all_baseline_scores = []
    all_reranker_scores = []
    dominant_labels = []
    dominant_baseline_scores = []
    dominant_reranker_scores = []
    rest_labels = []
    rest_baseline_scores = []
    rest_reranker_scores = []

    query_summary = dataset_meta["query_summary"]
    dominant_ids = set(dataset_meta["dominant_identity_ids"])
    tail_ids = set(dataset_meta["tail_identity_ids"])

    for query_key, rows in grouped.items():
        rows = sorted(rows, key=lambda row: row["baseline_distance"])
        reranked = sorted(rows, key=lambda row: (row["reranker_score"], -row["baseline_distance"]), reverse=True)
        summary = query_summary[query_key]

        baseline_top1.append(int(rows[0]["label"] == 1))
        reranker_top1.append(int(reranked[0]["label"] == 1))
        baseline_top3.append(int(any(row["label"] == 1 for row in rows[:3])))
        reranker_top3.append(int(any(row["label"] == 1 for row in reranked[:3])))

        if summary["true_identity_id"] in tail_ids:
            tail_total += 1
            tail_baseline_hits += baseline_top1[-1]
            tail_reranker_hits += reranker_top1[-1]

        year_gap = summary.get("year_gap")
        if year_gap is not None and year_gap >= 20:
            age20_baseline.append(baseline_top1[-1])
            age20_reranker.append(reranker_top1[-1])
        if year_gap is not None and year_gap >= 30:
            age30_baseline.append(baseline_top1[-1])
            age30_reranker.append(reranker_top1[-1])

        baseline_fp_row = rows[0] if rows[0]["label"] == 0 else None
        reranker_fp_row = reranked[0] if reranked[0]["label"] == 0 else None
        if baseline_fp_row is not None:
            kinship_queries += 1
            kinship_fp_baseline += int(
                baseline_fp_row["kinship_is_parent_child"]
                or baseline_fp_row["kinship_is_sibling"]
                or baseline_fp_row["kinship_is_skip_generation"]
            )
        if reranker_fp_row is not None:
            kinship_fp_reranker += int(
                reranker_fp_row["kinship_is_parent_child"]
                or reranker_fp_row["kinship_is_sibling"]
                or reranker_fp_row["kinship_is_skip_generation"]
            )

        for row in rows:
            label = int(row["label"])
            baseline_score = -float(row["baseline_distance"])
            reranker_score = float(row["reranker_score"])
            all_labels.append(label)
            all_baseline_scores.append(baseline_score)
            all_reranker_scores.append(reranker_score)
            if summary["true_identity_id"] in dominant_ids:
                dominant_labels.append(label)
                dominant_baseline_scores.append(baseline_score)
                dominant_reranker_scores.append(reranker_score)
            else:
                rest_labels.append(label)
                rest_baseline_scores.append(baseline_score)
                rest_reranker_scores.append(reranker_score)

    baseline_auc = _auc(all_labels, all_baseline_scores)
    reranker_auc = _auc(all_labels, all_reranker_scores)
    dominant_baseline_auc = _auc(dominant_labels, dominant_baseline_scores)
    dominant_reranker_auc = _auc(dominant_labels, dominant_reranker_scores)
    rest_baseline_auc = _auc(rest_labels, rest_baseline_scores)
    rest_reranker_auc = _auc(rest_labels, rest_reranker_scores)

    dominant_improvement = (dominant_reranker_auc or 0.0) - (dominant_baseline_auc or 0.0)
    rest_improvement = (rest_reranker_auc or 0.0) - (rest_baseline_auc or 0.0)
    if rest_improvement <= 0 and dominant_improvement > 0:
        dominant_lift_ratio = math.inf
    elif rest_improvement <= 0:
        dominant_lift_ratio = 0.0
    else:
        dominant_lift_ratio = dominant_improvement / rest_improvement

    baseline_tail_recall = (tail_baseline_hits / tail_total) if tail_total else None
    reranker_tail_recall = (tail_reranker_hits / tail_total) if tail_total else None

    return {
        "query_count": len(grouped),
        "baseline_top1_recall": round(float(np.mean(baseline_top1)), 4) if baseline_top1 else None,
        "reranker_top1_recall": round(float(np.mean(reranker_top1)), 4) if reranker_top1 else None,
        "baseline_top3_recall": round(float(np.mean(baseline_top3)), 4) if baseline_top3 else None,
        "reranker_top3_recall": round(float(np.mean(reranker_top3)), 4) if reranker_top3 else None,
        "baseline_auc": round(baseline_auc, 4) if baseline_auc is not None else None,
        "reranker_auc": round(reranker_auc, 4) if reranker_auc is not None else None,
        "year_gap_ge_20": {
            "baseline_top1_recall": round(float(np.mean(age20_baseline)), 4) if age20_baseline else None,
            "reranker_top1_recall": round(float(np.mean(age20_reranker)), 4) if age20_reranker else None,
        },
        "year_gap_ge_30": {
            "baseline_top1_recall": round(float(np.mean(age30_baseline)), 4) if age30_baseline else None,
            "reranker_top1_recall": round(float(np.mean(age30_reranker)), 4) if age30_reranker else None,
        },
        "dominant_lift_ratio": round(float(dominant_lift_ratio), 4) if math.isfinite(dominant_lift_ratio) else math.inf,
        "tail_recall_delta": (
            round(float(reranker_tail_recall - baseline_tail_recall), 4)
            if baseline_tail_recall is not None and reranker_tail_recall is not None
            else None
        ),
        "same_family_false_positive_rate": {
            "baseline": round(kinship_fp_baseline / kinship_queries, 4) if kinship_queries else None,
            "reranker": round(kinship_fp_reranker / kinship_queries, 4) if kinship_queries else None,
        },
    }


def fit_feature_variants(
    rows: list[dict],
    *,
    random_state: int = 42,
) -> tuple[dict[str, Any], list[dict], list[dict]]:
    """Train all feature variants and return evaluation reports."""
    train_rows, test_rows = _group_split(rows, random_state=random_state)
    reports = {}

    for variant, feature_names in FEATURE_SETS.items():
        model = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=4,
            max_iter=200,
            min_samples_leaf=10,
            random_state=random_state,
        )
        model.fit(
            _matrix_from_rows(train_rows, feature_names),
            np.asarray([row["label"] for row in train_rows], dtype=np.int64),
            sample_weight=_sample_weights(train_rows),
        )
        scored_rows = _score_rows(model, test_rows, feature_names)
        reports[variant] = {
            "feature_names": feature_names,
            "model": model,
            "metrics": evaluate_candidate_rows(scored_rows, {"query_summary": {}, "dominant_identity_ids": [], "tail_identity_ids": []}),
        }

    return reports, train_rows, test_rows


def train_longitudinal_shadow_reranker(
    identities_data: dict,
    face_data: dict,
    data_path: Path,
    *,
    top_k: int = 5,
    max_prototypes: int = 5,
    random_state: int = 42,
) -> tuple[dict[str, Any], LongitudinalRuntimeContext]:
    """Train and evaluate the shadow reranker across all feature variants."""
    rows, runtime, dataset_meta = build_shadow_dataset(
        identities_data,
        face_data,
        data_path,
        top_k=top_k,
        max_prototypes=max_prototypes,
    )
    train_rows, test_rows = _group_split(rows, random_state=random_state)
    reports = {}

    for variant, feature_names in FEATURE_SETS.items():
        model = HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=4,
            max_iter=200,
            min_samples_leaf=10,
            random_state=random_state,
        )
        model.fit(
            _matrix_from_rows(train_rows, feature_names),
            np.asarray([row["label"] for row in train_rows], dtype=np.int64),
            sample_weight=_sample_weights(train_rows),
        )
        scored_rows = _score_rows(model, test_rows, feature_names)
        reports[variant] = {
            "feature_names": feature_names,
            "model": model,
            "metrics": evaluate_candidate_rows(scored_rows, dataset_meta),
        }

    best_variant = max(
        reports.items(),
        key=lambda item: (
            item[1]["metrics"]["reranker_top1_recall"] or 0.0,
            item[1]["metrics"]["year_gap_ge_20"]["reranker_top1_recall"] or 0.0,
        ),
    )[0]

    return {
        "dataset_rows": len(rows),
        "train_rows": len(train_rows),
        "test_rows": len(test_rows),
        "top_k": top_k,
        "max_prototypes": max_prototypes,
        "dominant_identity_ids": dataset_meta["dominant_identity_ids"],
        "tail_identity_ids": dataset_meta["tail_identity_ids"],
        "prototype_bank": runtime.prototype_bank,
        "variants": {
            variant: {
                "feature_names": payload["feature_names"],
                "metrics": payload["metrics"],
            }
            for variant, payload in reports.items()
        },
        "best_variant": best_variant,
        "_models": {variant: payload["model"] for variant, payload in reports.items()},
    }, runtime


def save_shadow_artifact(output_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Persist the best shadow reranker artifact and a compact manifest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    best_variant = report["best_variant"]
    model = report["_models"][best_variant]
    model_path = output_dir / "model.joblib"
    dump(model, model_path)

    manifest = {
        "artifact_version": 1,
        "trained_at": report.get("trained_at"),
        "git_commit": report.get("git_commit"),
        "best_variant": best_variant,
        "feature_names": report["variants"][best_variant]["feature_names"],
        "metrics": report["variants"][best_variant]["metrics"],
        "top_k": report["top_k"],
        "max_prototypes": report["max_prototypes"],
        "model_path": str(model_path.name),
    }
    with open(output_dir / "manifest.json", "w") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest


class LongitudinalShadowReranker:
    """Runtime loader used by the shared offline scorer when the flag is enabled."""

    def __init__(
        self,
        *,
        manifest: dict[str, Any],
        model,
        runtime: LongitudinalRuntimeContext,
    ):
        self.manifest = manifest
        self.model = model
        self.runtime = runtime

    @classmethod
    def load(
        cls,
        artifact_dir: Path,
        identities_data: dict,
        face_data: dict,
        data_path: Path,
    ) -> "LongitudinalShadowReranker":
        manifest = json.load(open(Path(artifact_dir) / "manifest.json"))
        model = load(Path(artifact_dir) / manifest["model_path"])
        runtime = LongitudinalRuntimeContext(
            photo_metadata=load_photo_metadata(data_path),
            face_to_photo_id=load_face_to_photo_lookup(data_path),
            birth_years=load_birth_years(data_path, identities_data),
            relationship_graph=load_relationship_graph(data_path),
            prototype_bank=build_prototype_bank(
                identities_data,
                face_data,
                load_photo_metadata(data_path),
                max_prototypes=manifest.get("max_prototypes", 5),
                face_to_photo_id=load_face_to_photo_lookup(data_path),
            ),
        )
        return cls(manifest=manifest, model=model, runtime=runtime)

    def rerank(
        self,
        query_face_id: str,
        query_face: dict,
        candidate_rows: list[dict],
        identity_index: dict[str, dict],
        *,
        source_identity: dict | None = None,
    ) -> list[dict]:
        """Rerank a baseline shortlist with the trained shadow model."""
        del source_identity
        feature_names = self.manifest["feature_names"]
        features = [
            build_candidate_feature_row(
                query_face_id,
                query_face,
                candidate,
                candidate_rows,
                identity_index,
                self.runtime,
            )
            for candidate in candidate_rows
        ]
        scores = self.model.predict_proba(_matrix_from_rows(features, feature_names))[:, 1]
        reranked = []
        for candidate, feature_row, score in zip(candidate_rows, features, scores):
            updated = dict(candidate)
            updated["reranker_score"] = float(score)
            updated["scorer_variant"] = f"longitudinal_shadow:{self.manifest['best_variant']}"
            updated["feature_debug"] = {
                key: feature_row[key]
                for key in ("nearest_year_gap", "year_span_gap", "same_collection", "cross_collection")
            }
            reranked.append(updated)
        reranked.sort(key=lambda row: (row["reranker_score"], -row["distance"]), reverse=True)
        return reranked
