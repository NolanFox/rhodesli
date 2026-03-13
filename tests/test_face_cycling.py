"""Tests for face cycling on identity cards.

Identity cards with multiple faces should include prev/next arrows and
dot indicators for cycling through face crops in-place. Uses data-action
event delegation per Lesson 39 / UI Scalability Rule 4.
"""

import pytest

from app.main import identity_card, to_xml


class TestFaceCyclingOnIdentityCard:
    """Face cycling arrows and dots on multi-face identity cards."""

    def _make_identity(self, face_count: int, name: str = "Test Person"):
        """Helper to build an identity dict with N inbox-style faces."""
        face_ids = [f"inbox_face{i:04d}" for i in range(face_count)]
        return {
            "identity_id": "test-cycle-id-001",
            "name": name,
            "state": "CONFIRMED",
            "anchor_ids": face_ids,
            "candidate_ids": [],
        }

    def _crop_files_for(self, face_count: int) -> set:
        """Return crop_files set matching the faces from _make_identity."""
        return {f"inbox_face{i:04d}.jpg" for i in range(face_count)}

    def test_single_face_no_cycling(self):
        """Identity with 1 face should NOT have cycling arrows or dots."""
        identity = self._make_identity(1)
        crop_files = self._crop_files_for(1)
        html = to_xml(identity_card(identity, crop_files))
        assert "face-cycle-prev" not in html
        assert "face-cycle-next" not in html
        assert "data-cycle-urls" not in html
        assert "data-dot-index" not in html

    def test_multi_face_has_cycling_arrows(self):
        """Identity with 3 faces should have prev/next cycling arrows."""
        identity = self._make_identity(3)
        crop_files = self._crop_files_for(3)
        html = to_xml(identity_card(identity, crop_files))
        assert 'data-action="face-cycle-prev"' in html
        assert 'data-action="face-cycle-next"' in html

    def test_multi_face_has_cycle_urls(self):
        """Identity with 3 faces should embed cycle URLs as data attribute."""
        identity = self._make_identity(3)
        crop_files = self._crop_files_for(3)
        html = to_xml(identity_card(identity, crop_files))
        assert "data-cycle-urls" in html
        # Should have pipe-separated URLs
        assert "|" in html

    def test_multi_face_has_dot_indicators(self):
        """Identity with 3 faces should have dot indicators."""
        identity = self._make_identity(3)
        crop_files = self._crop_files_for(3)
        html = to_xml(identity_card(identity, crop_files))
        assert 'data-dot-index="0"' in html
        assert 'data-dot-index="1"' in html
        assert 'data-dot-index="2"' in html

    def test_cycle_urls_capped_at_five(self):
        """Even with 10+ faces, only up to 5 cycle URLs should be embedded."""
        identity = self._make_identity(10)
        crop_files = self._crop_files_for(10)
        html = to_xml(identity_card(identity, crop_files))
        # Extract the data-cycle-urls attribute value
        import re

        match = re.search(r'data-cycle-urls="([^"]*)"', html)
        assert match, "data-cycle-urls attribute not found"
        urls = match.group(1).split("|")
        assert len(urls) <= 5

    def test_cycle_index_starts_at_zero(self):
        """The data-cycle-index should start at 0."""
        identity = self._make_identity(3)
        crop_files = self._crop_files_for(3)
        html = to_xml(identity_card(identity, crop_files))
        assert 'data-cycle-index="0"' in html

    def test_arrows_use_data_action_delegation(self):
        """Arrows must use data-action pattern, not onclick (Lesson 39)."""
        identity = self._make_identity(3)
        crop_files = self._crop_files_for(3)
        html = to_xml(identity_card(identity, crop_files))
        # Must use data-action, not inline onclick
        assert 'data-action="face-cycle-prev"' in html
        assert 'data-action="face-cycle-next"' in html

    def test_hero_image_has_cycle_img_marker(self):
        """Hero image needs data-cycle-img for JS to find it."""
        identity = self._make_identity(3)
        crop_files = self._crop_files_for(3)
        html = to_xml(identity_card(identity, crop_files))
        assert "data-cycle-img" in html
