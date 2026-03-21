"""Tests for IP-based rate limiting on public upload endpoints."""

import time
from unittest.mock import patch

import pytest

from app.rate_limit import check_rate_limit, reset_rate_limits


@pytest.fixture(autouse=True)
def _clean_rate_limits():
    """Reset rate limits before and after each test."""
    reset_rate_limits()
    yield
    reset_rate_limits()


class TestCheckRateLimit:
    """Unit tests for check_rate_limit function."""

    def test_allows_first_20_requests(self):
        """First 20 requests from same IP should be allowed."""
        for i in range(20):
            assert check_rate_limit("1.2.3.4") is True, f"Request {i + 1} should be allowed"

    def test_blocks_21st_request(self):
        """21st request from same IP within an hour should be blocked."""
        for _ in range(20):
            check_rate_limit("1.2.3.4")
        assert check_rate_limit("1.2.3.4") is False

    def test_allows_after_time_passes(self):
        """Requests should be allowed again after the hour window passes."""
        for _ in range(20):
            check_rate_limit("1.2.3.4")
        assert check_rate_limit("1.2.3.4") is False

        # Advance time past the 1-hour window
        with patch("app.rate_limit.time") as mock_time:
            mock_time.time.return_value = time.time() + 3601
            assert check_rate_limit("1.2.3.4") is True

    def test_different_ips_independent(self):
        """Different IPs should have independent rate limits."""
        for _ in range(20):
            check_rate_limit("1.1.1.1")
        assert check_rate_limit("1.1.1.1") is False
        # Different IP should still be allowed
        assert check_rate_limit("2.2.2.2") is True

    def test_reset_clears_state(self):
        """reset_rate_limits() should clear all tracked requests."""
        for _ in range(20):
            check_rate_limit("1.2.3.4")
        assert check_rate_limit("1.2.3.4") is False
        reset_rate_limits()
        assert check_rate_limit("1.2.3.4") is True

    def test_custom_max_per_hour(self):
        """Custom max_per_hour parameter should be respected."""
        for _ in range(5):
            assert check_rate_limit("1.2.3.4", max_per_hour=5) is True
        assert check_rate_limit("1.2.3.4", max_per_hour=5) is False


class TestRateLimitedEndpoints:
    """Integration tests verifying rate limiting is wired into endpoints."""

    def test_compare_upload_returns_429_when_rate_limited(self, client):
        """POST /api/compare/upload should return 429 when rate limited."""
        with patch("app.compare_routes.check_rate_limit", return_value=False):
            resp = client.post("/api/compare/upload")
            assert resp.status_code == 429

    def test_compare_upload_multiple_returns_429_when_rate_limited(self, client):
        """POST /api/compare/upload-multiple should return 429 when rate limited."""
        with patch("app.compare_routes.check_rate_limit", return_value=False):
            resp = client.post("/api/compare/upload-multiple")
            assert resp.status_code == 429

    def test_compare_pair_upload_returns_429_when_rate_limited(self, client):
        """POST /api/compare/pair/upload should return 429 when rate limited."""
        with patch("app.compare_routes.check_rate_limit", return_value=False):
            resp = client.post("/api/compare/pair/upload")
            assert resp.status_code == 429

    def test_facecompare_upload_returns_429_when_rate_limited(self, client):
        """POST /api/facecompare/upload should return 429 when rate limited."""
        with patch("app.match_facecompare_routes.check_rate_limit", return_value=False):
            resp = client.post("/api/facecompare/upload")
            assert resp.status_code == 429

    def test_upload_stream_returns_429_when_rate_limited(self, client):
        """POST /api/upload/stream should return 429 when rate limited."""
        with patch("app.page_routes.check_rate_limit", return_value=False):
            resp = client.post("/api/upload/stream")
            assert resp.status_code == 429

    def test_estimate_upload_returns_429_when_rate_limited(self, client):
        """POST /api/estimate/upload should return 429 when rate limited."""
        with patch("app.estimate_routes.check_rate_limit", return_value=False):
            resp = client.post("/api/estimate/upload")
            assert resp.status_code == 429

    def test_compare_respond_returns_429_when_rate_limited(self, client):
        """POST /api/compare/result/{id}/respond should return 429 when rate limited."""
        with patch("app.compare_routes.check_rate_limit", return_value=False):
            resp = client.post("/api/compare/result/test-id/respond")
            assert resp.status_code == 429
