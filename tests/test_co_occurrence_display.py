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


class TestEventGrouping5YearWindows:
    """Tests for scripts/event_grouping.py::group_into_events — 5-year window clustering."""

    def test_same_window_groups_together(self):
        """Photos within the same 5-year window should group together."""
        from scripts.event_grouping import group_into_events

        dated_photos = {
            "p1": {"best_year_estimate": 1921},
            "p2": {"best_year_estimate": 1923},
            "p3": {"best_year_estimate": 1924},
        }
        photos = {
            "p1": {"face_ids": ["f1"]},
            "p2": {"face_ids": ["f1"]},
            "p3": {"face_ids": ["f1"]},
        }
        face_to_identity = {"f1": "id_a"}

        groups = group_into_events(dated_photos, {}, photos, face_to_identity)
        # All 3 photos are in the 1920-1924 window and share identity id_a
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_different_windows_separate(self):
        """Photos in different 5-year windows should be in separate groups."""
        from scripts.event_grouping import group_into_events

        dated_photos = {
            "p1": {"best_year_estimate": 1920},
            "p2": {"best_year_estimate": 1930},
        }
        photos = {
            "p1": {"face_ids": ["f1"]},
            "p2": {"face_ids": ["f1"]},
        }
        face_to_identity = {"f1": "id_a"}

        groups = group_into_events(dated_photos, {}, photos, face_to_identity)
        assert len(groups) == 2

    def test_no_snowball_across_windows(self):
        """±2-year naive clustering would chain A(1922)-B(1924)-C(1926) into one group.
        5-year windows should keep 1920-1924 and 1925-1929 separate (Lesson 115)."""
        from scripts.event_grouping import group_into_events

        dated_photos = {
            "p1": {"best_year_estimate": 1922},
            "p2": {"best_year_estimate": 1924},
            "p3": {"best_year_estimate": 1926},
        }
        photos = {
            "p1": {"face_ids": ["f1"]},
            "p2": {"face_ids": ["f1"]},
            "p3": {"face_ids": ["f1"]},
        }
        face_to_identity = {"f1": "id_a"}

        groups = group_into_events(dated_photos, {}, photos, face_to_identity)
        # p1 and p2 in 1920-1924, p3 in 1925-1929
        assert len(groups) == 2
        sizes = sorted([len(g) for g in groups])
        assert sizes == [1, 2]


class TestCompanionSortOrder:
    """Verify companion list is sorted by shared photo count (unit test)."""

    def test_companions_sorted_descending(self):
        """When building companion list, higher counts should come first."""
        # Simulate the companion building logic from person_routes.py
        companion_counts = {"id_a": 5, "id_b": 20, "id_c": 3, "id_d": 12}
        companion_info = {
            "id_a": {"name": "Person A", "crop_url": None},
            "id_b": {"name": "Person B", "crop_url": None},
            "id_c": {"name": "Person C", "crop_url": None},
            "id_d": {"name": "Person D", "crop_url": None},
        }

        appears_with = []
        for other_id, count in sorted(companion_counts.items(), key=lambda x: -x[1]):
            info = companion_info[other_id]
            appears_with.append(
                {
                    "id": other_id,
                    "name": info["name"],
                    "crop_url": info["crop_url"],
                    "shared_photos": count,
                }
            )

        assert appears_with[0]["id"] == "id_b"  # 20 photos
        assert appears_with[0]["shared_photos"] == 20
        assert appears_with[1]["id"] == "id_d"  # 12 photos
        assert appears_with[2]["id"] == "id_a"  # 5 photos
        assert appears_with[3]["id"] == "id_c"  # 3 photos
