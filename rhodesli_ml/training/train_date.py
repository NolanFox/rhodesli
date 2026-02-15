"""Training loop for date/era estimation model.

Uses PyTorch Lightning with CORAL loss for ordinal regression.
Trains on silver labels (Gemini estimates) + gold labels (user corrections).

Usage:
    # Dry run: 2 epochs on 10 images to validate pipeline
    python -m rhodesli_ml.training.train_date --dry-run

    # Full training
    python -m rhodesli_ml.training.train_date

    # Custom config
    python -m rhodesli_ml.training.train_date --config rhodesli_ml/config/date_estimation.yaml
"""

import argparse
import sys
from pathlib import Path

import yaml
import torch
from torch.utils.data import DataLoader

import lightning as L
from lightning.pytorch.callbacks import ModelCheckpoint, EarlyStopping
from lightning.pytorch.loggers import MLFlowLogger

from rhodesli_ml.models.date_classifier import DateEstimationModel
from rhodesli_ml.data.date_dataset import (
    DateEstimationDataset,
    load_labels_from_file,
    create_train_val_split,
)
from rhodesli_ml.data.augmentations import get_train_transforms, get_val_transforms


def load_config(config_path: str) -> dict:
    """Load YAML config file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Train date estimation model")
    parser.add_argument(
        "--config", default="rhodesli_ml/config/date_estimation.yaml",
        help="Path to config YAML file",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run 2 epochs on 10 images to validate pipeline",
    )
    parser.add_argument(
        "--labels", default=None,
        help="Path to date labels JSON (overrides config)",
    )
    parser.add_argument(
        "--photos-dir", default=None,
        help="Path to photos directory (overrides config)",
    )
    parser.add_argument(
        "--exclude-models", nargs="*", default=None,
        help="Exclude labels from these model name substrings (e.g. gemini-2.5-flash)",
    )
    parser.add_argument(
        "--include-all", action="store_true",
        help="Include training_eligible=False labels (override default filter)",
    )
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    model_cfg = config.get("model", {})
    train_cfg = config.get("training", {})
    data_cfg = config.get("data", {})
    aug_cfg = config.get("augmentation", {})
    mlflow_cfg = config.get("mlflow", {})

    # Resolve paths
    labels_path = args.labels or data_cfg.get("labels_path", "rhodesli_ml/data/date_labels.json")
    photos_dir = args.photos_dir or data_cfg.get("photos_dir", "raw_photos")
    image_size = data_cfg.get("image_size", 224)

    # Load labels
    training_only = not args.include_all
    print(f"Loading labels from {labels_path}...")
    labels = load_labels_from_file(
        labels_path,
        exclude_models=args.exclude_models,
        training_only=training_only,
    )
    if not labels:
        print("ERROR: No labels found. Run generate_date_labels.py first.")
        sys.exit(1)

    if args.exclude_models:
        print(f"Excluded models: {args.exclude_models}")
    if training_only:
        print(f"Training-eligible only: yes")
    print(f"Loaded {len(labels)} labels")

    # Load photo_index for path resolution
    photo_index_path = data_cfg.get("photo_index_path", "data/photo_index.json")
    photo_index = {}
    if Path(photo_index_path).exists():
        import json as _json
        with open(photo_index_path) as f:
            pi_data = _json.load(f)
        photo_index = pi_data.get("photos", pi_data)
        print(f"Loaded photo index: {len(photo_index)} photos")

    # Split train/val
    train_ratio = data_cfg.get("train_split", 0.8)
    train_labels, val_labels = create_train_val_split(labels, train_ratio=train_ratio)
    print(f"Train: {len(train_labels)}, Val: {len(val_labels)}")

    # Dry-run mode: limit data and skip pretrained weights
    if args.dry_run:
        train_labels = train_labels[:10]
        val_labels = val_labels[:5] if len(val_labels) >= 5 else val_labels[:2]
        model_cfg["pretrained"] = False  # Skip weight download in dry-run
        print(f"DRY RUN: Using {len(train_labels)} train, {len(val_labels)} val samples")

    # Create transforms
    train_transform = get_train_transforms(image_size, aug_cfg)
    val_transform = get_val_transforms(image_size)

    # Create datasets
    num_classes = model_cfg.get("num_decades", 11)
    train_dataset = DateEstimationDataset(
        labels=train_labels,
        photos_dir=photos_dir,
        photo_index=photo_index,
        transform=train_transform,
        num_classes=num_classes,
    )
    val_dataset = DateEstimationDataset(
        labels=val_labels,
        photos_dir=photos_dir,
        photo_index=photo_index,
        transform=val_transform,
        num_classes=num_classes,
    )

    if len(train_dataset) == 0:
        print("ERROR: No training samples found. Check photos_dir and labels.")
        sys.exit(1)

    print(f"Dataset sizes: train={len(train_dataset)}, val={len(val_dataset)}")

    # Create dataloaders
    batch_size = train_cfg.get("batch_size", 16)
    if args.dry_run:
        batch_size = min(batch_size, 4)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,  # Single-threaded for small dataset
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
    )

    # Create model
    model = DateEstimationModel(
        num_classes=num_classes,
        backbone=model_cfg.get("backbone", "efficientnet_b0"),
        pretrained=model_cfg.get("pretrained", True),
        freeze_layers=model_cfg.get("freeze_layers", 6),
        learning_rate=train_cfg.get("learning_rate", 0.001),
        weight_decay=train_cfg.get("weight_decay", 0.01),
        soft_label_weight=train_cfg.get("soft_label_weight", 0.3),
    )

    # Callbacks
    checkpoint_dir = Path("rhodesli_ml/checkpoints")
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    callbacks = [
        ModelCheckpoint(
            dirpath=str(checkpoint_dir),
            filename="date-{epoch:02d}-{val/mae_decades:.2f}",
            monitor="val/mae_decades",
            mode="min",
            save_top_k=3,
        ),
        EarlyStopping(
            monitor="val/mae_decades",
            patience=train_cfg.get("early_stopping_patience", 10),
            mode="min",
        ),
    ]

    # MLflow logger
    mlflow_tracking_uri = mlflow_cfg.get("tracking_uri", "rhodesli_ml/mlruns")
    experiment_name = mlflow_cfg.get("experiment_name", "rhodesli_date_estimation")

    logger = MLFlowLogger(
        experiment_name=experiment_name,
        tracking_uri=mlflow_tracking_uri,
        log_model=False,
    )

    # Trainer
    max_epochs = 2 if args.dry_run else train_cfg.get("epochs", 100)
    accelerator = "gpu" if torch.cuda.is_available() else "cpu"

    trainer = L.Trainer(
        max_epochs=max_epochs,
        accelerator=accelerator,
        callbacks=callbacks,
        logger=logger,
        enable_progress_bar=True,
        log_every_n_steps=1,
        val_check_interval=1.0,
    )

    # Train
    print(f"\nStarting training: {max_epochs} epochs, {accelerator}")
    print(f"MLflow tracking: {mlflow_tracking_uri}")
    print(f"Checkpoints: {checkpoint_dir}")
    print()

    trainer.fit(model, train_loader, val_loader)

    print(f"\nTraining complete. Best model: {checkpoint_dir}")


if __name__ == "__main__":
    main()
