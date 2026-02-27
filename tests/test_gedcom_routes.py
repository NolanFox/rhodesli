"""Tests for GEDCOM admin routes.

TEST 5: Confirmed match enriches identity
TEST 9: Admin UI shows pending matches
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient


@pytest.fixture
def admin_client():
    """Test client with admin auth mocked."""
    with patch("app.main.is_auth_enabled", return_value=True), \
         patch("app.main.get_current_user") as mock_user:
        mock_user.return_value = MagicMock(email="admin@test.com", is_admin=True, id="admin-id")
        from app.main import app
        yield TestClient(app)


@pytest.fixture
def anon_client():
    """Test client with no auth."""
    with patch("app.main.is_auth_enabled", return_value=True), \
         patch("app.main.get_current_user", return_value=None):
        from app.main import app
        yield TestClient(app)


class TestGedcomAdminPage:
    """TEST 9: Admin UI shows pending matches."""

    def test_admin_can_access(self, admin_client):
        resp = admin_client.get("/admin/gedcom")
        assert resp.status_code == 200
        assert "GEDCOM Import" in resp.text

    def test_anon_cannot_access(self, anon_client):
        resp = anon_client.get("/admin/gedcom")
        assert resp.status_code in (401, 403)

    def test_shows_upload_form(self, admin_client):
        resp = admin_client.get("/admin/gedcom")
        assert 'type="file"' in resp.text
        assert "Upload" in resp.text

    def test_shows_stats(self, admin_client):
        resp = admin_client.get("/admin/gedcom")
        assert "Total Matches" in resp.text
        assert "Relationships" in resp.text
        assert "Co-occurrences" in resp.text

    def test_shows_pending_matches_when_data_exists(self, admin_client, tmp_path):
        """When gedcom_matches.json has data, show it."""
        matches_data = {
            "schema_version": 1,
            "source_file": "test.ged",
            "matches": [
                {
                    "gedcom_xref": "@I1@",
                    "gedcom_name": "Leon Capeluto",
                    "gedcom_birth_year": 1903,
                    "identity_id": "id-leon",
                    "identity_name": "Big Leon Capeluto",
                    "match_score": 0.92,
                    "match_reason": "test match",
                    "match_layer": 1,
                    "status": "pending",
                }
            ],
        }

        with patch("app.main._load_gedcom_matches", return_value=matches_data):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "Leon Capeluto" in resp.text
            assert "Big Leon Capeluto" in resp.text
            assert "Confirm" in resp.text
            assert "Reject" in resp.text

    def test_shows_test_data_warning(self, admin_client, tmp_path):
        """GEDCOM page shows warning when source file is test data."""
        matches_data = {
            "schema_version": 1,
            "source_file": "test_capeluto.ged",
            "matches": [],
        }
        with patch("app.main._load_gedcom_matches", return_value=matches_data):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "test-data-warning" in resp.text
            assert "test data" in resp.text.lower()

    def test_no_warning_for_real_file(self, admin_client, tmp_path):
        """GEDCOM page does NOT show warning for real GEDCOM files."""
        matches_data = {
            "schema_version": 1,
            "source_file": "capeluto_family.ged",
            "matches": [],
        }
        with patch("app.main._load_gedcom_matches", return_value=matches_data):
            resp = admin_client.get("/admin/gedcom")
            assert resp.status_code == 200
            assert "test-data-warning" not in resp.text


class TestGedcomConfirm:
    """TEST 5: Confirmed match enriches identity."""

    def test_confirm_updates_status(self, admin_client, tmp_path):
        # Create test matches file
        matches_path = tmp_path / "gedcom_matches.json"
        matches_data = {
            "schema_version": 1,
            "source_file": "test.ged",
            "matches": [
                {
                    "gedcom_xref": "@I1@",
                    "gedcom_name": "Leon Capeluto",
                    "gedcom_birth_year": 1903,
                    "gedcom_birth_place": "Rhodes",
                    "gedcom_death_year": 1982,
                    "identity_id": "test-id-leon",
                    "identity_name": "Big Leon Capeluto",
                    "match_score": 0.92,
                    "match_reason": "test",
                    "match_layer": 1,
                    "status": "pending",
                }
            ],
        }
        matches_path.write_text(json.dumps(matches_data))

        # Mock registry
        mock_registry = MagicMock()
        mock_identity = {
            "identity_id": "test-id-leon",
            "name": "Big Leon Capeluto",
            "state": "CONFIRMED",
            "version_id": 1,
        }
        mock_registry.get_identity.return_value = mock_identity

        with patch("app.main.data_path", tmp_path), \
             patch("app.main.load_registry", return_value=mock_registry), \
             patch("app.main.save_registry"), \
             patch("app.main._gedcom_matches_cache", None), \
             patch("app.main._birth_year_cache", None):

            resp = admin_client.post("/admin/gedcom/confirm/@I1@")
            assert resp.status_code == 200
            assert "Confirmed" in resp.text

            # Verify set_metadata was called with GEDCOM data
            mock_registry.set_metadata.assert_called_once()
            call_args = mock_registry.set_metadata.call_args
            assert call_args[0][0] == "test-id-leon"
            metadata = call_args[0][1]
            assert metadata["birth_year"] == 1903
            assert metadata["birth_place"] == "Rhodes"
            assert metadata["death_year"] == 1982

    def test_reject_updates_status(self, admin_client, tmp_path):
        matches_path = tmp_path / "gedcom_matches.json"
        matches_data = {
            "schema_version": 1,
            "source_file": "test.ged",
            "matches": [
                {
                    "gedcom_xref": "@I1@",
                    "gedcom_name": "Test Person",
                    "identity_id": "test-id",
                    "identity_name": "Test Identity",
                    "match_score": 0.8,
                    "match_reason": "test",
                    "match_layer": 1,
                    "status": "pending",
                }
            ],
        }
        matches_path.write_text(json.dumps(matches_data))

        with patch("app.main.data_path", tmp_path), \
             patch("app.main._gedcom_matches_cache", None):
            resp = admin_client.post("/admin/gedcom/reject/@I1@")
            assert resp.status_code == 200
            assert "Rejected" in resp.text

            # Verify file updated
            updated = json.loads(matches_path.read_text())
            assert updated["matches"][0]["status"] == "rejected"


class TestGedcomSidebarLink:
    """Verify GEDCOM link appears in admin sidebar."""

    def test_sidebar_has_gedcom_link(self, admin_client):
        resp = admin_client.get("/")
        assert resp.status_code == 200
        assert "/admin/gedcom" in resp.text
        assert "GEDCOM" in resp.text


class TestGedcomPermissions:
    """Permission boundary tests for GEDCOM routes."""

    def test_upload_requires_admin(self, anon_client):
        resp = anon_client.post("/admin/gedcom/upload")
        assert resp.status_code in (401, 403)

    def test_confirm_requires_admin(self, anon_client):
        resp = anon_client.post("/admin/gedcom/confirm/@I1@")
        assert resp.status_code in (401, 403)

    def test_reject_requires_admin(self, anon_client):
        resp = anon_client.post("/admin/gedcom/reject/@I1@")
        assert resp.status_code in (401, 403)

    def test_skip_requires_admin(self, anon_client):
        resp = anon_client.post("/admin/gedcom/skip/@I1@")
        assert resp.status_code in (401, 403)


# --- Session 65b: GEDCOM Search & Linking API (AD-160) ---


SAMPLE_GEDCOM_INDIVIDUALS = [
    {"gedcom_id": "@I1@", "name": "Leon Capeluto", "given_name": "Leon", "surname": "Capeluto",
     "gender": "M", "birth_date": "1903", "birth_place": "Rhodes, Greece",
     "death_date": "1982", "death_place": "Tampa, Florida"},
    {"gedcom_id": "@I2@", "name": "Victoria Capuano", "given_name": "Victoria", "surname": "Capuano",
     "gender": "F", "birth_date": "1908", "birth_place": "Rhodes",
     "death_date": "1990", "death_place": ""},
    {"gedcom_id": "@I3@", "name": "Moise Capeluto", "given_name": "Moise", "surname": "Capeluto",
     "gender": "M", "birth_date": "1904", "birth_place": "Rhodes",
     "death_date": "", "death_place": ""},
    {"gedcom_id": "@I4@", "name": "Isaac Israel", "given_name": "Isaac", "surname": "Israel",
     "gender": "M", "birth_date": "1880", "birth_place": "",
     "death_date": "1945", "death_place": ""},
    {"gedcom_id": "@I5@", "name": "Selma Capouya", "given_name": "Selma", "surname": "Capouya",
     "gender": "F", "birth_date": "", "birth_place": "",
     "death_date": "", "death_place": ""},
]


class TestGedcomSearchAPI:
    """Tests for GET /api/gedcom/search (AD-160)."""

    def test_search_returns_results(self, admin_client):
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main._load_gedcom_face_links", return_value={}):
            resp = admin_client.get("/api/gedcom/search?q=Leon Capeluto&identity_id=test-id")
            assert resp.status_code == 200
            assert "Leon Capeluto" in resp.text

    def test_search_case_insensitive(self, admin_client):
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main._load_gedcom_face_links", return_value={}):
            resp = admin_client.get("/api/gedcom/search?q=leon capeluto&identity_id=test-id")
            assert resp.status_code == 200
            assert "Leon Capeluto" in resp.text

    def test_search_no_match(self, admin_client):
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main._load_gedcom_face_links", return_value={}):
            resp = admin_client.get("/api/gedcom/search?q=Nonexistent Person&identity_id=test-id")
            assert resp.status_code == 200
            assert "No matches found" in resp.text

    def test_search_empty_query(self, admin_client):
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main._load_gedcom_face_links", return_value={}):
            resp = admin_client.get("/api/gedcom/search?q=&identity_id=test-id")
            assert resp.status_code == 200
            assert "No matches found" in resp.text

    def test_search_surname_variant(self, admin_client):
        """Sephardic name variants: Capuano should match Capeluto."""
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main._load_gedcom_face_links", return_value={}):
            resp = admin_client.get("/api/gedcom/search?q=Victoria Capeluto&identity_id=test-id")
            assert resp.status_code == 200
            # Should find Victoria Capuano (variant of Capeluto)
            assert "Victoria Capuano" in resp.text

    def test_search_requires_admin(self, anon_client):
        resp = anon_client.get("/api/gedcom/search?q=test")
        assert resp.status_code in (401, 403)

    def test_search_shows_birth_death_years(self, admin_client):
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main._load_gedcom_face_links", return_value={}):
            resp = admin_client.get("/api/gedcom/search?q=Leon Capeluto&identity_id=test-id")
            assert resp.status_code == 200
            assert "1903" in resp.text
            assert "1982" in resp.text


class TestGedcomLinkAPI:
    """Tests for POST /api/gedcom/link and /api/gedcom/unlink (AD-160)."""

    def test_link_saves_to_supabase(self, admin_client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_registry = MagicMock()

        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main.load_registry", return_value=mock_registry), \
             patch("app.main.save_registry"), \
             patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = admin_client.post(
                "/api/gedcom/link",
                data={"identity_id": "test-id", "gedcom_id": "@I1@"},
            )
            assert resp.status_code == 200
            assert "Linked to Family Tree" in resp.text

            # Verify Supabase was called
            mock_sb.table.assert_called_with("gedcom_face_links")

    def test_link_enriches_identity(self, admin_client):
        """Linking should set birth/death year on the identity."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        mock_registry = MagicMock()

        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main.load_registry", return_value=mock_registry), \
             patch("app.main.save_registry"), \
             patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = admin_client.post(
                "/api/gedcom/link",
                data={"identity_id": "test-id", "gedcom_id": "@I1@"},
            )
            assert resp.status_code == 200
            # Verify birth/death enrichment
            mock_registry.set_metadata.assert_called_once()
            metadata = mock_registry.set_metadata.call_args[0][1]
            assert metadata.get("birth_year") == 1903
            assert metadata.get("death_year") == 1982

    def test_link_requires_admin(self, anon_client):
        resp = anon_client.post("/api/gedcom/link", data={"identity_id": "x", "gedcom_id": "y"})
        assert resp.status_code in (401, 403)

    def test_link_missing_params(self, admin_client):
        resp = admin_client.post("/api/gedcom/link", data={})
        assert resp.status_code == 400

    def test_unlink_requires_admin(self, anon_client):
        resp = anon_client.post("/api/gedcom/unlink", data={"identity_id": "x"})
        assert resp.status_code in (401, 403)

    def test_unlink_deletes_from_supabase(self, admin_client):
        mock_sb = MagicMock()
        mock_sb.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()
        mock_registry = MagicMock()
        mock_registry.get_identity.return_value = {"identity_id": "test-id", "name": "Test Person"}

        with patch("app.main.load_registry", return_value=mock_registry), \
             patch("app.main._gedcom_face_links_cache", None), \
             patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            resp = admin_client.post(
                "/api/gedcom/unlink",
                data={"identity_id": "test-id", "gedcom_id": "@I1@"},
            )
            assert resp.status_code == 200
            # Should return the link panel for re-linking
            assert "Link to Family Tree" in resp.text

    def test_confirm_shows_gedcom_panel(self, admin_client, tmp_path):
        """After confirming an identity, GEDCOM link panel should appear."""
        mock_registry = MagicMock()
        identity = {
            "identity_id": "test-id",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "version_id": 1,
            "anchor_ids": [],
        }
        mock_registry.get_identity.return_value = identity
        mock_registry.confirm_identity.return_value = None

        with patch("app.main.load_registry", return_value=mock_registry), \
             patch("app.main.save_registry"), \
             patch("app.main.get_crop_files", return_value=set()), \
             patch("app.main._load_gedcom_face_links", return_value={}), \
             patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS):
            resp = admin_client.post("/confirm/test-id")
            assert resp.status_code == 200
            assert "Link to Family Tree" in resp.text
            assert "Leon Capeluto" in resp.text


class TestSearchGedcomFunction:
    """Unit tests for _search_gedcom_individuals."""

    def test_exact_match_scores_highest(self):
        from app.main import _search_gedcom_individuals
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS):
            results, total = _search_gedcom_individuals("Leon Capeluto")
            assert len(results) > 0
            assert results[0]["xref_id"] == "@I1@"
            # Score is 1.0 base + bonus for having dates + Rhodes location
            assert results[0]["score"] >= 1.0

    def test_partial_match(self):
        from app.main import _search_gedcom_individuals
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS):
            results, total = _search_gedcom_individuals("Capeluto")
            assert len(results) >= 2  # Leon + Moise

    def test_surname_variant(self):
        from app.main import _search_gedcom_individuals
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS):
            results, total = _search_gedcom_individuals("Victoria Capeluto")
            # Should find Victoria Capuano via surname variant
            xrefs = [r["xref_id"] for r in results]
            assert "@I2@" in xrefs

    def test_empty_query_returns_empty(self):
        from app.main import _search_gedcom_individuals
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS):
            results, total = _search_gedcom_individuals("")
            assert results == []
            assert total == 0
            results2, total2 = _search_gedcom_individuals("a")
            assert results2 == []

    def test_no_match_returns_empty(self):
        from app.main import _search_gedcom_individuals
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS):
            results, total = _search_gedcom_individuals("Zzzzz Nonexistent")
            assert results == []
            assert total == 0

    def test_date_bonus_scoring(self):
        """People with dates and Rhodes connection get bonus score (B1)."""
        from app.main import _search_gedcom_individuals
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS):
            results, total = _search_gedcom_individuals("Capeluto")
            # Leon (has dates + Rhodes) should rank above Selma Capouya (no dates)
            scored = {r["xref_id"]: r["score"] for r in results}
            # Leon Capeluto has both dates AND Rhodes → should have highest bonus
            assert scored.get("@I1@", 0) > scored.get("@I5@", 0) if "@I5@" in scored else True

    def test_pagination_offset(self):
        """Pagination returns correct slice of results."""
        from app.main import _search_gedcom_individuals
        # Create many similar individuals
        many_individuals = [
            {"gedcom_id": f"@I{i}@", "name": f"Person Capeluto {i}", "given_name": f"Person{i}",
             "surname": "Capeluto", "gender": "M", "birth_date": "", "birth_place": "",
             "death_date": "", "death_place": ""}
            for i in range(25)
        ]
        with patch("app.main._load_gedcom_individuals", return_value=many_individuals):
            page1, total = _search_gedcom_individuals("Capeluto", limit=10, offset=0)
            assert total == 25
            assert len(page1) == 10
            page2, total2 = _search_gedcom_individuals("Capeluto", limit=10, offset=10)
            assert total2 == 25
            assert len(page2) == 10
            page3, total3 = _search_gedcom_individuals("Capeluto", limit=10, offset=20)
            assert total3 == 25
            assert len(page3) == 5  # Only 5 remaining

    def test_result_count_in_search_response(self, admin_client):
        """Search endpoint shows result count (B1)."""
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main._load_gedcom_face_links", return_value={}):
            resp = admin_client.get("/api/gedcom/search?q=Capeluto&identity_id=test-id")
            assert resp.status_code == 200
            assert "result" in resp.text.lower()  # Shows "N results"

    def test_match_strength_indicator(self, admin_client):
        """Search results show match strength labels (B1)."""
        with patch("app.main._load_gedcom_individuals", return_value=SAMPLE_GEDCOM_INDIVIDUALS), \
             patch("app.main._load_gedcom_face_links", return_value={}):
            resp = admin_client.get("/api/gedcom/search?q=Leon Capeluto&identity_id=test-id")
            assert resp.status_code == 200
            assert "Strong" in resp.text  # Exact match → Strong


class TestGedcomTreeButtonOnIdentityCard:
    """B3: Identity cards should show GEDCOM tree button for confirmed identities."""

    def test_confirmed_identity_shows_tree_link(self):
        """Confirmed identity card shows 'Link to Tree' when not linked."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-id-gedcom-001",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-gedcom-001_0.jpg"}
        with patch("app.main._load_gedcom_face_links", return_value={}):
            html = to_xml(identity_card(identity, crop_files, is_admin=True))
        assert "Link to Tree" in html
        assert f"/person/test-id-gedcom-001#gedcom" in html

    def test_linked_identity_shows_view_tree(self):
        """Confirmed identity card shows 'View in Tree' when linked."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-id-gedcom-002",
            "name": "Victoria Capuano",
            "state": "CONFIRMED",
            "anchor_ids": ["face-2"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-gedcom-002_0.jpg"}
        linked = {"test-id-gedcom-002": {"gedcom_id": "@I2@"}}
        with patch("app.main._load_gedcom_face_links", return_value=linked):
            html = to_xml(identity_card(identity, crop_files, is_admin=True))
        assert "View in Tree" in html

    def test_proposed_identity_no_tree_button(self):
        """Proposed identities should NOT show tree button."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-id-gedcom-003",
            "name": "Unknown Person",
            "state": "PROPOSED",
            "anchor_ids": ["face-3"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-gedcom-003_0.jpg"}
        with patch("app.main._load_gedcom_face_links", return_value={}):
            html = to_xml(identity_card(identity, crop_files, is_admin=True))
        assert "Link to Tree" not in html
        assert "View in Tree" not in html

    def test_non_admin_no_tree_button(self):
        """Non-admin users should NOT see tree button."""
        from app.main import identity_card, to_xml
        identity = {
            "identity_id": "test-id-gedcom-004",
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face-4"],
            "candidate_ids": [],
        }
        crop_files = {"test-id-gedcom-004_0.jpg"}
        with patch("app.main._load_gedcom_face_links", return_value={}):
            html = to_xml(identity_card(identity, crop_files, is_admin=False))
        assert "Link to Tree" not in html
