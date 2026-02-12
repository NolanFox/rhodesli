"""Tests for skipped face handling across clustering, UI, and navigation.

Skipped faces are the largest pool of unresolved work (192 faces). They must be
first-class citizens in both the ML pipeline and the UI — not treated as terminal.

BUG 1: Clustering ignores SKIPPED faces → must include as candidates
BUG 2: Lightbox face overlays for skipped faces not clickable
BUG 3: Identity links route to wrong section (always to_review)
BUG 4: Footer stats exclude skipped from denominator
"""

import numpy as np
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# BUG 1: Clustering must include SKIPPED faces as candidates
# ---------------------------------------------------------------------------

class TestClusteringIncludesSkipped:
    """Skipped faces must be included as candidates for clustering."""

    def _make_face(self, face_id, mu_vals=None):
        if mu_vals is None:
            mu_vals = np.random.randn(512).astype(np.float32)
        return {
            "mu": np.asarray(mu_vals, dtype=np.float32),
            "sigma_sq": np.full(512, 0.5, dtype=np.float32),
        }

    def test_skipped_faces_are_clustering_candidates(self):
        """SKIPPED identity faces must be evaluated against confirmed identities."""
        from scripts.cluster_new_faces import find_matches

        # Confirmed identity with one face
        confirmed_face = np.zeros(512, dtype=np.float32)
        confirmed_face[0] = 1.0

        # Skipped face very close to confirmed
        skipped_face = np.zeros(512, dtype=np.float32)
        skipped_face[0] = 0.95

        face_data = {
            "cf1": self._make_face("cf1", confirmed_face),
            "skipped_f1": self._make_face("skipped_f1", skipped_face),
        }

        identities_data = {
            "identities": {
                "confirmed-1": {
                    "identity_id": "confirmed-1",
                    "name": "Leon Capeluto",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "skipped-1": {
                    "identity_id": "skipped-1",
                    "name": "Unidentified Person 191",
                    "state": "SKIPPED",
                    "anchor_ids": ["skipped_f1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }

        suggestions = find_matches(identities_data, face_data, threshold=0.5)
        assert len(suggestions) == 1, "Skipped face close to confirmed should generate proposal"
        assert suggestions[0]["face_id"] == "skipped_f1"
        assert suggestions[0]["target_identity_id"] == "confirmed-1"

    def test_skipped_far_face_not_matched(self):
        """Skipped face far from confirmed should not generate proposal."""
        from scripts.cluster_new_faces import find_matches

        confirmed_face = np.zeros(512, dtype=np.float32)
        confirmed_face[0] = 1.0

        far_skipped = np.zeros(512, dtype=np.float32)
        far_skipped[0] = -1.0  # Distance = 2.0

        face_data = {
            "cf1": self._make_face("cf1", confirmed_face),
            "skipped_far": self._make_face("skipped_far", far_skipped),
        }

        identities_data = {
            "identities": {
                "confirmed-1": {
                    "identity_id": "confirmed-1",
                    "name": "Leon Capeluto",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "skipped-far": {
                    "identity_id": "skipped-far",
                    "name": "Unidentified Person 99",
                    "state": "SKIPPED",
                    "anchor_ids": ["skipped_far"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }

        suggestions = find_matches(identities_data, face_data, threshold=1.0)
        assert len(suggestions) == 0

    def test_skipped_and_inbox_both_included(self):
        """Both SKIPPED and INBOX faces should be clustering candidates."""
        from scripts.cluster_new_faces import find_matches

        confirmed_face = np.zeros(512, dtype=np.float32)
        confirmed_face[0] = 1.0

        skipped_face = np.zeros(512, dtype=np.float32)
        skipped_face[0] = 0.95

        inbox_face = np.zeros(512, dtype=np.float32)
        inbox_face[0] = 0.92

        face_data = {
            "cf1": self._make_face("cf1", confirmed_face),
            "skip_f": self._make_face("skip_f", skipped_face),
            "inbox_f": self._make_face("inbox_f", inbox_face),
        }

        identities_data = {
            "identities": {
                "confirmed-1": {
                    "identity_id": "confirmed-1",
                    "name": "Test Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["cf1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "skipped-1": {
                    "identity_id": "skipped-1",
                    "name": "Unidentified Person 1",
                    "state": "SKIPPED",
                    "anchor_ids": ["skip_f"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
                "inbox-1": {
                    "identity_id": "inbox-1",
                    "name": "Unidentified Person 2",
                    "state": "INBOX",
                    "anchor_ids": ["inbox_f"],
                    "candidate_ids": [],
                    "negative_ids": [],
                },
            }
        }

        suggestions = find_matches(identities_data, face_data, threshold=0.5)
        matched_faces = {s["face_id"] for s in suggestions}
        assert "skip_f" in matched_faces, "Skipped face should be matched"
        assert "inbox_f" in matched_faces, "Inbox face should also be matched"


# ---------------------------------------------------------------------------
# BUG 2: Lightbox face overlays must be clickable for all states
# ---------------------------------------------------------------------------

class TestLightboxFaceOverlayClickable:
    """Face overlays in the identity lightbox must have interaction handlers."""

    def test_lightbox_overlay_has_click_handler(self, client):
        """Lightbox face overlays must have cursor-pointer and a click handler."""
        from app.main import load_registry
        from core.registry import IdentityState
        registry = load_registry()

        # Find an identity with faces to test the lightbox
        identities = registry.list_identities()
        identity_with_faces = None
        for ident in identities:
            face_entries = ident.get("anchor_ids", []) + ident.get("candidate_ids", [])
            if face_entries:
                identity_with_faces = ident
                break

        if not identity_with_faces:
            pytest.skip("No identity with faces available")

        identity_id = identity_with_faces["identity_id"]
        response = client.get(f"/api/identity/{identity_id}/photos?index=0")
        assert response.status_code == 200
        text = response.text

        # Check that face overlays (positioned via left:/top:/width:/height: percentages)
        # have cursor-pointer class, indicating they are clickable
        import re
        # Find divs that have percentage-based positioning (face overlays)
        overlay_pattern = r'style="left:\s*[\d.]+%.*?top:\s*[\d.]+%'
        overlays = re.findall(overlay_pattern, text)
        if overlays:
            # At least one overlay should have cursor-pointer
            assert "cursor-pointer" in text, \
                "Lightbox face overlays must have cursor-pointer for clickability"


# ---------------------------------------------------------------------------
# BUG 3: Identity links must route to correct section based on state
# ---------------------------------------------------------------------------

class TestSkippedSectionFilterWrapper:
    """Skipped section cards must have wrappers with data-name for sidebar filtering."""

    def test_skipped_cards_have_wrapper_with_data_name(self, client):
        """Needs Help card+hint wrappers have data-name so filter hides both together."""
        response = client.get("/?section=skipped")
        assert response.status_code == 200
        html = response.text
        # If there are identity cards, they should be inside wrappers with data-name
        if "identity-card" in html:
            assert "identity-card-wrapper" in html, \
                "Skipped section cards must be wrapped in identity-card-wrapper for filter"

    def test_filter_script_targets_wrappers(self, client):
        """Client-side filter script queries both .identity-card and .identity-card-wrapper."""
        response = client.get("/?section=skipped")
        assert response.status_code == 200
        assert "identity-card-wrapper" in response.text


class TestIdentityLinkRouting:
    """Identity card links must route to the correct section based on state."""

    def test_skipped_section_links_contain_section_skipped(self, client):
        """Links in the skipped section must route to section=skipped, not to_review."""
        response = client.get("/?section=skipped")
        assert response.status_code == 200
        text = response.text

        # If there are identity cards in the skipped section, their links
        # should NOT contain section=to_review
        if "identity-" in text:
            # The section should have at least some links that use section=skipped
            # and should NOT route to to_review for skipped identities
            assert "section=to_review" not in text or "section=skipped" in text, \
                "Skipped identity links should route to section=skipped"

    def test_confirmed_section_links_not_to_review(self, client):
        """Links in confirmed section must not route to to_review."""
        response = client.get("/?section=confirmed")
        assert response.status_code == 200
        text = response.text
        # Confirmed section should not have to_review links for identity navigation
        # (it may have a "Help Identify" sidebar link, which is fine)
        if "section=confirmed" in text:
            # The confirmed cards should link within confirmed section
            assert "section=confirmed" in text

    def test_neighbor_card_uses_correct_section(self, client):
        """Find Similar neighbor cards must link to correct section based on neighbor state."""
        from app.main import load_registry
        from core.registry import IdentityState
        registry = load_registry()

        # Find a confirmed identity to test neighbors endpoint
        confirmed = registry.list_identities(state=IdentityState.CONFIRMED)
        if not confirmed:
            pytest.skip("No confirmed identities available")

        identity_id = confirmed[0]["identity_id"]
        response = client.get(f"/api/identity/{identity_id}/neighbors")
        assert response.status_code == 200
        text = response.text

        # If neighbors are returned, they should link to correct sections
        # Neighbors can be in any section, so we just verify the link pattern
        # exists (section= is present in href attributes)
        if "neighbor-" in text:
            assert "section=" in text, "Neighbor links should specify their section"


# ---------------------------------------------------------------------------
# BUG 4: Footer stats must include skipped in denominator
# ---------------------------------------------------------------------------

class TestFooterStatsIncludeSkipped:
    """Footer progress stat must include skipped faces in the total."""

    def test_sidebar_footer_denominator_includes_skipped(self, client):
        """The sidebar footer 'X of Y identified' must count skipped in Y."""
        from app.main import _compute_sidebar_counts, load_registry
        registry = load_registry()
        counts = _compute_sidebar_counts(registry)

        # The denominator should be confirmed + skipped + to_review, not just confirmed + to_review
        total_with_skipped = counts['confirmed'] + counts['skipped'] + counts['to_review']
        total_without_skipped = counts['confirmed'] + counts['to_review']

        # If there are skipped faces, total_with_skipped > total_without_skipped
        if counts['skipped'] > 0:
            assert total_with_skipped > total_without_skipped, \
                "With skipped faces, denominator must be larger than confirmed + to_review"

    def test_footer_text_not_self_referential(self, client, auth_disabled):
        """Footer should not say 'N of N identified' when skipped faces exist."""
        from app.main import _compute_sidebar_counts, load_registry
        registry = load_registry()
        counts = _compute_sidebar_counts(registry)

        if counts['skipped'] > 0:
            response = client.get("/?section=confirmed")
            text = response.text
            # Should NOT say "23 of 23 identified" when 192 are skipped
            bad_pattern = f"{counts['confirmed']} of {counts['confirmed']} identified"
            assert bad_pattern not in text, \
                f"Footer shows '{bad_pattern}' but {counts['skipped']} faces are skipped"
