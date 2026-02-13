"""Shared test fixtures for rhodesli_ml tests."""

import json
import os
from pathlib import Path

import pytest
from PIL import Image


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SYNTHETIC_IMAGES_DIR = FIXTURES_DIR / "synthetic_images"
SYNTHETIC_LABELS_PATH = FIXTURES_DIR / "synthetic_date_labels.json"


@pytest.fixture
def synthetic_images_dir(tmp_path):
    """Create a directory with 30 synthetic 64x64 test images."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    for i in range(30):
        img = Image.new("RGB", (64, 64), color=(i * 8 % 256, i * 12 % 256, i * 16 % 256))
        img.save(images_dir / f"photo_{i:03d}.jpg")
    return images_dir


@pytest.fixture
def synthetic_labels():
    """Load synthetic date labels fixture."""
    if SYNTHETIC_LABELS_PATH.exists():
        with open(SYNTHETIC_LABELS_PATH) as f:
            data = json.load(f)
        return data.get("labels", [])

    # Generate inline if fixture doesn't exist yet
    return _generate_synthetic_labels()


@pytest.fixture
def synthetic_labels_file(tmp_path, synthetic_labels):
    """Write synthetic labels to a temp file and return the path."""
    labels_path = tmp_path / "date_labels.json"
    with open(labels_path, "w") as f:
        json.dump({"schema_version": 2, "labels": synthetic_labels}, f)
    return labels_path


@pytest.fixture
def synthetic_labels_with_images(tmp_path):
    """Create both synthetic images and matching labels."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    labels = _generate_synthetic_labels()

    for label in labels:
        photo_id = label["photo_id"]
        img = Image.new("RGB", (64, 64), color=(100, 150, 200))
        img.save(images_dir / f"{photo_id}.jpg")

    labels_path = tmp_path / "date_labels.json"
    with open(labels_path, "w") as f:
        json.dump({"schema_version": 2, "labels": labels}, f)

    return labels_path, images_dir


def _generate_synthetic_labels() -> list[dict]:
    """Generate 30 synthetic date labels covering all decades."""
    import random
    random.seed(42)

    decades = [1900, 1910, 1920, 1930, 1940, 1950, 1960, 1970, 1980, 1990, 2000]
    confidences = ["high", "medium", "low"]
    labels = []

    for i in range(30):
        decade = decades[i % len(decades)]
        conf = confidences[i % 3]

        # Build realistic decade probabilities
        probs = {}
        main_prob = random.uniform(0.4, 0.7)
        probs[str(decade)] = main_prob
        remaining = 1.0 - main_prob

        # Spread remaining probability to adjacent decades
        for offset in [-10, 10]:
            adj = decade + offset
            if 1900 <= adj <= 2000:
                p = remaining * random.uniform(0.2, 0.5)
                probs[str(adj)] = p
                remaining -= p

        # Normalize
        total = sum(probs.values())
        probs = {k: round(v / total, 3) for k, v in probs.items()}

        labels.append({
            "photo_id": f"photo_{i:03d}",
            "source": "gemini",
            "model": "gemini-3-pro-preview",
            "estimated_decade": decade,
            "best_year_estimate": decade + random.randint(0, 9),
            "confidence": conf,
            "probable_range": [decade - 5, decade + 15],
            "decade_probabilities": probs,
            "location_estimate": random.choice(["Rhodes", "NYC", "Miami", "Tampa"]),
            "is_color": decade >= 1960,
            "evidence": {
                "print_format": [{"cue": "test cue", "strength": "moderate", "suggested_range": [decade - 5, decade + 5]}],
                "fashion": [],
                "environment": [],
                "technology": [],
            },
            "cultural_lag_applied": random.choice([True, False]),
            "cultural_lag_note": "",
            "capture_vs_print": "",
            "reasoning_summary": f"Synthetic label for testing, decade {decade}s",
            "created_at": "2026-02-13T00:00:00Z",
        })

    return labels
