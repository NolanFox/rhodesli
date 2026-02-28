"""
Tests for Session 70 UX Fixes.

Covers:
- #3 (MEDIUM): ML confidence banner uses user-friendly vocabulary
- #4 (MEDIUM): Active tab styling in dark theme
- #5 (MEDIUM): Summary bar has visual separation from card below
- #8 (UX-110): Discovery card identity names max-w increased
- #9 (UX-111): Discovery confidence badge has tooltip
- #10 (UX-112): Confirm button truncates long names
- #11 (UX-113): Discovery empty state message
- UX-104: Compare Selected Faces button disabled state
- UX-105: Help Identify CTA for all-unidentified photos
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_identity(identity_id, name, state, anchor_ids=None, candidate_ids=None, negative_ids=None):
    """Build a minimal identity dict matching the schema."""
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": anchor_ids or [],
        "candidate_ids": candidate_ids or [],
        "negative_ids": negative_ids or [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _make_registry_mock(identities):
    """Build a registry mock from a list of identity dicts."""
    registry = MagicMock()

    def list_identities(state=None):
        if state is None:
            return identities
        return [i for i in identities if i["state"] == state.value]

    def get_identity(iid):
        for i in identities:
            if i["identity_id"] == iid:
                return i
        raise KeyError(iid)

    registry.list_identities = list_identities
    registry.get_identity = get_identity
    registry.list_proposed_matches = MagicMock(return_value=[])
    registry._identities = {i["identity_id"]: i for i in identities}
    return registry


# ---------------------------------------------------------------------------
# Test: #3 — ML confidence banner uses user-friendly vocabulary
# ---------------------------------------------------------------------------

class TestMLConfidenceBannerVocabulary:
    """Issue #3: ML confidence banner should use user-friendly labels instead of system vocabulary."""

    def test_banner_uses_friendly_label_not_system_code(self, tmp_path):
        """_proposal_banner renders 'Strong match' etc., not 'ML MATCH: VERY HIGH'."""
        proposals = {
            "proposals": [
                {
                    "source_identity_id": "test-src",
                    "target_identity_id": "test-tgt",
                    "target_name": "Rica Moussafer",
                    "target_identity_name": "Rica Moussafer",
                    "distance": 0.5,
                    "confidence": "VERY HIGH",
                }
            ]
        }
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(proposals, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _proposal_banner
            banner = _proposal_banner("test-src")
            assert banner is not None
            banner_html = str(banner)
            # Should use user-friendly label
            assert "Strong match" in banner_html
            # Should NOT contain system vocabulary like "ML MATCH:"
            assert "ML Match" not in banner_html
            assert "ML MATCH" not in banner_html

    def test_banner_moderate_uses_possible_match(self, tmp_path):
        """MODERATE confidence renders as 'Possible match'."""
        proposals = {
            "proposals": [
                {
                    "source_identity_id": "test-src",
                    "target_identity_id": "test-tgt",
                    "target_name": "Unknown Person",
                    "target_identity_name": "Unknown Person",
                    "distance": 1.1,
                    "confidence": "MODERATE",
                }
            ]
        }
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(proposals, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _proposal_banner
            banner = _proposal_banner("test-src")
            assert banner is not None
            banner_html = str(banner)
            assert "Possible match" in banner_html

    def test_banner_high_uses_good_match(self, tmp_path):
        """HIGH confidence renders as 'Good match'."""
        proposals = {
            "proposals": [
                {
                    "source_identity_id": "test-src",
                    "target_identity_id": "test-tgt",
                    "target_name": "Test Person",
                    "target_identity_name": "Test Person",
                    "distance": 0.9,
                    "confidence": "HIGH",
                }
            ]
        }
        proposals_path = tmp_path / "proposals.json"
        with open(proposals_path, "w") as f:
            json.dump(proposals, f)

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._proposals_cache", None):
            from app.main import _proposal_banner
            banner = _proposal_banner("test-src")
            assert banner is not None
            banner_html = str(banner)
            assert "Good match" in banner_html

    def test_confidence_label_dict_has_all_tiers(self):
        """_CONFIDENCE_LABEL has entries for all confidence tiers."""
        from app.main import _CONFIDENCE_LABEL
        assert "VERY HIGH" in _CONFIDENCE_LABEL
        assert "HIGH" in _CONFIDENCE_LABEL
        assert "MODERATE" in _CONFIDENCE_LABEL
        assert "LOW" in _CONFIDENCE_LABEL


# ---------------------------------------------------------------------------
# Test: #4 — Active tab styling in dark theme
# ---------------------------------------------------------------------------

class TestActiveTabStyling:
    """Issue #4: Active tab must be visually distinct in dark theme."""

    def test_section_header_active_focus_tab_has_white_bg(self):
        """Active Focus tab uses bg-white for high contrast."""
        from app.main import section_header
        from fastcore.xml import to_xml

        html = to_xml(section_header("To Review", "50 faces to review",
                                     view_mode="focus", section="to_review"))
        # Active tab has bg-white
        assert "bg-white" in html
        # Active tab has shadow for emphasis
        assert "shadow-md" in html

    def test_section_header_inactive_tab_has_muted_color(self):
        """Inactive tabs use muted slate color."""
        from app.main import section_header
        from fastcore.xml import to_xml

        html = to_xml(section_header("To Review", "50 faces to review",
                                     view_mode="focus", section="to_review"))
        # The "View All" and "Match" tabs (inactive) should have the muted class
        assert "text-slate-400" in html

    def test_section_header_match_tab_active_has_amber(self):
        """Active Match tab uses bg-amber-500 for visual distinction."""
        from app.main import section_header
        from fastcore.xml import to_xml

        html = to_xml(section_header("To Review", "50 faces to review",
                                     view_mode="match", section="to_review"))
        assert "bg-amber-500" in html
        assert "shadow-amber" in html

    def test_section_header_tabs_have_transition(self):
        """All tabs have transition-colors for smooth hover effect."""
        from app.main import section_header
        from fastcore.xml import to_xml

        html = to_xml(section_header("To Review", "50 faces to review",
                                     view_mode="focus", section="to_review"))
        assert "transition-colors" in html

    def test_skipped_section_tabs_have_active_styling(self):
        """Skipped section tabs also get the updated active styling."""
        from app.main import section_header
        from fastcore.xml import to_xml

        html = to_xml(section_header("Help Identify", "10 faces",
                                     view_mode="focus", section="skipped"))
        assert "bg-white" in html
        assert "shadow-md" in html


# ---------------------------------------------------------------------------
# Test: #5 — Summary bar has visual separation
# ---------------------------------------------------------------------------

class TestTriageBarSeparation:
    """Issue #5: Summary bar must have visual separation from card below."""

    def test_triage_bar_has_border_bottom(self):
        """_build_triage_bar renders a border-b for visual separation."""
        from app.main import _build_triage_bar
        from fastcore.xml import to_xml

        to_review = [
            _make_identity("id1", "Person A", "INBOX", candidate_ids=["f1"]),
        ]

        # Need to mock _compute_triage_counts to control the output
        mock_counts = {
            "ready_to_confirm": 10,
            "rediscovered": 5,
            "unmatched": 30,
        }
        with patch("app.main._compute_triage_counts", return_value=mock_counts):
            bar = _build_triage_bar(to_review, "focus")
            assert bar is not None
            html = to_xml(bar)
            assert "border-b" in html

    def test_triage_bar_has_padding_bottom(self):
        """_build_triage_bar renders pb-4 for spacing."""
        from app.main import _build_triage_bar
        from fastcore.xml import to_xml

        to_review = [
            _make_identity("id1", "Person A", "INBOX", candidate_ids=["f1"]),
        ]

        mock_counts = {
            "ready_to_confirm": 10,
            "rediscovered": 0,
            "unmatched": 30,
        }
        with patch("app.main._compute_triage_counts", return_value=mock_counts):
            bar = _build_triage_bar(to_review, "focus")
            assert bar is not None
            html = to_xml(bar)
            assert "pb-4" in html

    def test_triage_bar_has_mb_6_not_mb_4(self):
        """_build_triage_bar uses mb-6 for increased spacing."""
        from app.main import _build_triage_bar
        from fastcore.xml import to_xml

        to_review = [
            _make_identity("id1", "Person A", "INBOX", candidate_ids=["f1"]),
        ]

        mock_counts = {
            "ready_to_confirm": 10,
            "rediscovered": 0,
            "unmatched": 30,
        }
        with patch("app.main._compute_triage_counts", return_value=mock_counts):
            bar = _build_triage_bar(to_review, "focus")
            assert bar is not None
            html = to_xml(bar)
            assert "mb-6" in html


# ---------------------------------------------------------------------------
# Test: #8 (UX-110) — Discovery card name width increased
# ---------------------------------------------------------------------------

class TestDiscoveryCardNameWidth:
    """UX-110: Discovery card identity names max-w increased from 120px to 200px."""

    def test_discovery_card_names_use_200px_max(self):
        """Discovery cards render name elements with max-w-[200px]."""
        from app.main import _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Estrella Matsliach Moussafer", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Victoria Capeluto Benatar", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        batch_result = {"inbox1": (0.5, "conf1", "Victoria Capeluto Benatar")}

        with patch("app.main._get_identities_with_proposals", return_value=set()), \
             patch("app.main.get_face_data", return_value={}), \
             patch("core.neighbors.batch_best_neighbor_distances", return_value=batch_result), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._check_admin", return_value=None):

            from app.main import app
            client = TestClient(app)
            response = client.get("/api/discoveries")
            html = response.text

            # Should use 200px, not 120px
            assert "max-w-[200px]" in html
            assert "max-w-[120px]" not in html

    def test_discovery_card_names_have_tooltip(self):
        """Discovery card names have title attribute as tooltip."""
        from app.main import _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Estrella Matsliach", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Victoria Capeluto", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        batch_result = {"inbox1": (0.5, "conf1", "Victoria Capeluto")}

        with patch("app.main._get_identities_with_proposals", return_value=set()), \
             patch("app.main.get_face_data", return_value={}), \
             patch("core.neighbors.batch_best_neighbor_distances", return_value=batch_result), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._check_admin", return_value=None):

            from app.main import app
            client = TestClient(app)
            response = client.get("/api/discoveries")
            html = response.text

            # Both source and target names should have title attributes
            assert 'title="Estrella Matsliach"' in html
            assert 'title="Victoria Capeluto"' in html


# ---------------------------------------------------------------------------
# Test: #9 (UX-111) — Discovery confidence badge has tooltip
# ---------------------------------------------------------------------------

class TestDiscoveryConfidenceBadgeTooltip:
    """UX-111: Discovery match confidence badge should have a tooltip explaining the match (AD-173)."""

    def test_confidence_badge_has_title(self):
        """Confidence badge has title with distance and tier for admin debugging."""
        from app.main import _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Known", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        batch_result = {"inbox1": (0.5, "conf1", "Known")}

        with patch("app.main._get_identities_with_proposals", return_value=set()), \
             patch("app.main.get_face_data", return_value={}), \
             patch("core.neighbors.batch_best_neighbor_distances", return_value=batch_result), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._check_admin", return_value=None), \
             patch("app.main.get_photo_id_for_face", return_value=None):

            from app.main import app
            client = TestClient(app)
            response = client.get("/api/discoveries")
            html = response.text

            # Badge shows confidence label, not percentage (AD-173)
            assert "Strong match" in html
            # Admin tooltip shows raw distance for debugging
            assert "Distance: 0.50" in html
            assert "VERY HIGH" in html


# ---------------------------------------------------------------------------
# Test: #10 (UX-112) — Confirm button truncates long names
# ---------------------------------------------------------------------------

class TestConfirmButtonTruncation:
    """UX-112: 'Confirm as {name}' button must truncate long names."""

    def test_confirm_button_has_truncate(self):
        """Confirm button span has truncate class for long names."""
        from app.main import _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Victoria Capeluto Benatar Long Name Here", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        batch_result = {"inbox1": (0.5, "conf1", "Victoria Capeluto Benatar Long Name Here")}

        with patch("app.main._get_identities_with_proposals", return_value=set()), \
             patch("app.main.get_face_data", return_value={}), \
             patch("core.neighbors.batch_best_neighbor_distances", return_value=batch_result), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._check_admin", return_value=None):

            from app.main import app
            client = TestClient(app)
            response = client.get("/api/discoveries")
            html = response.text

            # Confirm button span should have truncate and max-w
            assert "truncate" in html
            assert "Confirm as Victoria Capeluto Benatar Long Name Here" in html
            # Button itself should have max-w-full
            assert "max-w-full" in html

    def test_confirm_button_has_title_tooltip(self):
        """Confirm button has title attribute for full name on hover."""
        from app.main import _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("inbox1", "Unknown", "INBOX", candidate_ids=["face_inbox1"]),
            _make_identity("conf1", "Test Person", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        batch_result = {"inbox1": (0.5, "conf1", "Test Person")}

        with patch("app.main._get_identities_with_proposals", return_value=set()), \
             patch("app.main.get_face_data", return_value={}), \
             patch("core.neighbors.batch_best_neighbor_distances", return_value=batch_result), \
             patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._check_admin", return_value=None):

            from app.main import app
            client = TestClient(app)
            response = client.get("/api/discoveries")
            html = response.text

            assert 'title="Confirm this face as Test Person"' in html


# ---------------------------------------------------------------------------
# Test: #11 (UX-113) — Discovery empty state message
# ---------------------------------------------------------------------------

class TestDiscoveryEmptyState:
    """UX-113: Discovery empty state should show a clear message, not blank div."""

    def test_empty_state_shows_reviewed_message(self):
        """Empty discoveries shows 'All discoveries reviewed!' message."""
        from app.main import _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._get_pending_discovery_entries", return_value=([], [])), \
             patch("app.main._check_admin", return_value=None):

            from app.main import app
            client = TestClient(app)
            response = client.get("/api/discoveries")
            html = response.text

            assert "All discoveries reviewed!" in html

    def test_empty_state_has_testid(self):
        """Empty state div has data-testid for browser testing."""
        from app.main import _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._get_pending_discovery_entries", return_value=([], [])), \
             patch("app.main._check_admin", return_value=None):

            from app.main import app
            client = TestClient(app)
            response = client.get("/api/discoveries")
            html = response.text

            assert "discoveries-empty-state" in html

    def test_empty_state_has_guidance_text(self):
        """Empty state explains when new discoveries will appear."""
        from app.main import _invalidate_discovery_cache

        _invalidate_discovery_cache()

        identities = [
            _make_identity("conf1", "Known Person", "CONFIRMED", anchor_ids=["face_conf1"]),
        ]
        registry = _make_registry_mock(identities)

        with patch("app.main.load_registry", return_value=registry), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._get_pending_discovery_entries", return_value=([], [])), \
             patch("app.main._check_admin", return_value=None):

            from app.main import app
            client = TestClient(app)
            response = client.get("/api/discoveries")
            html = response.text

            assert "New discoveries will appear here" in html


# ---------------------------------------------------------------------------
# Test: UX-104 — Compare Selected Faces button disabled state
# ---------------------------------------------------------------------------

class TestCompareSelectedFacesDisabled:
    """UX-104: Compare Selected Faces button should be disabled until 2+ faces selected."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_pair_compare_button_starts_disabled(self, client):
        """The pair compare page button starts in disabled state."""
        response = client.get("/compare/pair")
        assert response.status_code == 200
        html = response.text
        assert 'id="pair-compare-btn"' in html
        # Button should be disabled initially
        assert "disabled" in html
        assert "opacity-50" in html
        assert "cursor-not-allowed" in html

    def test_pair_compare_button_text_is_compare_selected(self, client):
        """Button text is 'Compare Selected Faces'."""
        response = client.get("/compare/pair")
        html = response.text
        assert "Compare Selected Faces" in html

    def test_pair_compare_js_enables_button_on_selection(self, client):
        """JavaScript enables button when both panels have selections."""
        response = client.get("/compare/pair")
        html = response.text
        # The JS should remove opacity-50 and cursor-not-allowed on selection
        assert "btn.disabled = false" in html
        assert "opacity-50" in html  # Present in initial state
        assert "cursor-not-allowed" in html  # Present in initial state


# ---------------------------------------------------------------------------
# Test: UX-105 — Help Identify CTA for all-unidentified photos
# ---------------------------------------------------------------------------

class TestHelpIdentifyCTA:
    """UX-105: More prominent CTA when ALL faces in a photo are unidentified."""

    def test_help_identify_cta_testid_exists_in_source(self):
        """Photo page source contains the help-identify-cta testid."""
        import app.main as main_module
        import inspect
        source_file = inspect.getfile(main_module)
        with open(source_file) as f:
            source_code = f.read()
        assert "help-identify-cta" in source_code
        assert "help-identify-section" in source_code
        assert "Nobody in this photo has been identified yet" in source_code

    def test_help_identify_prominent_when_all_unidentified(self):
        """When identified_count == 0, the CTA uses amber/prominent styling."""
        import app.main as main_module
        import inspect
        source_file = inspect.getfile(main_module)
        with open(source_file) as f:
            source_code = f.read()

        # The amber prominent styling should appear when identified_count == 0
        assert "bg-amber-600" in source_code
        assert "bg-amber-950/10" in source_code
        assert "border-amber-800/30" in source_code
        # The standard styling uses indigo (for mixed identified/unidentified)
        assert "bg-indigo-600" in source_code

    def test_help_identify_cta_has_awaiting_count(self):
        """When all faces unidentified, CTA shows count of people awaiting identification."""
        import app.main as main_module
        import inspect
        source_file = inspect.getfile(main_module)
        with open(source_file) as f:
            source_code = f.read()

        assert "awaiting identification" in source_code


# ---------------------------------------------------------------------------
# Test: _CONFIDENCE_LABEL mapping consistency
# ---------------------------------------------------------------------------

class TestConfidenceLabelMapping:
    """Verify that _CONFIDENCE_LABEL, _CONFIDENCE_RING, and _CONFIDENCE_COLOR are consistent."""

    def test_all_dicts_have_same_keys(self):
        """All confidence dicts cover the same tier set."""
        from app.main import _CONFIDENCE_LABEL, _CONFIDENCE_RING, _CONFIDENCE_COLOR
        # LABEL has all 4 tiers
        assert set(_CONFIDENCE_LABEL.keys()) == {"VERY HIGH", "HIGH", "MODERATE", "LOW"}
        # RING and COLOR have the top 3 (LOW may not have ring/color)
        for key in ["VERY HIGH", "HIGH", "MODERATE"]:
            assert key in _CONFIDENCE_RING
            assert key in _CONFIDENCE_COLOR

    def test_confidence_labels_are_human_readable(self):
        """Each label is a user-friendly phrase, not a system code."""
        from app.main import _CONFIDENCE_LABEL
        for key, label in _CONFIDENCE_LABEL.items():
            # Should contain lowercase words (readable prose)
            assert label[0].isupper(), f"Label for {key} should be capitalized"
            assert "match" in label.lower(), f"Label for {key} should contain 'match'"
            # Should NOT be the same as the key
            assert label != key, f"Label for {key} should not be the raw tier code"
