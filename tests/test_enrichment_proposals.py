"""Tests for GEDCOM-enriched Gemini analysis proposals (Gatekeeper pattern).

Validates:
- Enrichment proposals display on photo page (admin-only)
- Gatekeeper stages proposals without auto-applying
- Accept updates date_labels and photo_locations
- Reject preserves original data
- Admin-only access control
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient
from fastcore.xml import to_xml


# --- Sample test data ---

SAMPLE_PROPOSAL_PENDING = {
    "status": "pending",
    "created_at": "2026-03-01T12:00:00+00:00",
    "old_location": {"place": "Miami, Florida", "confidence": "high"},
    "new_location": {
        "place": "Asheville, North Carolina",
        "confidence": "medium",
        "evidence": "GEDCOM records show family visits to Asheville, NC.",
    },
    "old_date": {"year": 1960, "decade": 1960, "confidence": "high"},
    "new_date": {
        "year": 1955,
        "decade": 1950,
        "confidence": "medium",
        "probable_range": [1953, 1958],
        "decade_probabilities": {"1950": 0.75, "1960": 0.25},
        "reasoning_summary": "GEDCOM data reveals family connections to Asheville.",
    },
    "scene_description": "Family gathering in a modest dining room.",
    "has_gedcom": True,
    "gedcom_value_assessment": "High",
    "cost": 0.0172,
    "location_changed": True,
    "date_changed": True,
    "confidence_improved": False,
    "reviewed_at": None,
    "reviewed_by": None,
}

SAMPLE_PROPOSAL_ACCEPTED = {
    **SAMPLE_PROPOSAL_PENDING,
    "status": "accepted",
    "reviewed_at": "2026-03-01T14:00:00+00:00",
    "reviewed_by": "admin",
}

SAMPLE_PROPOSAL_REJECTED = {
    **SAMPLE_PROPOSAL_PENDING,
    "status": "rejected",
    "reviewed_at": "2026-03-01T14:00:00+00:00",
    "reviewed_by": "admin",
}

TEST_PHOTO_ID = "inbox_staged-20260210-182610_7_596771420.719238"

SAMPLE_DATE_LABEL = {
    "photo_id": TEST_PHOTO_ID,
    "source": "gemini",
    "model": "gemini-3-flash-preview",
    "estimated_decade": 1960,
    "best_year_estimate": 1960,
    "confidence": "high",
    "probable_range": [1957, 1963],
    "location_estimate": "United States (likely Miami, Tampa, or New York City)",
}

SAMPLE_PHOTO_LOCATION = {
    "photo_id": TEST_PHOTO_ID,
    "lat": 25.7617,
    "lng": -80.1918,
    "location_name": "Miami, Florida",
    "location_key": "miami",
    "region": "United States",
    "location_estimate": "United States (likely Miami, Tampa, or New York City)",
    "confidence": "high",
}


class TestEnrichmentProposalDisplay:
    """Enrichment proposals are displayed on photo pages for admin review."""

    def test_gemini_results_displayed_on_photo_page(self):
        """Photo page shows enrichment proposal banner when admin views a photo with pending proposal."""
        from app.main import _build_enrichment_proposal_banner

        banner = _build_enrichment_proposal_banner(TEST_PHOTO_ID, SAMPLE_PROPOSAL_PENDING)
        html = to_xml(banner)

        # Check banner contains key elements
        assert "Enrichment Proposal" in html
        assert "Miami, Florida" in html
        assert "Asheville, North Carolina" in html
        assert "1960" in html
        assert "1955" in html
        assert "enrichment-accept" in html
        assert "enrichment-reject" in html
        assert "GEDCOM-enriched" in html
        assert "enrichment-proposal" in html  # data-testid

    def test_accepted_proposal_shows_green_banner(self):
        """Accepted proposals show a green confirmation banner without action buttons."""
        from app.main import _build_enrichment_proposal_banner

        banner = _build_enrichment_proposal_banner(TEST_PHOTO_ID, SAMPLE_PROPOSAL_ACCEPTED)
        html = to_xml(banner)

        assert "Accepted" in html
        assert "enrichment-accept" not in html  # No accept button
        assert "enrichment-reject" not in html  # No reject button

    def test_rejected_proposal_shows_red_banner(self):
        """Rejected proposals show a red banner without action buttons."""
        from app.main import _build_enrichment_proposal_banner

        banner = _build_enrichment_proposal_banner(TEST_PHOTO_ID, SAMPLE_PROPOSAL_REJECTED)
        html = to_xml(banner)

        assert "Rejected" in html
        assert "enrichment-accept" not in html
        assert "enrichment-reject" not in html

    def test_banner_shows_location_change_evidence(self):
        """Banner displays the evidence for location change."""
        from app.main import _build_enrichment_proposal_banner

        banner = _build_enrichment_proposal_banner(TEST_PHOTO_ID, SAMPLE_PROPOSAL_PENDING)
        html = to_xml(banner)

        assert "GEDCOM records show family visits to Asheville" in html
        assert "enrichment-evidence" in html

    def test_banner_shows_date_change(self):
        """Banner displays old and new date values."""
        from app.main import _build_enrichment_proposal_banner

        banner = _build_enrichment_proposal_banner(TEST_PHOTO_ID, SAMPLE_PROPOSAL_PENDING)
        html = to_xml(banner)

        assert "enrichment-date-change" in html

    def test_accepted_proposal_shows_enrichment_badge(self):
        """When a proposal is accepted, the location section shows a badge."""
        from app.main import _build_ai_analysis_section

        proposals = {TEST_PHOTO_ID: SAMPLE_PROPOSAL_ACCEPTED}
        labels = {TEST_PHOTO_ID: SAMPLE_DATE_LABEL}
        locations = {TEST_PHOTO_ID: SAMPLE_PHOTO_LOCATION}

        with patch("app.main._load_enrichment_proposals", return_value=proposals), \
             patch("app.main._load_date_labels", return_value=labels), \
             patch("app.main._load_photo_locations", return_value=locations), \
             patch("app.main._load_search_index", return_value=[]):
            result = _build_ai_analysis_section(TEST_PHOTO_ID, is_admin=True)

        if result:
            html = to_xml(result)
            assert "enrichment-accepted-badge" in html
            assert "Location updated" in html


class TestGatekeeperStaging:
    """Gemini enrichment results are staged as proposals, not auto-applied."""

    def test_gatekeeper_stages_gemini_proposals(self):
        """Enrichment proposals are stored with 'pending' status, not auto-applied."""
        from scripts.stage_enrichment_proposals import build_proposals
        from pathlib import Path
        import tempfile, os

        # Create mock enrichment results
        enrichment = {
            "batch_id": "test_batch",
            "model": "gemini-3.1-pro-preview",
            "variant": "curated",
            "total_cost": 0.01,
            "results": [
                {
                    "photo_id": TEST_PHOTO_ID,
                    "status": "success",
                    "has_gedcom": True,
                    "cost": 0.01,
                    "result": {
                        "date_estimation": {
                            "estimated_decade": 1950,
                            "best_year_estimate": 1955,
                            "confidence": "medium",
                            "probable_range": [1953, 1958],
                            "decade_probabilities": {"1950": 0.75},
                        },
                        "location": {
                            "place": "Asheville, North Carolina",
                            "confidence": "medium",
                            "evidence": "GEDCOM data",
                        },
                        "scene_description": "Family gathering",
                        "gedcom_value_assessment": "High",
                    },
                }
            ],
        }

        # Create temp data directory with existing labels
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            # Write date_labels.json
            date_labels = {
                "schema_version": 2,
                "labels": [SAMPLE_DATE_LABEL],
            }
            (data_dir / "date_labels.json").write_text(json.dumps(date_labels))

            # Write photo_locations.json
            photo_locations = {
                "version": 1,
                "photos": {TEST_PHOTO_ID: SAMPLE_PHOTO_LOCATION},
            }
            (data_dir / "photo_locations.json").write_text(json.dumps(photo_locations))

            # Write enrichment results
            enrichment_path = data_dir / "enrichment.json"
            enrichment_path.write_text(json.dumps(enrichment))

            proposals = build_proposals(str(enrichment_path), data_dir)

        # Verify proposals have pending status
        assert TEST_PHOTO_ID in proposals["proposals"]
        p = proposals["proposals"][TEST_PHOTO_ID]
        assert p["status"] == "pending"
        assert p["reviewed_at"] is None
        assert p["location_changed"] is True
        assert p["date_changed"] is True

    def test_no_proposal_when_nothing_changed(self):
        """If enrichment result matches existing data, no proposal is created."""
        from scripts.stage_enrichment_proposals import build_proposals
        from pathlib import Path
        import tempfile

        enrichment = {
            "batch_id": "test_batch",
            "model": "gemini-3.1-pro-preview",
            "variant": "curated",
            "total_cost": 0.01,
            "results": [
                {
                    "photo_id": TEST_PHOTO_ID,
                    "status": "success",
                    "has_gedcom": False,
                    "cost": 0.01,
                    "result": {
                        "date_estimation": {
                            "estimated_decade": 1960,
                            "best_year_estimate": 1960,
                            "confidence": "high",
                        },
                        "location": {
                            "place": "Miami, Florida",
                            "confidence": "high",
                            "evidence": "Same location",
                        },
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            date_labels = {"schema_version": 2, "labels": [SAMPLE_DATE_LABEL]}
            (data_dir / "date_labels.json").write_text(json.dumps(date_labels))
            photo_locations = {"version": 1, "photos": {TEST_PHOTO_ID: SAMPLE_PHOTO_LOCATION}}
            (data_dir / "photo_locations.json").write_text(json.dumps(photo_locations))
            enrichment_path = data_dir / "enrichment.json"
            enrichment_path.write_text(json.dumps(enrichment))

            proposals = build_proposals(str(enrichment_path), data_dir)

        assert TEST_PHOTO_ID not in proposals["proposals"]


class TestEnrichmentAccept:
    """Accept route updates data files with enriched values."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_enrichment_accept_updates_location(self, client):
        """Accept updates date_labels and photo_locations with new enrichment data."""
        proposals = {TEST_PHOTO_ID: dict(SAMPLE_PROPOSAL_PENDING)}
        labels = {TEST_PHOTO_ID: dict(SAMPLE_DATE_LABEL)}
        locations = {TEST_PHOTO_ID: dict(SAMPLE_PHOTO_LOCATION)}

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_enrichment_proposals", return_value=proposals), \
             patch("app.main._save_enrichment_proposals") as mock_save_proposals, \
             patch("app.main._load_date_labels", return_value=labels), \
             patch("app.main._save_date_label") as mock_save_label, \
             patch("app.main._load_photo_locations", return_value=locations), \
             patch("app.main._save_photo_locations") as mock_save_locations:

            response = client.post(f"/api/enrichment/accept/{TEST_PHOTO_ID}")
            assert response.status_code == 200

            # Verify proposal marked as accepted
            mock_save_proposals.assert_called_once()
            saved_proposals = mock_save_proposals.call_args[0][0]
            assert saved_proposals[TEST_PHOTO_ID]["status"] == "accepted"
            assert saved_proposals[TEST_PHOTO_ID]["reviewed_by"] == "admin"

            # Verify photo_locations was updated
            mock_save_locations.assert_called_once()
            saved_locs = mock_save_locations.call_args[0][0]
            assert saved_locs[TEST_PHOTO_ID]["location_name"] == "Asheville, North Carolina"
            assert saved_locs[TEST_PHOTO_ID]["lat"] == 35.5951
            assert saved_locs[TEST_PHOTO_ID]["lng"] == -82.5515

            # Verify date label was updated
            mock_save_label.assert_called_once()
            saved_label = mock_save_label.call_args[0][1]
            assert saved_label["best_year_estimate"] == 1955
            assert saved_label["estimated_decade"] == 1950

    def test_enrichment_accept_returns_updated_banner(self, client):
        """Accept returns an updated banner showing accepted status."""
        proposals = {TEST_PHOTO_ID: dict(SAMPLE_PROPOSAL_PENDING)}
        labels = {TEST_PHOTO_ID: dict(SAMPLE_DATE_LABEL)}
        locations = {TEST_PHOTO_ID: dict(SAMPLE_PHOTO_LOCATION)}

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_enrichment_proposals", return_value=proposals), \
             patch("app.main._save_enrichment_proposals"), \
             patch("app.main._load_date_labels", return_value=labels), \
             patch("app.main._save_date_label"), \
             patch("app.main._load_photo_locations", return_value=locations), \
             patch("app.main._save_photo_locations"):

            response = client.post(f"/api/enrichment/accept/{TEST_PHOTO_ID}")
            assert response.status_code == 200
            html = response.text
            assert "Accepted" in html


class TestEnrichmentReject:
    """Reject route preserves original data, only updates proposal status."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_enrichment_reject_preserves_original(self, client):
        """Reject marks proposal but does not modify date_labels or photo_locations."""
        proposals = {TEST_PHOTO_ID: dict(SAMPLE_PROPOSAL_PENDING)}

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_enrichment_proposals", return_value=proposals), \
             patch("app.main._save_enrichment_proposals") as mock_save, \
             patch("app.main._save_date_label") as mock_save_label, \
             patch("app.main._save_photo_locations") as mock_save_locations:

            response = client.post(f"/api/enrichment/reject/{TEST_PHOTO_ID}")
            assert response.status_code == 200

            # Verify proposal marked as rejected
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            assert saved[TEST_PHOTO_ID]["status"] == "rejected"
            assert saved[TEST_PHOTO_ID]["reviewed_by"] == "admin"

            # Verify NO data modifications
            mock_save_label.assert_not_called()
            mock_save_locations.assert_not_called()

    def test_enrichment_reject_returns_updated_banner(self, client):
        """Reject returns an updated banner showing rejected status."""
        proposals = {TEST_PHOTO_ID: dict(SAMPLE_PROPOSAL_PENDING)}

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_enrichment_proposals", return_value=proposals), \
             patch("app.main._save_enrichment_proposals"):

            response = client.post(f"/api/enrichment/reject/{TEST_PHOTO_ID}")
            assert response.status_code == 200
            html = response.text
            assert "Rejected" in html


class TestEnrichmentAdminOnly:
    """Non-admin users cannot see or act on enrichment proposals."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_enrichment_proposals_admin_only_accept(self, client):
        """Non-admin cannot accept enrichment proposals."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.post(f"/api/enrichment/accept/{TEST_PHOTO_ID}")
            assert response.status_code == 401

    def test_enrichment_proposals_admin_only_reject(self, client):
        """Non-admin cannot reject enrichment proposals."""
        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=None):
            response = client.post(f"/api/enrichment/reject/{TEST_PHOTO_ID}")
            assert response.status_code == 401

    def test_enrichment_proposals_non_admin_forbidden(self, client):
        """Logged-in non-admin gets 403."""
        mock_user = MagicMock()
        mock_user.is_admin = False
        mock_user.email = "user@example.com"

        with patch("app.main.is_auth_enabled", return_value=True), \
             patch("app.main.get_current_user", return_value=mock_user):
            response = client.post(f"/api/enrichment/accept/{TEST_PHOTO_ID}")
            assert response.status_code == 403

    def test_enrichment_banner_hidden_for_non_admin(self):
        """Non-admin users do not see the enrichment proposal banner."""
        from app.main import _build_ai_analysis_section

        proposals = {TEST_PHOTO_ID: SAMPLE_PROPOSAL_PENDING}
        labels = {TEST_PHOTO_ID: SAMPLE_DATE_LABEL}
        locations = {TEST_PHOTO_ID: SAMPLE_PHOTO_LOCATION}

        with patch("app.main._load_enrichment_proposals", return_value=proposals), \
             patch("app.main._load_date_labels", return_value=labels), \
             patch("app.main._load_photo_locations", return_value=locations), \
             patch("app.main._load_search_index", return_value=[]):
            result = _build_ai_analysis_section(TEST_PHOTO_ID, is_admin=False)

        if result:
            html = to_xml(result)
            # Non-admin should NOT see the enrichment proposal
            assert "enrichment-proposal" not in html
            assert "enrichment-accept" not in html


class TestEnrichmentEdgeCases:
    """Edge cases and error handling for enrichment proposals."""

    @pytest.fixture
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_accept_nonexistent_proposal(self, client):
        """Accept returns 404 for nonexistent photo_id."""
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_enrichment_proposals", return_value={}):
            response = client.post("/api/enrichment/accept/nonexistent-id")
            assert response.status_code == 404

    def test_reject_nonexistent_proposal(self, client):
        """Reject returns 404 for nonexistent photo_id."""
        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_enrichment_proposals", return_value={}):
            response = client.post("/api/enrichment/reject/nonexistent-id")
            assert response.status_code == 404

    def test_accept_already_reviewed_proposal(self, client):
        """Accept returns 400 for already-reviewed proposal."""
        proposals = {TEST_PHOTO_ID: dict(SAMPLE_PROPOSAL_ACCEPTED)}

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_enrichment_proposals", return_value=proposals):
            response = client.post(f"/api/enrichment/accept/{TEST_PHOTO_ID}")
            assert response.status_code == 400

    def test_reject_already_reviewed_proposal(self, client):
        """Reject returns 400 for already-reviewed proposal."""
        proposals = {TEST_PHOTO_ID: dict(SAMPLE_PROPOSAL_REJECTED)}

        with patch("app.main.is_auth_enabled", return_value=False), \
             patch("app.main._load_enrichment_proposals", return_value=proposals):
            response = client.post(f"/api/enrichment/reject/{TEST_PHOTO_ID}")
            assert response.status_code == 400

    def test_geocode_enrichment_location_known_cities(self):
        """Geocoding lookup returns correct coordinates for known cities."""
        from app.main import _geocode_enrichment_location

        # Asheville
        geo = _geocode_enrichment_location("Asheville, North Carolina")
        assert geo is not None
        assert geo["lat"] == 35.5951
        assert geo["name"] == "Asheville, North Carolina"

        # Tampa
        geo = _geocode_enrichment_location("Tampa, Florida")
        assert geo is not None
        assert geo["lat"] == 27.9506

        # Buenos Aires
        geo = _geocode_enrichment_location("Buenos Aires, Argentina")
        assert geo is not None
        assert geo["lat"] == -34.6037

        # Unknown city
        geo = _geocode_enrichment_location("Unknown City, Nowhere")
        assert geo is None


class TestStagingScript:
    """Tests for the staging script itself."""

    def test_build_proposals_schema(self):
        """build_proposals returns correct schema structure."""
        from scripts.stage_enrichment_proposals import build_proposals
        from pathlib import Path
        import tempfile

        enrichment = {
            "batch_id": "test",
            "model": "gemini-3.1-pro-preview",
            "variant": "curated",
            "total_cost": 0.01,
            "results": [
                {
                    "photo_id": TEST_PHOTO_ID,
                    "status": "success",
                    "has_gedcom": True,
                    "cost": 0.01,
                    "result": {
                        "date_estimation": {
                            "estimated_decade": 1950,
                            "best_year_estimate": 1955,
                            "confidence": "medium",
                        },
                        "location": {
                            "place": "Asheville, North Carolina",
                            "confidence": "medium",
                            "evidence": "test",
                        },
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            date_labels = {"schema_version": 2, "labels": [SAMPLE_DATE_LABEL]}
            (data_dir / "date_labels.json").write_text(json.dumps(date_labels))
            photo_locations = {"version": 1, "photos": {TEST_PHOTO_ID: SAMPLE_PHOTO_LOCATION}}
            (data_dir / "photo_locations.json").write_text(json.dumps(photo_locations))
            enrichment_path = data_dir / "enrichment.json"
            enrichment_path.write_text(json.dumps(enrichment))

            result = build_proposals(str(enrichment_path), data_dir)

        assert result["schema_version"] == 1
        assert "proposals" in result
        assert "source" in result
        assert "model" in result
        assert "created_at" in result

    def test_error_results_are_skipped(self):
        """Error results in enrichment batch are skipped."""
        from scripts.stage_enrichment_proposals import build_proposals
        from pathlib import Path
        import tempfile

        enrichment = {
            "batch_id": "test",
            "model": "gemini-3.1-pro-preview",
            "variant": "curated",
            "total_cost": 0.01,
            "results": [
                {
                    "photo_id": "error-photo",
                    "status": "error",
                    "reason": "Gemini API call failed",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            (data_dir / "date_labels.json").write_text('{"schema_version": 2, "labels": []}')
            (data_dir / "photo_locations.json").write_text('{"version": 1, "photos": {}}')
            enrichment_path = data_dir / "enrichment.json"
            enrichment_path.write_text(json.dumps(enrichment))

            result = build_proposals(str(enrichment_path), data_dir)

        assert len(result["proposals"]) == 0
