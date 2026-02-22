"""Centralized Gemini model configuration — single source of truth.

All Gemini model references across the codebase should import from here.
See AD-136 for model selection rationale.
"""

import os

# --- Model Selection ---
# Preferred model for vision analysis tasks (date estimation, progressive refinement)
# Updated to 3.1 Pro (Session 61) — best reasoning + vision, ARC-AGI-2: 77.1%
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")

# Fast model for cost-sensitive, batch, or real-time operations
GEMINI_MODEL_FAST = os.getenv("GEMINI_MODEL_FAST", "gemini-3-flash")

# --- API Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# media_resolution options: "low" (fewer tokens) or "high" (more detail)
MEDIA_RESOLUTION = "high"

# --- Cost Controls ---
MAX_COST_DEFAULT = 1.00  # USD, for dry runs
DRY_RUN_PHOTO_LIMIT = 3

# --- Model Pricing (per 1M tokens) ---
# Update when models change. Historical models kept for cost_tracker compatibility.
MODEL_PRICING = {
    # Current recommended models (Session 61 — AD-139)
    "gemini-3.1-pro-preview": {
        "input": 2.00, "output": 12.00, "per_photo": 0.037,
        "note": "RECOMMENDED — best reasoning + vision, ARC-AGI-2: 77.1%",
    },
    "gemini-3-flash": {
        "input": 0.50, "output": 3.00, "per_photo": 0.010,
        "note": "Fast + cheap, good for batch/real-time operations",
    },
    # Previous defaults
    "gemini-2.5-pro-preview-05-06": {
        "input": 1.25, "output": 10.00, "per_photo": 0.032,
        "note": "Previous RECOMMENDED (AD-136)",
    },
    "gemini-2.5-flash-preview-04-17": {
        "input": 0.15, "output": 3.50, "per_photo": 0.011,
        "note": "Previous fast model",
    },
    # Legacy models (for historical cost tracking)
    "gemini-2.0-flash": {
        "input": 0.10, "output": 0.40, "per_photo": 0.003,
        "note": "Deprecated",
    },
    "gemini-2.5-flash": {
        "input": 0.15, "output": 0.60, "per_photo": 0.008,
        "note": "Stable, good price/performance",
    },
    "gemini-2.5-pro": {
        "input": 1.25, "output": 5.00, "per_photo": 0.025,
        "note": "Previous stable Pro",
    },
    "gemini-3-pro-preview": {
        "input": 2.00, "output": 12.00, "per_photo": 0.037,
        "note": "Previous best, SOTA vision reasoning",
    },
    "gemini-3-flash-preview": {
        "input": 0.50, "output": 3.00, "per_photo": 0.010,
        "note": "Previous free tier, very good quality",
    },
}


def get_model_pricing(model: str) -> dict:
    """Get pricing info for a model, with sensible default fallback."""
    return MODEL_PRICING.get(model, MODEL_PRICING[GEMINI_MODEL])


def get_api_key() -> str:
    """Get Gemini API key with clear error message if missing."""
    key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if not key:
        raise EnvironmentError(
            "GEMINI_API_KEY not set. Get one at: https://aistudio.google.com/apikey"
        )
    return key
