"""
Configuration for Rhodesli application.

Contains:
- Server configuration (environment-based)
- Recognition thresholds for face matching (calibrated values)

Server config is read from environment variables with sensible defaults.
Recognition thresholds derived from golden set evaluation (90 faces, 23 identities).
Changes require re-running: scripts/evaluate_golden_set.py --sweep

Source: AD-013 Threshold Calibration (2026-02-09)
Evidence: data/golden_set_evaluation_2026-02-09.json
Harness: scripts/evaluate_golden_set.py, scripts/calibrate_thresholds.py
"""

import os

# =============================================================================
# Server Configuration (from environment variables)
# =============================================================================

# Network binding
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5001"))

# Debug mode (enables hot reload, verbose logging)
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# Storage configuration
# Railway supports only ONE persistent volume per service.
# When STORAGE_DIR is set (Railway), DATA_DIR and PHOTOS_DIR derive from it.
# When STORAGE_DIR is not set (local dev), use individual path defaults.
STORAGE_DIR = os.getenv("STORAGE_DIR")  # Only set on Railway

if STORAGE_DIR:
    # Railway single-volume mode: /app/storage contains data/ and raw_photos/
    DATA_DIR = os.path.join(STORAGE_DIR, "data")
    PHOTOS_DIR = os.path.join(STORAGE_DIR, "raw_photos")
else:
    # Local development: use individual paths
    DATA_DIR = os.getenv("DATA_DIR", "data")
    PHOTOS_DIR = os.getenv("PHOTOS_DIR", "raw_photos")

# Processing mode: when False, uploads are staged but not processed
# Set to False in production (Railway) where ML deps aren't installed
PROCESSING_ENABLED = os.getenv("PROCESSING_ENABLED", "true").lower() == "true"

# =============================================================================
# Recognition Thresholds (calibrated values - do not change without evaluation)
# Source: AD-013 Threshold Calibration (2026-02-09)
# Evidence: Golden set evaluation (90 faces, 23 identities, 4005 pairs)
# Harness: scripts/evaluate_golden_set.py --sweep
# =============================================================================

# Very high confidence: slam-dunk matches (< 0.80 distance)
# ~100% precision, ~13% recall. Safe to auto-suggest prominently.
MATCH_THRESHOLD_VERY_HIGH = 0.80

# High confidence: zero false positives in golden set (< 1.05 distance)
# 100% precision, ~63% recall. Raised from 1.00 per AD-013 calibration.
MATCH_THRESHOLD_HIGH = 1.05

# Moderate confidence: includes some family-resemblance FPs (< 1.15)
# ~94% precision, ~81% recall. Show with "likely match" label.
MATCH_THRESHOLD_MODERATE = 1.15

# Medium confidence: includes pose variations (extreme angles, vintage quality)
# ~87% precision, ~87% recall. Use for exploratory search.
MATCH_THRESHOLD_MEDIUM = 1.20

# Low confidence: deep search / "possible match" (< 1.25)
# ~69% precision, ~91% recall. Requires strong human judgment.
MATCH_THRESHOLD_LOW = 1.25

# Grouping threshold for ingestion-time face clustering.
# Stricter than MATCH_THRESHOLD_HIGH to prefer under-grouping.
# Used by core/grouping.py during inbox ingestion.
GROUPING_THRESHOLD = 0.95
