"""Training loop for date/era estimation model.

Uses PyTorch Lightning with CORAL loss for ordinal regression.
Trains on silver labels (Gemini estimates) + gold labels (user corrections).

Usage:
    python -m rhodesli_ml.training.train_date --config config/date_estimation.yaml
"""

# Placeholder — will be implemented when date labels are available.
#
# Pipeline:
# 1. Load date labels (silver + gold merged)
# 2. Split train/val (stratified by decade)
# 3. Create DataLoader with heritage augmentations
# 4. Train EfficientNet-B0 + ordinal head
# 5. Evaluate on held-out set
# 6. Run regression gate
# 7. Log to MLflow
