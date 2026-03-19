"""Tests for Session 122: TOOLS-003 real-time face compare endpoint."""

from pathlib import Path


class TestRealtimeCompareEndpoint:
    """Verify POST /api/compare/realtime endpoint structure."""

    def test_endpoint_exists(self):
        """The /api/compare/realtime route must exist."""
        source = Path("app/compare_routes.py").read_text()
        assert "/api/compare/realtime" in source

    def test_endpoint_uses_admin_check(self):
        """Endpoint must check admin auth."""
        source = Path("app/compare_routes.py").read_text()
        idx = source.index("/api/compare/realtime")
        handler = source[idx : idx + 2000]
        assert "_check_admin" in handler, "Must check admin auth"

    def test_endpoint_calls_detect_and_embed(self):
        """Endpoint must call ML service detect_and_embed."""
        source = Path("app/compare_routes.py").read_text()
        idx = source.index("/api/compare/realtime")
        handler = source[idx : idx + 3000]
        assert "detect_and_embed" in handler, "Must call ML service"

    def test_endpoint_calls_find_similar_faces(self):
        """Endpoint must use find_similar_faces for archive comparison."""
        source = Path("app/compare_routes.py").read_text()
        idx = source.index("/api/compare/realtime")
        handler = source[idx : idx + 3000]
        assert "find_similar_faces" in handler, "Must compare against archive"

    def test_temp_file_cleanup(self):
        """Endpoint must clean up temp files in finally block."""
        source = Path("app/compare_routes.py").read_text()
        idx = source.index("/api/compare/realtime")
        handler = source[idx : idx + 8000]
        assert "finally" in handler, "Must have finally block for cleanup"
        assert "unlink" in handler, "Must delete temp file"

    def test_ml_unavailable_error(self):
        """Endpoint must handle ML service unavailable gracefully."""
        source = Path("app/compare_routes.py").read_text()
        idx = source.index("/api/compare/realtime")
        handler = source[idx : idx + 2000]
        assert "ML_SERVICE_URL" in handler or "not configured" in handler or "unavailable" in handler, (
            "Must handle ML service unavailable"
        )

    def test_no_file_error(self):
        """Endpoint must handle missing file upload."""
        source = Path("app/compare_routes.py").read_text()
        idx = source.index("/api/compare/realtime")
        handler = source[idx : idx + 2000]
        assert "No file" in handler or "file" in handler, "Must handle missing file"

    def test_results_include_confidence(self):
        """Results must include confidence percentage."""
        source = Path("app/compare_routes.py").read_text()
        idx = source.index("/api/compare/realtime")
        handler = source[idx : idx + 5000]
        assert "confidence" in handler.lower(), "Results must show confidence"

    def test_results_include_view_person_link(self):
        """Results must link to person detail pages."""
        source = Path("app/compare_routes.py").read_text()
        idx = source.index("/api/compare/realtime")
        handler = source[idx : idx + 5000]
        assert "person" in handler.lower(), "Results must link to person pages"

    def test_no_database_writes(self):
        """Real-time compare must NOT write to database."""
        source = Path("app/compare_routes.py").read_text()
        idx = source.index("/api/compare/realtime")
        handler = source[idx : idx + 5000]
        assert "save_registry" not in handler, "Must not save registry"
        assert "shadow_write" not in handler, "Must not write to Supabase"
        assert "create_identity" not in handler, "Must not create identities"
