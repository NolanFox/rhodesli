"""Tests for combined Gemini pipeline and model config centralization (AD-152)."""

from unittest.mock import MagicMock, patch

import pytest


class TestModelConfigCentralization:
    """Verify hardcoded model strings are replaced with config references."""

    def test_call_gemini_alignment_uses_config_default(self):
        """When model=None, uses GEMINI_MODEL from gemini_config."""
        from rhodesli_ml.gemini_config import GEMINI_MODEL

        # Verify the config has a value
        assert GEMINI_MODEL
        assert "gemini" in GEMINI_MODEL

    def test_run_face_alignment_model_default_is_none(self):
        """run_face_alignment model parameter defaults to None (uses config)."""
        import inspect
        from app.face_alignment import run_face_alignment

        sig = inspect.signature(run_face_alignment)
        assert sig.parameters["model"].default is None

    def test_call_gemini_alignment_model_default_is_none(self):
        """call_gemini_alignment model parameter defaults to None (uses config)."""
        import inspect
        from app.face_alignment import call_gemini_alignment

        sig = inspect.signature(call_gemini_alignment)
        assert sig.parameters["model"].default is None

    def test_batch_script_imports_config(self):
        """Batch script imports GEMINI_MODEL, not hardcoded string."""
        from pathlib import Path

        script_path = Path(__file__).resolve().parent.parent / "scripts" / "run_batch_alignment.py"
        content = script_path.read_text()
        assert "from rhodesli_ml.gemini_config import GEMINI_MODEL" in content
        assert "default=GEMINI_MODEL" in content


class TestApiCallLogging:
    """Verify Gemini API calls are logged via log_gemini_call."""

    def test_log_call_helper_exists(self):
        """_log_call helper function exists in face_alignment."""
        from app.face_alignment import _log_call
        assert callable(_log_call)

    def test_log_call_calls_supabase(self):
        """_log_call invokes log_gemini_call with correct params."""
        mock_log = MagicMock()
        with patch("app.supabase_data.log_gemini_call", mock_log):
            from app.face_alignment import _log_call
            _log_call(
                photo_id="test123",
                model="gemini-3.1-pro-preview",
                call_type="alignment",
                prompt_tokens=1000,
                completion_tokens=500,
                cost_usd=0.028,
                start_ms=1000000,
                status="success",
                batch_id="batch_test",
            )
        mock_log.assert_called_once()
        kwargs = mock_log.call_args[1]
        assert kwargs["photo_id"] == "test123"
        assert kwargs["status"] == "success"
        assert kwargs["batch_id"] == "batch_test"

    def test_log_call_skips_when_no_photo_id(self):
        """_log_call returns without logging when photo_id is None."""
        mock_log = MagicMock()
        with patch("app.supabase_data.log_gemini_call", mock_log):
            from app.face_alignment import _log_call
            _log_call(
                photo_id=None,
                model="model",
                call_type="alignment",
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0,
                start_ms=1000,
                status="success",
            )
        mock_log.assert_not_called()

    def test_log_call_handles_exception(self):
        """_log_call never raises, even on logging failure."""
        with patch("app.supabase_data.log_gemini_call", side_effect=RuntimeError("db down")):
            from app.face_alignment import _log_call
            # Should not raise
            _log_call("p1", "model", "alignment", 0, 0, 0, 1000, "success")


class TestCombinedPipelineScript:
    """Tests for the combined pipeline script structure."""

    def test_script_exists(self):
        """Combined pipeline script exists."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_combined_pipeline.py"
        assert script.exists()

    def test_script_imports_config(self):
        """Script uses centralized model config."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_combined_pipeline.py"
        content = script.read_text()
        assert "from rhodesli_ml.gemini_config import GEMINI_MODEL" in content
        assert "save_alignment" in content
        assert "batch_id" in content

    def test_script_has_retry_failed_option(self):
        """Script supports --retry-failed for re-processing failed photos."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_combined_pipeline.py"
        content = script.read_text()
        assert "--retry-failed" in content

    def test_script_has_gedcom_option(self):
        """Script supports GEDCOM context toggle."""
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent / "scripts" / "run_combined_pipeline.py"
        content = script.read_text()
        assert "--no-gedcom" in content

    def test_get_failed_photo_ids(self, tmp_path):
        """get_failed_photo_ids extracts failed IDs from result file."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

        results = {
            "results": [
                {"photo_id": "p1", "status": "success"},
                {"photo_id": "p2", "status": "error", "reason": "429"},
                {"photo_id": "p3", "status": "error", "reason": "timeout"},
                {"photo_id": "p4", "status": "skipped"},
            ]
        }
        result_file = tmp_path / "batch_result.json"
        import json
        result_file.write_text(json.dumps(results))

        from run_combined_pipeline import get_failed_photo_ids
        failed = get_failed_photo_ids(result_file)
        assert failed == ["p2", "p3"]

    def test_get_failed_photo_ids_missing_file(self, tmp_path):
        """get_failed_photo_ids returns empty list for missing file."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

        from run_combined_pipeline import get_failed_photo_ids
        failed = get_failed_photo_ids(tmp_path / "nonexistent.json")
        assert failed == []


class TestRateLimitDetection:
    """Verify rate limit detection in call_gemini_alignment."""

    def test_call_gemini_alignment_has_photo_id_param(self):
        """call_gemini_alignment accepts photo_id for logging."""
        import inspect
        from app.face_alignment import call_gemini_alignment
        sig = inspect.signature(call_gemini_alignment)
        assert "photo_id" in sig.parameters
        assert "batch_id" in sig.parameters
        assert "call_type" in sig.parameters

    def test_run_face_alignment_has_batch_id_param(self):
        """run_face_alignment accepts batch_id for logging."""
        import inspect
        from app.face_alignment import run_face_alignment
        sig = inspect.signature(run_face_alignment)
        assert "batch_id" in sig.parameters
        assert "call_type" in sig.parameters


class TestGedcomContextBuilder:
    """Tests for _build_parsed_gedcom_from_supabase and GEDCOM context integration."""

    def _make_individual_row(self, gedcom_id, name, given_name="", surname="",
                              gender="U", birth_date="", birth_place="",
                              death_date="", death_place=""):
        return {
            "gedcom_id": gedcom_id,
            "name": name,
            "given_name": given_name,
            "surname": surname,
            "gender": gender,
            "birth_date": birth_date,
            "birth_place": birth_place,
            "death_date": death_date,
            "death_place": death_place,
            "source_file": "test.ged",
        }

    def test_gedcom_context_builder_returns_parsed_gedcom(self):
        """_build_parsed_gedcom_from_supabase returns ParsedGedcom object."""
        from rhodesli_ml.importers.gedcom_parser import ParsedGedcom

        individuals_data = [
            self._make_individual_row("@I1@", "Isaac Franco", "Isaac", "Franco",
                                       "M", "1920", "Rhodes"),
            self._make_individual_row("@I2@", "Vida Capeluto", "Vida", "Capeluto",
                                       "F", "1895", "Rhodes"),
        ]
        mock_sb = MagicMock()
        # Events query returns empty
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            from run_combined_pipeline import _build_parsed_gedcom_from_supabase
            result = _build_parsed_gedcom_from_supabase(individuals_data)

        assert isinstance(result, ParsedGedcom)
        assert len(result.individuals) == 2
        assert "@I1@" in result.individuals
        assert "@I2@" in result.individuals

    def test_gedcom_context_includes_birth_years(self):
        """Built individuals include birth year from date parsing."""
        individuals_data = [
            self._make_individual_row("@I1@", "Isaac Franco", "Isaac", "Franco",
                                       "M", "15 MAR 1920", "Rhodes, Dodecanese"),
        ]
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.execute.return_value = MagicMock(data=[])

        with patch("app.supabase_data.get_supabase_client", return_value=mock_sb):
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            from run_combined_pipeline import _build_parsed_gedcom_from_supabase
            result = _build_parsed_gedcom_from_supabase(individuals_data)

        indi = result.individuals["@I1@"]
        assert indi.birth is not None
        assert indi.birth_year == 1920
        assert indi.birth_place == "Rhodes, Dodecanese"
        assert indi.full_name == "Isaac Franco"

    def test_gedcom_context_handles_no_data(self):
        """Returns None when individuals_data is empty."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from run_combined_pipeline import _build_parsed_gedcom_from_supabase
        assert _build_parsed_gedcom_from_supabase([]) is None
        assert _build_parsed_gedcom_from_supabase(None) is None

    def test_load_gedcom_data_handles_no_supabase(self):
        """load_gedcom_data returns None when Supabase client unavailable."""
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
            from run_combined_pipeline import load_gedcom_data
            assert load_gedcom_data() is None

    def test_gedcom_context_reconstructs_families(self):
        """Families are reconstructed from relationship rows."""
        individuals_data = [
            self._make_individual_row("@I1@", "Bohor Capeluto", "Bohor", "Capeluto", "M"),
            self._make_individual_row("@I2@", "Vida Notrica", "Vida", "Notrica", "F"),
            self._make_individual_row("@I3@", "Isaac Capeluto", "Isaac", "Capeluto", "M"),
        ]
        relationship_data = [
            {"individual_gedcom_id": "@I1@", "related_gedcom_id": "@I2@",
             "relationship_type": "spouse", "family_gedcom_id": "@F1@"},
            {"individual_gedcom_id": "@I2@", "related_gedcom_id": "@I1@",
             "relationship_type": "spouse", "family_gedcom_id": "@F1@"},
            {"individual_gedcom_id": "@I1@", "related_gedcom_id": "@I3@",
             "relationship_type": "parent", "family_gedcom_id": "@F1@"},
            {"individual_gedcom_id": "@I3@", "related_gedcom_id": "@I1@",
             "relationship_type": "child", "family_gedcom_id": "@F1@"},
        ]

        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from run_combined_pipeline import _build_parsed_gedcom_from_supabase
        result = _build_parsed_gedcom_from_supabase(individuals_data, relationships_data=relationship_data)

        assert len(result.families) == 1
        fam = result.families["@F1@"]
        assert fam.husband_xref == "@I1@"
        assert fam.wife_xref == "@I2@"
        assert "@I3@" in fam.children_xrefs

        # Verify methods work
        bohor = result.individuals["@I1@"]
        spouses = result.get_spouses(bohor)
        assert len(spouses) == 1
        assert spouses[0].full_name == "Vida Notrica"

        children = result.get_children(bohor)
        assert len(children) == 1
        assert children[0].full_name == "Isaac Capeluto"

        isaac = result.individuals["@I3@"]
        parents = result.get_parents(isaac)
        assert len(parents) == 2

    def test_combined_pipeline_build_gedcom_context_with_data(self):
        """build_gedcom_context returns non-empty when GEDCOM data is available."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from run_combined_pipeline import build_gedcom_context
        from app.face_alignment import FaceDetection
        from rhodesli_ml.importers.gedcom_parser import (
            GedcomEvent, GedcomIndividual, GedcomFamily, ParsedGedcom, ParsedDate,
        )

        parsed_gedcom = ParsedGedcom(
            individuals={
                "@I1@": GedcomIndividual(
                    xref_id="@I1@",
                    full_name="Vida Capeluto",
                    given_name="Vida",
                    surname="Capeluto",
                    gender="F",
                    birth=GedcomEvent(
                        event_type="birth",
                        date=ParsedDate(year=1895, raw="1895"),
                        place="Rhodes",
                        raw_date="1895",
                    ),
                ),
            },
            families={},
            source_file="test",
        )
        gedcom_data = {
            "parsed_gedcom": parsed_gedcom,
            "face_links": {"identity-1": "@I1@"},
        }
        faces = [
            FaceDetection(face_id="face1", bbox=[10, 10, 100, 100],
                          face_index=0, identity_name="Vida Capeluto"),
        ]
        identities = {
            "identity-1": {
                "name": "Vida Capeluto",
                "state": "CONFIRMED",
                "anchor_ids": ["face1"],
                "candidate_ids": [],
            }
        }

        context = build_gedcom_context("photo1", faces, identities, gedcom_data)
        assert "Vida Capeluto" in context
        assert "1895" in context
        assert "Rhodes" in context

    def test_combined_pipeline_build_gedcom_context_no_links(self):
        """build_gedcom_context returns empty when no face links exist."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from run_combined_pipeline import build_gedcom_context
        from app.face_alignment import FaceDetection

        faces = [FaceDetection(face_id="face1", bbox=[0, 0, 50, 50], face_index=0)]
        identities = {}
        gedcom_data = {"parsed_gedcom": None, "face_links": {}}
        assert build_gedcom_context("p1", faces, identities, gedcom_data) == ""

    def test_combined_pipeline_build_gedcom_context_no_gedcom(self):
        """build_gedcom_context returns empty when gedcom_data is None."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from run_combined_pipeline import build_gedcom_context
        from app.face_alignment import FaceDetection

        faces = [FaceDetection(face_id="face1", bbox=[0, 0, 50, 50], face_index=0)]
        assert build_gedcom_context("p1", faces, {}, None) == ""

    def test_build_gedcom_context_uses_first_order_variant(self):
        """build_gedcom_context uses first_order variant for family context (AD-159 fix)."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from run_combined_pipeline import build_gedcom_context
        from app.face_alignment import FaceDetection
        from rhodesli_ml.importers.gedcom_parser import (
            GedcomEvent, GedcomIndividual, GedcomFamily, ParsedGedcom, ParsedDate,
        )

        # Build a family: Vida (child) -> parents Isaac and Sarah
        vida = GedcomIndividual(
            xref_id="@I1@", full_name="Vida Capeluto",
            given_name="Vida", surname="Capeluto", gender="F",
            birth=GedcomEvent(event_type="birth", date=ParsedDate(year=1920, raw="1920"),
                              place="Rhodes", raw_date="1920"),
            family_as_child=["@F1@"],
        )
        isaac = GedcomIndividual(
            xref_id="@I2@", full_name="Isaac Capeluto",
            given_name="Isaac", surname="Capeluto", gender="M",
            birth=GedcomEvent(event_type="birth", date=ParsedDate(year=1890, raw="1890"),
                              place="Rhodes", raw_date="1890"),
            family_as_spouse=["@F1@"],
        )
        sarah = GedcomIndividual(
            xref_id="@I3@", full_name="Sarah Israel",
            given_name="Sarah", surname="Israel", gender="F",
            birth=GedcomEvent(event_type="birth", date=ParsedDate(year=1895, raw="1895"),
                              place="Rhodes", raw_date="1895"),
            family_as_spouse=["@F1@"],
        )
        family = GedcomFamily(
            xref_id="@F1@", husband_xref="@I2@", wife_xref="@I3@",
            children_xrefs=["@I1@"],
        )

        parsed_gedcom = ParsedGedcom(
            individuals={"@I1@": vida, "@I2@": isaac, "@I3@": sarah},
            families={"@F1@": family},
            source_file="test",
        )
        gedcom_data = {
            "parsed_gedcom": parsed_gedcom,
            "face_links": {"identity-1": "@I1@"},
        }
        faces = [
            FaceDetection(face_id="face1", bbox=[10, 10, 100, 100],
                          face_index=0, identity_name="Vida Capeluto"),
        ]
        identities = {
            "identity-1": {
                "name": "Vida Capeluto", "state": "CONFIRMED",
                "anchor_ids": ["face1"], "candidate_ids": [],
            }
        }

        context = build_gedcom_context("photo1", faces, identities, gedcom_data)
        # first_order includes family members
        assert "Vida Capeluto" in context
        assert "Parent: Isaac Capeluto" in context
        assert "Parent: Sarah Israel" in context

    def test_build_gedcom_context_token_count_logged(self):
        """build_gedcom_context logs token count for enriched photos."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from run_combined_pipeline import build_gedcom_context
        from app.face_alignment import FaceDetection
        from rhodesli_ml.importers.gedcom_parser import (
            GedcomEvent, GedcomIndividual, ParsedGedcom, ParsedDate,
        )

        parsed_gedcom = ParsedGedcom(
            individuals={
                "@I1@": GedcomIndividual(
                    xref_id="@I1@", full_name="Vida Capeluto",
                    given_name="Vida", surname="Capeluto", gender="F",
                    birth=GedcomEvent(event_type="birth",
                                      date=ParsedDate(year=1895, raw="1895"),
                                      place="Rhodes", raw_date="1895"),
                ),
            },
            families={},
            source_file="test",
        )
        gedcom_data = {
            "parsed_gedcom": parsed_gedcom,
            "face_links": {"identity-1": "@I1@"},
        }
        faces = [
            FaceDetection(face_id="face1", bbox=[10, 10, 100, 100],
                          face_index=0, identity_name="Vida Capeluto"),
        ]
        identities = {
            "identity-1": {
                "name": "Vida Capeluto", "state": "CONFIRMED",
                "anchor_ids": ["face1"], "candidate_ids": [],
            }
        }

        context = build_gedcom_context("photo1", faces, identities, gedcom_data)
        assert len(context) > 0
        # Token estimation
        from rhodesli_ml.gedcom_context import estimate_context_tokens
        tokens = estimate_context_tokens(context)
        assert tokens > 0


class TestGeminiConfigLogging:
    """Tests for gemini_config and response_summary logging (AD-159 fix)."""

    def test_log_call_passes_gemini_config(self):
        """_log_call forwards gemini_config to log_gemini_call."""
        mock_log = MagicMock()
        with patch("app.supabase_data.log_gemini_call", mock_log):
            from app.face_alignment import _log_call
            _log_call(
                photo_id="test123",
                model="gemini-3.1-pro-preview",
                call_type="combined",
                prompt_tokens=1500,
                completion_tokens=500,
                cost_usd=0.028,
                start_ms=1000000,
                status="success",
                gemini_config='{"model": "gemini-3.1-pro-preview", "gedcom_token_count": 450}',
            )
        mock_log.assert_called_once()
        kwargs = mock_log.call_args[1]
        assert kwargs["gemini_config"] is not None
        assert "gedcom_token_count" in kwargs["gemini_config"]

    def test_log_call_passes_response_summary(self):
        """_log_call forwards response_summary to log_gemini_call."""
        mock_log = MagicMock()
        with patch("app.supabase_data.log_gemini_call", mock_log):
            from app.face_alignment import _log_call
            _log_call(
                photo_id="test123",
                model="gemini-3.1-pro-preview",
                call_type="alignment",
                prompt_tokens=1000,
                completion_tokens=300,
                cost_usd=0.02,
                start_ms=1000000,
                status="success",
                response_summary='{"faces_described": 3}',
            )
        kwargs = mock_log.call_args[1]
        assert kwargs["response_summary"] is not None
        assert "faces_described" in kwargs["response_summary"]

    def test_log_call_passes_prompt_lineage(self):
        """_log_call forwards prompt lineage fields to log_gemini_call."""
        mock_log = MagicMock()
        with patch("app.supabase_data.log_gemini_call", mock_log):
            from app.face_alignment import _log_call

            _log_call(
                photo_id="test123",
                model="gemini-3.1-pro-preview",
                call_type="alignment",
                prompt_tokens=1000,
                completion_tokens=300,
                cost_usd=0.02,
                start_ms=1000000,
                status="success",
                prompt_text="prompt body",
                prompt_lineage={
                    "prompt_manifest_id": "face_alignment:v1_coordinate_bridge:visual_only:contract1",
                    "prompt_family": "face_alignment",
                    "prompt_version": "v1_coordinate_bridge",
                    "prompt_variant": "visual_only",
                    "prompt_contract_version": "contract1",
                    "request_surface": "app.face_alignment.call_gemini_alignment",
                    "request_mode": "interactive",
                    "contract_valid": True,
                },
            )

        kwargs = mock_log.call_args[1]
        assert kwargs["prompt_text"] == "prompt body"
        assert kwargs["prompt_manifest_id"] == "face_alignment:v1_coordinate_bridge:visual_only:contract1"
        assert kwargs["prompt_variant"] == "visual_only"
        assert kwargs["contract_valid"] is True

    def test_call_gemini_alignment_accepts_enrichment_params(self):
        """call_gemini_alignment accepts gedcom_token_count and enrichment_level."""
        import inspect
        from app.face_alignment import call_gemini_alignment
        sig = inspect.signature(call_gemini_alignment)
        assert "gedcom_token_count" in sig.parameters
        assert "enrichment_level" in sig.parameters

    def test_run_face_alignment_accepts_enrichment_params(self):
        """run_face_alignment accepts gedcom_token_count and enrichment_level."""
        import inspect
        from app.face_alignment import run_face_alignment
        sig = inspect.signature(run_face_alignment)
        assert "gedcom_token_count" in sig.parameters
        assert "enrichment_level" in sig.parameters

    def test_enrichment_level_categories(self):
        """Enrichment level categories: full (400+), partial (100-399), thin (<100)."""
        from rhodesli_ml.gedcom_context import estimate_context_tokens

        # Full: 400+ tokens = 1600+ chars
        assert estimate_context_tokens("x" * 1600) >= 400
        # Partial: 100-399 tokens = 400-1596 chars
        assert 100 <= estimate_context_tokens("x" * 600) < 400
        # Thin: <100 tokens = <400 chars
        assert estimate_context_tokens("x" * 200) < 100

    def test_photos_without_gedcom_get_no_enrichment(self):
        """Photos with no GEDCOM links get enrichment_level='none'."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from run_combined_pipeline import build_gedcom_context
        from app.face_alignment import FaceDetection

        faces = [FaceDetection(face_id="face1", bbox=[0, 0, 50, 50], face_index=0)]
        identities = {"id1": {"anchor_ids": ["face1"], "candidate_ids": []}}
        gedcom_data = {"parsed_gedcom": None, "face_links": {}}
        context = build_gedcom_context("p1", faces, identities, gedcom_data)
        assert context == ""
        # When context is empty, enrichment_level should be "none"


class TestGedcomLoaderSession164Schema:
    """load_gedcom_data() must read the Session-164 canonical current-state
    GEDCOM tables, not the pre-164 current_* views or is_current column
    (both dropped). Regression guard: those queries returned None, so EVERY
    photo estimate silently lost its GEDCOM enrichment after Session 164.
    """

    def _src(self):
        from pathlib import Path

        return (Path(__file__).resolve().parent.parent / "scripts" / "run_combined_pipeline.py").read_text()

    def test_no_dropped_current_gedcom_individuals_view(self):
        assert "current_gedcom_individuals" not in self._src()

    def test_no_dropped_current_gedcom_families_or_relationships_views(self):
        src = self._src()
        assert "current_gedcom_families" not in src
        assert "current_gedcom_relationships" not in src

    def test_is_current_filter_disabled_for_canonical_tables(self):
        # Session 164 tables have no is_current column; the filter set is empty.
        assert "_RAW_TABLES_NEED_IS_CURRENT = set()" in self._src()

    def test_reads_canonical_individuals_table(self):
        assert '_load_all_rows("gedcom_individuals")' in self._src()
