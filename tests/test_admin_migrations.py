"""Tests for /api/admin/run-migrations endpoint."""

from pathlib import Path


class TestAdminMigrationsEndpoint:
    """Test the admin migration endpoint."""

    def test_endpoint_exists(self):
        source = Path("app/admin_routes.py").read_text()
        assert "/api/admin/run-migrations" in source

    def test_endpoint_requires_admin(self):
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/run-migrations")
        handler = source[idx : idx + 500]
        assert "_check_admin" in handler

    def test_endpoint_creates_community_indexes(self):
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/run-migrations")
        handler = source[idx : idx + 1000]
        assert "idx_photo_communities_community_id" in handler
        assert "idx_identity_communities_community_id" in handler

    def test_endpoint_handles_no_supabase(self):
        source = Path("app/admin_routes.py").read_text()
        idx = source.index("/api/admin/run-migrations")
        handler = source[idx : idx + 1000]
        assert "503" in handler or "not configured" in handler.lower()
