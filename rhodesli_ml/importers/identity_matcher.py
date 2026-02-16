"""Identity matcher for GEDCOM-to-archive matching.

Layered matching strategy:
1. Exact name match (with surname variant expansion)
2. Fuzzy name + date proximity match
3. Unmatched individuals stay in GEDCOM-only pool

AD-074: Identity matching algorithm
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rhodesli_ml.importers.gedcom_parser import GedcomIndividual, ParsedGedcom


@dataclass
class MatchProposal:
    """A proposed match between a GEDCOM individual and an archive identity."""
    gedcom_individual: GedcomIndividual
    identity_id: str
    identity_name: str
    match_score: float  # 0.0 to 1.0
    match_reason: str
    match_layer: int  # 1=exact, 2=fuzzy
    status: str = "pending"  # pending, confirmed, rejected, skipped

    def to_dict(self) -> dict:
        return {
            "gedcom_xref": self.gedcom_individual.xref_id,
            "gedcom_name": self.gedcom_individual.full_name,
            "gedcom_birth_year": self.gedcom_individual.birth_year,
            "gedcom_birth_place": self.gedcom_individual.birth_place,
            "gedcom_death_year": self.gedcom_individual.death_year,
            "identity_id": self.identity_id,
            "identity_name": self.identity_name,
            "match_score": round(self.match_score, 3),
            "match_reason": self.match_reason,
            "match_layer": self.match_layer,
            "status": self.status,
        }


@dataclass
class MatchResult:
    """Complete result of matching a GEDCOM file against the archive."""
    proposals: list = field(default_factory=list)  # List[MatchProposal]
    unmatched_gedcom: list = field(default_factory=list)  # List[GedcomIndividual]
    unmatched_identities: list = field(default_factory=list)  # identity_ids not matched

    @property
    def match_count(self) -> int:
        return len(self.proposals)

    def to_dict(self) -> dict:
        return {
            "proposals": [p.to_dict() for p in self.proposals],
            "unmatched_gedcom_count": len(self.unmatched_gedcom),
            "unmatched_identities_count": len(self.unmatched_identities),
        }


# --- Name normalization ---

# Common prefixes/suffixes to strip for matching
NAME_PREFIXES = {"big", "little", "young", "old", "baby"}
NAME_SUFFIXES = {"jr", "jr.", "sr", "sr.", "ii", "iii", "iv"}


def normalize_name(name: str) -> str:
    """Normalize a name for matching: lowercase, strip prefixes/suffixes."""
    if not name:
        return ""
    parts = name.lower().strip().split()
    # Strip known prefixes
    while parts and parts[0] in NAME_PREFIXES:
        parts = parts[1:]
    # Strip known suffixes
    while parts and parts[-1] in NAME_SUFFIXES:
        parts = parts[:-1]
    return " ".join(parts)


def extract_name_parts(name: str) -> tuple:
    """Extract (first_names, surname) from a display name.

    Handles multi-word names like "Victoria Cukran Capeluto" where
    the last word is likely the surname.
    """
    parts = name.strip().split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return ("", parts[0].lower())
    return (" ".join(parts[:-1]).lower(), parts[-1].lower())


def load_surname_variants(path: Optional[str] = None) -> dict:
    """Load surname variant groups and build a lookup table.

    Returns: dict mapping each variant (lowercase) to its canonical form.
    """
    if path is None:
        path = Path(__file__).resolve().parent.parent.parent / "data" / "surname_variants.json"
    else:
        path = Path(path)

    if not path.exists():
        return {}

    with open(path) as f:
        data = json.load(f)

    lookup = {}
    for group in data.get("variant_groups", []):
        canonical = group["canonical"].lower()
        lookup[canonical] = canonical
        for variant in group.get("variants", []):
            lookup[variant.lower()] = canonical
    return lookup


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr_row.append(min(
                curr_row[j] + 1,        # insert
                prev_row[j + 1] + 1,    # delete
                prev_row[j] + cost,      # substitute
            ))
        prev_row = curr_row
    return prev_row[-1]


def name_similarity(name1: str, name2: str) -> float:
    """Compute similarity between two names (0.0 to 1.0).

    Uses Levenshtein distance normalized by max length.
    """
    if not name1 or not name2:
        return 0.0
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()
    if n1 == n2:
        return 1.0
    max_len = max(len(n1), len(n2))
    if max_len == 0:
        return 0.0
    dist = levenshtein_distance(n1, n2)
    return max(0.0, 1.0 - dist / max_len)


# --- Matching logic ---

def match_gedcom_to_identities(
    parsed_gedcom: ParsedGedcom,
    identities: dict,
    surname_variants_path: Optional[str] = None,
    birth_year_estimates: Optional[dict] = None,
) -> MatchResult:
    """Match GEDCOM individuals to archive identities.

    Args:
        parsed_gedcom: Parsed GEDCOM data
        identities: Dict of identity_id -> identity record from identities.json
        surname_variants_path: Path to surname_variants.json (optional)
        birth_year_estimates: Dict of identity_id -> estimate record (optional)

    Returns:
        MatchResult with proposed matches and unmatched individuals
    """
    variant_lookup = load_surname_variants(surname_variants_path)

    # Build identity lookup: normalize names for matching
    identity_records = []
    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue  # Skip merged identities
        name = ident.get("name", "") or ""
        if name.startswith("Unidentified"):
            continue  # Skip unnamed identities
        state = ident.get("state", "")
        if state not in ("CONFIRMED", "PROPOSED"):
            continue  # Only match against confirmed/proposed

        norm_name = normalize_name(name)
        first_parts, surname = extract_name_parts(name)
        canonical_surname = variant_lookup.get(surname, surname)

        # Get ML birth year estimate if available
        ml_birth_year = None
        if birth_year_estimates and iid in birth_year_estimates:
            ml_birth_year = birth_year_estimates[iid].get("birth_year_estimate")

        # Get metadata birth year
        meta_birth_year = ident.get("metadata", {}).get("birth_year") if isinstance(ident.get("metadata"), dict) else None
        # Also check top-level birth_year
        birth_year = meta_birth_year or ident.get("birth_year") or ml_birth_year

        # Also build canonical forms for all name words (for maiden name matching)
        all_name_words = [w.lower() for w in name.split()]
        all_canonical_words = {variant_lookup.get(w, w) for w in all_name_words}

        identity_records.append({
            "identity_id": iid,
            "name": name,
            "normalized_name": norm_name,
            "first_parts": first_parts,
            "surname": surname,
            "canonical_surname": canonical_surname,
            "all_canonical_words": all_canonical_words,
            "birth_year": birth_year,
            "state": state,
        })

    result = MatchResult()
    matched_identity_ids = set()
    matched_gedcom_xrefs = set()

    # Layer 1: Exact name matches (with surname variant expansion)
    for xref, indi in parsed_gedcom.individuals.items():
        if xref in matched_gedcom_xrefs:
            continue

        ged_given = indi.given_name.lower().strip()
        ged_surname = indi.surname.lower().strip()
        ged_canonical_surname = variant_lookup.get(ged_surname, ged_surname)

        best_match = None
        best_score = 0.0

        for rec in identity_records:
            if rec["identity_id"] in matched_identity_ids:
                continue

            # Check surname match (exact or variant)
            # Also check maiden name: GEDCOM "Cukran" matches archive word "Cukran" in "Victoria Cukran Capeluto"
            surname_match = (
                rec["surname"] == ged_surname or
                rec["canonical_surname"] == ged_canonical_surname or
                ged_canonical_surname in rec["all_canonical_words"]
            )
            if not surname_match:
                continue

            # Check first name match
            # GEDCOM "Leon" should match archive "Big Leon" (after prefix stripping)
            rec_first = rec["first_parts"]
            first_sim = name_similarity(ged_given, rec_first)

            # Also check if GEDCOM given name is contained in archive first name
            contains_match = ged_given and ged_given in rec_first.split()

            # Also check maiden name match: GEDCOM given "Victoria" + surname "Cukran"
            # should match archive "Victoria Cukran Capeluto" where given="victoria cukran"
            maiden_match = (
                ged_given and ged_surname and
                ged_given in rec_first.split() and
                ged_surname in rec["first_parts"].split()
            )

            if first_sim >= 0.8 or contains_match or maiden_match:
                score = 0.8  # Base score for exact match layer

                # Bonus for exact contains (breaks ties)
                if contains_match:
                    score += 0.02
                # Bonus for maiden name match (high confidence)
                if maiden_match:
                    score += 0.05

                # Boost by date proximity
                if indi.birth_year and rec["birth_year"]:
                    year_diff = abs(indi.birth_year - rec["birth_year"])
                    if year_diff <= 3:
                        score += 0.15
                    elif year_diff <= 10:
                        score += 0.05

                # Boost for CONFIRMED identities
                if rec["state"] == "CONFIRMED":
                    score += 0.05

                if score > best_score:
                    best_score = score
                    reason_parts = [f"surname variant match ({ged_surname} → {rec['canonical_surname']})"]
                    if maiden_match:
                        reason_parts.append(f"maiden name match ({ged_given} {ged_surname} in '{rec['first_parts']}')")
                    elif contains_match:
                        reason_parts.append(f"given name contained in '{rec['first_parts']}'")
                    else:
                        reason_parts.append(f"given name similarity {first_sim:.0%}")
                    if indi.birth_year and rec["birth_year"]:
                        reason_parts.append(f"birth year diff: {abs(indi.birth_year - rec['birth_year'])} years")
                    best_match = MatchProposal(
                        gedcom_individual=indi,
                        identity_id=rec["identity_id"],
                        identity_name=rec["name"],
                        match_score=min(1.0, best_score),
                        match_reason="; ".join(reason_parts),
                        match_layer=1,
                    )

        if best_match:
            result.proposals.append(best_match)
            matched_identity_ids.add(best_match.identity_id)
            matched_gedcom_xrefs.add(xref)

    # Layer 2: Fuzzy name + date proximity
    for xref, indi in parsed_gedcom.individuals.items():
        if xref in matched_gedcom_xrefs:
            continue

        ged_full = f"{indi.given_name} {indi.surname}".strip().lower()

        best_match = None
        best_score = 0.0

        for rec in identity_records:
            if rec["identity_id"] in matched_identity_ids:
                continue

            # Full name similarity
            full_sim = name_similarity(ged_full, rec["normalized_name"])

            # Date proximity bonus
            date_bonus = 0.0
            if indi.birth_year and rec["birth_year"]:
                year_diff = abs(indi.birth_year - rec["birth_year"])
                if year_diff <= 5:
                    date_bonus = 0.2
                elif year_diff <= 10:
                    date_bonus = 0.1

            combined = full_sim * 0.7 + date_bonus + (0.05 if rec["state"] == "CONFIRMED" else 0)

            if combined > 0.7 and combined > best_score:
                best_score = combined
                best_match = MatchProposal(
                    gedcom_individual=indi,
                    identity_id=rec["identity_id"],
                    identity_name=rec["name"],
                    match_score=min(1.0, combined),
                    match_reason=f"fuzzy name similarity {full_sim:.0%}, date proximity bonus {date_bonus:.0%}",
                    match_layer=2,
                )

        if best_match:
            result.proposals.append(best_match)
            matched_identity_ids.add(best_match.identity_id)
            matched_gedcom_xrefs.add(xref)

    # Collect unmatched
    for xref, indi in parsed_gedcom.individuals.items():
        if xref not in matched_gedcom_xrefs:
            result.unmatched_gedcom.append(indi)

    for rec in identity_records:
        if rec["identity_id"] not in matched_identity_ids:
            result.unmatched_identities.append(rec["identity_id"])

    # Sort proposals by score (highest first)
    result.proposals.sort(key=lambda p: p.match_score, reverse=True)

    return result
