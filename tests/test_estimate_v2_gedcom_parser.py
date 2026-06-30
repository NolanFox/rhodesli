"""
Unit tests for the Estimate v2 lightweight GEDCOM parser + context builder
and the geography-retry reconciliation context (PRD-055 Flows 1 & 3).

These are pure-function tests — no HTTP, no Gemini.
"""

from app.estimate_routes import (
    _build_estimate_user_context,
    _geography_retry_context,
    _parse_gedcom_text_for_context,
    _gedcom_extract_year,
)


SAMPLE = """
0 @I1@ INDI
1 NAME Leon /Capeluto/
1 BIRT
2 DATE 12 MAR 1895
2 PLAC Rhodes, Greece
1 DEAT
2 DATE 1970
2 PLAC New York, USA

0 @I2@ INDI
1 NAME Sarah /Capeluto/
1 BIRT
2 DATE 1900
2 PLAC Rhodes, Greece
""".strip()


class TestGedcomYearExtraction:
    def test_extracts_year_from_full_date(self):
        assert _gedcom_extract_year("12 MAR 1895") == "1895"

    def test_extracts_bare_year(self):
        assert _gedcom_extract_year("1970") == "1970"

    def test_no_year_returns_none(self):
        assert _gedcom_extract_year("ABT spring") is None

    def test_rejects_out_of_range(self):
        assert _gedcom_extract_year("3000") is None


class TestParseGedcomText:
    def test_parses_individuals(self):
        ctx = _parse_gedcom_text_for_context(SAMPLE)
        assert ctx is not None
        assert "Leon Capeluto" in ctx  # slashes stripped
        assert "born 1895 in Rhodes, Greece" in ctx
        assert "died 1970 in New York, USA" in ctx
        assert "Sarah Capeluto" in ctx

    def test_empty_returns_none(self):
        assert _parse_gedcom_text_for_context("") is None
        assert _parse_gedcom_text_for_context("   ") is None

    def test_garbage_returns_none(self):
        assert _parse_gedcom_text_for_context("just some random text, no records") is None

    def test_plain_notes_without_indi_returns_none(self):
        # Free-text notes are not GEDCOM — handled by text_hints, not the parser.
        assert _parse_gedcom_text_for_context("My grandmother in the 1940s in Rhodes") is None

    def test_name_only_individual_is_kept(self):
        ctx = _parse_gedcom_text_for_context("0 @I1@ INDI\n1 NAME Albert /Fox/")
        assert ctx is not None
        assert "Albert Fox" in ctx

    def test_individual_cap_enforced(self):
        # Build 100 individuals; only the cap should appear.
        big = "\n".join(f"0 @I{i}@ INDI\n1 NAME Person{i} /Test/\n1 BIRT\n2 DATE 19{i:02d}" for i in range(100))
        ctx = _parse_gedcom_text_for_context(big)
        assert ctx is not None
        # Person0..Person59 should be present; Person99 should not (cap = 60).
        assert "Person0 Test" in ctx
        assert "Person99 Test" not in ctx


class TestBuildEstimateUserContext:
    def test_gedcom_only(self):
        ctx, level = _build_estimate_user_context(gedcom_text=SAMPLE, text_hints="")
        assert level == "gedcom_user_provided"
        assert "Leon Capeluto" in ctx

    def test_text_hints_only(self):
        ctx, level = _build_estimate_user_context(gedcom_text="", text_hints="wedding in Rhodes ~1930s")
        assert level == "text_hints"
        assert "wedding in Rhodes" in ctx

    def test_both_combined(self):
        ctx, level = _build_estimate_user_context(gedcom_text=SAMPLE, text_hints="taken at a wedding")
        assert level == "gedcom_user_provided"  # GEDCOM dominates the label
        assert "Leon Capeluto" in ctx
        assert "taken at a wedding" in ctx

    def test_neither_is_visual_only(self):
        ctx, level = _build_estimate_user_context(gedcom_text="  ", text_hints="   ")
        assert ctx is None
        assert level is None

    def test_invalid_gedcom_with_no_hints_is_visual_only(self):
        ctx, level = _build_estimate_user_context(gedcom_text="not gedcom", text_hints="")
        assert ctx is None
        assert level is None


class TestGeographyRetryContext:
    def test_includes_location_and_reconciliation(self):
        ctx = _geography_retry_context("Rhodes, Greece")
        assert "Rhodes, Greece" in ctx
        assert "VISUAL evidence" in ctx
        assert "do NOT raise confidence" in ctx

    def test_handles_blank_location(self):
        # Endpoint guards empty location, but the helper must not crash.
        ctx = _geography_retry_context("   ")
        assert "reconsideration" in ctx.lower()
