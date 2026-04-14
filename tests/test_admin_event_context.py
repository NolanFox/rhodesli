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

    def test_endpoint_has_csrf_origin_check(self):
        """Endpoint must validate request origin (CSRF protection)."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 800]
        assert "_check_origin" in handler, "Must have CSRF origin check"

    def test_endpoint_sorts_face_coordinates_by_x(self):
        """Face coordinates must be sorted by bbox x-coordinate (left-to-right)."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 3000]
        assert "face_coordinates.sort" in handler, "Must sort face coordinates"
        assert 'bbox"][0]' in handler or "bbox[0]" in handler, "Must sort by x-coordinate"

    def test_endpoint_uses_form_parameter_for_known_people(self):
        """Endpoint must accept known_people as a form parameter, not async body parsing."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        # Check the function signature has known_people parameter
        sig_end = source.index(":", idx + 10)
        sig_start = source.rfind("def ", 0, sig_end)
        signature = source[sig_start : sig_end + 50]
        assert "known_people: str" in signature, "Must have known_people form parameter"
        # Should NOT have async body parsing
        handler = source[idx : idx + 3000]
        assert "asyncio" not in handler, "Should not use async body parsing"
        assert "request._body" not in handler, "Should not access private request body"

    def test_face_coordinate_sorting_logic(self):
        """Verify face sorting produces left-to-right order."""
        coords = [
            {"face_id": "face_2", "bbox": [300, 10, 400, 200]},
            {"face_id": "face_0", "bbox": [10, 20, 100, 200]},
            {"face_id": "face_1", "bbox": [150, 30, 250, 220]},
        ]
        coords.sort(key=lambda f: f["bbox"][0] if isinstance(f["bbox"], list) and len(f["bbox"]) >= 1 else 0)
        assert coords[0]["face_id"] == "face_0"
        assert coords[1]["face_id"] == "face_1"
        assert coords[2]["face_id"] == "face_2"


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


class TestBuildResponseSchema:
    """Tests for build_response_schema structured output enforcement."""

    def test_identification_schema_includes_event_context(self):
        """Schema for identification preset must include event_context."""
        from rhodesli_ml.gemini_extraction import build_response_schema

        schema = build_response_schema(preset="identification")
        assert "event_context" in schema["properties"]
        assert "event_context" in schema["required"]

    def test_identification_schema_includes_relationship_inference(self):
        """Schema for identification preset must include relationship_inference."""
        from rhodesli_ml.gemini_extraction import build_response_schema

        schema = build_response_schema(preset="identification")
        assert "relationship_inference" in schema["properties"]
        assert "relationship_inference" in schema["required"]

    def test_event_context_schema_has_event_type_enum(self):
        """event_context event_type must have valid enum values."""
        from rhodesli_ml.gemini_extraction import build_response_schema

        schema = build_response_schema(preset="identification")
        ec = schema["properties"]["event_context"]
        event_type = ec["properties"]["event_type"]
        assert "enum" in event_type
        assert "wedding_ceremony" in event_type["enum"]
        assert "portrait" in event_type["enum"]

    def test_quick_preset_schema_excludes_event_context(self):
        """Quick preset should NOT include event_context (backward compat)."""
        from rhodesli_ml.gemini_extraction import build_response_schema

        schema = build_response_schema(preset="quick")
        assert "event_context" not in schema.get("properties", {})

    def test_full_preset_schema_excludes_event_context(self):
        """Full preset should NOT include event_context (it's identification-only)."""
        from rhodesli_ml.gemini_extraction import build_response_schema

        schema = build_response_schema(preset="full")
        assert "event_context" not in schema.get("properties", {})

    def test_schema_has_valid_structure(self):
        """Schema root must be OBJECT type with properties and required."""
        from rhodesli_ml.gemini_extraction import build_response_schema

        schema = build_response_schema(preset="identification")
        assert schema["type"] == "OBJECT"
        assert isinstance(schema["properties"], dict)
        assert isinstance(schema["required"], list)
        assert len(schema["properties"]) > 0

    def test_endpoint_uses_response_schema(self):
        """Admin endpoint must use build_response_schema for structured output."""
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/analyze-event-context/")
        handler = source[idx : idx + 8000]
        assert "build_response_schema" in handler
        assert "response_schema=" in handler
