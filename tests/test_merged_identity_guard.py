"""Tests for UX-038: POST operations on merged identities redirect to canonical.

Verifies that all POST routes that modify identity data check for merged_into
and return HX-Redirect to the canonical identity instead of silently succeeding.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestMergedIdentityPOSTGuard:
    """POST to a merged identity should return HX-Redirect to canonical."""

    def _find_merged_and_canonical(self):
        """Find a merged identity and its canonical target from test data."""
        from app.main import load_registry
        registry = load_registry()
        for iid, data in registry._identities.items():
            if data.get("merged_into"):
                return iid, data["merged_into"]
        return None, None

    def _find_non_merged_ids(self, count=2):
        """Find non-merged identity IDs for testing."""
        from app.main import load_registry
        registry = load_registry()
        ids = [iid for iid, data in registry._identities.items()
               if not data.get("merged_into")]
        if len(ids) < count:
            pytest.skip(f"Need at least {count} non-merged identities")
        return ids[:count]

    def test_reject_match_merged_returns_redirect(self, client):
        """POST /api/identity/{merged_id}/reject-match/{other} returns HX-Redirect."""
        merged_id, canonical_id = self._find_merged_and_canonical()
        if not merged_id:
            pytest.skip("No merged identities in test data")
        other_ids = self._find_non_merged_ids(1)
        with patch("app.main.save_registry"):
            response = client.post(f"/api/identity/{merged_id}/reject-match/{other_ids[0]}")
        assert response.status_code == 200
        assert f"/person/{canonical_id}" in response.headers.get("hx-redirect", "")

    def test_reject_match_non_merged_works_normally(self, client):
        """POST /api/identity/{id}/reject-match/{other} works for non-merged identity."""
        ids = self._find_non_merged_ids(2)
        with patch("app.main.save_registry"):
            response = client.post(f"/api/identity/{ids[0]}/reject-match/{ids[1]}")
        assert response.status_code == 200
        # Should NOT have HX-Redirect (it worked normally)
        assert "hx-redirect" not in response.headers

    def test_rename_merged_returns_redirect(self, client):
        """POST /api/identity/{merged_id}/rename returns HX-Redirect."""
        merged_id, canonical_id = self._find_merged_and_canonical()
        if not merged_id:
            pytest.skip("No merged identities in test data")
        with patch("app.main.save_registry"):
            response = client.post(
                f"/api/identity/{merged_id}/rename",
                data={"name": "Test Name"},
            )
        assert response.status_code == 200
        assert f"/person/{canonical_id}" in response.headers.get("hx-redirect", "")

    def test_merge_with_merged_target_returns_redirect(self, client):
        """POST /api/identity/{merged_target}/merge/{source} returns HX-Redirect."""
        merged_id, canonical_id = self._find_merged_and_canonical()
        if not merged_id:
            pytest.skip("No merged identities in test data")
        other_ids = self._find_non_merged_ids(1)
        with patch("app.main.save_registry"):
            response = client.post(f"/api/identity/{merged_id}/merge/{other_ids[0]}")
        assert response.status_code == 200
        assert f"/person/{canonical_id}" in response.headers.get("hx-redirect", "")

    def test_merge_with_merged_source_returns_redirect(self, client):
        """POST /api/identity/{target}/merge/{merged_source} returns HX-Redirect."""
        merged_id, canonical_id = self._find_merged_and_canonical()
        if not merged_id:
            pytest.skip("No merged identities in test data")
        other_ids = self._find_non_merged_ids(1)
        with patch("app.main.save_registry"):
            response = client.post(f"/api/identity/{other_ids[0]}/merge/{merged_id}")
        assert response.status_code == 200
        assert f"/person/{canonical_id}" in response.headers.get("hx-redirect", "")

    def test_skip_merged_returns_redirect(self, client):
        """POST /api/identity/{merged_id}/skip returns HX-Redirect."""
        merged_id, canonical_id = self._find_merged_and_canonical()
        if not merged_id:
            pytest.skip("No merged identities in test data")
        response = client.post(f"/api/identity/{merged_id}/skip")
        assert response.status_code == 200
        assert f"/person/{canonical_id}" in response.headers.get("hx-redirect", "")

    def test_confirm_merged_returns_redirect(self, client):
        """POST /confirm/{merged_id} returns HX-Redirect."""
        merged_id, canonical_id = self._find_merged_and_canonical()
        if not merged_id:
            pytest.skip("No merged identities in test data")
        with patch("app.main.save_registry"):
            response = client.post(f"/confirm/{merged_id}")
        assert response.status_code == 200
        assert f"/person/{canonical_id}" in response.headers.get("hx-redirect", "")

    def test_reject_pair_merged_returns_redirect(self, client):
        """POST /api/identity/{merged_id}/reject/{target} returns HX-Redirect."""
        merged_id, canonical_id = self._find_merged_and_canonical()
        if not merged_id:
            pytest.skip("No merged identities in test data")
        other_ids = self._find_non_merged_ids(1)
        with patch("app.main.save_registry"):
            response = client.post(f"/api/identity/{merged_id}/reject/{other_ids[0]}")
        assert response.status_code == 200
        assert f"/person/{canonical_id}" in response.headers.get("hx-redirect", "")

    def test_reset_merged_returns_redirect(self, client):
        """POST /identity/{merged_id}/reset returns HX-Redirect."""
        merged_id, canonical_id = self._find_merged_and_canonical()
        if not merged_id:
            pytest.skip("No merged identities in test data")
        with patch("app.main.save_registry"):
            response = client.post(f"/identity/{merged_id}/reset")
        assert response.status_code == 200
        assert f"/person/{canonical_id}" in response.headers.get("hx-redirect", "")


class TestEstimateUploadUXPolish:
    """Tests for UX-053/056/057: estimate upload photo preview, CTAs, form reset."""

    def _make_jpeg_bytes(self):
        """Create minimal valid JPEG bytes."""
        from PIL import Image
        import io
        img = Image.new("RGB", (100, 100), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    def test_upload_result_has_photo_preview(self, client):
        """UX-053: Estimate upload response includes uploaded photo <img> preview."""
        import io
        content = self._make_jpeg_bytes()
        with patch("app.estimate_routes._main_mod"):
            response = client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
            )
        html = response.text
        assert "estimate-photo-preview" in html

    def test_upload_result_has_try_another_cta(self, client):
        """UX-056: Result includes 'Try Another Photo' CTA."""
        import io
        content = self._make_jpeg_bytes()
        response = client.post(
            "/api/estimate/upload",
            files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
        )
        html = response.text
        assert "Try Another Photo" in html
        assert "estimate-try-another" in html

    def test_upload_result_has_share_cta(self, client):
        """UX-056: Result includes 'Share Estimate' CTA."""
        import io
        content = self._make_jpeg_bytes()
        response = client.post(
            "/api/estimate/upload",
            files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
        )
        html = response.text
        assert "Share Estimate" in html
        assert "estimate-share" in html

    def test_upload_form_has_after_request_reset(self, client):
        """UX-057: Estimate upload form has hx-on::after-request for form reset."""
        response = client.get("/estimate")
        html = response.text
        assert "hx-on::after-request" in html
        assert "this.reset()" in html
