"""Data enrichment from GEDCOM matches.

Applies confirmed GEDCOM-to-identity matches by updating identity
metadata with birth/death dates, places, and gender.

Preserves ML estimates — GEDCOM values become primary source.
"""

from datetime import datetime, timezone
from typing import Optional

from rhodesli_ml.importers.gedcom_parser import GedcomIndividual


def apply_gedcom_enrichment(
    identity: dict,
    gedcom_individual: GedcomIndividual,
    registry=None,
) -> dict:
    """Apply GEDCOM data to an identity record.

    Updates metadata fields with GEDCOM values.
    If registry is provided, uses set_metadata() for proper persistence.
    Otherwise, modifies the identity dict directly (for testing).

    Returns: dict of fields that were updated.
    """
    updates = {}

    # Birth year
    if gedcom_individual.birth_year:
        updates["birth_year"] = gedcom_individual.birth_year

    # Death year
    if gedcom_individual.death_year:
        updates["death_year"] = gedcom_individual.death_year

    # Birth place
    if gedcom_individual.birth_place:
        updates["birth_place"] = gedcom_individual.birth_place

    # Death place
    if gedcom_individual.death_place:
        updates["death_place"] = gedcom_individual.death_place

    # Full birth date (if more precise than year)
    if gedcom_individual.birth and gedcom_individual.birth.raw_date:
        updates["birth_date_full"] = gedcom_individual.birth.raw_date

    # Full death date
    if gedcom_individual.death and gedcom_individual.death.raw_date:
        updates["death_date_full"] = gedcom_individual.death.raw_date

    # Gender
    if gedcom_individual.gender and gedcom_individual.gender != "U":
        updates["gender"] = gedcom_individual.gender

    if not updates:
        return {}

    identity_id = identity.get("identity_id", "")

    if registry:
        # Use proper registry method for persistence
        registry.set_metadata(identity_id, updates, user_source="gedcom")
    else:
        # Direct dict update (for testing without registry)
        if "metadata" not in identity:
            identity["metadata"] = {}
        identity["metadata"].update(updates)

    return updates


def build_enrichment_summary(
    proposals: list,
    identities: dict,
) -> dict:
    """Build a summary of what GEDCOM enrichment would change.

    Args:
        proposals: List of confirmed MatchProposal objects
        identities: Current identity records

    Returns: Summary dict with counts and per-identity changes.
    """
    summary = {
        "total_confirmed": 0,
        "birth_years_added": 0,
        "death_years_added": 0,
        "birth_places_added": 0,
        "death_places_added": 0,
        "genders_added": 0,
        "changes": [],
    }

    for proposal in proposals:
        if proposal.status != "confirmed":
            continue

        summary["total_confirmed"] += 1
        indi = proposal.gedcom_individual
        changes = []

        if indi.birth_year:
            summary["birth_years_added"] += 1
            changes.append(f"birth_year: {indi.birth_year}")
        if indi.death_year:
            summary["death_years_added"] += 1
            changes.append(f"death_year: {indi.death_year}")
        if indi.birth_place:
            summary["birth_places_added"] += 1
            changes.append(f"birth_place: {indi.birth_place}")
        if indi.death_place:
            summary["death_places_added"] += 1
            changes.append(f"death_place: {indi.death_place}")
        if indi.gender and indi.gender != "U":
            summary["genders_added"] += 1
            changes.append(f"gender: {indi.gender}")

        summary["changes"].append({
            "identity_id": proposal.identity_id,
            "identity_name": proposal.identity_name,
            "gedcom_name": indi.full_name,
            "fields_updated": changes,
        })

    return summary
