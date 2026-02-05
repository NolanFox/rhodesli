"""
Configuration for Rhodesli application.

Contains:
- Server configuration (environment-based)
- Recognition thresholds for face matching (calibrated values)

Server config is read from environment variables with sensible defaults.
Recognition thresholds are derived from forensic evaluation against the
Leon Capeluto ground truth set. Changes require re-running the evaluation harness.

Source: ADR 007 - Calibration Adjustment (Run 2 Leon Standard)
Calibration date: 2026-02-03
Evaluation harness: scripts/evaluate_recognition.py
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

# Data paths (relative to project root)
DATA_DIR = os.getenv("DATA_DIR", "data")
PHOTOS_DIR = os.getenv("PHOTOS_DIR", "raw_photos")

# Processing mode: when False, uploads are staged but not processed
# Set to False in production (Railway) where ML deps aren't installed
PROCESSING_ENABLED = os.getenv("PROCESSING_ENABLED", "true").lower() == "true"

# =============================================================================
# Recognition Thresholds (calibrated values - do not change without evaluation)
# =============================================================================

# High confidence: core cluster matches (frontal poses, good quality)
MATCH_THRESHOLD_HIGH = 1.00

# Medium confidence: includes pose variations (extreme angles, vintage quality)
MATCH_THRESHOLD_MEDIUM = 1.20

# Grouping threshold for ingestion-time face clustering.
# Stricter than MATCH_THRESHOLD_HIGH to prefer under-grouping.
# Used by core/grouping.py during inbox ingestion.
GROUPING_THRESHOLD = 0.95
