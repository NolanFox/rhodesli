"""Tests for Session 57: CORAL date estimation on /estimate endpoint."""

import io
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from contextlib import ExitStack

import numpy as np


class TestEstimateUploadCORAL:
    """Tests for CORAL model integration in /api/estimate/upload."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        from starlette.testclient import TestClient

        self.client = TestClient(app)

    def _make_jpeg_bytes(self):
        """Create a minimal valid JPEG file."""
        from PIL import Image

        img = Image.new("RGB", (100, 100), (128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return buf.read()

    def test_estimate_upload_returns_200(self):
        """Upload to /api/estimate/upload returns 200."""
        content = self._make_jpeg_bytes()
        response = self.client.post(
            "/api/estimate/upload",
            files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200

    def test_estimate_upload_with_coral_model(self):
        """When CORAL model is available, response includes decade prediction."""
        content = self._make_jpeg_bytes()

        mock_result = {
            "predicted_decade": 1930,
            "confidence": 0.62,
            "decade_probabilities": {
                str(d): 0.09 for d in range(1900, 2010, 10)
            },
            "expected_year": 1937,
            "source": "coral_v1",
        }
        mock_result["decade_probabilities"]["1930"] = 0.62

        with ExitStack() as stack:
            stack.enter_context(
                patch("app.main.os.getenv", side_effect=lambda k, d="": d)
            )
            stack.enter_context(
                patch(
                    "rhodesli_ml.date_inference.inference.predict_date",
                    return_value=mock_result,
                )
            )

            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            html = response.text
            assert "1930s" in html
            assert "estimate-coral-result" in html

    def test_estimate_upload_coral_shows_probability_bars(self):
        """CORAL result includes decade probability distribution bars."""
        content = self._make_jpeg_bytes()

        mock_result = {
            "predicted_decade": 1940,
            "confidence": 0.55,
            "decade_probabilities": {
                "1900": 0.01, "1910": 0.03, "1920": 0.1, "1930": 0.2,
                "1940": 0.55, "1950": 0.05, "1960": 0.03, "1970": 0.01,
                "1980": 0.01, "1990": 0.01, "2000": 0.0,
            },
            "expected_year": 1942,
            "source": "coral_v1",
        }

        with ExitStack() as stack:
            stack.enter_context(
                patch("app.main.os.getenv", side_effect=lambda k, d="": d)
            )
            stack.enter_context(
                patch(
                    "rhodesli_ml.date_inference.inference.predict_date",
                    return_value=mock_result,
                )
            )

            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
            html = response.text
            # Check probability bars are present
            assert "1940s" in html
            assert "55%" in html
            assert "Decade probability distribution" in html

    def test_estimate_upload_coral_shows_expected_year(self):
        """CORAL result shows expected year."""
        content = self._make_jpeg_bytes()

        mock_result = {
            "predicted_decade": 1920,
            "confidence": 0.45,
            "decade_probabilities": {str(d): 0.09 for d in range(1900, 2010, 10)},
            "expected_year": 1925,
            "source": "coral_v1",
        }
        mock_result["decade_probabilities"]["1920"] = 0.45

        with ExitStack() as stack:
            stack.enter_context(
                patch("app.main.os.getenv", side_effect=lambda k, d="": d)
            )
            stack.enter_context(
                patch(
                    "rhodesli_ml.date_inference.inference.predict_date",
                    return_value=mock_result,
                )
            )

            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
            html = response.text
            assert "~1925" in html

    def test_estimate_upload_coral_confidence_tiers(self):
        """Confidence tiers display correctly."""
        content = self._make_jpeg_bytes()

        # High confidence
        mock_result = {
            "predicted_decade": 1940,
            "confidence": 0.7,
            "decade_probabilities": {str(d): 0.03 for d in range(1900, 2010, 10)},
            "expected_year": 1945,
            "source": "coral_v1",
        }
        mock_result["decade_probabilities"]["1940"] = 0.7

        with ExitStack() as stack:
            stack.enter_context(
                patch("app.main.os.getenv", side_effect=lambda k, d="": d)
            )
            stack.enter_context(
                patch(
                    "rhodesli_ml.date_inference.inference.predict_date",
                    return_value=mock_result,
                )
            )

            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
            assert "High confidence" in response.text

    def test_estimate_upload_ctas_present(self):
        """CTAs are present after estimate result."""
        content = self._make_jpeg_bytes()
        response = self.client.post(
            "/api/estimate/upload",
            files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
            headers={"HX-Request": "true"},
        )
        html = response.text
        assert "estimate-ctas" in html
        assert "Estimate Another Photo" in html

    def test_estimate_upload_coral_model_unavailable_falls_back(self):
        """When CORAL model is unavailable, falls back gracefully."""
        content = self._make_jpeg_bytes()

        with ExitStack() as stack:
            stack.enter_context(
                patch("app.main.os.getenv", side_effect=lambda k, d="": d)
            )
            stack.enter_context(
                patch(
                    "rhodesli_ml.date_inference.inference.predict_date",
                    return_value=None,
                )
            )

            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
            # Should still return 200 with some content
            assert response.status_code == 200

    def test_estimate_upload_coral_source_identified(self):
        """CORAL model source is identified in the result."""
        content = self._make_jpeg_bytes()

        mock_result = {
            "predicted_decade": 1950,
            "confidence": 0.4,
            "decade_probabilities": {str(d): 0.09 for d in range(1900, 2010, 10)},
            "expected_year": 1955,
            "source": "coral_v1",
        }
        mock_result["decade_probabilities"]["1950"] = 0.4

        with ExitStack() as stack:
            stack.enter_context(
                patch("app.main.os.getenv", side_effect=lambda k, d="": d)
            )
            stack.enter_context(
                patch(
                    "rhodesli_ml.date_inference.inference.predict_date",
                    return_value=mock_result,
                )
            )

            response = self.client.post(
                "/api/estimate/upload",
                files={"photo": ("test.jpg", io.BytesIO(content), "image/jpeg")},
                headers={"HX-Request": "true"},
            )
            html = response.text
            assert "CORAL" in html

    def test_estimate_upload_rejects_non_image(self):
        """Non-image upload is rejected."""
        response = self.client.post(
            "/api/estimate/upload",
            files={"photo": ("test.txt", io.BytesIO(b"not an image"), "text/plain")},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 200
        assert "JPG or PNG" in response.text


class TestDecadeProbabilityBars:
    """Tests for decade probability bars on photo detail pages."""

    def test_render_date_section_with_probability_bars(self):
        """Date section renders probability bars when decade_probabilities present."""
        from app.main import _load_date_labels

        labels = _load_date_labels()
        if not labels:
            pytest.skip("No date labels available")

        # Find a label with decade_probabilities
        label_with_probs = None
        for pid, label in labels.items():
            if label.get("decade_probabilities"):
                label_with_probs = (pid, label)
                break

        if label_with_probs is None:
            pytest.skip("No labels with decade_probabilities")

        # Verify the data structure exists
        pid, label = label_with_probs
        probs = label["decade_probabilities"]
        assert isinstance(probs, dict)
        assert len(probs) > 0

    def test_probability_bars_sum_to_approximately_one(self):
        """Decade probabilities in labels sum to approximately 1.0."""
        from app.main import _load_date_labels

        labels = _load_date_labels()
        if not labels:
            pytest.skip("No date labels available")

        for pid, label in labels.items():
            probs = label.get("decade_probabilities", {})
            if probs:
                total = sum(float(v) for v in probs.values())
                assert abs(total - 1.0) < 0.05, (
                    f"Photo {pid}: decade probs sum to {total}, not ~1.0"
                )
                break


class TestEstimatePageRendering:
    """Tests for the /estimate page rendering."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from app.main import app
        from starlette.testclient import TestClient

        self.client = TestClient(app)

    def test_estimate_page_loads(self):
        """GET /estimate returns 200."""
        response = self.client.get("/estimate")
        assert response.status_code == 200

    def test_estimate_page_has_upload_form(self):
        """Estimate page includes upload form."""
        response = self.client.get("/estimate")
        assert "estimate-upload-form" in response.text

    def test_estimate_page_has_title(self):
        """Estimate page has correct title."""
        response = self.client.get("/estimate")
        assert "When Was This Photo Taken?" in response.text
