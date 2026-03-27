"""Tests for the event groups timeline page."""

import json
from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def sample_event_groups():
    return {
        "metadata": {
            "esther_id": "65207728-9ee6-48c1-be68-a2da23354caf",
            "albert_id": "85546ebf-75b9-4971-a9d4-b2ce2271bc19",
            "year_tolerance": 2,
            "frequent_companion_threshold": 2,
            "total_dated_photos": 82,
        },
        "event_groups": [
            {
                "photo_ids": ["photo_001", "photo_002"],
                "num_photos": 2,
                "date_range": [1920, 1924],
                "contains_esther": True,
                "contains_albert": True,
                "total_faces": 10,
                "identified_count": 3,
                "unidentified_count": 7,
                "identified_faces": {
                    "face_a": {
                        "identity_id": "id-esther",
                        "name": "Esther Burd Fox",
                        "appearances": 2,
                    },
                    "face_b": {
                        "identity_id": "id-albert",
                        "name": "Albert Fox",
                        "appearances": 1,
                    },
                },
                "unidentified_faces": {},
                "all_face_ids": ["face_a", "face_b"],
            },
            {
                "photo_ids": ["photo_003"],
                "num_photos": 1,
                "date_range": [1915, 1918],
                "contains_esther": True,
                "contains_albert": False,
                "total_faces": 5,
                "identified_count": 1,
                "unidentified_count": 4,
                "identified_faces": {
                    "face_c": {
                        "identity_id": "id-esther",
                        "name": "Esther Burd Fox",
                        "appearances": 1,
                    },
                },
                "unidentified_faces": {},
                "all_face_ids": ["face_c"],
            },
        ],
        "frequent_companions": [
            {
                "identity_id": "id-companion-1",
                "identity_name": "Unidentified Person 3051",
                "face_ids": ["face_x", "face_y"],
                "num_faces": 2,
                "event_group_count": 2,
                "event_details": [
                    {
                        "date_range": [1920, 1924],
                        "photo_ids": ["photo_001"],
                        "with_esther": True,
                        "with_albert": True,
                    },
                ],
                "age_trajectory": [
                    {
                        "year": 1920,
                        "estimated_age": 30,
                        "gender": "female",
                        "description": "Woman in a hat",
                        "photo_id": "photo_001",
                        "face_id": "face_x",
                    },
                ],
            }
        ],
    }


class TestEventGroupsRoute:
    """Tests for /admin/event-groups route."""

    def test_event_groups_requires_admin(self, client):
        """Non-admin users should be denied."""
        from starlette.responses import Response

        with patch(
            "app.temporal_routes._main_mod._check_admin",
            return_value=Response("Forbidden", status_code=403),
        ):
            resp = client.get("/admin/event-groups")
            assert resp.status_code == 403

    def test_event_groups_page_loads_with_data(self, client, sample_event_groups):
        """Admin can access event groups page when data exists."""
        with (
            patch("app.temporal_routes._main_mod._check_admin", return_value=None),
            patch(
                "app.temporal_routes.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")
            ),
            patch("app.temporal_routes._load_event_groups", return_value=sample_event_groups),
        ):
            resp = client.get("/admin/event-groups")
            assert resp.status_code == 200
            text = resp.text
            assert "Event Groups" in text
            assert "1920" in text
            assert "1915" in text
            assert "Esther" in text
            assert "Albert" in text

    def test_event_groups_page_no_data(self, client):
        """Page shows message when no data file exists."""
        with (
            patch("app.temporal_routes._main_mod._check_admin", return_value=None),
            patch(
                "app.temporal_routes.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")
            ),
            patch("app.temporal_routes._load_event_groups", return_value=None),
        ):
            resp = client.get("/admin/event-groups")
            assert resp.status_code == 200
            assert "No event group data found" in resp.text

    def test_event_groups_shows_companions(self, client, sample_event_groups):
        """Frequent companions section renders."""
        with (
            patch("app.temporal_routes._main_mod._check_admin", return_value=None),
            patch(
                "app.temporal_routes.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")
            ),
            patch("app.temporal_routes._load_event_groups", return_value=sample_event_groups),
        ):
            resp = client.get("/admin/event-groups")
            assert resp.status_code == 200
            text = resp.text
            assert "Frequent Companions" in text
            assert "Unidentified Person 3051" in text
            assert "Woman in a hat" in text

    def test_event_groups_shows_stat_cards(self, client, sample_event_groups):
        """Summary stat cards are rendered."""
        with (
            patch("app.temporal_routes._main_mod._check_admin", return_value=None),
            patch(
                "app.temporal_routes.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")
            ),
            patch("app.temporal_routes._load_event_groups", return_value=sample_event_groups),
        ):
            resp = client.get("/admin/event-groups")
            text = resp.text
            # 2 event groups
            assert ">2<" in text
            # 3 photos total
            assert ">3<" in text

    def test_event_groups_links_to_photos(self, client, sample_event_groups):
        """Photo IDs link to photo pages."""
        with (
            patch("app.temporal_routes._main_mod._check_admin", return_value=None),
            patch(
                "app.temporal_routes.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")
            ),
            patch("app.temporal_routes._load_event_groups", return_value=sample_event_groups),
        ):
            resp = client.get("/admin/event-groups")
            assert "/photo/photo_001" in resp.text

    def test_event_groups_links_to_people(self, client, sample_event_groups):
        """Identified people link to person pages."""
        with (
            patch("app.temporal_routes._main_mod._check_admin", return_value=None),
            patch(
                "app.temporal_routes.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")
            ),
            patch("app.temporal_routes._load_event_groups", return_value=sample_event_groups),
        ):
            resp = client.get("/admin/event-groups")
            assert "/person/id-esther" in resp.text
            assert "/person/id-albert" in resp.text

    def test_event_groups_sorted_chronologically(self, client, sample_event_groups):
        """Event groups are displayed in chronological order."""
        with (
            patch("app.temporal_routes._main_mod._check_admin", return_value=None),
            patch(
                "app.temporal_routes.get_current_user", return_value=MagicMock(is_admin=True, email="admin@test.com")
            ),
            patch("app.temporal_routes._load_event_groups", return_value=sample_event_groups),
        ):
            resp = client.get("/admin/event-groups")
            text = resp.text
            # 1915 should appear before 1920 in the output
            pos_1915 = text.index("1915")
            pos_1920 = text.index("1920")
            assert pos_1915 < pos_1920


class TestUniqueIdentifiedPeople:
    """Tests for the deduplication helper."""

    def test_deduplicates_by_identity_id(self):
        from app.temporal_routes import _unique_identified_people

        faces = {
            "face_a": {"identity_id": "id-1", "name": "Person A", "appearances": 1},
            "face_b": {"identity_id": "id-1", "name": "Person A", "appearances": 1},
            "face_c": {"identity_id": "id-2", "name": "Person B", "appearances": 1},
        }
        result = _unique_identified_people(faces)
        assert len(result) == 2
        # Person A should have 2 total appearances
        person_a = next(p for p in result if p["identity_id"] == "id-1")
        assert person_a["total_appearances"] == 2

    def test_empty_input(self):
        from app.temporal_routes import _unique_identified_people

        assert _unique_identified_people({}) == []
