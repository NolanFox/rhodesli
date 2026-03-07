"""Unified Gemini extraction architecture with configurable presets.

One API call per photo extracts everything needed. Presets control which
extraction types are included, saving ~80% on costs vs separate calls.

See AD-143 for decision rationale.

Usage:
    from rhodesli_ml.gemini_extraction import build_extraction_prompt, EXTRACTION_PRESETS

    # Full analysis (batch runs)
    prompt = build_extraction_prompt(preset="full")

    # Quick estimate (interactive upload)
    prompt = build_extraction_prompt(preset="quick")

    # Custom: full minus face_analysis
    prompt = build_extraction_prompt(preset="full", exclude=["face_analysis"])
"""

from __future__ import annotations

EXTRACTION_PRESETS: dict[str, dict[str, bool]] = {
    "full": {
        "date_estimation": True,
        "face_analysis": True,
        "location": True,
        "cultural_markers": True,
        "clothing_era": True,
        "photo_technique": True,
        "text_signage": True,
        "group_composition": True,
        "photo_condition": True,
        "subject_ages": True,
    },
    "quick": {
        "date_estimation": True,
        "face_analysis": False,
        "location": True,
        "cultural_markers": False,
        "clothing_era": False,
        "photo_technique": False,
        "text_signage": True,
        "group_composition": False,
        "photo_condition": False,
        "subject_ages": False,
    },
    "compare": {
        "date_estimation": True,
        "face_analysis": True,
        "location": False,
        "cultural_markers": False,
        "clothing_era": False,
        "photo_technique": False,
        "text_signage": False,
        "group_composition": False,
        "photo_condition": False,
        "subject_ages": True,
    },
}

# JSON output schema fragments per extraction type
_SCHEMA_FRAGMENTS: dict[str, str] = {
    "date_estimation": """"date_estimation": {
    "evidence": {
      "print_format": [{"cue": "...", "strength": "strong|moderate|weak", "suggested_range": [YYYY, YYYY]}],
      "fashion": [...],
      "environment": [...],
      "technology": [...]
    },
    "cultural_lag_applied": true,
    "cultural_lag_note": "...",
    "estimated_decade": DDDD,
    "best_year_estimate": YYYY,
    "confidence": "high|medium|low",
    "probable_range": [YYYY, YYYY],
    "decade_probabilities": {"1920": 0.05, "1930": 0.55, ...},
    "reasoning_summary": "1-2 sentences"
  }""",
    "face_analysis": """"face_analysis": [
    {"face_index": 0, "estimated_age": 35, "gender": "male|female", "description": "..."}
  ]""",
    "location": """"location": {
    "place": "Rhodes, Greece",
    "confidence": "high|medium|low",
    "visual_evidence": "Mediterranean stone architecture, visible Greek signage",
    "biographical_evidence": "Family resided at 33 Elizabeth St, Asheville NC per GEDCOM records",
    "missing_child_analysis": "3 of 4 children visible; youngest (born 1935) absent, suggesting pre-1935"
  }""",
    "cultural_markers": """"cultural_markers": ["Sephardic formal attire", "studio backdrop typical of Rhodes photographers"]""",
    "clothing_era": '''"clothing_notes": "Man in dark three-piece suit with pocket watch chain..."''',
    "photo_technique": """"photo_technique": {
    "type": "gelatin silver print",
    "format": "cabinet card",
    "is_color": false,
    "condition": "good"
  }""",
    "text_signage": """"visible_text": {
    "detected": true,
    "text": "A mi querida Estrella...",
    "language": "Ladino",
    "script": "Latin"
  }""",
    "group_composition": """"group_composition": {
    "type": "formal_portrait|candid|ceremony|group_photo",
    "people_count": 3,
    "arrangement": "seated family group with standing elder"
  }""",
    "photo_condition": """"condition": {
    "overall": "good|fair|poor|excellent",
    "issues": ["slight fading", "corner damage"]
  }""",
    "subject_ages": """"subject_ages": [45, 12, 8]""",
}

# Prompt section fragments per extraction type
_PROMPT_SECTIONS: dict[str, str] = {
    "date_estimation": """## Date Estimation
Examine FOUR evidence categories: (1) Print/Physical Format, (2) Fashion/Grooming,
(3) Environmental/Geographic, (4) Technological/Object Markers.
Rate each cue as STRONG, MODERATE, or WEAK. Provide suggested date ranges.
The decade_probabilities MUST sum to 1.0 (only decades with >0.01 probability).
best_year_estimate should be your best point estimate, NOT just the midpoint.""",
    "face_analysis": """## Face Analysis
For each detected face (use face_index starting from 0, left-to-right),
estimate age, gender, and provide a brief physical description.
{face_coordinates_section}""",
    "location": """## Location Identification
Identify the likely geographic location using BOTH visual evidence AND biographical context.

**Step 1: Visual Analysis**
Examine architecture style, vegetation, signage, street features, and environmental cues.

**Step 2: Biographical Cross-Reference** (if genealogical context provided)
Cross-reference visual observations with known biographical data:
- Compare visual clues against known family addresses and residential history
- Check if children's birth places match the apparent location
- Consider the "missing child" test: count people visible vs known children at a given date
  to narrow the date AND location (e.g., if 3 of 4 children are present, the photo predates
  the 4th child's birth)
- Use occupation/workplace info to narrow geographic possibilities
- Consider migration patterns: where did this family live at different times?

**Step 2b: Business Name Cross-Reference**
- Cross-reference visible business names (signs, storefronts) with known family members
- Example: A sign reading "LEON'S RESTAURANT" + a family member named "Leon Capeluto"
  strongly suggests this is Leon's business. Use Leon's known locations.
- Business name matches are VERY STRONG location evidence.

**Step 2c: Immigration & Transit Disambiguation**
- Passenger list and immigration records show PORTS OF ENTRY, which may be transit points
  (e.g., San Francisco was a major Pacific port -- arrivals often continued to other cities)
- Do NOT assume a port-of-entry city is where someone lived
- Residence events, occupation events, and children's birth places are more reliable
  indicators of where someone actually lived than immigration ports
- When visual evidence (signage, architecture) conflicts with transit/immigration records,
  PREFER the visual evidence for determining photo location

**Step 3: Confidence Assessment**
Rate confidence. If visual evidence AND biographical data agree on a location, rate
confidence higher. If they conflict, explain the discrepancy.""",
    "cultural_markers": """## Cultural Markers
Identify any culturally specific items, traditions, or markers visible
(e.g., religious items, traditional dress, community-specific customs).""",
    "clothing_era": """## Clothing & Fashion Analysis
Describe notable clothing and accessories. Note era-specific fashion details
that help with dating or cultural context.""",
    "photo_technique": """## Photographic Technique
Identify the photographic process (daguerreotype, albumen, gelatin silver, etc.),
format (cabinet card, carte de visite, snapshot), and color type.""",
    "text_signage": """## Text & Signage Detection
Transcribe ALL visible text (handwritten inscriptions, printed text, signs,
documents). Preserve original language and spelling. Detect language and script.
Inscriptions may be in Ladino, French, Italian, Greek, or English.
Handwritten text may use Solitreo (Sephardic cursive Hebrew script).""",
    "group_composition": """## Group Composition
Classify the photo type (formal portrait, candid, ceremony, group photo).
Describe the arrangement of people and count total visible.""",
    "photo_condition": """## Photo Condition Assessment
Rate overall condition (excellent/good/fair/poor) and list specific issues
(fading, tears, stains, water damage, foxing).""",
    "subject_ages": """## Subject Age Estimation
Estimate the approximate age of each visible person as integers,
ordered left-to-right as they appear in the photo.""",
}

_PREAMBLE = """You are a forensic photo analyst specializing in dating historical photographs
from Sephardic Jewish communities, particularly from Rhodes (Dodecanese), Greece and
diaspora communities in New York City, Miami, and Tampa, Florida.

## Cultural Context (IMPORTANT)
- Fashion in Rhodes and immigrant communities often LAGGED 5-15 years behind mainstream
- Studio portraits used deliberately conservative formal attire
- Early immigrant photos show a mix of old-world and new-world styles
- Rhodes stone architecture spans centuries — it is a WEAK dating signal alone
"""


def build_extraction_prompt(
    preset: str = "full",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    face_coordinates: list[dict] | None = None,
    verified_facts: dict | None = None,
    gedcom_context: str | None = None,
    photo_metadata: dict | None = None,
) -> str:
    """Build a unified Gemini prompt that extracts all requested info in one call.

    Args:
        preset: One of EXTRACTION_PRESETS keys ("full", "quick", "compare")
        include: Additional extraction types to enable
        exclude: Extraction types to disable from preset
        face_coordinates: InsightFace bounding box data for face_analysis
        verified_facts: Known facts (confirmed names, dates) for progressive refinement
        gedcom_context: GEDCOM genealogical context string for identified people
        photo_metadata: Dict with collection, source, filename, visible_text keys

    Returns:
        Structured prompt string requesting JSON response
    """
    if preset not in EXTRACTION_PRESETS:
        raise ValueError(f"Unknown preset '{preset}'. Valid: {list(EXTRACTION_PRESETS.keys())}")

    config = EXTRACTION_PRESETS[preset].copy()
    if include:
        for key in include:
            config[key] = True
    if exclude:
        for key in exclude:
            config[key] = False

    # Build prompt sections
    sections = [_PREAMBLE, "## Task\nAnalyze this photograph and extract the following information.\n"]

    # Add verified facts context if available
    if verified_facts:
        facts_section = "## Known Facts (verified by human reviewers)\n"
        if verified_facts.get("confirmed_names"):
            facts_section += f"- Confirmed identities: {', '.join(verified_facts['confirmed_names'])}\n"
        if verified_facts.get("confirmed_date"):
            facts_section += f"- Confirmed date: {verified_facts['confirmed_date']}\n"
        if verified_facts.get("confirmed_location"):
            facts_section += f"- Confirmed location: {verified_facts['confirmed_location']}\n"
        if verified_facts.get("notes"):
            facts_section += f"- Additional context: {verified_facts['notes']}\n"
        facts_section += "\nUse these facts to improve your analysis accuracy.\n"
        sections.append(facts_section)

    # Add GEDCOM genealogical context if provided
    if gedcom_context:
        sections.append(
            f"## Genealogical Context\n{gedcom_context}\n\n"
            "Use this genealogical data to improve date, location, and identity analysis."
        )

    # Add photo metadata context if provided
    if photo_metadata:
        meta_section = "## Photo Metadata Context\n"
        if photo_metadata.get("collection"):
            meta_section += f"Collection: {photo_metadata['collection']}\n"
        if photo_metadata.get("source"):
            meta_section += f"Source: {photo_metadata['source']}\n"
        if photo_metadata.get("filename"):
            meta_section += f"Original filename: {photo_metadata['filename']}\n"
        if photo_metadata.get("visible_text"):
            meta_section += f"Previously extracted text: {photo_metadata['visible_text']}\n"
        meta_section += (
            "\nIMPORTANT: The collection name often indicates the geographic origin "
            "of photos.\n"
            'For example, "Tampa Collection" strongly suggests photos were taken '
            "in or near Tampa.\n"
            "Use this as corroborating evidence alongside visual and biographical "
            "analysis."
        )
        sections.append(meta_section)

    # Add enabled extraction sections
    active_types = [k for k, v in config.items() if v]
    for extraction_type in active_types:
        section = _PROMPT_SECTIONS.get(extraction_type, "")
        if extraction_type == "face_analysis" and face_coordinates:
            coords_text = "InsightFace detected faces at these bounding boxes:\n"
            for i, fc in enumerate(face_coordinates):
                bbox = fc.get("bbox", [])
                coords_text += f"  Face {i}: bbox={bbox}\n"
            section = section.replace("{face_coordinates_section}", coords_text)
        else:
            section = section.replace("{face_coordinates_section}", "")
        sections.append(section)

    # Build JSON schema
    schema_parts = []
    for extraction_type in active_types:
        fragment = _SCHEMA_FRAGMENTS.get(extraction_type)
        if fragment:
            schema_parts.append(f"  {fragment}")

    schema = "{\n" + ",\n".join(schema_parts) + "\n}"
    sections.append(f"\n## Response Format (JSON only)\n{schema}")

    return "\n\n".join(sections)


def get_active_extractions(
    preset: str = "full", include: list[str] | None = None, exclude: list[str] | None = None
) -> list[str]:
    """Return list of active extraction types for a given configuration."""
    if preset not in EXTRACTION_PRESETS:
        raise ValueError(f"Unknown preset '{preset}'")
    config = EXTRACTION_PRESETS[preset].copy()
    if include:
        for key in include:
            config[key] = True
    if exclude:
        for key in exclude:
            config[key] = False
    return [k for k, v in config.items() if v]
