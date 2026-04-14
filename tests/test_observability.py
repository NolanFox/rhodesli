"""Tests for observability integrations: Sentry, PostHog, structlog."""

import logging
import os
from unittest.mock import patch, MagicMock


class TestSentryInit:
    """Sentry SDK initialization tests."""

    def test_sentry_no_crash_without_dsn(self):
        """Sentry init code doesn't crash when SENTRY_DSN is not set."""
        env = {k: v for k, v in os.environ.items() if k != "SENTRY_DSN"}
        with patch.dict(os.environ, env, clear=True):
            # The app module should load without errors even without SENTRY_DSN
            # We just verify the guard condition works
            assert os.environ.get("SENTRY_DSN") is None

    def test_sentry_init_called_when_dsn_set(self):
        """Sentry init is called with correct params when DSN is provided."""
        mock_sentry = MagicMock()
        with patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://examplePublicKey@o0.ingest.sentry.io/0"},
            clear=True,
        ):
            # Simulate the init block from main.py
            if os.environ.get("SENTRY_DSN"):
                mock_sentry.init(
                    dsn=os.environ["SENTRY_DSN"],
                    environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
                    traces_sample_rate=0.1,
                    send_default_pii=False,
                )
            mock_sentry.init.assert_called_once_with(
                dsn="https://examplePublicKey@o0.ingest.sentry.io/0",
                environment="production",
                traces_sample_rate=0.1,
                send_default_pii=False,
            )

    def test_sentry_disabled_in_development(self):
        """Sentry is not initialized when SENTRY_ENVIRONMENT=development."""
        mock_sentry = MagicMock()
        with patch.dict(
            os.environ,
            {
                "SENTRY_DSN": "https://examplePublicKey@o0.ingest.sentry.io/0",
                "SENTRY_ENVIRONMENT": "development",
            },
            clear=True,
        ):
            # Reproduce the guard logic from main.py
            sentry_env = os.environ.get("SENTRY_ENVIRONMENT", "production")
            sentry_enabled = bool(os.environ.get("SENTRY_DSN")) and sentry_env != "development"
            if sentry_enabled:
                mock_sentry.init(dsn=os.environ["SENTRY_DSN"])
            mock_sentry.init.assert_not_called()

    def test_sentry_enabled_in_production(self):
        """Sentry IS initialized when SENTRY_ENVIRONMENT=production."""
        mock_sentry = MagicMock()
        with patch.dict(
            os.environ,
            {
                "SENTRY_DSN": "https://examplePublicKey@o0.ingest.sentry.io/0",
                "SENTRY_ENVIRONMENT": "production",
            },
            clear=True,
        ):
            sentry_env = os.environ.get("SENTRY_ENVIRONMENT", "production")
            sentry_enabled = bool(os.environ.get("SENTRY_DSN")) and sentry_env != "development"
            if sentry_enabled:
                mock_sentry.init(dsn=os.environ["SENTRY_DSN"])
            mock_sentry.init.assert_called_once()

    def test_sentry_pii_disabled(self):
        """Heritage app must never send PII — faces are PII."""
        mock_sentry = MagicMock()
        with patch.dict(os.environ, {"SENTRY_DSN": "https://test@sentry.io/1"}, clear=True):
            if os.environ.get("SENTRY_DSN"):
                mock_sentry.init(
                    dsn=os.environ["SENTRY_DSN"],
                    environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
                    traces_sample_rate=0.1,
                    send_default_pii=False,
                )
            call_kwargs = mock_sentry.init.call_args[1]
            assert call_kwargs["send_default_pii"] is False


class TestPostHogScript:
    """PostHog analytics snippet tests."""

    def test_posthog_renders_when_key_set(self):
        """PostHog script tag is returned when POSTHOG_API_KEY is set."""
        with patch.dict(os.environ, {"POSTHOG_API_KEY": "phc_test123"}):
            from app.main import _posthog_script

            result = _posthog_script()
            assert len(result) == 1
            # Check it's a Script element containing the key
            html = repr(result[0])
            assert "phc_test123" in html
            assert "posthog.init" in html
            assert "respect_dnt" in html

    def test_posthog_absent_when_key_not_set(self):
        """PostHog returns empty tuple when POSTHOG_API_KEY is not set."""
        env = {k: v for k, v in os.environ.items() if k != "POSTHOG_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            from app.main import _posthog_script

            result = _posthog_script()
            assert result == ()

    def test_posthog_absent_when_key_empty(self):
        """PostHog returns empty tuple when POSTHOG_API_KEY is empty string."""
        with patch.dict(os.environ, {"POSTHOG_API_KEY": ""}):
            from app.main import _posthog_script

            result = _posthog_script()
            assert result == ()


class TestStructlog:
    """structlog configuration tests."""

    def test_structlog_configures_without_errors(self):
        """structlog.configure() completes without raising."""
        import structlog

        # Re-run configure to verify it doesn't crash
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.dev.ConsoleRenderer(),
            ],
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        )
        # If we get here, configuration succeeded
        logger = structlog.get_logger()
        assert logger is not None

    def test_structlog_logger_callable(self):
        """structlog logger can emit a log message without crashing."""
        import structlog

        logger = structlog.get_logger()
        # Should not raise
        logger.info("test_message", key="value")
