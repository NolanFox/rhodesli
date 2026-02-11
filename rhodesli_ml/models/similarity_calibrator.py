"""Learned similarity calibration on frozen embeddings (Phase 2).

A small MLP that takes embedding pairs + metadata signals and outputs
a calibrated match probability. Trained on confirmed pairs (positive)
and rejections + hard negatives (negative).

This is the first "learning intervention" — reduces Type I/II error rates
with near-zero risk of catastrophic forgetting since the backbone is frozen.
"""

# Placeholder — will be implemented after signal harvester validates
# sufficient training data (50+ confirmed pairs, 20+ rejections).
#
# Architecture: MLP with inputs:
# - Concatenated embedding pair (1024-dim)
# - Cosine distance (1-dim)
# - Face quality difference (1-dim)
# - Same-collection indicator (1-dim)
# - Future: date proximity, name similarity
#
# Output: calibrated probability [0, 1]
# Loss: Binary cross-entropy with hard negative upweighting
