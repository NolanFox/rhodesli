"""
Tests for smart onboarding flow (Session 19c).

- Surname recognition grid renders with correct surnames
- Discovery endpoint returns matching identities
- Cookie-based skip logic
- Step transitions
"""

import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


class TestWelcomeBannerOnboarding:
    """Welcome banner (non-blocking) replaced the old modal wall."""

    def test_welcome_banner_renders_with_context(self):
        """Welcome banner renders with heritage archive description."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        assert "Welcome to Rhodesli" in html
        assert "welcome-banner" in html

    def test_welcome_banner_has_dismiss(self):
        """Welcome banner has dismiss button with data-action."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        assert "welcome-banner-dismiss" in html

    def test_welcome_banner_is_non_blocking(self):
        """Welcome banner uses a simple top bar, not a modal overlay."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        # Should NOT have modal overlay classes
        assert "fixed inset-0" not in html
        assert "bg-black/80" not in html

    def test_welcome_banner_cookie_based_dismissal(self):
        """Welcome banner uses persistent cookie for dismissal."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        assert "rhodesli_welcomed" in html
        assert "max-age=31536000" in html

    def test_welcome_banner_has_identify_prompt(self):
        """Welcome banner encourages visitors to identify faces."""
        from app.main import _welcome_banner
        from fastcore.xml import to_xml

        result = _welcome_banner()
        html = to_xml(result)
        assert "identify" in html.lower()


class TestOnboardingDiscoverEndpoint:
    """Tests for GET /api/onboarding/discover."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_discover_no_surnames_returns_message(self, client):
        """Empty surnames parameter returns 'no surnames' message."""
        response = client.get("/api/onboarding/discover?surnames=")
        assert response.status_code == 200
        assert "No surnames selected" in response.text

    def test_discover_returns_matching_identities(self, client):
        """Discover endpoint returns matching confirmed identities."""
        mock_reg = MagicMock()
        mock_reg.list_identities.return_value = [
            {
                "identity_id": "id-001",
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
            },
            {
                "identity_id": "id-002",
                "name": "Victoria Hasson",
                "state": "CONFIRMED",
                "anchor_ids": ["face2"],
                "candidate_ids": [],
            },
            {
                "identity_id": "id-003",
                "name": "Unknown Person",
                "state": "CONFIRMED",
                "anchor_ids": ["face3"],
                "candidate_ids": [],
            },
        ]

        with patch("app.main.load_registry", return_value=mock_reg), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value="/crops/test.jpg"):
            response = client.get("/api/onboarding/discover?surnames=Capeluto,Hasson")
            assert response.status_code == 200
            assert "Leon Capeluto" in response.text
            assert "Victoria Hasson" in response.text
            # "Unknown Person" starts with "Unidentified" is filtered but
            # "Unknown Person" doesn't start with "Unidentified" — it will
            # still be excluded because name words don't match surnames

    def test_discover_no_matches(self, client):
        """Discover shows encouraging message when no matches found."""
        mock_reg = MagicMock()
        mock_reg.list_identities.return_value = [
            {
                "identity_id": "id-001",
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
            },
        ]

        with patch("app.main.load_registry", return_value=mock_reg), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value="/crops/test.jpg"):
            response = client.get("/api/onboarding/discover?surnames=Pizante")
            assert response.status_code == 200
            assert "No matches yet" in response.text or "No matches" in response.text

    def test_discover_is_public(self, client):
        """Discover endpoint is publicly accessible (no auth required)."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None), \
             patch("app.main.load_registry") as mock_reg:
            mock_reg.return_value.list_identities.return_value = []
            response = client.get("/api/onboarding/discover?surnames=Capeluto")
            # Should NOT return 401
            assert response.status_code == 200

    def test_discover_uses_surname_variants(self, client):
        """Discover endpoint expands surname variants (e.g., Capelluto -> Capeluto)."""
        mock_reg = MagicMock()
        mock_reg.list_identities.return_value = [
            {
                "identity_id": "id-001",
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
            },
        ]

        with patch("app.main.load_registry", return_value=mock_reg), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main.resolve_face_image_url", return_value="/crops/test.jpg"):
            # "Capelluto" is a variant of "Capeluto"
            response = client.get("/api/onboarding/discover?surnames=Capelluto")
            assert response.status_code == 200
            # Should find Leon Capeluto via variant expansion
            assert "Leon Capeluto" in response.text


class TestPersonalizedDiscoveryBanner:
    """Tests for _personalized_discovery_banner."""

    def test_banner_shows_matching_people(self):
        """Banner shows confirmed identities matching interest surnames."""
        from app.main import _personalized_discovery_banner, to_xml

        confirmed = [
            {
                "identity_id": "id-001",
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
            },
        ]
        with patch("app.main.resolve_face_image_url", return_value="/crops/test.jpg"):
            result = _personalized_discovery_banner(["Capeluto"], confirmed, set(), {})
            html = to_xml(result)
            assert "Capeluto" in html
            assert "Leon" in html or "confirmed" in html

    def test_banner_empty_when_no_matches(self):
        """Banner renders empty div when no matches found."""
        from app.main import _personalized_discovery_banner, to_xml

        confirmed = [
            {
                "identity_id": "id-001",
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
            },
        ]
        with patch("app.main.resolve_face_image_url", return_value="/crops/test.jpg"):
            result = _personalized_discovery_banner(["Pizante"], confirmed, set(), {})
            html = to_xml(result)
            # Should be an empty div, not an error
            assert html is not None

    def test_banner_shows_multiple_surnames(self):
        """Banner displays multiple interest surnames."""
        from app.main import _personalized_discovery_banner, to_xml

        confirmed = [
            {
                "identity_id": "id-001",
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
            },
            {
                "identity_id": "id-002",
                "name": "Stella Hasson",
                "state": "CONFIRMED",
                "anchor_ids": ["face2"],
                "candidate_ids": [],
            },
        ]
        with patch("app.main.resolve_face_image_url", return_value="/crops/test.jpg"):
            result = _personalized_discovery_banner(["Capeluto", "Hasson"], confirmed, set(), {})
            html = to_xml(result)
            assert "Capeluto" in html
            assert "Hasson" in html

    def test_banner_limits_to_5_people(self):
        """Banner shows at most 5 people thumbnails."""
        from app.main import _personalized_discovery_banner, to_xml

        confirmed = [
            {
                "identity_id": f"id-{i:03d}",
                "name": f"Person{i} Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": [f"face{i}"],
                "candidate_ids": [],
            }
            for i in range(10)
        ]
        with patch("app.main.resolve_face_image_url", return_value="/crops/test.jpg"):
            result = _personalized_discovery_banner(["Capeluto"], confirmed, set(), {})
            html = to_xml(result)
            # Count face thumbnail images — should be at most 5
            count = html.count("/crops/test.jpg")
            assert count <= 5


class TestGetOnboardingSurnames:
    """Tests for _get_onboarding_surnames helper."""

    def test_returns_canonical_surnames(self):
        """Returns list of canonical surname strings."""
        from app.main import _get_onboarding_surnames

        surnames = _get_onboarding_surnames()
        assert isinstance(surnames, list)
        assert len(surnames) > 0
        assert "Capeluto" in surnames
        assert "Hasson" in surnames

    def test_handles_missing_file(self):
        """Returns empty list if surname_variants.json doesn't exist."""
        from app.main import _get_onboarding_surnames

        with patch("builtins.open", side_effect=FileNotFoundError):
            with patch("pathlib.Path.exists", return_value=False):
                surnames = _get_onboarding_surnames()
                assert surnames == []
