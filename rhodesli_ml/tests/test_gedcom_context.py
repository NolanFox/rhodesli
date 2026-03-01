"""Tests for GEDCOM context builder — 5 enrichment variants.

Session: 61C
"""

import pytest
from unittest.mock import MagicMock

from rhodesli_ml.gedcom_context import (
    build_photo_context,
    build_all_variants,
    estimate_context_tokens,
    get_enrichment_delta,
    VARIANTS,
    _filter_events_by_date,
    _find_identity_for_face,
)
from rhodesli_ml.importers.gedcom_parser import (
    parse_gedcom,
    GedcomIndividual,
    GedcomEvent,
    GedcomFamily,
    ParsedGedcom,
    ParsedDate,
)

FIXTURE_PATH = "tests/fixtures/test_capeluto.ged"


@pytest.fixture
def parsed_gedcom():
    """Parse the test GEDCOM fixture."""
    return parse_gedcom(FIXTURE_PATH)


@pytest.fixture
def sample_identities():
    """Sample identities matching test GEDCOM."""
    return {
        "id-leon": {
            "name": "Leon Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face_leon_1", "face_leon_2"],
            "candidate_ids": [],
            "negative_ids": [],
        },
        "id-nace": {
            "name": "Nace Capeluto",
            "state": "CONFIRMED",
            "anchor_ids": ["face_nace_1"],
            "candidate_ids": [],
            "negative_ids": [],
        },
        "id-unknown": {
            "name": "Unknown Person",
            "state": "INBOX",
            "anchor_ids": ["face_unknown_1"],
            "candidate_ids": [],
            "negative_ids": [],
        },
    }


@pytest.fixture
def gedcom_face_links():
    """Link identities to GEDCOM individuals."""
    return {
        "id-leon": "@I3@",   # Leon Capeluto
        "id-nace": "@I5@",   # Nace Capeluto
    }


@pytest.fixture
def sample_photo_index():
    """Sample photo index for co-occurrence testing."""
    return {
        "photos": {
            "photo1": {
                "path": "Image_001.jpg",
                "face_ids": ["face_leon_1", "face_nace_1"],
            },
            "photo2": {
                "path": "Image_002.jpg",
                "face_ids": ["face_leon_2", "face_unknown_1"],
            },
        },
        "face_to_photo": {
            "face_leon_1": "photo1",
            "face_leon_2": "photo2",
            "face_nace_1": "photo1",
            "face_unknown_1": "photo2",
        },
    }


class TestBuildContextNone:
    def test_none_returns_empty(self, parsed_gedcom, sample_identities, gedcom_face_links):
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
            variant="none",
        )
        assert result == ""

    def test_no_faces_returns_empty(self, parsed_gedcom, sample_identities, gedcom_face_links):
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=[],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
            variant="full",
        )
        assert result == ""


class TestBuildContextFull:
    def test_full_includes_all_events(self, parsed_gedcom, sample_identities, gedcom_face_links):
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
            variant="full",
        )
        assert "Leon Capeluto" in result
        assert "Born:" in result
        assert "Died:" in result

    def test_full_includes_header(self, parsed_gedcom, sample_identities, gedcom_face_links):
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
            variant="full",
        )
        assert "GENEALOGICAL CONTEXT" in result

    def test_unlinked_face_skipped(self, parsed_gedcom, sample_identities, gedcom_face_links):
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_unknown_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
            variant="full",
        )
        assert result == ""


class TestBuildContextCurated:
    def test_curated_filters_by_date(self):
        """Events outside date window should be excluded."""
        events = [
            GedcomEvent(event_type="residence", date=ParsedDate(year=1920), place="NY", raw_date="1920"),
            GedcomEvent(event_type="residence", date=ParsedDate(year=1960), place="FL", raw_date="1960"),
        ]
        filtered = _filter_events_by_date(events, photo_date=1925, window=15)
        assert len(filtered) == 1
        assert filtered[0].place == "NY"

    def test_curated_includes_undated_events(self):
        """Events without dates should be included."""
        events = [
            GedcomEvent(event_type="occupation", date=None, place=None, raw_date=""),
        ]
        filtered = _filter_events_by_date(events, photo_date=1925, window=15)
        assert len(filtered) == 1


class TestBuildContextFirstOrder:
    def test_first_order_includes_family(self, parsed_gedcom, sample_identities, gedcom_face_links):
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
            variant="first_order",
        )
        # Leon's parents should be included
        assert "Parent:" in result
        # Leon's siblings should be included
        assert "Sibling:" in result or "Child:" in result


class TestBuildContextCoOccurrence:
    def test_co_occurrence_includes_shared_photos(
        self, parsed_gedcom, sample_identities, gedcom_face_links, sample_photo_index
    ):
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
            photo_index=sample_photo_index,
            variant="co_occurrence",
        )
        # Nace shares photo1 with Leon, so should be included
        assert "Nace Capeluto" in result


class TestTokenEstimation:
    def test_empty_string(self):
        assert estimate_context_tokens("") == 0

    def test_known_string(self):
        # "Hello World" = 11 chars → ~2-3 tokens
        tokens = estimate_context_tokens("Hello World!")
        assert tokens == 3  # 12 // 4

    def test_long_context(self):
        context = "A" * 4000
        assert estimate_context_tokens(context) == 1000


class TestEnrichmentDelta:
    def test_no_change(self):
        baseline = {"date_estimation": {"estimated_year": 1930, "confidence": 0.5}}
        enriched = {"date_estimation": {"estimated_year": 1930, "confidence": 0.5}}
        delta = get_enrichment_delta(baseline, enriched)
        assert not delta["date_changed"]
        assert delta["confidence_delta"] == 0

    def test_date_changed(self):
        baseline = {"date_estimation": {"estimated_year": 1930, "confidence": 0.5}}
        enriched = {"date_estimation": {"estimated_year": 1925, "confidence": 0.8}}
        delta = get_enrichment_delta(baseline, enriched)
        assert delta["date_changed"]
        assert delta["date_shift_years"] == -5
        assert delta["confidence_delta"] == pytest.approx(0.3)

    def test_location_changed(self):
        baseline = {"date_estimation": {}, "location": {"city": "Unknown"}}
        enriched = {"date_estimation": {}, "location": {"city": "Rhodes"}}
        delta = get_enrichment_delta(baseline, enriched)
        assert delta["location_changed"]


class TestBuildAllVariants:
    def test_returns_all_variants(self, parsed_gedcom, sample_identities, gedcom_face_links):
        result = build_all_variants(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
        )
        assert set(result.keys()) == set(VARIANTS)
        assert result["none"] == ""
        assert len(result["full"]) > 0


class TestFindIdentityForFace:
    def test_finds_anchor(self, sample_identities):
        assert _find_identity_for_face("face_leon_1", sample_identities) == "id-leon"

    def test_returns_none_for_unknown(self, sample_identities):
        assert _find_identity_for_face("face_xyz", sample_identities) is None


class TestResidentialHistory:
    """Test that residential addresses are emitted in context (AD-192)."""

    def test_full_variant_includes_residence_events(
        self, parsed_gedcom, sample_identities, gedcom_face_links
    ):
        """Full variant should include residential history for Leon."""
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
            variant="full",
        )
        assert "Residential History:" in result
        assert "33 Elizabeth Street, Asheville" in result

    def test_full_variant_includes_occupation(
        self, parsed_gedcom, sample_identities, gedcom_face_links
    ):
        """Full variant should include occupation events."""
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=sample_identities,
            variant="full",
        )
        assert "Occupation:" in result
        assert "Asheville" in result

    def test_first_order_includes_spouse_residence(self, parsed_gedcom):
        """First-order variant should include Victoria's residence via spouse context."""
        identities = {
            "id-leon": {
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face_leon_1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }
        links = {"id-leon": "@I3@"}
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=links,
            identities=identities,
            variant="first_order",
        )
        # Victoria (Leon's spouse) has RESI events
        assert "Victoria Capuano" in result
        assert "Residence:" in result or "33 Elizabeth Street" in result

    def test_first_order_includes_children_with_birth_places(self, parsed_gedcom):
        """First-order variant should include children's birth places."""
        identities = {
            "id-leon": {
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face_leon_1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }
        links = {"id-leon": "@I3@"}
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_leon_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=links,
            identities=identities,
            variant="first_order",
        )
        # Children of Leon+Victoria: Selma (1926 Asheville), Anita (1931 NC),
        # Nace (1933 Asheville), Betty (1950 Miami), Vida (1945 NY)
        assert "Children (birth dates help narrow photo date and location):" in result
        assert "Asheville" in result
        assert "North Carolina" in result

    def test_curated_filters_residence_events(self, parsed_gedcom):
        """Curated variant should only include residence events near photo date."""
        identities = {
            "id-victoria": {
                "name": "Victoria Capuano",
                "state": "CONFIRMED",
                "anchor_ids": ["face_victoria_1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }
        links = {"id-victoria": "@I7@"}
        # Photo estimated at 1934 — should include Asheville RESI (1930-1940)
        # but not Tampa RESI (after 1940, which is year 1941 due to AFT adjustment)
        result = build_photo_context(
            photo_id="photo1",
            identified_faces=["face_victoria_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=links,
            identities=identities,
            variant="curated",
            photo_date_estimate=1934,
        )
        assert "33 Elizabeth Street, Asheville" in result


class TestAshevilleGroundTruth:
    """Test the Asheville case study — Victoria Capeluto + children photo.

    Ground truth: Photo 746dd11e5b4d86a1 shows Victoria with 3 of 4 children
    at 33 Elizabeth Street, Asheville, NC circa Autumn 1934.
    AD-192: GEDCOM-enriched location prompting.
    """

    @pytest.fixture
    def asheville_identities(self):
        """Identities matching the Asheville photo."""
        return {
            "id-victoria": {
                "name": "Victoria Capuano Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face_victoria_1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
            "id-leon": {
                "name": "Leon Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face_leon_1"],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }

    @pytest.fixture
    def asheville_links(self):
        """GEDCOM links for Asheville case."""
        return {
            "id-victoria": "@I7@",   # Victoria Capuano
            "id-leon": "@I3@",       # Leon Capeluto
        }

    def test_first_order_includes_asheville_address(
        self, parsed_gedcom, asheville_identities, asheville_links
    ):
        """First-order context for Victoria should include Asheville address."""
        result = build_photo_context(
            photo_id="asheville_photo",
            identified_faces=["face_victoria_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=asheville_links,
            identities=asheville_identities,
            variant="first_order",
        )
        assert "33 Elizabeth Street, Asheville" in result

    def test_first_order_includes_all_children(
        self, parsed_gedcom, asheville_identities, asheville_links
    ):
        """First-order context should list all children with birth years."""
        result = build_photo_context(
            photo_id="asheville_photo",
            identified_faces=["face_victoria_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=asheville_links,
            identities=asheville_identities,
            variant="first_order",
        )
        # Victoria's children in fixture: Selma (1926), Anita (1931),
        # Nace (1933), Betty (1950), Vida (1945)
        assert "b.1926" in result  # Selma
        assert "b.1931" in result  # Anita
        assert "b.1933" in result  # Nace Jr
        assert "b.1950" in result  # Betty
        assert "b.1945" in result  # Vida

    def test_first_order_includes_nace_birth_month(
        self, parsed_gedcom, asheville_identities, asheville_links
    ):
        """Nace Jr has a specific month (5 MAR 1933), should include month."""
        result = build_photo_context(
            photo_id="asheville_photo",
            identified_faces=["face_victoria_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=asheville_links,
            identities=asheville_identities,
            variant="first_order",
        )
        assert "b.1933 Mar" in result

    def test_combined_context_for_asheville_prompt(
        self, parsed_gedcom, asheville_identities, asheville_links
    ):
        """Combined prompt for Asheville photo should have all location-relevant data."""
        from rhodesli_ml.gemini_extraction import build_extraction_prompt

        context = build_photo_context(
            photo_id="asheville_photo",
            identified_faces=["face_victoria_1"],
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=asheville_links,
            identities=asheville_identities,
            variant="first_order",
        )
        prompt = build_extraction_prompt(
            preset="full",
            gedcom_context=context,
        )
        # Prompt should contain BOTH the enhanced location instructions
        # AND the GEDCOM context
        assert "Biographical Cross-Reference" in prompt
        assert "missing child" in prompt.lower()
        assert "33 Elizabeth Street, Asheville" in prompt
        assert "Genealogical Context" in prompt


class TestInvalidVariant:
    def test_raises_for_unknown_variant(self, parsed_gedcom, sample_identities, gedcom_face_links):
        with pytest.raises(ValueError, match="Unknown variant"):
            build_photo_context(
                photo_id="photo1",
                identified_faces=["face_leon_1"],
                parsed_gedcom=parsed_gedcom,
                gedcom_face_links=gedcom_face_links,
                identities=sample_identities,
                variant="invalid",
            )
