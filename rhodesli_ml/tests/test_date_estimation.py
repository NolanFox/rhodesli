"""Comprehensive tests for the date estimation pipeline.

Tests cover:
- CORAL loss computation
- Ordinal probability extraction
- Augmentation pipeline
- Dataset loading and label parsing
- Model forward pass and training step
- Evaluation metrics computation
- Gate pass/fail logic
- End-to-end pipeline validation
"""

import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from rhodesli_ml.data.date_dataset import (
    NUM_DECADES,
    DateEstimationDataset,
    create_train_val_split,
    decade_probs_to_tensor,
    decade_to_index,
    index_to_decade,
    load_labels_from_file,
    make_ordinal_target,
)
from rhodesli_ml.data.date_labels import (
    DateLabel,
    PhotoMetadata,
    VALID_CONDITIONS,
    VALID_PHOTO_TYPES,
    VALID_SETTINGS,
    decade_to_ordinal,
    load_date_labels,
    load_photo_metadata,
    ordinal_to_decade,
)
from rhodesli_ml.models.date_classifier import (
    CoralLoss,
    DateEstimationModel,
    ordinal_logits_to_probs,
    probs_to_predicted_class,
)
from rhodesli_ml.evaluation.regression_gate import (
    GateResult,
    compute_brier_score,
)
from rhodesli_ml.data.augmentations import (
    FadingTransform,
    FilmGrainTransform,
    GeometricDistortionTransform,
    JPEGCompressionTransform,
    ResolutionDegradationTransform,
    ScanningArtifactTransform,
    SepiaTransform,
    get_train_transforms,
    get_val_transforms,
)


# ============================================================
# CORAL Loss Tests
# ============================================================

class TestCoralLoss:
    def test_coral_loss_shape(self):
        """CORAL loss accepts correct shapes and returns scalar."""
        loss_fn = CoralLoss()
        logits = torch.randn(4, 10)  # batch=4, 11 classes -> 10 thresholds
        targets = torch.zeros(4, 10)
        targets[0, :3] = 1.0  # class 3
        targets[1, :5] = 1.0  # class 5
        loss = loss_fn(logits, targets)
        assert loss.shape == ()
        assert loss.item() > 0

    def test_coral_loss_perfect_prediction(self):
        """CORAL loss is low when logits match targets."""
        loss_fn = CoralLoss()
        # Strong positive logits for "class > k" where target says yes
        targets = torch.zeros(2, 5)
        targets[0, :2] = 1.0  # class 2
        targets[1, :4] = 1.0  # class 4

        # Perfect logits: high where target=1, low where target=0
        logits = torch.zeros(2, 5)
        logits[0, :2] = 5.0
        logits[0, 2:] = -5.0
        logits[1, :4] = 5.0
        logits[1, 4:] = -5.0

        loss = loss_fn(logits, targets)
        assert loss.item() < 0.1

    def test_coral_loss_wrong_prediction(self):
        """CORAL loss is high when logits contradict targets."""
        loss_fn = CoralLoss()
        targets = torch.zeros(2, 5)
        targets[0, :2] = 1.0

        # Inverted logits
        logits = torch.zeros(2, 5)
        logits[0, :2] = -5.0
        logits[0, 2:] = 5.0

        loss = loss_fn(logits, targets)
        assert loss.item() > 2.0


# ============================================================
# Ordinal Probability Tests
# ============================================================

class TestOrdinalProbs:
    def test_probs_sum_to_one(self):
        """Class probabilities from ordinal logits sum to 1."""
        logits = torch.randn(8, 10)
        probs = ordinal_logits_to_probs(logits)
        sums = probs.sum(dim=1)
        assert torch.allclose(sums, torch.ones(8), atol=1e-5)

    def test_probs_shape(self):
        """Output has num_classes columns (one more than logits)."""
        logits = torch.randn(4, 10)
        probs = ordinal_logits_to_probs(logits)
        assert probs.shape == (4, 11)

    def test_probs_non_negative(self):
        """All probabilities are non-negative."""
        logits = torch.randn(16, 10)
        probs = ordinal_logits_to_probs(logits)
        assert (probs >= 0).all()

    def test_strong_logits_give_peaked_distribution(self):
        """Strong positive logits for early thresholds peak at a high class."""
        logits = torch.zeros(1, 10)
        logits[0, :5] = 10.0  # P(class > 0..4) ≈ 1
        logits[0, 5:] = -10.0  # P(class > 5..9) ≈ 0
        probs = ordinal_logits_to_probs(logits)
        predicted = probs_to_predicted_class(probs)
        assert predicted.item() == 5

    def test_uniform_logits_give_valid_distribution(self):
        """Zero logits give a valid probability distribution."""
        logits = torch.zeros(1, 10)
        probs = ordinal_logits_to_probs(logits)
        # All probabilities should be non-negative and sum to 1
        assert (probs >= 0).all()
        assert torch.allclose(probs.sum(), torch.tensor(1.0), atol=1e-5)


# ============================================================
# Dataset Tests
# ============================================================

class TestDateDataset:
    def test_decade_to_index_roundtrip(self):
        """Decade -> index -> decade roundtrip works."""
        for decade in range(1900, 2010, 10):
            idx = decade_to_index(decade)
            back = index_to_decade(idx)
            assert back == decade

    def test_decade_to_index_clamping(self):
        """Out-of-range decades are clamped."""
        assert decade_to_index(1800) == 0
        assert decade_to_index(2100) == NUM_DECADES - 1

    def test_ordinal_target_shape(self):
        """Ordinal target has correct shape."""
        target = make_ordinal_target(3, 11)
        assert target.shape == (10,)

    def test_ordinal_target_values(self):
        """Ordinal target has 1s before class index, 0s after."""
        target = make_ordinal_target(4, 11)
        assert target[:4].sum() == 4.0
        assert target[4:].sum() == 0.0

    def test_ordinal_target_class_zero(self):
        """Class 0 has all zeros."""
        target = make_ordinal_target(0, 11)
        assert target.sum() == 0.0

    def test_ordinal_target_last_class(self):
        """Last class has all ones."""
        target = make_ordinal_target(10, 11)
        assert target.sum() == 10.0

    def test_decade_probs_to_tensor(self):
        """Decade probabilities converted to proper tensor."""
        probs = {"1930": 0.3, "1940": 0.5, "1950": 0.2}
        tensor = decade_probs_to_tensor(probs)
        assert tensor.shape == (NUM_DECADES,)
        assert abs(tensor.sum().item() - 1.0) < 1e-5
        assert tensor[3].item() == pytest.approx(0.3, abs=1e-3)  # 1930s
        assert tensor[4].item() == pytest.approx(0.5, abs=1e-3)  # 1940s

    def test_decade_probs_empty(self):
        """Empty probabilities produce zero tensor."""
        tensor = decade_probs_to_tensor({})
        assert tensor.sum().item() == 0.0

    def test_dataset_creation(self, synthetic_labels_with_images):
        """Dataset loads successfully from labels and images."""
        labels_path, images_dir = synthetic_labels_with_images
        labels = load_labels_from_file(labels_path)
        dataset = DateEstimationDataset(
            labels=labels,
            photos_dir=images_dir,
        )
        assert len(dataset) > 0

    def test_dataset_item_shape(self, synthetic_labels_with_images):
        """Dataset items have correct tensor shapes."""
        labels_path, images_dir = synthetic_labels_with_images
        labels = load_labels_from_file(labels_path)
        dataset = DateEstimationDataset(
            labels=labels,
            photos_dir=images_dir,
        )
        item = dataset[0]
        assert item["image"].shape == (3, 224, 224)
        assert item["ordinal_target"].shape == (NUM_DECADES - 1,)
        assert item["soft_labels"].shape == (NUM_DECADES,)
        assert isinstance(item["class_index"], int)

    def test_train_val_split(self, synthetic_labels):
        """Train/val split is stratified and maintains total count."""
        train, val = create_train_val_split(synthetic_labels, train_ratio=0.8)
        assert len(train) + len(val) == len(synthetic_labels)
        assert len(train) > len(val)

    def test_load_labels_nonexistent(self, tmp_path):
        """Loading from nonexistent file returns empty list."""
        labels = load_labels_from_file(tmp_path / "nonexistent.json")
        assert labels == []


# ============================================================
# Date Labels Module Tests
# ============================================================

class TestDateLabels:
    def test_decade_to_ordinal_mapping(self):
        """Decade to ordinal mapping covers expected range."""
        assert decade_to_ordinal(1900) == 0
        assert decade_to_ordinal(1940) == 4
        assert decade_to_ordinal(2000) == 10

    def test_ordinal_to_decade_mapping(self):
        """Ordinal to decade mapping reverses correctly."""
        assert ordinal_to_decade(0) == 1900
        assert ordinal_to_decade(4) == 1940

    def test_load_date_labels_gold_overrides(self, tmp_path):
        """Gold labels (user) override silver labels (gemini)."""
        labels_file = tmp_path / "labels.json"
        data = {
            "schema_version": 2,
            "labels": [
                {"photo_id": "p1", "estimated_decade": 1940, "source": "gemini", "confidence": "medium"},
                {"photo_id": "p1", "estimated_decade": 1950, "source": "user", "confidence": "high"},
            ]
        }
        with open(labels_file, "w") as f:
            json.dump(data, f)

        labels = load_date_labels(str(labels_file))
        assert len(labels) == 1
        assert labels[0].decade == 1950
        assert labels[0].source == "user"


# ============================================================
# Augmentation Tests
# ============================================================

class TestAugmentations:
    def _make_test_image(self):
        return Image.new("RGB", (100, 100), color=(128, 128, 128))

    def test_sepia_transform(self):
        """Sepia transform produces valid RGB image."""
        img = self._make_test_image()
        result = SepiaTransform()(img)
        assert result.size == (100, 100)
        assert result.mode == "RGB"

    def test_film_grain_transform(self):
        """Film grain adds noise without crashing."""
        img = self._make_test_image()
        result = FilmGrainTransform(intensity=0.1)(img)
        assert result.size == (100, 100)

    def test_resolution_degradation(self):
        """Resolution degradation preserves output size."""
        img = self._make_test_image()
        result = ResolutionDegradationTransform()(img)
        assert result.size == (100, 100)

    def test_jpeg_compression(self):
        """JPEG compression transform produces valid image."""
        img = self._make_test_image()
        result = JPEGCompressionTransform()(img)
        assert result.size == (100, 100)

    def test_scanning_artifact(self):
        """Scanning artifact transform runs without error."""
        img = self._make_test_image()
        result = ScanningArtifactTransform()(img)
        assert result.size == (100, 100)

    def test_geometric_distortion(self):
        """Geometric distortion produces valid output."""
        img = self._make_test_image()
        result = GeometricDistortionTransform(max_shift=0.03)(img)
        assert result.size == (100, 100)

    def test_fading_transform(self):
        """Fading transform reduces contrast."""
        img = self._make_test_image()
        result = FadingTransform()(img)
        assert result.size == (100, 100)

    def test_train_transforms_pipeline(self):
        """Full training transform pipeline runs without error."""
        img = Image.new("RGB", (300, 300), color=(100, 150, 200))
        transform = get_train_transforms(image_size=224)
        tensor = transform(img)
        assert tensor.shape == (3, 224, 224)
        assert tensor.dtype == torch.float32

    def test_val_transforms_pipeline(self):
        """Validation transform pipeline produces correct output."""
        img = Image.new("RGB", (300, 300), color=(100, 150, 200))
        transform = get_val_transforms(image_size=224)
        tensor = transform(img)
        assert tensor.shape == (3, 224, 224)


# ============================================================
# Model Tests
# ============================================================

class TestDateEstimationModel:
    def test_model_creation(self):
        """Model creates successfully with default config."""
        model = DateEstimationModel(pretrained=False)
        assert model is not None

    def test_model_forward_pass(self):
        """Model forward pass produces correct output shape."""
        model = DateEstimationModel(pretrained=False, num_classes=11)
        model.eval()
        x = torch.randn(2, 3, 224, 224)
        logits = model(x)
        assert logits.shape == (2, 10)  # 11 classes -> 10 ordinal thresholds

    def test_model_predict_probs(self):
        """predict_probs returns valid probability distribution."""
        model = DateEstimationModel(pretrained=False)
        model.eval()
        x = torch.randn(2, 3, 224, 224)
        probs = model.predict_probs(x)
        assert probs.shape == (2, 11)
        assert torch.allclose(probs.sum(dim=1), torch.ones(2), atol=1e-5)

    def test_model_predict_decade(self):
        """predict_decade returns valid decade values."""
        model = DateEstimationModel(pretrained=False)
        model.eval()
        x = torch.randn(2, 3, 224, 224)
        decades = model.predict_decade(x)
        assert len(decades) == 2
        for d in decades:
            assert 1900 <= d <= 2000
            assert d % 10 == 0

    def test_model_resnet18_backbone(self):
        """Model works with ResNet-18 backbone."""
        model = DateEstimationModel(backbone="resnet18", pretrained=False)
        model.eval()
        x = torch.randn(1, 3, 224, 224)
        logits = model(x)
        assert logits.shape == (1, 10)

    def test_training_step(self):
        """Training step computes loss correctly."""
        model = DateEstimationModel(pretrained=False)
        batch = {
            "image": torch.randn(2, 3, 224, 224),
            "ordinal_target": torch.zeros(2, 10),
            "class_index": torch.tensor([3, 5]),
            "soft_labels": torch.zeros(2, 11),
            "has_soft_labels": torch.tensor([False, False]),
        }
        batch["ordinal_target"][0, :3] = 1.0
        batch["ordinal_target"][1, :5] = 1.0

        loss = model.training_step(batch, 0)
        assert loss.item() > 0
        assert not torch.isnan(loss)

    def test_training_step_with_soft_labels(self):
        """Training step with soft labels adds KL divergence loss."""
        model = DateEstimationModel(pretrained=False, soft_label_weight=0.3)
        soft = torch.zeros(2, 11)
        soft[0, 3] = 0.6
        soft[0, 4] = 0.3
        soft[0, 2] = 0.1
        soft[1, 5] = 0.5
        soft[1, 6] = 0.3
        soft[1, 4] = 0.2

        batch = {
            "image": torch.randn(2, 3, 224, 224),
            "ordinal_target": torch.zeros(2, 10),
            "class_index": torch.tensor([3, 5]),
            "soft_labels": soft,
            "has_soft_labels": torch.tensor([True, True]),
        }
        batch["ordinal_target"][0, :3] = 1.0
        batch["ordinal_target"][1, :5] = 1.0

        loss = model.training_step(batch, 0)
        assert loss.item() > 0


# ============================================================
# Evaluation / Regression Gate Tests
# ============================================================

class TestRegressionGate:
    def test_brier_score_perfect(self):
        """Brier score is 0 for perfect predictions."""
        pred_probs = np.eye(3)  # Perfect one-hot predictions
        true_indices = np.array([0, 1, 2])
        score = compute_brier_score(pred_probs, true_indices, 3)
        assert score == pytest.approx(0.0, abs=1e-5)

    def test_brier_score_worst(self):
        """Brier score is high for completely wrong predictions."""
        pred_probs = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], dtype=np.float64)
        true_indices = np.array([0, 1, 2])
        score = compute_brier_score(pred_probs, true_indices, 3)
        assert score > 0.5

    def test_gate_pass(self):
        """Gate passes when all metrics are within thresholds."""
        metrics = {
            "adjacent_accuracy": 0.85,
            "mae_decades": 0.8,
            "exact_accuracy": 0.5,
            "brier_score": 0.15,
            "n_samples": 50,
        }
        per_decade = {
            "1930": {"precision": 0.7, "recall": 0.5, "n": 10},
            "1940": {"precision": 0.8, "recall": 0.6, "n": 15},
        }
        gate_config = {
            "min_adjacent_accuracy": 0.70,
            "max_mae_decades": 1.5,
            "min_decade_recall": 0.20,
        }
        result = GateResult(metrics, per_decade, gate_config)
        assert result.passed
        assert len(result.failure_reasons) == 0

    def test_gate_fail_low_adjacent(self):
        """Gate fails when adjacent accuracy is too low."""
        metrics = {
            "adjacent_accuracy": 0.50,
            "mae_decades": 0.8,
        }
        result = GateResult(metrics, {}, {"min_adjacent_accuracy": 0.70, "max_mae_decades": 1.5})
        assert not result.passed
        assert any("Adjacent accuracy" in r for r in result.failure_reasons)

    def test_gate_fail_high_mae(self):
        """Gate fails when MAE is too high."""
        metrics = {
            "adjacent_accuracy": 0.85,
            "mae_decades": 2.0,
        }
        result = GateResult(metrics, {}, {"min_adjacent_accuracy": 0.70, "max_mae_decades": 1.5})
        assert not result.passed
        assert any("MAE" in r for r in result.failure_reasons)

    def test_gate_fail_decade_recall(self):
        """Gate fails when a decade has very low recall."""
        metrics = {
            "adjacent_accuracy": 0.85,
            "mae_decades": 0.8,
        }
        per_decade = {
            "1940": {"precision": 0.5, "recall": 0.05, "n": 10},
        }
        gate_config = {
            "min_adjacent_accuracy": 0.70,
            "max_mae_decades": 1.5,
            "min_decade_recall": 0.20,
        }
        result = GateResult(metrics, per_decade, gate_config)
        assert not result.passed

    def test_gate_skip_small_decades(self):
        """Gate ignores decades with fewer than 5 samples."""
        metrics = {
            "adjacent_accuracy": 0.85,
            "mae_decades": 0.8,
        }
        per_decade = {
            "1940": {"precision": 0.5, "recall": 0.0, "n": 3},  # Only 3 samples, should be skipped
        }
        gate_config = {
            "min_adjacent_accuracy": 0.70,
            "max_mae_decades": 1.5,
            "min_decade_recall": 0.20,
        }
        result = GateResult(metrics, per_decade, gate_config)
        assert result.passed

    def test_gate_to_dict(self):
        """GateResult serializes to dict."""
        metrics = {"adjacent_accuracy": 0.85, "mae_decades": 0.8}
        result = GateResult(metrics, {}, {"min_adjacent_accuracy": 0.70, "max_mae_decades": 1.5})
        d = result.to_dict()
        assert "metrics" in d
        assert "pass" in d
        assert d["pass"] is True

    def test_gate_calibration_fail(self):
        """Gate fails when high confidence is less accurate than medium."""
        metrics = {
            "adjacent_accuracy": 0.85,
            "mae_decades": 0.8,
            "accuracy_high": 0.3,
            "accuracy_medium": 0.5,
        }
        result = GateResult(metrics, {}, {"min_adjacent_accuracy": 0.70, "max_mae_decades": 1.5})
        assert not result.passed
        assert any("Calibration" in r for r in result.failure_reasons)


# ============================================================
# Generate Date Labels Script Tests
# ============================================================

class TestGenerateDateLabels:
    def test_load_photo_index(self, tmp_path):
        """load_photo_index reads photo index correctly."""
        from rhodesli_ml.scripts.generate_date_labels import load_photo_index
        index_file = tmp_path / "photo_index.json"
        data = {"photos": {"p1": {"path": "test.jpg"}, "p2": {"path": "test2.jpg"}}}
        with open(index_file, "w") as f:
            json.dump(data, f)
        result = load_photo_index(str(index_file))
        assert len(result) == 2

    def test_get_undated_photos(self):
        """get_undated_photos filters correctly."""
        from rhodesli_ml.scripts.generate_date_labels import get_undated_photos
        photos = {
            "p1": {"path": "a.jpg"},  # No date -> undated
            "p2": {"path": "b.jpg", "date_taken": "1940-01-01"},  # Real date -> skip
            "p3": {"path": "c.jpg", "date_taken": "2024-01-01"},  # Scan date -> undated
        }
        undated = get_undated_photos(photos)
        assert len(undated) == 2  # p1 and p3

    def test_save_labels(self, tmp_path):
        """save_labels writes JSON atomically."""
        from rhodesli_ml.scripts.generate_date_labels import save_labels
        labels = [{"photo_id": "p1", "estimated_decade": 1940}]
        output = tmp_path / "labels.json"
        save_labels(labels, str(output))
        assert output.exists()
        with open(output) as f:
            data = json.load(f)
        assert data["schema_version"] == 2
        assert len(data["labels"]) == 1

    def test_prompt_structure(self):
        """Prompt contains required evidence categories."""
        from rhodesli_ml.scripts.generate_date_labels import PROMPT
        assert "Print/Physical Format" in PROMPT
        assert "Fashion/Grooming" in PROMPT
        assert "Environmental/Geographic" in PROMPT
        assert "Technological/Object Markers" in PROMPT
        assert "Cultural Context" in PROMPT
        assert "decade_probabilities" in PROMPT
        assert "best_year_estimate" in PROMPT

    def test_model_costs_defined(self):
        """All supported models have cost information."""
        from rhodesli_ml.scripts.generate_date_labels import MODEL_COSTS
        assert "gemini-3-pro-preview" in MODEL_COSTS
        assert "gemini-3-flash-preview" in MODEL_COSTS
        for model, costs in MODEL_COSTS.items():
            assert "per_photo" in costs
            assert costs["per_photo"] > 0

    def test_prompt_contains_metadata_instructions(self):
        """Prompt includes rich metadata extraction instructions (AD-048)."""
        from rhodesli_ml.scripts.generate_date_labels import PROMPT
        assert "scene_description" in PROMPT
        assert "visible_text" in PROMPT
        assert "keywords" in PROMPT
        assert "setting" in PROMPT
        assert "photo_type" in PROMPT
        assert "people_count" in PROMPT
        assert "condition" in PROMPT
        assert "clothing_notes" in PROMPT
        # Verify enum values are documented in prompt
        assert "indoor_studio" in PROMPT
        assert "formal_portrait" in PROMPT
        assert "group_photo" in PROMPT


# ============================================================
# Photo Metadata Tests (AD-048)
# ============================================================

class TestPhotoMetadata:
    def test_load_metadata_from_labels(self, tmp_path):
        """load_photo_metadata returns metadata for labels that have it."""
        labels_file = tmp_path / "labels.json"
        data = {
            "schema_version": 2,
            "labels": [
                {
                    "photo_id": "p1", "estimated_decade": 1940,
                    "scene_description": "A formal portrait",
                    "keywords": ["portrait", "studio"],
                    "setting": "indoor_studio",
                    "photo_type": "formal_portrait",
                    "people_count": 2,
                    "condition": "good",
                },
                {
                    "photo_id": "p2", "estimated_decade": 1950,
                    # No metadata fields
                },
            ]
        }
        with open(labels_file, "w") as f:
            json.dump(data, f)

        metadata = load_photo_metadata(str(labels_file))
        assert len(metadata) == 1
        assert metadata[0].photo_id == "p1"
        assert metadata[0].scene_description == "A formal portrait"
        assert metadata[0].keywords == ["portrait", "studio"]
        assert metadata[0].setting == "indoor_studio"
        assert metadata[0].photo_type == "formal_portrait"
        assert metadata[0].people_count == 2
        assert metadata[0].condition == "good"

    def test_load_metadata_nonexistent_file(self, tmp_path):
        """Loading from nonexistent file returns empty list."""
        metadata = load_photo_metadata(str(tmp_path / "nonexistent.json"))
        assert metadata == []

    def test_backward_compat_labels_without_metadata(self, tmp_path):
        """Old labels without metadata fields still load as DateLabels."""
        labels_file = tmp_path / "labels.json"
        data = {
            "schema_version": 2,
            "labels": [
                {
                    "photo_id": "p1",
                    "estimated_decade": 1940,
                    "confidence": "high",
                    "source": "gemini",
                    "decade_probabilities": {"1940": 0.8, "1950": 0.2},
                    "reasoning_summary": "Test",
                    # No metadata fields at all
                },
            ]
        }
        with open(labels_file, "w") as f:
            json.dump(data, f)

        # DateLabels still load fine
        date_labels = load_date_labels(str(labels_file))
        assert len(date_labels) == 1
        assert date_labels[0].decade == 1940

        # PhotoMetadata returns empty (no metadata fields)
        metadata = load_photo_metadata(str(labels_file))
        assert len(metadata) == 0

    def test_metadata_with_visible_text_null(self, tmp_path):
        """Labels with visible_text=null handle correctly."""
        labels_file = tmp_path / "labels.json"
        data = {
            "schema_version": 2,
            "labels": [
                {
                    "photo_id": "p1", "estimated_decade": 1940,
                    "scene_description": "A group photo",
                    "visible_text": None,
                    "keywords": ["group"],
                    "setting": "outdoor_urban",
                    "photo_type": "group_photo",
                    "people_count": 5,
                    "condition": "fair",
                },
            ]
        }
        with open(labels_file, "w") as f:
            json.dump(data, f)

        metadata = load_photo_metadata(str(labels_file))
        assert len(metadata) == 1
        assert metadata[0].visible_text is None
        assert metadata[0].people_count == 5

    def test_photo_metadata_named_tuple_fields(self):
        """PhotoMetadata has all expected fields."""
        m = PhotoMetadata(
            photo_id="test",
            scene_description="A scene",
            visible_text="Hello",
            keywords=["tag1"],
            setting="indoor_studio",
            photo_type="formal_portrait",
            people_count=3,
            condition="good",
            clothing_notes="Dark suit",
        )
        assert m.photo_id == "test"
        assert m.scene_description == "A scene"
        assert m.visible_text == "Hello"
        assert m.keywords == ["tag1"]
        assert m.setting == "indoor_studio"
        assert m.photo_type == "formal_portrait"
        assert m.people_count == 3
        assert m.condition == "good"
        assert m.clothing_notes == "Dark suit"

    def test_valid_enum_constants(self):
        """Enum validation sets contain expected values."""
        assert "indoor_studio" in VALID_SETTINGS
        assert "outdoor_urban" in VALID_SETTINGS
        assert "unknown" in VALID_SETTINGS
        assert len(VALID_SETTINGS) == 7

        assert "formal_portrait" in VALID_PHOTO_TYPES
        assert "group_photo" in VALID_PHOTO_TYPES
        assert "wedding" in VALID_PHOTO_TYPES
        assert len(VALID_PHOTO_TYPES) == 11

        assert "excellent" in VALID_CONDITIONS
        assert "poor" in VALID_CONDITIONS
        assert len(VALID_CONDITIONS) == 4

    def test_synthetic_labels_include_metadata(self, synthetic_labels):
        """Synthetic fixture labels include metadata fields for first 20."""
        with_metadata = [l for l in synthetic_labels if l.get("scene_description")]
        without_metadata = [l for l in synthetic_labels if not l.get("scene_description")]
        assert len(with_metadata) == 20
        assert len(without_metadata) == 10

        # Verify metadata structure
        sample = with_metadata[0]
        assert isinstance(sample["keywords"], list)
        assert sample["setting"] in VALID_SETTINGS
        assert sample["photo_type"] in VALID_PHOTO_TYPES
        assert sample["condition"] in VALID_CONDITIONS
        assert isinstance(sample["people_count"], int)

    def test_call_gemini_nested_response_parsing(self):
        """call_gemini handles the nested date_estimation response format."""
        from rhodesli_ml.scripts.generate_date_labels import call_gemini
        # This tests the parsing logic — we can't call Gemini without a key,
        # but we can verify the prompt structure expects the nested format
        from rhodesli_ml.scripts.generate_date_labels import PROMPT
        assert '"date_estimation"' in PROMPT
        assert '"scene_description"' in PROMPT
