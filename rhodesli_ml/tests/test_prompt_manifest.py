"""Tests for rhodesli_ml.prompt_manifest — prompt manifest identity and lineage."""

import hashlib
import json

import pytest

from rhodesli_ml.prompt_manifest import (
    build_prompt_lineage_fields,
    build_prompt_manifest,
    build_prompt_manifest_id,
)


class TestBuildPromptManifestId:
    def test_basic_id(self):
        result = build_prompt_manifest_id("estimate", "v2", "base", "contract1")
        assert result == "estimate:v2:base:contract1"

    def test_normalizes_contract_version(self):
        result = build_prompt_manifest_id("estimate", "v2", "base", "1")
        assert result == "estimate:v2:base:contract1"

    def test_already_prefixed_contract(self):
        result = build_prompt_manifest_id("estimate", "v2", "base", "contract3")
        assert result == "estimate:v2:base:contract3"

    def test_different_families(self):
        r1 = build_prompt_manifest_id("estimate", "v1", "base", "1")
        r2 = build_prompt_manifest_id("compare", "v1", "base", "1")
        assert r1 != r2
        assert r1.startswith("estimate:")
        assert r2.startswith("compare:")

    def test_id_format_has_four_parts(self):
        result = build_prompt_manifest_id("fam", "ver", "var", "1")
        parts = result.split(":")
        assert len(parts) == 4


class TestBuildPromptManifest:
    def test_basic_manifest(self):
        m = build_prompt_manifest(
            prompt_family="estimate",
            prompt_version="v2",
            prompt_variant="gedcom",
            prompt_contract_version="1",
            channel="web",
        )
        assert m["prompt_family"] == "estimate"
        assert m["prompt_version"] == "v2"
        assert m["prompt_variant"] == "gedcom"
        assert m["prompt_contract_version"] == "contract1"
        assert m["channel"] == "web"
        assert m["prompt_manifest_id"] == "estimate:v2:gedcom:contract1"

    def test_defaults(self):
        m = build_prompt_manifest(
            prompt_family="f",
            prompt_version="v1",
            prompt_variant="base",
            prompt_contract_version="1",
            channel="cli",
        )
        assert m["context_flags"] == {}
        assert m["template_source"] == ""
        assert m["status"] == "active"

    def test_custom_context_flags(self):
        m = build_prompt_manifest(
            prompt_family="f",
            prompt_version="v1",
            prompt_variant="base",
            prompt_contract_version="1",
            channel="web",
            context_flags={"gedcom": True, "visible_text": False},
        )
        assert m["context_flags"] == {"gedcom": True, "visible_text": False}

    def test_custom_template_source_and_status(self):
        m = build_prompt_manifest(
            prompt_family="f",
            prompt_version="v1",
            prompt_variant="base",
            prompt_contract_version="1",
            channel="web",
            template_source="prompts/estimate_v2.txt",
            status="deprecated",
        )
        assert m["template_source"] == "prompts/estimate_v2.txt"
        assert m["status"] == "deprecated"

    def test_manifest_id_matches_standalone(self):
        m = build_prompt_manifest(
            prompt_family="est",
            prompt_version="v3",
            prompt_variant="full",
            prompt_contract_version="2",
            channel="api",
        )
        standalone_id = build_prompt_manifest_id("est", "v3", "full", "2")
        assert m["prompt_manifest_id"] == standalone_id


class TestBuildPromptLineageFields:
    def _make_manifest(self):
        return build_prompt_manifest(
            prompt_family="estimate",
            prompt_version="v2",
            prompt_variant="base",
            prompt_contract_version="1",
            channel="web",
        )

    def test_basic_lineage_fields(self):
        m = self._make_manifest()
        fields = build_prompt_lineage_fields(m)
        assert fields["prompt_manifest_id"] == m["prompt_manifest_id"]
        assert fields["prompt_family"] == "estimate"
        assert fields["prompt_version"] == "v2"
        assert fields["prompt_variant"] == "base"
        assert fields["prompt_contract_version"] == "contract1"

    def test_prompt_hash_computed(self):
        m = self._make_manifest()
        prompt_text = "Analyze this photo for date estimation."
        fields = build_prompt_lineage_fields(m, prompt_text=prompt_text)
        expected_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
        assert fields["prompt_hash"] == expected_hash

    def test_response_hash_computed(self):
        m = self._make_manifest()
        response = {"year": 1940, "confidence": 0.8}
        fields = build_prompt_lineage_fields(m, full_response=response)
        expected = hashlib.sha256(
            json.dumps(response, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert fields["full_response_hash"] == expected

    def test_optional_fields_excluded_when_none(self):
        m = self._make_manifest()
        fields = build_prompt_lineage_fields(m)
        assert "prompt_hash" not in fields
        assert "full_response_hash" not in fields
        assert "experiment_id" not in fields
        assert "shadow_run_id" not in fields
        assert "request_surface" not in fields

    def test_all_optional_fields_included(self):
        m = self._make_manifest()
        fields = build_prompt_lineage_fields(
            m,
            prompt_text="test",
            full_response={"ok": True},
            experiment_id="exp-001",
            shadow_run_id="shadow-42",
            request_surface="web",
            request_mode="interactive",
            related_state_event_id="evt-99",
            contract_valid=True,
        )
        assert "prompt_hash" in fields
        assert "full_response_hash" in fields
        assert fields["experiment_id"] == "exp-001"
        assert fields["shadow_run_id"] == "shadow-42"
        assert fields["request_surface"] == "web"
        assert fields["request_mode"] == "interactive"
        assert fields["related_state_event_id"] == "evt-99"
        assert fields["contract_valid"] is True

    def test_contract_valid_false(self):
        m = self._make_manifest()
        fields = build_prompt_lineage_fields(m, contract_valid=False)
        assert fields["contract_valid"] is False

    def test_lineage_fields_are_flat_dict(self):
        m = self._make_manifest()
        fields = build_prompt_lineage_fields(m, prompt_text="hello")
        # All values should be primitive types (str, bool, None), not nested dicts
        for k, v in fields.items():
            assert isinstance(v, (str, bool, type(None))), f"{k} has non-primitive type {type(v)}"
