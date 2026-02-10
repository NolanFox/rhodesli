"""
Tests for photo-level annotations (AN-002–AN-006).

Covers: caption, date, location, story, source annotations on photos.
"""

import pytest
import json
from starlette.testclient import TestClient
from unittest.mock import patch, MagicMock
from fastcore.xml import to_xml


class TestPhotoAnnotationsSection:
    """Tests for _photo_annotations_section helper."""

    def test_renders_empty_state(self):
        """Photo annotations section renders when no annotations exist."""
        from app.main import _photo_annotations_section, _invalidate_annotations_cache

        _invalidate_annotations_cache()

        with patch("app.main._load_annotations", return_value={"annotations": {}}):
            result = _photo_annotations_section("photo-1", is_admin=False)
            html = to_xml(result)
            assert "photo-annotations-photo-1" in html
            assert "Add annotation" in html

    def test_shows_approved_annotations(self, tmp_path):
        """Approved photo annotations display in the section."""
        from app.main import _photo_annotations_section, _invalidate_annotations_cache

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "ann-1": {
                    "annotation_id": "ann-1",
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "photo-1",
                    "value": "Wedding at the synagogue",
                    "confidence": "certain",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "approved",
                    "reviewed_by": "admin@test.com",
                    "reviewed_at": "2026-02-10T01:00:00Z",
                },
            }
        }

        _invalidate_annotations_cache()
        with patch("app.main._load_annotations", return_value=ann_data):
            result = _photo_annotations_section("photo-1")
            html = to_xml(result)
            assert "Wedding at the synagogue" in html
            assert "Caption" in html

    def test_does_not_show_pending_annotations(self, tmp_path):
        """Pending annotations are not shown in the display."""
        from app.main import _photo_annotations_section, _invalidate_annotations_cache

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "ann-pending": {
                    "annotation_id": "ann-pending",
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "photo-1",
                    "value": "Pending caption",
                    "confidence": "guess",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                },
            }
        }

        _invalidate_annotations_cache()
        with patch("app.main._load_annotations", return_value=ann_data):
            result = _photo_annotations_section("photo-1")
            html = to_xml(result)
            assert "Pending caption" not in html

    def test_admin_sees_pending_count(self, tmp_path):
        """Admin sees count of pending annotations as a badge."""
        from app.main import _photo_annotations_section, _invalidate_annotations_cache

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "ann-1": {
                    "annotation_id": "ann-1",
                    "type": "caption",
                    "target_type": "photo",
                    "target_id": "photo-1",
                    "value": "Pending",
                    "confidence": "guess",
                    "reason": "",
                    "submitted_by": "user@test.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "pending",
                    "reviewed_by": None,
                    "reviewed_at": None,
                },
            }
        }

        _invalidate_annotations_cache()
        with patch("app.main._load_annotations", return_value=ann_data):
            result = _photo_annotations_section("photo-1", is_admin=True)
            html = to_xml(result)
            assert "1 pending" in html

    def test_form_has_annotation_types(self):
        """Annotation form includes all AN-002–AN-006 types."""
        from app.main import _photo_annotations_section, _invalidate_annotations_cache

        _invalidate_annotations_cache()
        with patch("app.main._load_annotations", return_value={"annotations": {}}):
            result = _photo_annotations_section("photo-1")
            html = to_xml(result)
            assert "caption" in html
            assert "date" in html
            assert "location" in html
            assert "story" in html
            assert "Source/Donor" in html

    def test_form_posts_to_annotations_submit(self):
        """Form submits to the annotation submission endpoint."""
        from app.main import _photo_annotations_section, _invalidate_annotations_cache

        _invalidate_annotations_cache()
        with patch("app.main._load_annotations", return_value={"annotations": {}}):
            result = _photo_annotations_section("photo-1")
            html = to_xml(result)
            assert "/api/annotations/submit" in html

    def test_form_includes_confidence_levels(self):
        """Form has confidence level selector."""
        from app.main import _photo_annotations_section, _invalidate_annotations_cache

        _invalidate_annotations_cache()
        with patch("app.main._load_annotations", return_value={"annotations": {}}):
            result = _photo_annotations_section("photo-1")
            html = to_xml(result)
            assert "certain" in html.lower()
            assert "likely" in html.lower()
            assert "guess" in html.lower()

    def test_shows_multiple_annotation_types(self):
        """Multiple annotation types display with correct labels."""
        from app.main import _photo_annotations_section, _invalidate_annotations_cache

        ann_data = {
            "schema_version": 1,
            "annotations": {
                "ann-cap": {
                    "annotation_id": "ann-cap", "type": "caption",
                    "target_type": "photo", "target_id": "photo-1",
                    "value": "Beach outing", "confidence": "certain",
                    "reason": "", "submitted_by": "u@t.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "approved", "reviewed_by": "a@t.com",
                    "reviewed_at": "2026-02-10T01:00:00Z",
                },
                "ann-date": {
                    "annotation_id": "ann-date", "type": "date",
                    "target_type": "photo", "target_id": "photo-1",
                    "value": "circa 1945", "confidence": "likely",
                    "reason": "", "submitted_by": "u@t.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "approved", "reviewed_by": "a@t.com",
                    "reviewed_at": "2026-02-10T01:00:00Z",
                },
                "ann-loc": {
                    "annotation_id": "ann-loc", "type": "location",
                    "target_type": "photo", "target_id": "photo-1",
                    "value": "Rhodes, Greece", "confidence": "certain",
                    "reason": "", "submitted_by": "u@t.com",
                    "submitted_at": "2026-02-10T00:00:00Z",
                    "status": "approved", "reviewed_by": "a@t.com",
                    "reviewed_at": "2026-02-10T01:00:00Z",
                },
            }
        }

        _invalidate_annotations_cache()
        with patch("app.main._load_annotations", return_value=ann_data):
            result = _photo_annotations_section("photo-1")
            html = to_xml(result)
            assert "Beach outing" in html
            assert "circa 1945" in html
            assert "Rhodes, Greece" in html
            assert "Caption" in html
            assert "Date" in html
            assert "Location" in html
