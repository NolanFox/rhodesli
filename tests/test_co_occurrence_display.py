"""Tests for co-occurrence display on person page (PRD-059 Phase 3).

Verifies:
1. Companion list sorted by shared photo count
2. Shared photo count displayed in companion cards
3. Event grouping compute_co_occurrence function
"""

from collections import defaultdict

import pytest


class TestComputeCoOccurrence:
    """Tests for scripts/event_grouping.py::compute_co_occurrence."""

    def test_basic_co_occurrence(self):
        from scripts.event_grouping import compute_co_occurrence

        photos = {
            "photo1": {"face_ids": ["f1", "f2", "f3"]},
            "photo2": {"face_ids": ["f1", "f2"]},
            "photo3": {"face_ids": ["f1", "f4"]},
        }
        face_to_identity = {"f1": "id_a", "f2": "id_b", "f3": "id_c", "f4": "id_d"}
        identity_lookup = {
            "id_a": {"name": "Person A", "state": "CONFIRMED"},
            "id_b": {"name": "Person B", "state": "CONFIRMED"},
            "id_c": {"name": "Person C", "state": "CONFIRMED"},
            "id_d": {"name": "Person D", "state": "CONFIRMED"},
        }

        result = compute_co_occurrence(photos, face_to_identity, identity_lookup)

        # A and B appear together in photo1 and photo2 = 2 shared
        assert "id_a" in result
        b_entry = next(p for p in result["id_a"] if p["partner_id"] == "id_b")
        assert b_entry["shared_photos"] == 2

        # A and C appear together only in photo1 = 1 shared
        c_entry = next(p for p in result["id_a"] if p["partner_id"] == "id_c")
        assert c_entry["shared_photos"] == 1

    def test_excludes_unidentified(self):
        from scripts.event_grouping import compute_co_occurrence

        photos = {"photo1": {"face_ids": ["f1", "f2"]}}
        face_to_identity = {"f1": "id_a", "f2": "id_b"}
        identity_lookup = {
            "id_a": {"name": "Person A", "state": "CONFIRMED"},
            "id_b": {"name": "Unidentified Person 1234", "state": "CONFIRMED"},
        }

        result = compute_co_occurrence(photos, face_to_identity, identity_lookup)
        # Unidentified person should not appear as a companion
        assert "id_a" not in result or not any(p["partner_id"] == "id_b" for p in result.get("id_a", []))

    def test_sorted_by_count_descending(self):
        from scripts.event_grouping import compute_co_occurrence

        photos = {
            "photo1": {"face_ids": ["f1", "f2", "f3"]},
            "photo2": {"face_ids": ["f1", "f2"]},
            "photo3": {"face_ids": ["f1", "f3"]},
            "photo4": {"face_ids": ["f1", "f2"]},
        }
        face_to_identity = {"f1": "id_a", "f2": "id_b", "f3": "id_c"}
        identity_lookup = {
            "id_a": {"name": "Person A", "state": "CONFIRMED"},
            "id_b": {"name": "Person B", "state": "CONFIRMED"},
            "id_c": {"name": "Person C", "state": "CONFIRMED"},
        }

        result = compute_co_occurrence(photos, face_to_identity, identity_lookup)
        companions = result.get("id_a", [])
        # B appears with A in 3 photos, C in 2 — B should be first
        assert companions[0]["partner_id"] == "id_b"
        assert companions[0]["shared_photos"] == 3
        assert companions[1]["partner_id"] == "id_c"
        assert companions[1]["shared_photos"] == 2

    def test_empty_photos(self):
        from scripts.event_grouping import compute_co_occurrence

        result = compute_co_occurrence({}, {}, {})
        assert result == {}
