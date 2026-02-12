"""
Tests for co-occurrence signal in neighbor cards.

Co-occurrence: when two identities appear in the same photo(s), this is
strong evidence they are different people (or family members).
"""

import pytest
from core.photo_registry import PhotoRegistry
from core.registry import IdentityRegistry


class TestComputeCoOccurrence:
    """Tests for _compute_co_occurrence() helper function."""

    def test_returns_zero_when_no_shared_photos(self):
        """Two identities in separate photos should have 0 co-occurrence."""
        from app.main import _compute_co_occurrence

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_b")

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")

        count = _compute_co_occurrence(id_a, id_b, registry, photo_registry)
        assert count == 0

    def test_returns_count_when_shared_photos(self):
        """Two identities in the same photo should have co-occurrence = 1."""
        from app.main import _compute_co_occurrence

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_b")

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=["face_b"], user_source="test")

        count = _compute_co_occurrence(id_a, id_b, registry, photo_registry)
        assert count == 1

    def test_returns_multiple_shared_photos(self):
        """Two identities in multiple shared photos should return correct count."""
        from app.main import _compute_co_occurrence

        photo_registry = PhotoRegistry()
        # Both appear in photo_1
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a1")
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_b1")
        # Both appear in photo_2
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_a2")
        photo_registry.register_face("photo_2", "/path/2.jpg", "face_b2")
        # Only identity A in photo_3
        photo_registry.register_face("photo_3", "/path/3.jpg", "face_a3")

        registry = IdentityRegistry()
        id_a = registry.create_identity(
            anchor_ids=["face_a1", "face_a2", "face_a3"], user_source="test"
        )
        id_b = registry.create_identity(
            anchor_ids=["face_b1", "face_b2"], user_source="test"
        )

        count = _compute_co_occurrence(id_a, id_b, registry, photo_registry)
        assert count == 2

    def test_includes_candidate_face_ids(self):
        """Should consider candidate_ids in addition to anchor_ids."""
        from app.main import _compute_co_occurrence

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_b_candidate")

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(
            anchor_ids=[], candidate_ids=["face_b_candidate"], user_source="test"
        )

        count = _compute_co_occurrence(id_a, id_b, registry, photo_registry)
        assert count == 1

    def test_handles_identity_with_no_faces(self):
        """Should return 0 if one identity has no faces at all."""
        from app.main import _compute_co_occurrence

        photo_registry = PhotoRegistry()
        photo_registry.register_face("photo_1", "/path/1.jpg", "face_a")

        registry = IdentityRegistry()
        id_a = registry.create_identity(anchor_ids=["face_a"], user_source="test")
        id_b = registry.create_identity(anchor_ids=[], user_source="test")

        count = _compute_co_occurrence(id_a, id_b, registry, photo_registry)
        assert count == 0


class TestNeighborCardCoOccurrenceBadge:
    """Tests for co-occurrence badge rendering in neighbor_card."""

    def test_badge_rendered_when_co_occurrence_positive(self):
        """Neighbor card should show co-occurrence badge when count > 0."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "neighbor-abc",
            "name": "Test Person",
            "distance": 0.5,
            "percentile": 0.8,
            "can_merge": False,
            "merge_blocked_reason": "co_occurrence",
            "merge_blocked_reason_display": "Appear together in a photo",
            "anchor_face_ids": ["face-1"],
            "candidate_face_ids": [],
            "co_occurrence": 2,
        }
        crop_files = set()

        html = to_xml(neighbor_card(neighbor, "target-id", crop_files))

        assert "Seen together in 2 photos" in html

    def test_badge_singular_for_one_photo(self):
        """Badge should use singular 'photo' when count is 1."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "neighbor-xyz",
            "name": "Another Person",
            "distance": 0.7,
            "percentile": 0.6,
            "can_merge": False,
            "merge_blocked_reason": "co_occurrence",
            "merge_blocked_reason_display": "Appear together in a photo",
            "anchor_face_ids": ["face-2"],
            "candidate_face_ids": [],
            "co_occurrence": 1,
        }
        crop_files = set()

        html = to_xml(neighbor_card(neighbor, "target-id", crop_files))

        assert "Seen together in 1 photo" in html
        assert "Seen together in 1 photos" not in html

    def test_badge_not_rendered_when_co_occurrence_zero(self):
        """Neighbor card should NOT show co-occurrence badge when count is 0."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "neighbor-def",
            "name": "Separate Person",
            "distance": 0.5,
            "percentile": 0.8,
            "can_merge": True,
            "merge_blocked_reason": None,
            "anchor_face_ids": ["face-3"],
            "candidate_face_ids": [],
            "co_occurrence": 0,
        }
        crop_files = set()

        html = to_xml(neighbor_card(neighbor, "target-id", crop_files))

        assert "Seen together" not in html

    def test_badge_not_rendered_when_co_occurrence_absent(self):
        """Neighbor card should handle missing co_occurrence key gracefully."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "neighbor-ghi",
            "name": "Legacy Neighbor",
            "distance": 0.5,
            "percentile": 0.8,
            "can_merge": True,
            "merge_blocked_reason": None,
            "anchor_face_ids": ["face-4"],
            "candidate_face_ids": [],
            # no co_occurrence key
        }
        crop_files = set()

        html = to_xml(neighbor_card(neighbor, "target-id", crop_files))

        assert "Seen together" not in html

    def test_badge_has_correct_styling(self):
        """Badge should have amber styling for visual emphasis."""
        from app.main import neighbor_card, to_xml

        neighbor = {
            "identity_id": "neighbor-jkl",
            "name": "Styled Person",
            "distance": 0.5,
            "percentile": 0.8,
            "can_merge": False,
            "merge_blocked_reason": "co_occurrence",
            "merge_blocked_reason_display": "Appear together in a photo",
            "anchor_face_ids": ["face-5"],
            "candidate_face_ids": [],
            "co_occurrence": 3,
        }
        crop_files = set()

        html = to_xml(neighbor_card(neighbor, "target-id", crop_files))

        assert "text-amber-400" in html
        assert "italic" in html
        assert "Seen together in 3 photos" in html
