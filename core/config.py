"""
Recognition thresholds for face matching.

Source: ADR 007 - Calibration Adjustment (Run 2 Leon Standard)
Calibration date: 2026-02-03
Evaluation harness: scripts/evaluate_recognition.py

These values are derived from forensic evaluation against the Leon Capeluto
ground truth set. Changes require re-running the evaluation harness.
"""

# High confidence: core cluster matches (frontal poses, good quality)
MATCH_THRESHOLD_HIGH = 1.00

# Medium confidence: includes pose variations (extreme angles, vintage quality)
MATCH_THRESHOLD_MEDIUM = 1.20

# Grouping threshold for ingestion-time face clustering.
# Stricter than MATCH_THRESHOLD_HIGH to prefer under-grouping.
# Used by core/grouping.py during inbox ingestion.
GROUPING_THRESHOLD = 0.95
