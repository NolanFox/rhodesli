"""GEDCOM context builder for Gemini prompt enrichment.

Builds per-photo context strings at 5 enrichment levels:
  - none: empty string (baseline)
  - full: all events for identified people
  - curated: events within ±15yr of photo_date_estimate
  - first_order: full + all events for immediate family
  - co_occurrence: first_order + events for anyone sharing ANY photo

Each level adds more genealogical context to the Gemini prompt,
at the cost of more tokens. Designed for the 2×5 comparison matrix
(Flash/Pro × 5 variants).

Session: 61C | AD-146
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

VARIANTS = ["none", "full", "curated", "first_order", "co_occurrence"]


def find_business_owner_context(
    visible_text: str,
    parsed_gedcom,
    photo_date_estimate: Optional[int] = None,
) -> str:
    """Search GEDCOM individuals for name matches in visible text (e.g. signage).

    When a photo contains text like "LEON'S RESTAURANT", this function finds
    GEDCOM individuals named "Leon" and returns their residential history.
    This helps Gemini infer location from business owners who may not be
    pictured in the photo. (AD-210)

    Args:
        visible_text: Text visible in the photo (e.g. signage, storefronts)
        parsed_gedcom: ParsedGedcom object
        photo_date_estimate: Estimated year of photo (for filtering events)

    Returns:
        Context string for business owner matches, or empty string if none found.
    """
    if not visible_text or not parsed_gedcom:
        return ""

    # Normalize visible text: uppercase, strip possessives and punctuation
    import re

    text_upper = visible_text.upper()
    # Extract individual words (3+ chars to avoid noise)
    words = set(re.findall(r"[A-Z]{3,}", text_upper))

    if not words:
        return ""

    matches = []
    for xref_id, indi in parsed_gedcom.individuals.items():
        # Check if given name or surname appears in the visible text
        given_upper = indi.given_name.upper() if indi.given_name else ""
        surname_upper = indi.surname.upper() if indi.surname else ""

        matched = False
        if given_upper and len(given_upper) >= 3 and given_upper in words:
            matched = True
        if surname_upper and len(surname_upper) >= 3 and surname_upper in words:
            matched = True

        if matched:
            matches.append(indi)

    if not matches:
        return ""

    # Build context for matched individuals (residential history is most useful)
    sections = []
    for indi in matches:
        section = _build_person_context(indi, parsed_gedcom, "full", photo_date_estimate)
        if section:
            sections.append(f"[Business owner candidate — name matches visible text]\n{section}")

    if not sections:
        return ""

    header = "BUSINESS OWNER CONTEXT (names found in visible text/signage):"
    return f"{header}\n\n" + "\n\n".join(sections)


def build_photo_context(
    photo_id: str,
    identified_faces: list,
    parsed_gedcom,
    gedcom_face_links: dict,
    identities: dict,
    photo_index: dict = None,
    variant: str = "curated",
    photo_date_estimate: Optional[int] = None,
    visible_text: Optional[str] = None,
) -> str:
    """Build GEDCOM context for all identified people in a photo.

    Args:
        photo_id: Photo ID from photo_index
        identified_faces: List of face_ids in this photo with confirmed identities
        parsed_gedcom: ParsedGedcom object (from gedcom_parser.parse_gedcom)
        gedcom_face_links: Dict mapping identity_id -> gedcom_xref
        identities: Dict of identity records (from identities.json)
        photo_index: Photo index data (for co-occurrence variant)
        variant: One of "none", "full", "curated", "first_order", "co_occurrence"
        photo_date_estimate: Estimated year of photo (for curated variant)
        visible_text: Text visible in the photo (signage, storefronts) for
            business owner lookup (AD-210)

    Returns:
        Context string for Gemini prompt injection (empty for "none")
    """
    if variant == "none" or not identified_faces:
        return ""

    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant: {variant}. Must be one of {VARIANTS}")

    sections = []

    for face_id in identified_faces:
        # Find the identity for this face
        identity_id = _find_identity_for_face(face_id, identities)
        if not identity_id:
            continue

        # Find the GEDCOM individual linked to this identity
        gedcom_xref = gedcom_face_links.get(identity_id)
        if not gedcom_xref:
            continue

        indi = parsed_gedcom.individuals.get(gedcom_xref)
        if not indi:
            continue

        person_section = _build_person_context(indi, parsed_gedcom, variant, photo_date_estimate)
        if person_section:
            sections.append(person_section)

    # Co-occurrence: add context for people sharing photos with identified people
    if variant == "co_occurrence" and photo_index:
        co_people = _get_co_occurring_people(
            identified_faces, identities, photo_index, gedcom_face_links, parsed_gedcom
        )
        for indi in co_people:
            section = _build_person_context(indi, parsed_gedcom, "full", photo_date_estimate)
            if section:
                sections.append(f"[Co-occurring person]\n{section}")

    # Add business owner context if visible text provided (AD-210)
    if visible_text and parsed_gedcom:
        owner_context = find_business_owner_context(visible_text, parsed_gedcom, photo_date_estimate)
        if owner_context:
            sections.append(owner_context)

    if not sections:
        return ""

    header = "GENEALOGICAL CONTEXT FOR IDENTIFIED INDIVIDUALS:"
    context = f"{header}\n\n" + "\n\n".join(sections)

    # Add structured confirmed identities block (AD-234)
    confirmed_block = _build_confirmed_identities_block(identified_faces, identities, gedcom_face_links)
    if confirmed_block:
        context = f"{confirmed_block}\n\n{context}"

    return context


def _build_person_context(indi, parsed_gedcom, variant, photo_date_estimate=None):
    """Build context string for a single person."""
    lines = [f"Person: {indi.full_name}"]

    # Always include birth/death with confidence annotation (AD-234)
    if indi.birth:
        birth_str = f"  Born: {indi.birth.raw_date or '?'}"
        if indi.birth.place:
            birth_str += f" in {indi.birth.place}"
        # Annotate date confidence for Gemini
        if indi.birth.date and getattr(indi.birth.date, "modifier", None):
            birth_str += f" [{indi.birth.date.modifier} — use cautiously for age calculations]"
        lines.append(birth_str)

    if indi.death:
        death_str = f"  Died: {indi.death.raw_date or '?'}"
        if indi.death.place:
            death_str += f" in {indi.death.place}"
        lines.append(death_str)

    # Events — separate residence/occupation for location summary
    events = indi.events
    if variant == "curated" and photo_date_estimate:
        events = _filter_events_by_date(events, photo_date_estimate, window=15)

    residence_events = []
    occupation_events = []
    other_events = []
    for event in events:
        if event.event_type == "residence":
            residence_events.append(event)
        elif event.event_type == "occupation":
            occupation_events.append(event)
        else:
            other_events.append(event)

    # Residential history (location-critical, shown prominently)
    if residence_events:
        lines.append("  Residential History:")
        for event in residence_events:
            r_str = f"    {event.raw_date or '?'}"
            if event.place:
                r_str += f": {event.place}"
            lines.append(r_str)

    # Occupation (location-relevant)
    for event in occupation_events:
        event_str = f"  Occupation: {event.raw_date or '?'}"
        if event.place:
            event_str += f" in {event.place}"
        lines.append(event_str)

    # Other events
    for event in other_events:
        event_str = f"  {event.event_type.title()}: {event.raw_date or '?'}"
        if event.place:
            event_str += f" in {event.place}"
        # Tag immigration/emigration as transit (AD-209)
        if event.event_type in ("immigration", "emigration"):
            event_str += " [PORT OF ENTRY — transit point, NOT necessarily residence]"
        lines.append(event_str)

    # Spouse timeline (AD-234: chronological with death dates + photo constraints)
    spouse_timeline = _build_spouse_timeline(indi, parsed_gedcom)
    if spouse_timeline:
        lines.extend(spouse_timeline)
    else:
        # Fallback: simple marriage listing
        marriages = parsed_gedcom.get_marriages(indi)
        for marriage in marriages:
            m_str = f"  Marriage: {marriage.raw_date or '?'}"
            if marriage.place:
                m_str += f" in {marriage.place}"
            lines.append(m_str)

    # First-order connections
    if variant in ("first_order", "co_occurrence"):
        family_lines = _build_family_context(indi, parsed_gedcom, photo_date_estimate)
        if family_lines:
            lines.extend(family_lines)

    return "\n".join(lines)


def _build_spouse_timeline(indi, parsed_gedcom) -> list[str]:
    """Build chronological spouse timeline with death dates and photo constraints.

    AD-234: For people with multiple spouses, this provides critical dating
    constraints. If spouse A died in 1966 and spouse B was married after that,
    any photo with spouse B must be post-1966.

    Returns list of context lines, or empty list if no spouses found.
    """
    spouses_with_families = []
    for fam_xref in indi.family_as_spouse:
        fam = parsed_gedcom.families.get(fam_xref)
        if not fam:
            continue
        # Find the spouse (the other person in this family)
        spouse_xref = None
        if fam.husband_xref == indi.xref_id:
            spouse_xref = fam.wife_xref
        elif fam.wife_xref == indi.xref_id:
            spouse_xref = fam.husband_xref
        if not spouse_xref:
            continue
        spouse = parsed_gedcom.individuals.get(spouse_xref)
        if not spouse:
            continue
        spouses_with_families.append((spouse, fam))

    if not spouses_with_families:
        return []

    # Sort by marriage date (earliest first), then by spouse birth year
    def sort_key(item):
        spouse, fam = item
        if fam.marriage and fam.marriage.date and fam.marriage.date.year:
            return fam.marriage.date.year
        if spouse.birth_year:
            return spouse.birth_year
        return 9999

    spouses_with_families.sort(key=sort_key)

    lines = [f"  SPOUSE TIMELINE for {indi.full_name}:"]
    prev_spouse_death = None

    for i, (spouse, fam) in enumerate(spouses_with_families, 1):
        # Marriage info
        marriage_str = ""
        if fam.marriage:
            marriage_str = f"married {fam.marriage.raw_date or '?'}"
            if fam.marriage.place:
                marriage_str += f" ({fam.marriage.place})"
        else:
            marriage_str = "married [date unknown]"

        # Spouse death info
        death_str = ""
        if spouse.death:
            death_str = f"died {spouse.death.raw_date or '?'}"
            if spouse.death_place:
                death_str += f" ({spouse.death_place})"

        # Build the spouse entry
        entry = f"    {i}. {spouse.full_name} — {marriage_str}"
        if death_str:
            entry += f" — {death_str}"
        lines.append(entry)

        # Photo dating constraint
        constraint_parts = []
        if fam.marriage and fam.marriage.date and fam.marriage.date.year:
            start_year = fam.marriage.date.year
        elif prev_spouse_death:
            start_year = prev_spouse_death
        else:
            start_year = None

        end_year = spouse.death_year

        if start_year and end_year:
            lines.append(f"       PHOTOS WITH {spouse.given_name or spouse.full_name}: must be {start_year}-{end_year}")
        elif start_year:
            lines.append(f"       PHOTOS WITH {spouse.given_name or spouse.full_name}: must be after {start_year}")
        elif end_year:
            lines.append(f"       PHOTOS WITH {spouse.given_name or spouse.full_name}: must be before {end_year}")

        # Track for next spouse's constraint
        if spouse.death_year:
            prev_spouse_death = spouse.death_year

    return lines


def _build_family_context(indi, parsed_gedcom, photo_date_estimate=None):
    """Build context for immediate family members.

    Enhanced to include residential addresses and occupation data for spouses
    and parents, and children's birth places prominently for location inference.
    """
    lines = []

    # Parents
    parents = parsed_gedcom.get_parents(indi)
    for parent in parents:
        p_str = f"  Parent: {parent.full_name}"
        if parent.birth and parent.birth_year:
            p_str += f" (b.{parent.birth_year})"
        if parent.birth_place:
            p_str += f", born in {parent.birth_place}"
        lines.append(p_str)
        # Include parent events (residence and occupation for location context)
        for event in parent.events:
            e_str = f"    {event.event_type.title()}: {event.raw_date or '?'}"
            if event.place:
                e_str += f" in {event.place}"
            # Tag immigration/emigration as transit (AD-209)
            if event.event_type in ("immigration", "emigration"):
                e_str += " [PORT OF ENTRY — transit point, NOT necessarily residence]"
            lines.append(e_str)

    # Spouses (with residence and occupation events for location context)
    spouses = parsed_gedcom.get_spouses(indi)
    for spouse in spouses:
        s_str = f"  Spouse: {spouse.full_name}"
        if spouse.birth and spouse.birth_year:
            s_str += f" (b.{spouse.birth_year})"
        if spouse.birth_place:
            s_str += f", born in {spouse.birth_place}"
        lines.append(s_str)
        # Include spouse events that help with location
        for event in spouse.events:
            if event.event_type in ("residence", "occupation", "immigration", "emigration"):
                e_str = f"    {event.event_type.title()}: {event.raw_date or '?'}"
                if event.place:
                    e_str += f" in {event.place}"
                # Tag immigration/emigration as transit (AD-209)
                if event.event_type in ("immigration", "emigration"):
                    e_str += " [PORT OF ENTRY — transit point, NOT necessarily residence]"
                lines.append(e_str)

    # Children (with birth dates and places — critical for location + date inference)
    children = parsed_gedcom.get_children(indi)
    if children:
        lines.append("  Children (birth dates help narrow photo date and location):")
        for child in children:
            c_str = f"    {child.full_name}"
            if child.birth and child.birth_year:
                c_str += f" (b.{child.birth_year}"
                if child.birth and child.birth.date and child.birth.date.month:
                    month_names = {
                        1: "Jan",
                        2: "Feb",
                        3: "Mar",
                        4: "Apr",
                        5: "May",
                        6: "Jun",
                        7: "Jul",
                        8: "Aug",
                        9: "Sep",
                        10: "Oct",
                        11: "Nov",
                        12: "Dec",
                    }
                    c_str += f" {month_names.get(child.birth.date.month, '')}"
                c_str += ")"
            if child.birth_place:
                c_str += f", born in {child.birth_place}"
            lines.append(c_str)

    # Siblings (with residence and occupation events for location context)
    siblings = parsed_gedcom.get_siblings(indi)
    for sibling in siblings:
        sb_str = f"  Sibling: {sibling.full_name}"
        if sibling.birth and sibling.birth_year:
            sb_str += f" (b.{sibling.birth_year})"
        if sibling.birth_place:
            sb_str += f", born in {sibling.birth_place}"
        lines.append(sb_str)
        # Include sibling events that help with location (AD-210)
        for event in sibling.events:
            if event.event_type in ("residence", "occupation", "immigration", "emigration"):
                e_str = f"    {event.event_type.title()}: {event.raw_date or '?'}"
                if event.place:
                    e_str += f" in {event.place}"
                if event.event_type in ("immigration", "emigration"):
                    e_str += " [PORT OF ENTRY — transit point, NOT necessarily residence]"
                lines.append(e_str)

    return lines


def _filter_events_by_date(events, photo_date, window=15):
    """Filter events to those within ±window years of photo_date."""
    filtered = []
    for event in events:
        if not event.date or not event.date.year:
            # Include events without dates (still useful context)
            filtered.append(event)
            continue
        if abs(event.date.year - photo_date) <= window:
            filtered.append(event)
    return filtered


def _build_confirmed_identities_block(identified_faces: list, identities: dict, gedcom_face_links: dict) -> str:
    """Build a structured block listing confirmed identities in this photo.

    AD-234: Provides Gemini with clear signals about who is definitively
    identified vs who is a candidate. This helps Gemini use the right names
    and avoid contradicting confirmed identifications.
    """
    confirmed = []
    for face_id in identified_faces:
        identity_id = _find_identity_for_face(face_id, identities)
        if not identity_id:
            continue
        identity = identities.get(identity_id, {})
        name = identity.get("name", "Unknown")
        state = identity.get("state", "")
        if state == "CONFIRMED" and not name.startswith("Unidentified"):
            has_gedcom = identity_id in gedcom_face_links
            confirmed.append((name, has_gedcom))

    if not confirmed:
        return ""

    lines = ["CONFIRMED IDENTITIES IN THIS PHOTO:"]
    for name, has_gedcom in confirmed:
        marker = " [GEDCOM linked]" if has_gedcom else ""
        lines.append(f"  - {name}{marker}")
    lines.append("Use these names when describing faces. Do NOT contradict confirmed identifications.")

    return "\n".join(lines)


def _find_identity_for_face(face_id, identities):
    """Find which identity a face belongs to.

    Prefers CONFIRMED identities over PROPOSED/INBOX, since a face_id
    may appear in multiple identities (e.g., INBOX + CONFIRMED).
    """
    fallback = None
    for identity_id, data in identities.items():
        anchor_ids = data.get("anchor_ids", [])
        candidate_ids = data.get("candidate_ids", [])
        if face_id in anchor_ids or face_id in candidate_ids:
            if data.get("state") == "CONFIRMED":
                return identity_id
            if fallback is None:
                fallback = identity_id
    return fallback


def _get_co_occurring_people(identified_faces, identities, photo_index, gedcom_face_links, parsed_gedcom):
    """Get all GEDCOM individuals who share any photo with identified faces."""
    face_to_photo = photo_index.get("face_to_photo", {})

    # Find all photos containing our identified faces
    related_photos = set()
    for face_id in identified_faces:
        photo_id = face_to_photo.get(face_id)
        if photo_id:
            related_photos.add(photo_id)

    # For each identity that has a face in any of those photos
    co_individuals = set()
    already_included = set()

    # Track which identities we already included
    for face_id in identified_faces:
        identity_id = _find_identity_for_face(face_id, identities)
        if identity_id:
            already_included.add(identity_id)

    # Find faces in related photos
    photos = photo_index.get("photos", {})
    for photo_id in related_photos:
        photo = photos.get(photo_id, {})
        for face_id in photo.get("face_ids", []):
            identity_id = _find_identity_for_face(face_id, identities)
            if identity_id and identity_id not in already_included:
                gedcom_xref = gedcom_face_links.get(identity_id)
                if gedcom_xref:
                    indi = parsed_gedcom.individuals.get(gedcom_xref)
                    if indi:
                        co_individuals.add(indi.xref_id)
                        already_included.add(identity_id)

    return [parsed_gedcom.individuals[xref] for xref in co_individuals if xref in parsed_gedcom.individuals]


def estimate_context_tokens(context_string: str) -> int:
    """Rough token count for GEDCOM context. ~4 chars per token for English."""
    return len(context_string) // 4


def get_enrichment_delta(baseline_result: dict, enriched_result: dict) -> dict:
    """Compare baseline vs enriched Gemini results.

    Returns dict of what changed and by how much.
    """
    delta = {
        "date_changed": False,
        "location_changed": False,
        "new_evidence_count": 0,
        "confidence_delta": 0,
    }

    b_date = baseline_result.get("date_estimation", {})
    e_date = enriched_result.get("date_estimation", {})

    if b_date.get("estimated_year") != e_date.get("estimated_year"):
        delta["date_changed"] = True
        b_year = b_date.get("estimated_year", 0) or 0
        e_year = e_date.get("estimated_year", 0) or 0
        delta["date_shift_years"] = e_year - b_year

    b_loc = baseline_result.get("location", {})
    e_loc = enriched_result.get("location", {})
    if b_loc.get("city") != e_loc.get("city") or b_loc.get("country") != e_loc.get("country"):
        delta["location_changed"] = True

    b_conf = b_date.get("confidence", 0) or 0
    e_conf = e_date.get("confidence", 0) or 0
    delta["confidence_delta"] = e_conf - b_conf

    return delta


def build_all_variants(
    photo_id: str,
    identified_faces: list,
    parsed_gedcom,
    gedcom_face_links: dict,
    identities: dict,
    photo_index: dict = None,
    photo_date_estimate: Optional[int] = None,
    visible_text: Optional[str] = None,
) -> dict:
    """Build context for all 5 variants. Returns dict of variant -> context string."""
    result = {}
    for variant in VARIANTS:
        context = build_photo_context(
            photo_id=photo_id,
            identified_faces=identified_faces,
            parsed_gedcom=parsed_gedcom,
            gedcom_face_links=gedcom_face_links,
            identities=identities,
            photo_index=photo_index,
            variant=variant,
            photo_date_estimate=photo_date_estimate,
            visible_text=visible_text,
        )
        result[variant] = context
        tokens = estimate_context_tokens(context)
        if tokens > 15000:
            logger.warning(f"Photo {photo_id} variant '{variant}': {tokens} tokens (>15K threshold)")
    return result
