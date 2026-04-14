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
        "scene_description": True,
        "capture_vs_print": True,
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
    "identification": {
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
        "scene_description": True,
        "capture_vs_print": True,
        "event_context": True,
        "relationship_inference": True,
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
    "reasoning_summary": "2-3 sentence explanation of how date was estimated"
  }""",
    "face_analysis": """"face_analysis": [
    {"face_index": 0, "estimated_age": 35, "gender": "male|female", "description": "..."}
  ]""",
    "location": """"location": {
    "place": "Rhodes, Greece",
    "confidence": "high|medium|low",
    "visual_evidence": "Mediterranean stone architecture, visible Greek signage",
    "biographical_evidence": "Family resided at 33 Elizabeth St, Asheville NC per GEDCOM records",
    "missing_child_analysis": "3 of 4 children visible; youngest (born 1935) absent, suggesting pre-1935",
    "source_type": "visual|biographical|both",
    "candidates": [
      {"place": "Asheville, North Carolina", "confidence": "medium", "source": "biographical", "reasoning": "Family address on record"},
      {"place": "Tampa, Florida", "confidence": "low", "source": "biographical", "reasoning": "Later family residence"}
    ]
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
    "scene_description": """"scene_description": "A formal sepia-toned studio portrait of a family group..."  """,
    "capture_vs_print": """"capture_vs_print": {
    "classification": "original_capture|later_print|scan_of_original|uncertain",
    "evidence": "Visible halftone dots suggest newspaper reproduction"
  }""",
    "event_context": """"event_context": {
    "event_type": "wedding_ceremony|wedding_reception|bar_mitzvah|funeral|holiday|school|military|casual|portrait|formal_dinner|party|religious_ceremony|graduation|reunion|unknown",
    "event_subtype": "head table dinner|aisle walk|father-daughter dance|...",
    "role_indicators": [
      {"face_index": 0, "roles": ["bride"]},
      {"face_index": 1, "roles": ["groom"]}
    ],
    "formality_level": "very_formal|formal|semi_formal|casual|intimate"
  }""",
    "relationship_inference": """"relationship_inference": {
    "couple_pairs": [{"face_indices": [0, 1], "confidence": 0.9, "evidence": "Central positioning, matching formal attire, physical proximity"}],
    "parent_child_pairs": [{"parent_index": 0, "child_index": 2, "confidence": 0.8, "evidence": "Age gap ~25 years, protective positioning"}],
    "sibling_pairs": [{"face_indices": [2, 3], "confidence": 0.7, "evidence": "Similar age, matching outfits, side-by-side placement"}],
    "positioning_notes": "Central couple flanked by younger generation, elders seated"
  }""",
}

# Prompt section fragments per extraction type
_PROMPT_SECTIONS: dict[str, str] = {
    "date_estimation": """## Date Estimation
Examine FOUR evidence categories: (1) Print/Physical Format, (2) Fashion/Grooming,
(3) Environmental/Geographic, (4) Technological/Object Markers.
Rate each cue as STRONG, MODERATE, or WEAK. Provide suggested date ranges.
The decade_probabilities MUST sum to 1.0 (only decades with >0.01 probability).
best_year_estimate should be your best point estimate, NOT just the midpoint.
Include a reasoning_summary (2-3 sentences) explaining HOW you arrived at the estimate —
which evidence was strongest, what was ambiguous, and any cultural lag adjustments applied.""",
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
  strongly suggests this is Leon's business. Use Leon's RESIDENTIAL ADDRESS, not his
  relatives' addresses, to determine the photo location.
- Business name matches are the STRONGEST location evidence — stronger than any other signal.
- If a business name matches a family member, the photo location is WHERE THAT PERSON LIVED
  AND WORKED, based on their RESIDENCE events (not immigration/transit records).
- CRITICAL: When a business name match is found AND that person has RESIDENCE events,
  you MUST use the specific city from their residence (e.g., "Asheville, North Carolina")
  as the photo location. Do NOT return just "United States" — return the actual city.

**Step 2c: Immigration & Transit Disambiguation**
- GEDCOM events tagged with [PORT OF ENTRY] are TRANSIT POINTS, not residences
- Passenger list and immigration records show PORTS OF ENTRY which may be transit points
  (e.g., San Francisco was a major Pacific port -- arrivals often continued to other cities)
- Do NOT assume a port-of-entry city is where someone lived
- ONLY use RESIDENCE events, OCCUPATION events, and children's BIRTH PLACES to determine
  where someone actually lived
- Immigration events (even without the [PORT OF ENTRY] tag) should NEVER be used as
  primary evidence for photo location
- When RESIDENCE data exists, it ALWAYS overrides immigration/transit data

**Step 3: Confidence Assessment & Candidates**
Rate confidence. If visual evidence AND biographical data agree on a location, rate
confidence higher. If they conflict, explain the discrepancy.

For "source_type": use "visual" if location is purely from what you see, "biographical"
if purely from GEDCOM/genealogical data, or "both" if evidence from both sources.

IMPORTANT: If you considered multiple locations, list up to 3 alternative "candidates"
with their reasoning. The primary location goes in "place", alternatives in "candidates".
If evidence is genuinely ambiguous with no clear winner, set confidence to "low" and
list all options as candidates.""",
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
    "scene_description": """## Scene Description
Write a detailed 2-4 sentence description of the entire photograph. Include the setting
(studio, outdoor, interior), composition, lighting, and any notable background elements.
This description should capture what a person would see when looking at the photo.""",
    "capture_vs_print": """## Capture vs Print Analysis
Determine whether this is the ORIGINAL photograph or a reproduction.
Look for: halftone dots (newspaper/book reproduction), moiré patterns (scan of print),
visible page edges or binding (book/album scan), digital artifacts vs analog grain,
color shifts from re-photography.
Classify as: original_capture / later_print / scan_of_original / uncertain.
This distinction is CRITICAL — a 1960s reprint of a 1920s photo should be dated to the 1920s.""",
    "event_context": """## Event Context
Identify the type of event or occasion depicted in this photograph.

**Event types** (choose one): wedding_ceremony, wedding_reception, bar_mitzvah, funeral,
holiday, school, military, casual, portrait, formal_dinner, party, religious_ceremony,
graduation, reunion, unknown.

**Event subtype**: Provide a more specific description if possible (e.g., "head table dinner",
"aisle walk", "father-daughter dance", "family seated portrait", "beach outing").

**Role indicators**: For each detected face, identify any event-specific roles visible from
positioning, attire, or ceremony context. Roles include: bride, groom, mother_of_bride,
father_of_bride, mother_of_groom, father_of_groom, bridesmaid, best_man, officiant,
guest, honored_guest. Only assign roles when evidence is clear — omit faces with no
discernible role.

**Formality level**: very_formal (black tie, ceremony), formal (suits/dresses, posed),
semi_formal (smart casual, structured event), casual (everyday clothing, relaxed setting),
intimate (small private gathering).
{face_coordinates_section}""",
    "relationship_inference": """## Relationship Inference
Analyze the spatial arrangement, body language, physical contact, age differences, and
attire coordination to infer likely relationships between people in the photograph.

**Couple pairs**: Identify pairs who appear to be romantic partners (spouses, engaged).
Evidence: matching attire, central positioning together, physical contact (arm-in-arm,
hand-holding), ring fingers, coordinated poses.

**Parent-child pairs**: Identify likely parent-child relationships.
Evidence: significant age gap (typically 20-35 years), protective positioning, resemblance,
hand on shoulder, child seated on lap.

**Sibling pairs**: Identify likely siblings.
Evidence: similar age range, matching or coordinated outfits, side-by-side placement,
physical resemblance.

For each pair, provide a confidence score (0.0-1.0) and specific evidence from the photo.
Only include pairs where you have meaningful evidence — do not guess.

**Positioning notes**: Describe the overall spatial arrangement and what it suggests about
family structure and hierarchy (e.g., "elders seated centrally, younger generation standing behind").
{face_coordinates_section}""",
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
        preset: One of EXTRACTION_PRESETS keys ("full", "quick", "compare", "identification")
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
            "\nNOTE ON COLLECTION NAMES: A collection name indicates WHO HAD these photos and\n"
            "WHERE THEY WERE STORED, not necessarily where the photos were taken. For example,\n"
            'a "Tampa Collection" means the photos were found in Tampa -- but the actual photos\n'
            "may depict locations the family visited or previously lived in (e.g., Asheville, NC;\n"
            "New York; Rhodes).\n"
            "Collection name is WEAK contextual evidence about the collector's later residence.\n"
            "Visual evidence (signage, architecture) and GEDCOM residence data at the time of\n"
            "the photo are MUCH STRONGER signals for actual photo location.\n"
            "Do NOT assume the collection city is the photo location."
        )
        sections.append(meta_section)

    # Add enabled extraction sections
    # Sections that benefit from face coordinate data
    _FACE_COORD_SECTIONS = {"face_analysis", "event_context", "relationship_inference"}
    active_types = [k for k, v in config.items() if v]
    for extraction_type in active_types:
        section = _PROMPT_SECTIONS.get(extraction_type, "")
        if extraction_type in _FACE_COORD_SECTIONS and face_coordinates:
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


def build_response_schema(
    preset: str = "full",
    include: list[str] | None = None,
    exclude: list[str] | None = None,
) -> dict:
    """Build a Gemini response_schema dict for enforced structured output.

    The schema uses Gemini's supported subset of JSON Schema (type, properties,
    items, enum, required). This forces the model to produce all requested fields.

    Args:
        preset: One of EXTRACTION_PRESETS keys
        include: Additional extraction types to enable
        exclude: Extraction types to disable from preset

    Returns:
        Dict compatible with google.genai types.GenerateContentConfig response_schema
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

    properties: dict = {}
    required: list[str] = []

    active_types = [k for k, v in config.items() if v]

    for extraction_type in active_types:
        schema = _RESPONSE_SCHEMA_FRAGMENTS.get(extraction_type)
        if schema:
            properties[schema["key"]] = schema["schema"]
            required.append(schema["key"])

    return {
        "type": "OBJECT",
        "properties": properties,
        "required": required,
    }


# Response schema fragments for Gemini structured output enforcement.
# Each maps an extraction_type to a JSON Schema fragment that Gemini enforces.
_RESPONSE_SCHEMA_FRAGMENTS: dict[str, dict] = {
    "date_estimation": {
        "key": "date_estimation",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "estimated_decade": {"type": "INTEGER"},
                "best_year_estimate": {"type": "INTEGER"},
                "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                "probable_range": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                "reasoning_summary": {"type": "STRING"},
                "cultural_lag_applied": {"type": "BOOLEAN"},
                "cultural_lag_note": {"type": "STRING"},
            },
            "required": ["estimated_decade", "best_year_estimate", "confidence", "probable_range", "reasoning_summary"],
        },
    },
    "face_analysis": {
        "key": "face_analysis",
        "schema": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "face_index": {"type": "INTEGER"},
                    "estimated_age": {"type": "INTEGER"},
                    "gender": {"type": "STRING"},
                    "description": {"type": "STRING"},
                },
                "required": ["face_index", "estimated_age", "gender"],
            },
        },
    },
    "location": {
        "key": "location",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "place": {"type": "STRING"},
                "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                "visual_evidence": {"type": "STRING"},
                "source_type": {"type": "STRING", "enum": ["visual", "biographical", "both"]},
            },
            "required": ["place", "confidence"],
        },
    },
    "cultural_markers": {
        "key": "cultural_markers",
        "schema": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "clothing_era": {
        "key": "clothing_notes",
        "schema": {"type": "STRING"},
    },
    "group_composition": {
        "key": "group_composition",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "type": {"type": "STRING"},
                "people_count": {"type": "INTEGER"},
                "arrangement": {"type": "STRING"},
            },
            "required": ["type", "people_count"],
        },
    },
    "subject_ages": {
        "key": "subject_ages",
        "schema": {"type": "ARRAY", "items": {"type": "INTEGER"}},
    },
    "scene_description": {
        "key": "scene_description",
        "schema": {"type": "STRING"},
    },
    "event_context": {
        "key": "event_context",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "event_type": {
                    "type": "STRING",
                    "enum": [
                        "wedding_ceremony",
                        "wedding_reception",
                        "bar_mitzvah",
                        "funeral",
                        "holiday",
                        "school",
                        "military",
                        "casual",
                        "portrait",
                        "formal_dinner",
                        "party",
                        "religious_ceremony",
                        "graduation",
                        "reunion",
                        "unknown",
                    ],
                },
                "event_subtype": {"type": "STRING"},
                "role_indicators": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "face_index": {"type": "INTEGER"},
                            "roles": {"type": "ARRAY", "items": {"type": "STRING"}},
                        },
                        "required": ["face_index", "roles"],
                    },
                },
                "formality_level": {
                    "type": "STRING",
                    "enum": ["very_formal", "formal", "semi_formal", "casual", "intimate"],
                },
            },
            "required": ["event_type", "formality_level"],
        },
    },
    "relationship_inference": {
        "key": "relationship_inference",
        "schema": {
            "type": "OBJECT",
            "properties": {
                "couple_pairs": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "face_indices": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                            "confidence": {"type": "NUMBER"},
                            "evidence": {"type": "STRING"},
                        },
                        "required": ["face_indices", "confidence", "evidence"],
                    },
                },
                "parent_child_pairs": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "parent_index": {"type": "INTEGER"},
                            "child_index": {"type": "INTEGER"},
                            "confidence": {"type": "NUMBER"},
                            "evidence": {"type": "STRING"},
                        },
                        "required": ["parent_index", "child_index", "confidence", "evidence"],
                    },
                },
                "sibling_pairs": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "face_indices": {"type": "ARRAY", "items": {"type": "INTEGER"}},
                            "confidence": {"type": "NUMBER"},
                            "evidence": {"type": "STRING"},
                        },
                        "required": ["face_indices", "confidence", "evidence"],
                    },
                },
                "positioning_notes": {"type": "STRING"},
            },
            "required": ["positioning_notes"],
        },
    },
}


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
