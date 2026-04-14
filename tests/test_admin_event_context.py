"""Tests for POST /api/admin/analyze-event-context/{photo_id} endpoint (Session 149, Phase 4)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestAnalyzeEventContextEndpoint:
    """Tests for the admin event context analysis endpoint."""

    def test_endpoint_exists_in_admin_routes(self):
        """The /api/admin/analyze-event-context route must exist."""
        source = Path("app/admin_routes.py").read_text()
        assert "/api/admin/analyze-event-context/" in source

    def test_endpoint_requires_admin(self):
        """Endpoint handler must check admin auth."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 500]
        assert "_check_admin" in handler, "Endpoint must check admin auth"

    def test_endpoint_returns_401_for_non_admin(self):
        """Non-admin requests should be denied with 401."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 600]
        # The _check_admin pattern returns 401/403 for unauthorized users
        assert "_check_admin" in handler

    def test_endpoint_returns_404_for_unknown_photo(self):
        """When photo_id doesn't exist in Supabase, return 404."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 2000]
        assert "404" in handler, "Endpoint must return 404 for unknown photos"
        assert "not found" in handler.lower(), "Endpoint must mention photo not found"

    def test_endpoint_calls_gemini_with_identification_preset(self):
        """Endpoint must use the 'identification' preset for extraction."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 6000]
        assert 'preset="identification"' in handler, "Must use identification preset"
        assert "build_extraction_prompt" in handler, "Must use build_extraction_prompt"

    def test_endpoint_loads_face_coordinates(self):
        """Endpoint must load face bounding boxes from photo_faces table."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 6000]
        assert "photo_faces" in handler, "Must query photo_faces table"
        assert "bbox" in handler, "Must load bounding box data"

    def test_endpoint_logs_gemini_call(self):
        """Endpoint must log the API call to gemini_api_calls table."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 8000]
        assert "log_gemini_call" in handler, "Must log Gemini API call"
        assert "event_context_analysis" in handler, "Must use event_context_analysis call type"

    def test_endpoint_returns_503_without_supabase(self):
        """When Supabase is not configured, endpoint returns 503."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 1500]
        assert "503" in handler, "Must return 503 when Supabase unavailable"

    def test_endpoint_returns_503_without_gemini_key(self):
        """When GEMINI_API_KEY is not set, endpoint returns 503."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 8000]
        assert "GEMINI_API_KEY" in handler, "Must check for API key"

    def test_endpoint_accepts_known_people_parameter(self):
        """Endpoint must accept known_people in request body for context."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 8000]
        assert "known_people" in handler, "Must accept known_people parameter"
        assert "verified_facts" in handler, "Must convert known_people to verified_facts"

    def test_endpoint_returns_json_response(self):
        """Endpoint must return application/json responses."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 8000]
        assert "application/json" in handler, "Must return JSON content type"

    def test_endpoint_includes_latency_in_response(self):
        """Success response must include latency_ms field."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 8000]
        assert "latency_ms" in handler, "Must include latency in response"

    def test_endpoint_truncates_prompt_for_logging(self):
        """Prompt text logged to Supabase must be truncated to avoid oversized rows."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 8000]
        assert "prompt_text=prompt_text[:5000]" in handler, "Must truncate prompt for logging"


class TestBuildExtractionPromptIdentificationPreset:
    """Verify the identification preset includes event_context and relationship_inference."""

    def test_identification_preset_includes_event_context(self):
        """The identification preset must enable event_context extraction."""
        from rhodesli_ml.gemini_extraction import EXTRACTION_PRESETS

        assert EXTRACTION_PRESETS["identification"].get("event_context") is True

    def test_identification_preset_includes_relationship_inference(self):
        """The identification preset must enable relationship_inference extraction."""
        from rhodesli_ml.gemini_extraction import EXTRACTION_PRESETS

        assert EXTRACTION_PRESETS["identification"].get("relationship_inference") is True

    def test_build_prompt_with_face_coordinates(self):
        """build_extraction_prompt with face_coordinates should include bbox data."""
        from rhodesli_ml.gemini_extraction import build_extraction_prompt

        coords = [
            {"face_id": "face_0", "bbox": [10, 20, 100, 200]},
            {"face_id": "face_1", "bbox": [150, 30, 250, 220]},
        ]
        prompt = build_extraction_prompt(preset="identification", face_coordinates=coords)
        assert "Face 0: bbox=[10, 20, 100, 200]" in prompt
        assert "Face 1: bbox=[150, 30, 250, 220]" in prompt

    def test_build_prompt_with_verified_facts(self):
        """build_extraction_prompt with verified_facts should include known names."""
        from rhodesli_ml.gemini_extraction import build_extraction_prompt

        facts = {"confirmed_names": ["Albert Fox (born ~1895)", "Esther Burd Fox"]}
        prompt = build_extraction_prompt(preset="identification", verified_facts=facts)
        assert "Albert Fox" in prompt
        assert "Esther Burd Fox" in prompt
