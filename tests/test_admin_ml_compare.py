"""Tests for Session 121: /api/admin/ml-compare endpoint and compare script --url mode."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAdminMLCompareEndpoint:
    """Test the admin ML compare proxy endpoint."""

    def test_endpoint_exists_in_admin_routes(self):
        """The /api/admin/ml-compare route must exist."""
        source = Path("app/admin_routes.py").read_text()
        assert "/api/admin/ml-compare" in source

    def test_endpoint_requires_admin(self):
        """Non-admin requests should be denied."""
        source = Path("app/admin_routes.py").read_text()
        # Find the ml-compare handler
        idx = source.index("/api/admin/ml-compare")
        handler = source[idx : idx + 500]
        assert "_check_admin" in handler, "Endpoint must check admin auth"

    def test_endpoint_returns_503_without_ml_service(self):
        """When ML_SERVICE_URL is not set, endpoint returns 503."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/ml-compare")
        handler = source[idx : idx + 800]
        assert "503" in handler or "not_configured" in handler, "Endpoint must handle missing ML_SERVICE_URL"

    def test_endpoint_no_db_writes(self):
        """The compare endpoint must NOT write to any database."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/ml-compare")
        handler = source[idx : idx + 1500]
        assert "save_registry" not in handler, "Compare must not save registry"
        assert "shadow_write" not in handler, "Compare must not write to Supabase"
        assert "create_identity" not in handler, "Compare must not create identities"


class TestCompareScriptURLMode:
    """Test the --url flag in compare_ml_embeddings.py."""

    def test_url_flag_exists(self):
        """Script must accept --url argument."""
        source = Path("scripts/compare_ml_embeddings.py").read_text()
        assert "--url" in source

    def test_url_mode_uses_admin_endpoint(self):
        """When --url is provided, script uses /api/admin/ml-compare."""
        source = Path("scripts/compare_ml_embeddings.py").read_text()
        assert "/api/admin/ml-compare" in source

    def test_extract_remote_faces_via_url_function_exists(self):
        """The URL-based extraction function must exist."""
        source = Path("scripts/compare_ml_embeddings.py").read_text()
        assert "def extract_remote_faces_via_url" in source
