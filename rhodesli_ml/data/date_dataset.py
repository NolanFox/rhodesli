"""PyTorch Dataset for date estimation training.

Loads photos and their silver/gold date labels, returns image tensors
with ordinal targets and optional soft label distributions.
"""

import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from rhodesli_ml.data.augmentations import get_train_transforms, get_val_transforms


# Decade classes: 1900s through 2000s (11 decades, indices 0-10)
NUM_DECADES = 11
DECADE_START = 1900
DECADE_END = 2000
VALID_DECADES = list(range(DECADE_START, DECADE_END + 1, 10))


def decade_to_index(decade: int) -> int:
    """Convert decade (e.g. 1940) to class index (0-10)."""
    idx = (decade - DECADE_START) // 10
    return max(0, min(NUM_DECADES - 1, idx))


def index_to_decade(index: int) -> int:
    """Convert class index back to decade."""
    return DECADE_START + index * 10


def decade_probs_to_tensor(probs: dict, num_classes: int = NUM_DECADES) -> torch.Tensor:
    """Convert decade_probabilities dict to a tensor of class probabilities.

    Args:
        probs: Dict mapping decade strings to probabilities, e.g. {"1930": 0.3, "1940": 0.7}
        num_classes: Number of decade classes.

    Returns:
        Tensor of shape (num_classes,) with probabilities summing to 1.0.
    """
    tensor = torch.zeros(num_classes)
    for decade_str, prob in probs.items():
        try:
            decade = int(decade_str)
            idx = decade_to_index(decade)
            tensor[idx] += prob
        except (ValueError, IndexError):
            continue

    # Normalize if any probability was assigned
    total = tensor.sum()
    if total > 0:
        tensor = tensor / total
    return tensor


def make_ordinal_target(class_idx: int, num_classes: int = NUM_DECADES) -> torch.Tensor:
    """Create ordinal regression target for CORAL loss.

    For class k, the target is [1, 1, ..., 1, 0, 0, ..., 0]
    where the first k elements are 1 (P(class > j) for j < k).

    Returns tensor of shape (num_classes - 1,).
    """
    target = torch.zeros(num_classes - 1)
    target[:class_idx] = 1.0
    return target


class DateEstimationDataset(Dataset):
    """Dataset for photo date estimation.

    Each item returns:
        - image: Tensor of shape (3, H, W)
        - ordinal_target: Tensor of shape (num_classes - 1,) for CORAL loss
        - class_index: Integer class index
        - soft_labels: Tensor of shape (num_classes,) with probability distribution
                       (zeros if no soft labels available)
        - has_soft_labels: Boolean indicating if soft labels are available
    """

    def __init__(
        self,
        labels: list[dict],
        photos_dir: str | Path,
        photo_index: dict | None = None,
        transform=None,
        num_classes: int = NUM_DECADES,
    ):
        """Initialize dataset.

        Args:
            labels: List of label dicts with photo_id, estimated_decade, etc.
            photos_dir: Directory containing photo files.
            photo_index: Optional photo_index dict for path lookup.
            transform: Image transform pipeline. If None, uses val transforms.
            num_classes: Number of decade classes.
        """
        self.photos_dir = Path(photos_dir)
        self.photo_index = photo_index or {}
        self.transform = transform or get_val_transforms()
        self.num_classes = num_classes

        # Filter to labels with valid decades and findable photos
        self.items = []
        for label in labels:
            decade = label.get("estimated_decade")
            if not isinstance(decade, int) or decade < DECADE_START or decade > DECADE_END:
                continue

            photo_path = self._resolve_photo_path(label["photo_id"])
            if photo_path is None:
                continue

            self.items.append({
                "photo_id": label["photo_id"],
                "photo_path": photo_path,
                "decade": decade,
                "class_index": decade_to_index(decade),
                "decade_probabilities": label.get("decade_probabilities", {}),
                "confidence": label.get("confidence", "medium"),
            })

    def _resolve_photo_path(self, photo_id: str) -> Path | None:
        """Resolve a photo ID to its file path."""
        # Try photo_index lookup first
        if photo_id in self.photo_index:
            photo_entry = self.photo_index[photo_id]
            if isinstance(photo_entry, dict):
                path_str = photo_entry.get("path", "")
                if path_str:
                    candidate = self.photos_dir / Path(path_str).name
                    if candidate.exists():
                        return candidate

        # Try direct file search in photos_dir
        if self.photos_dir.exists():
            for ext in [".jpg", ".jpeg", ".png"]:
                for f in self.photos_dir.iterdir():
                    if f.stem == photo_id or photo_id in f.name:
                        return f

        return None

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int) -> dict:
        item = self.items[idx]

        # Load image
        try:
            img = Image.open(item["photo_path"]).convert("RGB")
        except Exception:
            # Return a blank image on error
            img = Image.new("RGB", (224, 224), (128, 128, 128))

        if self.transform:
            img = self.transform(img)

        # Ordinal target for CORAL loss
        ordinal_target = make_ordinal_target(item["class_index"], self.num_classes)

        # Soft labels from decade_probabilities
        soft_labels = decade_probs_to_tensor(
            item["decade_probabilities"], self.num_classes
        )
        has_soft_labels = soft_labels.sum() > 0

        return {
            "image": img,
            "ordinal_target": ordinal_target,
            "class_index": item["class_index"],
            "soft_labels": soft_labels,
            "has_soft_labels": has_soft_labels,
            "photo_id": item["photo_id"],
        }


def load_labels_from_file(
    path: str | Path,
    exclude_models: list[str] | None = None,
    training_only: bool = True,
) -> list[dict]:
    """Load date labels from JSON file with optional filtering.

    Args:
        path: Path to date labels JSON file.
        exclude_models: List of model name substrings to exclude (e.g. ["2.5-flash"]).
        training_only: If True (default), exclude labels where training_eligible=False.
            Labels without the field are assumed eligible (backward compatible).

    Returns:
        List of label dicts.
    """
    path = Path(path)
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    labels = data.get("labels", [])

    if training_only:
        labels = [l for l in labels if l.get("training_eligible", True)]

    if exclude_models:
        labels = [
            l for l in labels
            if not any(ex in l.get("model", "") for ex in exclude_models)
        ]

    return labels


def create_train_val_split(
    labels: list[dict],
    train_ratio: float = 0.8,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """Split labels into train and validation sets, stratified by decade.

    Uses a hash-based assignment so each photo's train/val membership is
    stable regardless of how many other photos are in the dataset.  Adding
    or removing labels never reshuffles existing assignments.

    Returns:
        (train_labels, val_labels)
    """
    import hashlib

    train_labels = []
    val_labels = []

    for label in labels:
        photo_id = label.get("photo_id", "")
        # Deterministic hash: same photo_id always maps to the same bucket
        h = hashlib.md5(f"{photo_id}:{seed}".encode()).hexdigest()
        bucket = int(h[:8], 16) / 0xFFFFFFFF  # uniform in [0, 1]
        if bucket < train_ratio:
            train_labels.append(label)
        else:
            val_labels.append(label)

    return train_labels, val_labels
