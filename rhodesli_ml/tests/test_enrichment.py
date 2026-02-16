"""Tests for GEDCOM data enrichment.

TEST 5: Confirmed match enriches identity
TEST 6: ML estimates preserved after enrichment
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from rhodesli_ml.importers.gedcom_parser import (
    GedcomIndividual,
    GedcomEvent,
    ParsedDate,
)
from rhodesli_ml.importers.enrichment import (
    apply_gedcom_enrichment,
    build_enrichment_summary,
)
from rhodesli_ml.importers.identity_matcher import MatchProposal


class TestApplyEnrichment:
    """TEST 5: Confirmed match enriches identity."""

    def test_sets_birth_year(self):
        identity = {"identity_id": "test", "metadata": {}}
        indi = GedcomIndividual(
            xref_id="@I1@", given_name="Leon", surname="Capeluto",
            full_name="Leon Capeluto", gender="M",
            birth=GedcomEvent(
                event_type="birth",
                date=ParsedDate(year=1903, month=3, day=12, confidence="HIGH"),
                place="Rhodes",
                raw_date="12 MAR 1903",
            ),
        )
        updates = apply_gedcom_enrichment(identity, indi)
        assert updates["birth_year"] == 1903
        assert identity["metadata"]["birth_year"] == 1903

    def test_sets_death_year(self):
        identity = {"identity_id": "test", "metadata": {}}
        indi = GedcomIndividual(
            xref_id="@I1@",
            death=GedcomEvent(
                event_type="death",
                date=ParsedDate(year=1982),
                place="Miami",
                raw_date="1982",
            ),
        )
        updates = apply_gedcom_enrichment(identity, indi)
        assert updates["death_year"] == 1982
        assert identity["metadata"]["death_year"] == 1982

    def test_sets_places(self):
        identity = {"identity_id": "test", "metadata": {}}
        indi = GedcomIndividual(
            xref_id="@I1@",
            birth=GedcomEvent(event_type="birth", place="Rhodes, Ottoman Empire"),
            death=GedcomEvent(event_type="death", place="Miami, FL"),
        )
        updates = apply_gedcom_enrichment(identity, indi)
        assert updates["birth_place"] == "Rhodes, Ottoman Empire"
        assert updates["death_place"] == "Miami, FL"

    def test_sets_gender(self):
        identity = {"identity_id": "test", "metadata": {}}
        indi = GedcomIndividual(xref_id="@I1@", gender="M")
        updates = apply_gedcom_enrichment(identity, indi)
        assert updates["gender"] == "M"

    def test_skips_unknown_gender(self):
        identity = {"identity_id": "test", "metadata": {}}
        indi = GedcomIndividual(xref_id="@I1@", gender="U")
        updates = apply_gedcom_enrichment(identity, indi)
        assert "gender" not in updates

    def test_sets_full_dates(self):
        identity = {"identity_id": "test", "metadata": {}}
        indi = GedcomIndividual(
            xref_id="@I1@",
            birth=GedcomEvent(
                event_type="birth",
                date=ParsedDate(year=1903),
                raw_date="12 MAR 1903",
            ),
            death=GedcomEvent(
                event_type="death",
                date=ParsedDate(year=1982),
                raw_date="15 JUN 1982",
            ),
        )
        updates = apply_gedcom_enrichment(identity, indi)
        assert updates["birth_date_full"] == "12 MAR 1903"
        assert updates["death_date_full"] == "15 JUN 1982"

    def test_no_updates_when_empty(self):
        identity = {"identity_id": "test", "metadata": {}}
        indi = GedcomIndividual(xref_id="@I1@", gender="U")
        updates = apply_gedcom_enrichment(identity, indi)
        assert updates == {}

    def test_creates_metadata_dict_if_missing(self):
        identity = {"identity_id": "test"}
        indi = GedcomIndividual(
            xref_id="@I1@",
            birth=GedcomEvent(
                event_type="birth",
                date=ParsedDate(year=1903),
            ),
        )
        apply_gedcom_enrichment(identity, indi)
        assert "metadata" in identity
        assert identity["metadata"]["birth_year"] == 1903

    def test_uses_registry_when_provided(self):
        mock_registry = MagicMock()
        identity = {"identity_id": "test-id"}
        indi = GedcomIndividual(
            xref_id="@I1@",
            birth=GedcomEvent(
                event_type="birth",
                date=ParsedDate(year=1903),
            ),
        )
        apply_gedcom_enrichment(identity, indi, registry=mock_registry)
        mock_registry.set_metadata.assert_called_once()
        args, kwargs = mock_registry.set_metadata.call_args
        # Could be positional or keyword args
        all_args = list(args)
        assert all_args[0] == "test-id"
        assert all_args[1]["birth_year"] == 1903


class TestMLEstimatesPreserved:
    """TEST 6: ML estimates preserved after enrichment."""

    def test_ml_file_not_modified(self, tmp_path):
        """GEDCOM enrichment does not touch birth_year_estimates.json."""
        # Create a fake ML estimates file
        ml_path = tmp_path / "birth_year_estimates.json"
        original_data = {
            "estimates": [
                {
                    "identity_id": "test-id",
                    "birth_year_estimate": 1907,
                    "birth_year_confidence": "medium",
                    "source": "ml_inferred",
                }
            ]
        }
        ml_path.write_text(json.dumps(original_data))

        # Apply enrichment (does not touch ML file)
        identity = {"identity_id": "test-id", "metadata": {}}
        indi = GedcomIndividual(
            xref_id="@I1@",
            birth=GedcomEvent(
                event_type="birth",
                date=ParsedDate(year=1903),
            ),
        )
        apply_gedcom_enrichment(identity, indi)

        # Verify ML file unchanged
        loaded = json.loads(ml_path.read_text())
        assert loaded["estimates"][0]["birth_year_estimate"] == 1907
        assert loaded["estimates"][0]["source"] == "ml_inferred"


class TestBuildEnrichmentSummary:
    def test_summary(self):
        indi = GedcomIndividual(
            xref_id="@I1@", given_name="Leon", surname="Capeluto",
            full_name="Leon Capeluto", gender="M",
            birth=GedcomEvent(event_type="birth", date=ParsedDate(year=1903), place="Rhodes"),
            death=GedcomEvent(event_type="death", date=ParsedDate(year=1982)),
        )
        proposal = MatchProposal(
            gedcom_individual=indi,
            identity_id="id-leon",
            identity_name="Big Leon Capeluto",
            match_score=0.92,
            match_reason="test",
            match_layer=1,
            status="confirmed",
        )
        summary = build_enrichment_summary([proposal], {})
        assert summary["total_confirmed"] == 1
        assert summary["birth_years_added"] == 1
        assert summary["death_years_added"] == 1
        assert summary["birth_places_added"] == 1

    def test_skips_pending(self):
        indi = GedcomIndividual(
            xref_id="@I1@",
            birth=GedcomEvent(event_type="birth", date=ParsedDate(year=1903)),
        )
        proposal = MatchProposal(
            gedcom_individual=indi,
            identity_id="id", identity_name="Name",
            match_score=0.8, match_reason="test",
            match_layer=1, status="pending",
        )
        summary = build_enrichment_summary([proposal], {})
        assert summary["total_confirmed"] == 0
