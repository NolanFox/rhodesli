"""
Similarity Calibration: Raw cosine → P(same person)

Converts raw InsightFace cosine similarity scores into calibrated
probabilities using isotonic regression. More flexible than
logistic/Platt scaling for non-standard score distributions.

Design:
- Versioned models stored in Supabase
- Continuous recalibration triggers
- Handles future non-match spike when "reject" UX launches
- Safety rails: rate limit, drift detection, never retroactive

AD reference: AD-145 Stage 1, AD-149
Session: 63
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CalibrationModel:
    """Versioned calibration model."""
    version: int
    created_at: str
    pair_count: int
    match_count: int
    nonmatch_count: int
    auc: float
    threshold_at_90_precision: float
    threshold_at_95_precision: float
    # Isotonic regression stores sorted input/output arrays
    iso_X: list[float]
    iso_y: list[float]


class SimilarityCalibrator:
    """Convert raw similarity → calibrated P(match)."""

    def __init__(self, supabase_client=None, model_dir: str | Path = None):
        """
        Args:
            supabase_client: Supabase client for loading pairs and storing models
            model_dir: Local directory for model storage (fallback if no Supabase)
        """
        self._sb = supabase_client
        self._model_dir = Path(model_dir) if model_dir else Path("data/calibration")
        self._model: Optional[CalibrationModel] = None
        self._iso_reg = None
        self._last_fit_time: float = 0
        self._last_pair_count: int = 0

    def fit(self, pairs: list[dict] = None) -> CalibrationModel:
        """
        Fit isotonic regression on calibration pairs.

        Args:
            pairs: List of dicts with 'similarity_score', 'is_match', 'weight'.
                   If None, loads from Supabase calibration_pairs table.

        Returns:
            CalibrationModel with fitted parameters.
        """
        from sklearn.isotonic import IsotonicRegression
        from sklearn.metrics import roc_auc_score

        if pairs is None:
            pairs = self._load_pairs()

        if len(pairs) < 10:
            raise ValueError(f"Need at least 10 pairs for calibration, got {len(pairs)}")

        X = np.array([p['similarity_score'] for p in pairs])
        y = np.array([1.0 if p['is_match'] else 0.0 for p in pairs])
        w = np.array([p.get('weight', 1.0) for p in pairs])

        # Train/val split (80/20, stratified)
        match_idx = np.where(y == 1)[0]
        nonmatch_idx = np.where(y == 0)[0]
        np.random.seed(42)
        np.random.shuffle(match_idx)
        np.random.shuffle(nonmatch_idx)

        train_match = match_idx[:int(0.8 * len(match_idx))]
        val_match = match_idx[int(0.8 * len(match_idx)):]
        train_nonmatch = nonmatch_idx[:int(0.8 * len(nonmatch_idx))]
        val_nonmatch = nonmatch_idx[int(0.8 * len(nonmatch_idx)):]

        train_idx = np.concatenate([train_match, train_nonmatch])
        val_idx = np.concatenate([val_match, val_nonmatch])

        # Fit isotonic regression
        iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds='clip')
        iso.fit(X[train_idx], y[train_idx], sample_weight=w[train_idx])

        # Evaluate on validation set
        if len(val_idx) >= 5:
            y_pred = iso.predict(X[val_idx])
            try:
                auc = float(roc_auc_score(y[val_idx], y_pred))
            except ValueError:
                auc = 0.0  # Single class in validation
        else:
            auc = float(roc_auc_score(y, iso.predict(X)))

        # Find thresholds
        threshold_90 = self._find_threshold(iso, X, y, target_precision=0.9)
        threshold_95 = self._find_threshold(iso, X, y, target_precision=0.95)

        # Store model
        version = (self._model.version + 1) if self._model else 1
        self._model = CalibrationModel(
            version=version,
            created_at=datetime.now(timezone.utc).isoformat(),
            pair_count=len(pairs),
            match_count=int(np.sum(y)),
            nonmatch_count=int(np.sum(1 - y)),
            auc=round(auc, 4),
            threshold_at_90_precision=round(threshold_90, 4),
            threshold_at_95_precision=round(threshold_95, 4),
            iso_X=iso.X_thresholds_.tolist() if hasattr(iso, 'X_thresholds_') else [],
            iso_y=iso.y_thresholds_.tolist() if hasattr(iso, 'y_thresholds_') else [],
        )
        self._iso_reg = iso
        self._last_fit_time = time.time()
        self._last_pair_count = len(pairs)

        logger.info(
            f"Calibration model v{version}: AUC={auc:.3f}, "
            f"threshold@90p={threshold_90:.3f}, threshold@95p={threshold_95:.3f}, "
            f"pairs={len(pairs)} ({int(np.sum(y))} match, {int(np.sum(1-y))} non-match)"
        )

        return self._model

    def predict(self, score: float) -> float:
        """Raw similarity score → calibrated P(match). Returns 0-1."""
        if self._iso_reg is None:
            self._load_model()
        if self._iso_reg is None:
            # No model available — return raw score clamped
            return max(0.0, min(1.0, score))
        return float(self._iso_reg.predict([score])[0])

    def predict_batch(self, scores: list[float]) -> list[float]:
        """Calibrate multiple scores at once."""
        if self._iso_reg is None:
            self._load_model()
        if self._iso_reg is None:
            return [max(0.0, min(1.0, s)) for s in scores]
        return [float(p) for p in self._iso_reg.predict(scores)]

    def get_threshold(self, target_precision: float = 0.9) -> float:
        """Get raw similarity threshold for target precision."""
        if self._model is None:
            self._load_model()
        if self._model is None:
            return 0.3  # Safe default
        if target_precision >= 0.95:
            return self._model.threshold_at_95_precision
        return self._model.threshold_at_90_precision

    def get_confidence_label(self, prob: float) -> str:
        """Human-readable confidence label from calibrated probability."""
        if prob >= 0.9:
            return "High"
        elif prob >= 0.7:
            return "Medium"
        elif prob >= 0.5:
            return "Low"
        else:
            return "Unlikely"

    def should_recalibrate(self) -> tuple[bool, str]:
        """
        Check if recalibration is needed.

        Returns: (should_recalibrate, reason)
        """
        if self._model is None:
            return True, "no model exists"

        current_pairs = self._get_pair_count()
        new_pairs = current_pairs - self._last_pair_count

        # Trigger: >20 new pairs
        if new_pairs > 20:
            return True, f"{new_pairs} new pairs since last fit"

        # Trigger: model age > 30 days
        try:
            model_age = datetime.now(timezone.utc) - datetime.fromisoformat(self._model.created_at)
            if model_age.days > 30:
                return True, f"model is {model_age.days} days old"
        except (ValueError, TypeError):
            pass

        # Trigger: class ratio shift > 50%
        if self._model.nonmatch_count > 0:
            old_ratio = self._model.match_count / self._model.nonmatch_count
            new_match, new_nonmatch = self._get_class_counts()
            if new_nonmatch > 0:
                new_ratio = new_match / new_nonmatch
                if abs(new_ratio - old_ratio) / max(old_ratio, 0.01) > 0.5:
                    return True, f"class ratio shifted from {old_ratio:.2f} to {new_ratio:.2f}"

        return False, "no trigger met"

    def recalibrate_if_needed(self) -> tuple[bool, Optional[str]]:
        """
        Recalibrate if triggered. Returns (recalibrated, drift_warning).

        Safety rails:
        - Rate limit: max 1 recalibration per hour
        - If threshold shifts > 0.1: flag for review
        """
        should, reason = self.should_recalibrate()
        if not should:
            return False, None

        # Rate limit
        if time.time() - self._last_fit_time < 3600:
            logger.info(f"Recalibration needed ({reason}) but rate-limited (< 1hr)")
            return False, None

        old_threshold = self._model.threshold_at_90_precision if self._model else 0.0
        old_version = self._model.version if self._model else 0

        # Refit
        self.fit()

        # Drift detection
        new_threshold = self._model.threshold_at_90_precision
        drift = abs(new_threshold - old_threshold)

        drift_warning = None
        if drift > 0.1:
            drift_warning = (
                f"DRIFT WARNING: threshold@90p shifted by {drift:.3f} "
                f"(v{old_version}: {old_threshold:.3f} → v{self._model.version}: {new_threshold:.3f}). "
                f"Review before deploying."
            )
            logger.warning(drift_warning)

        self._save_model()
        logger.info(f"Recalibrated: v{old_version} → v{self._model.version} (reason: {reason})")

        return True, drift_warning

    def calibration_report(self) -> dict:
        """Get calibration model stats."""
        if self._model is None:
            return {"status": "no_model"}
        return {
            "version": self._model.version,
            "created_at": self._model.created_at,
            "pair_count": self._model.pair_count,
            "match_count": self._model.match_count,
            "nonmatch_count": self._model.nonmatch_count,
            "auc": self._model.auc,
            "threshold_at_90_precision": self._model.threshold_at_90_precision,
            "threshold_at_95_precision": self._model.threshold_at_95_precision,
        }

    # --- Private methods ---

    def _find_threshold(self, iso, X, y, target_precision=0.9) -> float:
        """Find raw score threshold for target precision."""
        scores = np.linspace(X.min(), X.max(), 1000)
        probs = iso.predict(scores)

        best_threshold = float(X.max())
        for i, (s, p) in enumerate(zip(scores, probs)):
            if p >= target_precision:
                # Check actual precision at this threshold
                pred_positive = X >= s
                if pred_positive.sum() > 0:
                    precision = y[pred_positive].mean()
                    if precision >= target_precision:
                        best_threshold = float(s)
                        break

        return best_threshold

    def _load_pairs(self) -> list[dict]:
        """Load calibration pairs from Supabase."""
        if self._sb is None:
            # Try local file
            local = self._model_dir / "calibration_pairs.json"
            if local.exists():
                with open(local) as f:
                    data = json.load(f)
                return data.get("pairs", [])
            return []

        all_pairs = []
        offset = 0
        while True:
            resp = self._sb.table('calibration_pairs').select('*').range(offset, offset + 999).execute()
            all_pairs.extend(resp.data)
            if len(resp.data) < 1000:
                break
            offset += 1000
        return all_pairs

    def _get_pair_count(self) -> int:
        """Get current pair count."""
        if self._sb is None:
            return self._last_pair_count
        resp = self._sb.table('calibration_pairs').select('id', count='exact').execute()
        return resp.count or 0

    def _get_class_counts(self) -> tuple[int, int]:
        """Get current match/non-match counts."""
        if self._sb is None:
            return (0, 0)
        match_resp = self._sb.table('calibration_pairs').select('id', count='exact').eq('is_match', True).execute()
        nonmatch_resp = self._sb.table('calibration_pairs').select('id', count='exact').eq('is_match', False).execute()
        return (match_resp.count or 0, nonmatch_resp.count or 0)

    def _save_model(self):
        """Save model to local JSON file."""
        if self._model is None:
            return
        self._model_dir.mkdir(parents=True, exist_ok=True)
        model_path = self._model_dir / f"calibration_v{self._model.version}.json"
        with open(model_path, "w") as f:
            json.dump({
                "version": self._model.version,
                "created_at": self._model.created_at,
                "pair_count": self._model.pair_count,
                "match_count": self._model.match_count,
                "nonmatch_count": self._model.nonmatch_count,
                "auc": self._model.auc,
                "threshold_at_90_precision": self._model.threshold_at_90_precision,
                "threshold_at_95_precision": self._model.threshold_at_95_precision,
                "iso_X": self._model.iso_X,
                "iso_y": self._model.iso_y,
            }, f, indent=2)

        # Also save as "latest"
        latest = self._model_dir / "calibration_latest.json"
        import shutil
        shutil.copy2(model_path, latest)
        logger.info(f"Model saved: {model_path}")

    def _load_model(self):
        """Load latest model from local storage."""
        latest = self._model_dir / "calibration_latest.json"
        if not latest.exists():
            return

        try:
            with open(latest) as f:
                data = json.load(f)
            self._model = CalibrationModel(**data)

            # Reconstruct isotonic regression from thresholds
            if self._model.iso_X and self._model.iso_y:
                from sklearn.isotonic import IsotonicRegression
                iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds='clip')
                iso.X_thresholds_ = np.array(self._model.iso_X)
                iso.y_thresholds_ = np.array(self._model.iso_y)
                iso.X_min_ = iso.X_thresholds_[0]
                iso.X_max_ = iso.X_thresholds_[-1]
                iso.f_ = None  # Will use threshold-based prediction
                self._iso_reg = iso

            logger.info(f"Loaded calibration model v{self._model.version}")
        except Exception as e:
            logger.warning(f"Failed to load calibration model: {e}")
