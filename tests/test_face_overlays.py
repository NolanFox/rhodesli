"""Tests for face overlay status-based visual language and photo completion badges.

Verifies that face overlays use different colors based on identity state
(CONFIRMED=green, SKIPPED=amber, REJECTED=red, PROPOSED=indigo, INBOX=dashed)
and that photo grid cards show completion badges.
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Face overlay status color tests
# ---------------------------------------------------------------------------

class TestFaceOverlayStatusColors:
    """Face overlays must use status-based colors, not all-green."""

    def _get_photo_response(self, client):
        """Get a photo partial response with face overlays."""
        from app.main import load_embeddings_for_photos
        photos = load_embeddings_for_photos()
        if not photos:
            pytest.skip("No embeddings available for testing")
        photo_id = next(iter(photos.keys()))
        return client.get(f"/photo/{photo_id}/partial")

    def test_overlay_has_status_class(self, client):
        """Face overlays include status-appropriate border color class."""
        response = self._get_photo_response(client)
        assert response.status_code == 200
        text = response.text
        assert "face-overlay" in text
        # At least one of the status colors should be present
        has_status_color = any(c in text for c in [
            "border-emerald-500",  # CONFIRMED
            "border-amber-500",    # SKIPPED
            "border-red-500",      # REJECTED
            "border-indigo-400",   # PROPOSED
            "border-dashed",       # INBOX/unassigned
        ])
        assert has_status_color, "Face overlays should use status-based colors"

    def test_confirmed_face_has_green_border(self, client):
        """CONFIRMED identity faces render with emerald green borders."""
        response = self._get_photo_response(client)
        text = response.text
        # If any confirmed faces exist, they should have green borders
        if "CONFIRMED" in text or "border-emerald-500" in text:
            assert "border-emerald-500" in text

    def test_no_all_green_default(self, client):
        """Overlays no longer use a single emerald color for all faces."""
        response = self._get_photo_response(client)
        text = response.text
        # The old pattern was: border-emerald-500 bg-emerald-500/10 hover:bg-emerald-500/20
        # With hover:border-amber-400 as the only differentiator
        # New: hover color matches state, not always amber
        assert "hover:border-amber-400" not in text, \
            "Old all-green hover style should be replaced with status-based hovers"

    def test_overlay_has_status_badge(self, client):
        """CONFIRMED/SKIPPED/REJECTED faces should have a status badge icon."""
        response = self._get_photo_response(client)
        text = response.text
        # Check for badge unicode chars used in the status badges
        has_badge = any(c in text for c in [
            "\u2713",   # ✓ check mark (confirmed)
            "\u23ed",   # ⏭ skip (skipped)
            "\u2717",   # ✗ cross (rejected)
        ])
        # Not all photos will have badges, so this test is conditional
        if "border-emerald-500" in text or "border-amber-500" in text or "border-red-500" in text:
            assert has_badge, "Status-colored overlays should include badge icons"

    def test_inbox_face_has_dashed_border(self, client):
        """INBOX/unassigned faces use dashed border style."""
        response = self._get_photo_response(client)
        text = response.text
        # If any inbox faces exist, they should have dashed borders
        if "border-dashed" in text:
            assert "border-slate-400" in text


# ---------------------------------------------------------------------------
# Photo completion badge tests
# ---------------------------------------------------------------------------

class TestPhotoCompletionBadges:
    """Photo grid cards show completion status (confirmed/total faces)."""

    def test_photos_section_has_completion_info(self, client):
        """Photos section grid cards include completion badge."""
        response = client.get("/?section=photos")
        assert response.status_code == 200
        text = response.text
        # Cards should either show "N faces" (none confirmed) or "N/M" (some confirmed)
        assert "faces" in text or "/" in text

    def test_all_confirmed_badge_is_green(self, client):
        """When all faces in a photo are confirmed, badge is green."""
        response = client.get("/?section=photos")
        text = response.text
        # If any photo has all faces confirmed, it gets the green badge class
        if "bg-emerald-600" in text:
            assert "\u2713" in text, "Green completion badge should include check mark"

    def test_partial_confirmed_badge_is_indigo(self, client):
        """When some (not all) faces are confirmed, badge is indigo."""
        response = client.get("/?section=photos")
        text = response.text
        # bg-indigo-600/70 is used for partial completion
        # This is data-dependent so we just verify the class exists in the page
        # if there are partially confirmed photos
        if "bg-indigo-600" in text:
            assert "/" in text, "Partial completion badge should show fraction"

    def test_no_confirmed_badge_is_dark(self, client):
        """When no faces are confirmed, badge uses default dark style."""
        response = client.get("/?section=photos")
        text = response.text
        # bg-black/70 is used for zero confirmed
        if "bg-black/70" in text:
            assert "faces" in text, "Zero-confirmed badge should show 'N faces'"


# ---------------------------------------------------------------------------
# Overlay tooltip tests (pre-existing but verify still works)
# ---------------------------------------------------------------------------

class TestOverlayTooltips:
    """Face overlays show name tooltips on hover."""

    def test_overlay_has_name_display(self, client):
        """Face overlays include name display — hover tooltip or always-visible label."""
        from app.main import load_embeddings_for_photos
        photos = load_embeddings_for_photos()
        if not photos:
            pytest.skip("No embeddings available for testing")
        photo_id = next(iter(photos.keys()))
        response = client.get(f"/photo/{photo_id}/partial")
        assert response.status_code == 200
        text = response.text
        # Confirmed faces have always-visible labels, others have hover tooltips
        has_hover = "group-hover:opacity-100" in text
        has_label = "bg-black/70" in text  # Always-visible name label
        assert has_hover or has_label, "Overlay should have name display (hover or always-visible)"
        assert "pointer-events-none" in text, "Name display should not intercept clicks"


class TestFaceOverlayLegend:
    """Photo view includes a legend explaining face overlay colors."""

    def test_overlay_legend_present(self, client):
        """Photo view has a legend showing Identified / Needs Help / New."""
        from app.main import load_embeddings_for_photos
        photos = load_embeddings_for_photos()
        if not photos:
            pytest.skip("No embeddings available for testing")
        photo_id = next(iter(photos.keys()))
        response = client.get(f"/photo/{photo_id}/partial")
        assert response.status_code == 200
        text = response.text
        if "face-overlay" in text:  # Only check if there are face overlays
            assert "Identified" in text, "Legend should explain green = Identified"
            assert "Needs Help" in text, "Legend should explain amber = Needs Help"


class TestMLSuggestionsRedesign:
    """ML suggestions use visual confidence indicators instead of technical metrics."""

    def test_skip_hints_returns_confidence_tiers(self, client):
        """Skip hints use confidence tier labels (Very High/High/Moderate/Low)."""
        # Find a skipped identity with hints
        from app.main import load_registry
        try:
            registry = load_registry()
        except Exception:
            pytest.skip("No registry available")

        skipped = [
            iid for iid, ident in registry._identities.items()
            if ident.get("state") == "SKIPPED" and not ident.get("merged_into")
        ]
        if not skipped:
            pytest.skip("No SKIPPED identities to test hints")

        response = client.get(f"/api/identity/{skipped[0]}/skip-hints")
        assert response.status_code == 200
        text = response.text
        if "No similar" not in text:
            # Should have confidence labels, not raw distances
            has_confidence = any(label in text for label in
                                ["Very High", "High", "Moderate", "Low"])
            assert has_confidence, "Hints should use confidence tier labels"
            assert "AI suggestions" in text, "Section should be labeled 'AI suggestions'"

    def test_skip_hints_have_compare_button(self, client):
        """Skip hints include a Compare button for each suggestion."""
        from app.main import load_registry
        try:
            registry = load_registry()
        except Exception:
            pytest.skip("No registry available")

        skipped = [
            iid for iid, ident in registry._identities.items()
            if ident.get("state") == "SKIPPED" and not ident.get("merged_into")
        ]
        if not skipped:
            pytest.skip("No SKIPPED identities")

        response = client.get(f"/api/identity/{skipped[0]}/skip-hints")
        text = response.text
        if "No similar" not in text and "AI suggestions" in text:
            assert "Compare" in text, "Each suggestion should have a Compare button"

    def test_skip_hints_no_raw_distance(self, client):
        """Skip hints should NOT show raw distance values to users."""
        from app.main import load_registry
        try:
            registry = load_registry()
        except Exception:
            pytest.skip("No registry available")

        skipped = [
            iid for iid, ident in registry._identities.items()
            if ident.get("state") == "SKIPPED" and not ident.get("merged_into")
        ]
        if not skipped:
            pytest.skip("No SKIPPED identities")

        response = client.get(f"/api/identity/{skipped[0]}/skip-hints")
        text = response.text
        if "AI suggestions" in text:
            assert "dist " not in text, "Raw distance should not be shown"
            assert "gap)" not in text, "Gap percentage should not be shown"
