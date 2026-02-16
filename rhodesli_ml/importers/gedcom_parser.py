"""GEDCOM file parser for Rhodesli.

Parses GEDCOM 5.5.1 files and extracts structured individual/family data.
Uses python-gedcom library for file parsing, with custom date handling.

AD-073: GEDCOM parsing strategy
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --- Date Parsing ---

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# Confidence mapping for date modifiers
# HIGH = exact date or year only
# MEDIUM = approximate (ABT, EST, CAL, BET...AND)
# LOW = directional (BEF, AFT) or phrase


@dataclass
class ParsedDate:
    """Structured representation of a GEDCOM date."""
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    modifier: Optional[str] = None  # "about", "before", "after", "between", "estimated", "calculated"
    confidence: str = "HIGH"  # HIGH, MEDIUM, LOW
    raw: str = ""
    year_end: Optional[int] = None  # For BET...AND ranges

    def __repr__(self):
        if self.modifier:
            return f"ParsedDate({self.modifier} {self.year}, confidence={self.confidence})"
        return f"ParsedDate({self.year}, confidence={self.confidence})"


def parse_gedcom_date(date_str: str) -> Optional[ParsedDate]:
    """Parse a GEDCOM date string into a structured ParsedDate.

    Handles formats:
      - "15 MAR 1895" (exact)
      - "MAR 1895" (month + year)
      - "1895" (year only)
      - "ABT 1905" (approximate)
      - "EST 1900" (estimated)
      - "CAL 1890" (calculated)
      - "BEF 1920" (before)
      - "AFT 1890" (after)
      - "BET 1890 AND 1900" (between)
      - "FROM 1920 TO 1945" (period)
      - "INT 1895 (explanation)" (interpreted)
      - "(phrase)" (free text — returns None)
    """
    if not date_str or not date_str.strip():
        return None

    raw = date_str.strip()
    s = raw.upper()

    # Phrase dates in parentheses — not parseable
    if s.startswith("("):
        return None

    # BET ... AND ... range
    bet_match = re.match(r"BET\s+(.+?)\s+AND\s+(.+)", s)
    if bet_match:
        start = _parse_simple_date(bet_match.group(1))
        end = _parse_simple_date(bet_match.group(2))
        if start and end and start.year and end.year:
            midpoint = (start.year + end.year) // 2
            return ParsedDate(
                year=midpoint, modifier="between", confidence="MEDIUM",
                raw=raw, year_end=end.year,
            )
        return None

    # FROM ... TO ... period
    from_match = re.match(r"FROM\s+(.+?)\s+TO\s+(.+)", s)
    if from_match:
        start = _parse_simple_date(from_match.group(1))
        end = _parse_simple_date(from_match.group(2))
        if start and end and start.year and end.year:
            midpoint = (start.year + end.year) // 2
            return ParsedDate(
                year=midpoint, modifier="between", confidence="MEDIUM",
                raw=raw, year_end=end.year,
            )
        return None

    # INT date (explanation) — interpreted date
    int_match = re.match(r"INT\s+(.+?)(?:\s*\(.*\))?$", s)
    if int_match:
        inner = _parse_simple_date(int_match.group(1))
        if inner:
            inner.modifier = "interpreted"
            inner.confidence = "MEDIUM"
            inner.raw = raw
            return inner
        return None

    # Modifier prefixes: ABT, EST, CAL, BEF, AFT
    for prefix, modifier, confidence in [
        ("ABT", "about", "MEDIUM"),
        ("EST", "estimated", "MEDIUM"),
        ("CAL", "calculated", "MEDIUM"),
        ("BEF", "before", "LOW"),
        ("AFT", "after", "LOW"),
    ]:
        if s.startswith(prefix + " "):
            rest = s[len(prefix):].strip()
            inner = _parse_simple_date(rest)
            if inner:
                inner.modifier = modifier
                inner.confidence = confidence
                inner.raw = raw
                # For BEF/AFT, adjust year slightly
                if modifier == "before" and inner.year:
                    inner.year = inner.year - 1
                elif modifier == "after" and inner.year:
                    inner.year = inner.year + 1
                return inner
            return None

    # Plain date (no modifier)
    result = _parse_simple_date(s)
    if result:
        result.raw = raw
    return result


def _parse_simple_date(s: str) -> Optional[ParsedDate]:
    """Parse a simple date: DD MMM YYYY, MMM YYYY, or YYYY."""
    s = s.strip()

    # Handle dual-year: 1750/51
    s = re.sub(r"(\d{4})/\d{2}$", r"\1", s)

    # DD MMM YYYY
    m = re.match(r"(\d{1,2})\s+([A-Z]{3})\s+(\d{4})", s)
    if m:
        day, month_str, year = int(m.group(1)), m.group(2), int(m.group(3))
        month = MONTH_MAP.get(month_str)
        if month:
            return ParsedDate(year=year, month=month, day=day, confidence="HIGH")

    # MMM YYYY
    m = re.match(r"([A-Z]{3})\s+(\d{4})", s)
    if m:
        month_str, year = m.group(1), int(m.group(2))
        month = MONTH_MAP.get(month_str)
        if month:
            return ParsedDate(year=year, month=month, confidence="HIGH")

    # YYYY only
    m = re.match(r"(\d{4})$", s)
    if m:
        return ParsedDate(year=int(m.group(1)), confidence="HIGH")

    return None


# --- Individual and Family data classes ---

@dataclass
class GedcomEvent:
    """An event (birth, death, marriage, etc.) from a GEDCOM file."""
    event_type: str  # "birth", "death", "marriage", "burial", etc.
    date: Optional[ParsedDate] = None
    place: Optional[str] = None
    raw_date: str = ""


@dataclass
class GedcomIndividual:
    """A parsed individual from a GEDCOM file."""
    xref_id: str  # e.g., "@I1@"
    given_name: str = ""
    surname: str = ""
    full_name: str = ""
    gender: str = "U"  # M, F, U
    birth: Optional[GedcomEvent] = None
    death: Optional[GedcomEvent] = None
    events: list = field(default_factory=list)  # Other life events
    family_as_spouse: list = field(default_factory=list)  # FAM xref_ids where this person is HUSB/WIFE
    family_as_child: list = field(default_factory=list)  # FAM xref_ids where this person is CHIL

    @property
    def birth_year(self) -> Optional[int]:
        if self.birth and self.birth.date:
            return self.birth.date.year
        return None

    @property
    def death_year(self) -> Optional[int]:
        if self.death and self.death.date:
            return self.death.date.year
        return None

    @property
    def birth_place(self) -> Optional[str]:
        if self.birth:
            return self.birth.place
        return None

    @property
    def death_place(self) -> Optional[str]:
        if self.death:
            return self.death.place
        return None


@dataclass
class GedcomFamily:
    """A parsed family unit from a GEDCOM file."""
    xref_id: str  # e.g., "@F1@"
    husband_xref: Optional[str] = None
    wife_xref: Optional[str] = None
    children_xrefs: list = field(default_factory=list)
    marriage: Optional[GedcomEvent] = None


@dataclass
class ParsedGedcom:
    """Complete parsed GEDCOM file."""
    individuals: dict = field(default_factory=dict)  # xref_id -> GedcomIndividual
    families: dict = field(default_factory=dict)  # xref_id -> GedcomFamily
    source_file: str = ""

    @property
    def individual_count(self) -> int:
        return len(self.individuals)

    @property
    def family_count(self) -> int:
        return len(self.families)

    def get_parents(self, individual: GedcomIndividual) -> list:
        """Get parent individuals for a given person."""
        parents = []
        for fam_xref in individual.family_as_child:
            fam = self.families.get(fam_xref)
            if not fam:
                continue
            if fam.husband_xref and fam.husband_xref in self.individuals:
                parents.append(self.individuals[fam.husband_xref])
            if fam.wife_xref and fam.wife_xref in self.individuals:
                parents.append(self.individuals[fam.wife_xref])
        return parents

    def get_children(self, individual: GedcomIndividual) -> list:
        """Get children of a given person."""
        children = []
        for fam_xref in individual.family_as_spouse:
            fam = self.families.get(fam_xref)
            if not fam:
                continue
            for child_xref in fam.children_xrefs:
                if child_xref in self.individuals:
                    children.append(self.individuals[child_xref])
        return children

    def get_spouses(self, individual: GedcomIndividual) -> list:
        """Get spouses of a given person."""
        spouses = []
        for fam_xref in individual.family_as_spouse:
            fam = self.families.get(fam_xref)
            if not fam:
                continue
            if fam.husband_xref == individual.xref_id and fam.wife_xref:
                if fam.wife_xref in self.individuals:
                    spouses.append(self.individuals[fam.wife_xref])
            elif fam.wife_xref == individual.xref_id and fam.husband_xref:
                if fam.husband_xref in self.individuals:
                    spouses.append(self.individuals[fam.husband_xref])
        return spouses

    def get_siblings(self, individual: GedcomIndividual) -> list:
        """Get siblings (same parents) of a given person."""
        siblings = []
        for fam_xref in individual.family_as_child:
            fam = self.families.get(fam_xref)
            if not fam:
                continue
            for child_xref in fam.children_xrefs:
                if child_xref != individual.xref_id and child_xref in self.individuals:
                    siblings.append(self.individuals[child_xref])
        return siblings

    def get_marriages(self, individual: GedcomIndividual) -> list:
        """Get marriage events for a given person."""
        marriages = []
        for fam_xref in individual.family_as_spouse:
            fam = self.families.get(fam_xref)
            if fam and fam.marriage:
                marriages.append(fam.marriage)
        return marriages


def parse_gedcom(filepath: str) -> ParsedGedcom:
    """Parse a GEDCOM file and return structured data.

    Uses python-gedcom library for parsing, then extracts
    individuals, families, and relationships.
    """
    from gedcom.parser import Parser
    from gedcom.element.individual import IndividualElement
    from gedcom.element.family import FamilyElement

    filepath = str(filepath)
    parser = Parser()
    parser.parse_file(filepath)

    result = ParsedGedcom(source_file=Path(filepath).name)

    # First pass: extract all individuals
    for element in parser.get_element_list():
        if isinstance(element, IndividualElement):
            indi = _parse_individual(element)
            result.individuals[indi.xref_id] = indi
        elif isinstance(element, FamilyElement):
            fam = _parse_family(element)
            result.families[fam.xref_id] = fam

    # Second pass: populate family references on individuals
    for fam_xref, fam in result.families.items():
        if fam.husband_xref and fam.husband_xref in result.individuals:
            indi = result.individuals[fam.husband_xref]
            if fam_xref not in indi.family_as_spouse:
                indi.family_as_spouse.append(fam_xref)
        if fam.wife_xref and fam.wife_xref in result.individuals:
            indi = result.individuals[fam.wife_xref]
            if fam_xref not in indi.family_as_spouse:
                indi.family_as_spouse.append(fam_xref)
        for child_xref in fam.children_xrefs:
            if child_xref in result.individuals:
                indi = result.individuals[child_xref]
                if fam_xref not in indi.family_as_child:
                    indi.family_as_child.append(fam_xref)

    return result


def _parse_individual(element) -> GedcomIndividual:
    """Extract structured data from a python-gedcom IndividualElement."""
    xref_id = element.get_pointer()

    # Name parsing
    name_tuple = element.get_name()
    given_name = name_tuple[0] if name_tuple[0] else ""
    surname = name_tuple[1] if name_tuple[1] else ""
    full_name = f"{given_name} {surname}".strip()

    # Gender
    gender = element.get_gender()

    # Birth
    birth_data = element.get_birth_data()
    birth_event = None
    if birth_data:
        date_str = birth_data[0] if birth_data[0] else ""
        place_str = birth_data[1] if birth_data[1] else ""
        parsed_date = parse_gedcom_date(date_str) if date_str else None
        if parsed_date or place_str:
            birth_event = GedcomEvent(
                event_type="birth",
                date=parsed_date,
                place=place_str if place_str else None,
                raw_date=date_str,
            )

    # Death
    death_data = element.get_death_data()
    death_event = None
    if death_data:
        date_str = death_data[0] if death_data[0] else ""
        place_str = death_data[1] if death_data[1] else ""
        parsed_date = parse_gedcom_date(date_str) if date_str else None
        if parsed_date or place_str:
            death_event = GedcomEvent(
                event_type="death",
                date=parsed_date,
                place=place_str if place_str else None,
                raw_date=date_str,
            )

    return GedcomIndividual(
        xref_id=xref_id,
        given_name=given_name,
        surname=surname,
        full_name=full_name,
        gender=gender,
        birth=birth_event,
        death=death_event,
    )


def _parse_family(element) -> GedcomFamily:
    """Extract structured data from a python-gedcom FamilyElement."""
    xref_id = element.get_pointer()

    # Get HUSB, WIFE, CHIL pointers and MARR event from child elements
    husband_xref = None
    wife_xref = None
    children_xrefs = []
    marriage_event = None

    for child in element.get_child_elements():
        tag = child.get_tag()
        if tag == "HUSB":
            husband_xref = child.get_value()
        elif tag == "WIFE":
            wife_xref = child.get_value()
        elif tag == "CHIL":
            children_xrefs.append(child.get_value())
        elif tag == "MARR":
            date_str = ""
            place_str = ""
            for sub in child.get_child_elements():
                if sub.get_tag() == "DATE":
                    date_str = sub.get_value()
                elif sub.get_tag() == "PLAC":
                    place_str = sub.get_value()
            parsed_date = parse_gedcom_date(date_str) if date_str else None
            marriage_event = GedcomEvent(
                event_type="marriage",
                date=parsed_date,
                place=place_str if place_str else None,
                raw_date=date_str,
            )

    return GedcomFamily(
        xref_id=xref_id,
        husband_xref=husband_xref,
        wife_xref=wife_xref,
        children_xrefs=children_xrefs,
        marriage=marriage_event,
    )
