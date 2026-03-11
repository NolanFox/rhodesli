"""Experiment-only embedding-adapter harness for Session 97 Phase 4."""

from __future__ import annotations

import json
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import roc_auc_score

from core.identity_scoring import extract_face_ids, get_photo_id
from rhodesli_ml.calibration_lineage import utcnow_iso


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


def _family_key(name: str) -> str:
    parts = [part for part in (name or "").split() if part]
    if len(parts) < 2:
        return ""
    return parts[-1].lower()


def _load_photo_years(data_path: Path) -> dict[str, int]:
    labels_path = data_path / "date_labels.json"
    if not labels_path.exists():
        return {}
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    years = {}
    for item in labels.get("labels", []):
        photo_id = item.get("photo_id")
        year = item.get("best_year_estimate")
        if year is None:
            year = item.get("estimated_year")
        if photo_id and year is not None:
            years[photo_id] = int(year)
    return years


@dataclass
class IdentityRecord:
    identity_id: str
    name: str
    family_key: str
    face_count: int
    faces: list[dict[str, Any]]


class ResidualEmbeddingAdapter(nn.Module):
    """A small residual projection that stays in embedding space."""

    def __init__(self, dim: int, hidden_dim: int = 128):
        super().__init__()
        self.adapter = nn.Sequential(
            nn.Linear(dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, dim),
        )
        self.scale = nn.Parameter(torch.tensor(8.0))
        self.bias = nn.Parameter(torch.tensor(0.0))

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return F.normalize(x + (0.1 * self.adapter(x)), dim=-1)

    def forward(self, emb_a: torch.Tensor, emb_b: torch.Tensor) -> torch.Tensor:
        adapted_a = self.encode(emb_a)
        adapted_b = self.encode(emb_b)
        cosine = torch.sum(adapted_a * adapted_b, dim=-1)
        return torch.sigmoid((self.scale * cosine) + self.bias)


def build_identity_records(
    identities_data: dict[str, Any],
    face_data: dict[str, dict[str, Any]],
    data_path: Path,
) -> list[IdentityRecord]:
    """Build confirmed identity records with family keys and photo years."""
    photo_years = _load_photo_years(data_path)
    records = []
    for identity_id, identity in identities_data.get("identities", {}).items():
        if identity.get("state") != "CONFIRMED" or identity.get("merged_into"):
            continue
        faces = []
        for face_id in extract_face_ids(identity):
            face = face_data.get(face_id)
            if face is None or face.get("mu") is None:
                continue
            photo_id = get_photo_id(face_id)
            faces.append(
                {
                    "face_id": face_id,
                    "embedding": np.asarray(face["mu"], dtype=np.float32),
                    "photo_year": photo_years.get(photo_id),
                }
            )
        if faces:
            records.append(
                IdentityRecord(
                    identity_id=identity_id,
                    name=identity.get("name", identity_id),
                    family_key=_family_key(identity.get("name", "")),
                    face_count=len(faces),
                    faces=faces,
                )
            )
    return records


def _split_records(records: list[IdentityRecord], *, by_family: bool, seed: int) -> tuple[list[IdentityRecord], list[IdentityRecord]]:
    rng = random.Random(seed)
    if by_family:
        grouped: dict[str, list[IdentityRecord]] = {}
        for record in records:
            key = record.family_key or record.identity_id
            grouped.setdefault(key, []).append(record)
        group_keys = list(grouped.keys())
        if len(group_keys) < 2:
            return records, []
        rng.shuffle(group_keys)
        eval_groups = set(group_keys[: max(1, len(group_keys) // 4)])
        train = [record for key, group in grouped.items() if key not in eval_groups for record in group]
        eval_records = [record for key, group in grouped.items() if key in eval_groups for record in group]
        if not eval_records:
            return records, []
        return train, eval_records

    multi_face = [record for record in records if len(record.faces) >= 2]
    single_face = [record for record in records if len(record.faces) < 2]
    rng.shuffle(multi_face)
    rng.shuffle(single_face)
    eval_multi = max(1, len(multi_face) // 5) if len(multi_face) > 1 else 0
    eval_single = len(single_face) // 5
    eval_records = multi_face[:eval_multi] + single_face[:eval_single]
    train = multi_face[eval_multi:] + single_face[eval_single:]
    if not eval_records:
        return records, []
    return train, eval_records


def build_pair_records(
    records: list[IdentityRecord],
    *,
    neg_ratio: int = 3,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate pair records with metadata for slice evaluation."""
    rng = random.Random(seed)
    positives: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []

    for record in records:
        if len(record.faces) < 2:
            continue
        for idx, face_a in enumerate(record.faces):
            for face_b in record.faces[idx + 1 :]:
                year_gap = None
                if face_a["photo_year"] is not None and face_b["photo_year"] is not None:
                    year_gap = abs(face_a["photo_year"] - face_b["photo_year"])
                positives.append(
                    {
                        "identity_id_a": record.identity_id,
                        "identity_id_b": record.identity_id,
                        "face_count_a": record.face_count,
                        "face_count_b": record.face_count,
                        "family_match": False,
                        "year_gap": year_gap,
                        "label": 1.0,
                        "embedding_a": face_a["embedding"],
                        "embedding_b": face_b["embedding"],
                    }
                )

    for idx, record_a in enumerate(records):
        for record_b in records[idx + 1 :]:
            pair_candidates = []
            for face_a in record_a.faces:
                for face_b in record_b.faces:
                    cosine = float(
                        np.dot(face_a["embedding"], face_b["embedding"])
                        / (np.linalg.norm(face_a["embedding"]) * np.linalg.norm(face_b["embedding"]) + 1e-8)
                    )
                    pair_candidates.append((cosine, face_a, face_b))
            if not pair_candidates:
                continue
            pair_candidates.sort(key=lambda item: item[0], reverse=True)
            best = pair_candidates[0]
            negatives.append(
                {
                    "identity_id_a": record_a.identity_id,
                    "identity_id_b": record_b.identity_id,
                    "face_count_a": record_a.face_count,
                    "face_count_b": record_b.face_count,
                    "family_match": bool(record_a.family_key and record_a.family_key == record_b.family_key),
                    "year_gap": None,
                    "label": 0.0,
                    "embedding_a": best[1]["embedding"],
                    "embedding_b": best[2]["embedding"],
                }
            )

    target_negatives = min(len(negatives), max(len(positives) * neg_ratio, len(positives)))
    if len(negatives) > target_negatives:
        family_negatives = [pair for pair in negatives if pair["family_match"]]
        non_family_negatives = [pair for pair in negatives if not pair["family_match"]]
        sampled = family_negatives[: max(1, min(len(family_negatives), target_negatives // 3))]
        remaining = target_negatives - len(sampled)
        if remaining > 0:
            sampled.extend(rng.sample(non_family_negatives, min(remaining, len(non_family_negatives))))
        negatives = sampled

    all_pairs = positives + negatives
    rng.shuffle(all_pairs)
    return all_pairs


def _baseline_scores(pair_records: list[dict[str, Any]]) -> np.ndarray:
    scores = []
    for pair in pair_records:
        emb_a = pair["embedding_a"]
        emb_b = pair["embedding_b"]
        scores.append(
            float(np.dot(emb_a, emb_b) / (np.linalg.norm(emb_a) * np.linalg.norm(emb_b) + 1e-8))
        )
    return np.asarray(scores, dtype=np.float32)


def _labels(pair_records: list[dict[str, Any]]) -> np.ndarray:
    return np.asarray([pair["label"] for pair in pair_records], dtype=np.float32)


def _best_threshold(scores: np.ndarray, labels: np.ndarray) -> float:
    candidates = np.unique(scores)
    best_threshold = float(candidates[0]) if len(candidates) else 0.5
    best_f1 = -1.0
    for threshold in candidates:
        preds = scores >= threshold
        tp = float(np.sum((preds == 1) & (labels == 1)))
        fp = float(np.sum((preds == 1) & (labels == 0)))
        fn = float(np.sum((preds == 0) & (labels == 1)))
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = float(threshold)
    return best_threshold


def _slice_metrics(pair_records: list[dict[str, Any]], scores: np.ndarray, threshold: float) -> dict[str, Any]:
    labels = _labels(pair_records)
    preds = scores >= threshold

    def _positive_recall(mask):
        positives = (labels == 1) & mask
        if not np.any(positives):
            return None
        return round(float(np.mean(preds[positives])), 4)

    def _negative_fp(mask):
        negatives = (labels == 0) & mask
        if not np.any(negatives):
            return None
        return round(float(np.mean(preds[negatives])), 4)

    same_family_mask = np.asarray([pair["family_match"] for pair in pair_records], dtype=bool)
    year_gap_20_mask = np.asarray(
        [pair["year_gap"] is not None and pair["year_gap"] >= 20 for pair in pair_records],
        dtype=bool,
    )
    dominant_mask = np.asarray([pair["face_count_a"] >= 5 for pair in pair_records], dtype=bool)
    tail_mask = np.asarray([pair["face_count_a"] <= 4 for pair in pair_records], dtype=bool)

    return {
        "same_family_false_positive_rate": _negative_fp(same_family_mask),
        "year_gap_ge_20_recall": _positive_recall(year_gap_20_mask),
        "dominant_positive_recall": _positive_recall(dominant_mask),
        "tail_positive_recall": _positive_recall(tail_mask),
    }


def _auc(scores: np.ndarray, labels: np.ndarray) -> float | None:
    if len(np.unique(labels)) < 2:
        return None
    return round(float(roc_auc_score(labels, scores)), 4)


def _torch_tensors(pair_records: list[dict[str, Any]]) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    emb_a = torch.tensor(np.stack([pair["embedding_a"] for pair in pair_records]), dtype=torch.float32)
    emb_b = torch.tensor(np.stack([pair["embedding_b"] for pair in pair_records]), dtype=torch.float32)
    labels = torch.tensor(_labels(pair_records), dtype=torch.float32)
    return emb_a, emb_b, labels


def train_embedding_adapter(
    train_pairs: list[dict[str, Any]],
    eval_pairs: list[dict[str, Any]],
    *,
    epochs: int = 20,
    seed: int = 42,
) -> tuple[ResidualEmbeddingAdapter, dict[str, Any]]:
    """Train the embedding adapter and return the best eval checkpoint."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    emb_a_train, emb_b_train, labels_train = _torch_tensors(train_pairs)
    emb_a_eval, emb_b_eval, labels_eval = _torch_tensors(eval_pairs)
    model = ResidualEmbeddingAdapter(emb_a_train.shape[1], hidden_dim=min(128, emb_a_train.shape[1] * 2))
    optimizer = torch.optim.Adam(model.parameters(), lr=5e-4, weight_decay=1e-3)
    criterion = nn.BCELoss()

    best_auc = -1.0
    best_state = None
    for _epoch in range(epochs):
        model.train()
        optimizer.zero_grad()
        preds = model(emb_a_train, emb_b_train)
        loss = criterion(preds, labels_train)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            eval_scores = model(emb_a_eval, emb_b_eval).cpu().numpy()
        eval_auc = roc_auc_score(labels_eval.cpu().numpy(), eval_scores) if len(np.unique(labels_eval.cpu().numpy())) > 1 else 0.0
        if eval_auc > best_auc:
            best_auc = eval_auc
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        train_scores = model(emb_a_train, emb_b_train).cpu().numpy()
        eval_scores = model(emb_a_eval, emb_b_eval).cpu().numpy()

    return model, {
        "train_auc": _auc(train_scores, labels_train.cpu().numpy()),
        "eval_auc": _auc(eval_scores, labels_eval.cpu().numpy()),
        "train_threshold": _best_threshold(train_scores, labels_train.cpu().numpy()),
        "eval_scores": eval_scores,
    }


def _evaluate_split(train_pairs: list[dict[str, Any]], eval_pairs: list[dict[str, Any]], *, seed: int) -> dict[str, Any]:
    if not train_pairs or not eval_pairs:
        return {"status": "insufficient_pairs"}

    baseline_train = _baseline_scores(train_pairs)
    baseline_eval = _baseline_scores(eval_pairs)
    labels_train = _labels(train_pairs)
    labels_eval = _labels(eval_pairs)
    baseline_threshold = _best_threshold(baseline_train, labels_train)
    model, adapter_report = train_embedding_adapter(train_pairs, eval_pairs, seed=seed)
    adapter_scores = adapter_report.pop("eval_scores")
    adapter_threshold = adapter_report["train_threshold"]

    return {
        "status": "ok",
        "counts": {"train_pairs": len(train_pairs), "eval_pairs": len(eval_pairs)},
        "baseline": {
            "auc": _auc(baseline_eval, labels_eval),
            "threshold": round(float(baseline_threshold), 4),
            "slices": _slice_metrics(eval_pairs, baseline_eval, baseline_threshold),
        },
        "adapter": {
            "auc": adapter_report["eval_auc"],
            "threshold": round(float(adapter_threshold), 4),
            "slices": _slice_metrics(eval_pairs, adapter_scores, adapter_threshold),
        },
        "_model_state": model.state_dict(),
    }


def _gate_split(split_report: dict[str, Any]) -> dict[str, Any]:
    if split_report.get("status") != "ok":
        return {"passes": False, "reason": split_report.get("status", "insufficient_pairs")}

    baseline = split_report["baseline"]
    adapter = split_report["adapter"]
    baseline_year20 = baseline["slices"]["year_gap_ge_20_recall"] or 0.0
    adapter_year20 = adapter["slices"]["year_gap_ge_20_recall"] or 0.0
    baseline_same_family = baseline["slices"]["same_family_false_positive_rate"]
    adapter_same_family = adapter["slices"]["same_family_false_positive_rate"]
    same_family_ok = (
        adapter_same_family is None
        or baseline_same_family is None
        or adapter_same_family <= baseline_same_family
    )
    auc_ok = (
        adapter["auc"] is not None
        and baseline["auc"] is not None
        and adapter["auc"] >= (baseline["auc"] - 0.01)
    )
    return {
        "passes": all([auc_ok, same_family_ok, (adapter_year20 - baseline_year20) >= 0.05]),
        "auc_ok": auc_ok,
        "same_family_ok": same_family_ok,
        "year20_improvement": round(adapter_year20 - baseline_year20, 4),
    }


def run_embedding_adapter_experiment(
    identities_data: dict[str, Any],
    face_data: dict[str, dict[str, Any]],
    data_path: Path,
    *,
    seed: int = 42,
) -> dict[str, Any]:
    """Run identity-held-out and family-held-out adapter experiments."""
    records = build_identity_records(identities_data, face_data, data_path)
    identity_train, identity_eval = _split_records(records, by_family=False, seed=seed)
    family_train, family_eval = _split_records(records, by_family=True, seed=seed)

    identity_report = _evaluate_split(
        build_pair_records(identity_train, seed=seed),
        build_pair_records(identity_eval, seed=seed + 1),
        seed=seed,
    )
    family_report = _evaluate_split(
        build_pair_records(family_train, seed=seed + 2),
        build_pair_records(family_eval, seed=seed + 3),
        seed=seed + 1,
    ) if family_eval else {"status": "insufficient_groups"}

    gate = {
        "identity_holdout": _gate_split(identity_report),
        "family_holdout": _gate_split(family_report),
    }
    gate["passes"] = gate["identity_holdout"]["passes"] and gate["family_holdout"]["passes"]

    return {
        "generated_at": utcnow_iso(),
        "git_commit": resolve_git_commit(),
        "dataset": {
            "confirmed_identities": len(records),
            "multi_face_identities": sum(1 for record in records if len(record.faces) >= 2),
            "families_with_labels": len({record.family_key for record in records if record.family_key}),
        },
        "identity_holdout": {key: value for key, value in identity_report.items() if not key.startswith("_")},
        "family_holdout": {key: value for key, value in family_report.items() if not key.startswith("_")},
        "gate": gate,
        "_models": {
            "identity_holdout": identity_report.get("_model_state"),
            "family_holdout": family_report.get("_model_state"),
        },
    }


def save_adapter_artifact(artifact_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    """Persist the best identity-held-out experiment artifact."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    model_state = report.get("_models", {}).get("identity_holdout")
    if model_state is None:
        return {"status": "no_model"}

    artifact_path = artifact_dir / "embedding_adapter_identity_holdout.pt"
    torch.save(model_state, artifact_path)
    manifest = {
        "artifact_path": str(artifact_path),
        "generated_at": report["generated_at"],
        "git_commit": report["git_commit"],
        "gate": report["gate"],
    }
    (artifact_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
