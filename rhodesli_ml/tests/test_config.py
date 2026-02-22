"""Tests for centralized Gemini config (rhodesli_ml/config.py)."""

import os
import pytest


class TestGeminiConfig:
    """Test centralized Gemini model configuration."""

    def test_default_model_is_set(self):
        """GEMINI_MODEL has a sensible default."""
        from rhodesli_ml.gemini_config import GEMINI_MODEL
        assert GEMINI_MODEL
        assert isinstance(GEMINI_MODEL, str)
        assert "gemini" in GEMINI_MODEL.lower()

    def test_default_fast_model_is_set(self):
        """GEMINI_MODEL_FAST has a sensible default."""
        from rhodesli_ml.gemini_config import GEMINI_MODEL_FAST
        assert GEMINI_MODEL_FAST
        assert isinstance(GEMINI_MODEL_FAST, str)
        assert "flash" in GEMINI_MODEL_FAST.lower()

    def test_model_pricing_includes_current_models(self):
        """MODEL_PRICING must include current recommended models."""
        from rhodesli_ml.gemini_config import MODEL_PRICING, GEMINI_MODEL, GEMINI_MODEL_FAST
        assert GEMINI_MODEL in MODEL_PRICING
        assert GEMINI_MODEL_FAST in MODEL_PRICING

    def test_model_pricing_has_required_fields(self):
        """Every pricing entry must have input, output, per_photo, note."""
        from rhodesli_ml.gemini_config import MODEL_PRICING
        for model, pricing in MODEL_PRICING.items():
            assert "input" in pricing, f"{model} missing 'input'"
            assert "output" in pricing, f"{model} missing 'output'"
            assert "per_photo" in pricing, f"{model} missing 'per_photo'"
            assert "note" in pricing, f"{model} missing 'note'"
            assert pricing["input"] > 0, f"{model} input must be positive"
            assert pricing["output"] > 0, f"{model} output must be positive"
            assert pricing["per_photo"] > 0, f"{model} per_photo must be positive"

    def test_get_model_pricing_known_model(self):
        """get_model_pricing returns correct pricing for known models."""
        from rhodesli_ml.gemini_config import get_model_pricing, GEMINI_MODEL
        pricing = get_model_pricing(GEMINI_MODEL)
        assert "input" in pricing
        assert "output" in pricing

    def test_get_model_pricing_unknown_model_falls_back(self):
        """get_model_pricing falls back to default for unknown models."""
        from rhodesli_ml.gemini_config import get_model_pricing, GEMINI_MODEL, MODEL_PRICING
        pricing = get_model_pricing("nonexistent-model-xyz")
        assert pricing == MODEL_PRICING[GEMINI_MODEL]

    def test_get_api_key_raises_when_missing(self):
        """get_api_key raises EnvironmentError when GEMINI_API_KEY is not set."""
        from rhodesli_ml.gemini_config import get_api_key
        # Temporarily clear the env var
        old = os.environ.pop("GEMINI_API_KEY", None)
        try:
            # Re-import to get fresh state (config reads at import time)
            import importlib
            import rhodesli_ml.gemini_config as cfg
            cfg.GEMINI_API_KEY = ""
            with pytest.raises(EnvironmentError, match="GEMINI_API_KEY not set"):
                get_api_key()
        finally:
            if old is not None:
                os.environ["GEMINI_API_KEY"] = old

    def test_env_var_override(self, monkeypatch):
        """GEMINI_MODEL can be overridden via environment variable."""
        monkeypatch.setenv("GEMINI_MODEL", "test-model-override")
        # Need to reimport to pick up the env change
        import importlib
        import rhodesli_ml.gemini_config as cfg
        importlib.reload(cfg)
        assert cfg.GEMINI_MODEL == "test-model-override"
        # Restore
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        importlib.reload(cfg)

    def test_cost_tracker_imports_from_config(self):
        """cost_tracker.MODEL_PRICING should include config models."""
        from rhodesli_ml.scripts.cost_tracker import MODEL_PRICING
        from rhodesli_ml.gemini_config import GEMINI_MODEL
        assert GEMINI_MODEL in MODEL_PRICING

    def test_legacy_models_preserved(self):
        """Historical model entries preserved for cost tracking."""
        from rhodesli_ml.gemini_config import MODEL_PRICING
        legacy_models = ["gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-3.1-pro-preview"]
        for model in legacy_models:
            assert model in MODEL_PRICING, f"Legacy model {model} missing from pricing"
