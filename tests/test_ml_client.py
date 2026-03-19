"""Tests for core/ml_client.py — ML Service HTTP Client (Session 116).

Tests the async HTTP client that communicates with the standalone ML service.
All tests use mocked httpx to avoid needing a running ML service.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestMLServiceClientConfig:
    """Test client configuration and feature flag behavior."""

    def test_not_configured_when_no_url(self):
        from core.ml_client import MLServiceClient

        with patch.dict(os.environ, {}, clear=False):
            # Remove ML_SERVICE_URL if set
            os.environ.pop("ML_SERVICE_URL", None)
            client = MLServiceClient(base_url="")
            assert client.is_configured is False

    def test_configured_when_url_set(self):
        from core.ml_client import MLServiceClient

        client = MLServiceClient(base_url="http://ml-service:5002")
        assert client.is_configured is True

    def test_reads_url_from_env(self):
        from core.ml_client import MLServiceClient

        with patch.dict(os.environ, {"ML_SERVICE_URL": "http://test:5002"}):
            client = MLServiceClient()
            assert client.base_url == "http://test:5002"
            assert client.is_configured is True

    def test_strips_trailing_slash(self):
        from core.ml_client import MLServiceClient

        client = MLServiceClient(base_url="http://ml-service:5002/")
        assert client.base_url == "http://ml-service:5002"

    def test_auth_token_from_param(self):
        from core.ml_client import MLServiceClient

        client = MLServiceClient(base_url="http://test:5002", token="my-token")
        assert client.token == "my-token"

    def test_auth_token_from_env(self):
        from core.ml_client import MLServiceClient

        with patch.dict(os.environ, {"ML_SERVICE_TOKEN": "env-token"}):
            client = MLServiceClient(base_url="http://test:5002")
            assert client.token == "env-token"


class TestMLServiceClientIsAvailable:
    """Test availability checking."""

    def test_not_available_when_not_configured(self):
        from core.ml_client import MLServiceClient
        import asyncio

        client = MLServiceClient(base_url="")
        result = asyncio.get_event_loop().run_until_complete(client.is_available())
        assert result is False

    def test_not_available_on_connection_error(self):
        from core.ml_client import MLServiceClient
        import asyncio

        client = MLServiceClient(base_url="http://127.0.0.1:59999")
        result = asyncio.get_event_loop().run_until_complete(client.is_available())
        assert result is False
        asyncio.get_event_loop().run_until_complete(client.close())


class TestMLServiceClientWarm:
    """Test model warm-up method."""

    def test_warm_calls_correct_endpoint(self):
        from core.ml_client import MLServiceClient
        import asyncio

        client = MLServiceClient(base_url="http://ml-service:5002")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "status": "warm",
            "model": "buffalo_l",
            "load_time_seconds": 0.01,
            "already_loaded": True,
        }
        mock_response.raise_for_status = MagicMock()

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.get = AsyncMock(return_value=mock_response)
        client._client = mock_http

        result = asyncio.get_event_loop().run_until_complete(client.warm())
        mock_http.get.assert_called_once_with("/api/v1/warm")
        assert result["status"] == "warm"
        assert result["model"] == "buffalo_l"


class TestGetMlClient:
    """Test singleton client factory."""

    def test_returns_same_instance(self):
        from core.ml_client import get_ml_client, _ml_client
        import core.ml_client as mod

        # Reset singleton
        mod._ml_client = None
        c1 = get_ml_client()
        c2 = get_ml_client()
        assert c1 is c2
        # Cleanup
        mod._ml_client = None

    def test_creates_client(self):
        from core.ml_client import get_ml_client
        import core.ml_client as mod

        mod._ml_client = None
        client = get_ml_client()
        assert client is not None
        mod._ml_client = None
