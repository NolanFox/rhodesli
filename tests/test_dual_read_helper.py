"""Tests for app/gedcom_dual_read.py — Session 164 (PRD-064 Option B-plus).

The dual-read collapsed to a single current-state reader over the canonical
``gedcom_individuals`` / ``gedcom_families`` tables (community-scoped, one row
per entity). The old v1/v2 fallback is gone. History now comes from R2.

Cases:
1. Individual exists → returns the row (community-filtered)
2. Individual absent → returns None
3. Empty id short-circuits (no table read)
4. include_rich selects the rich fields
5. Family parallel coverage
6. get_individual_history reads R2 diffs (or returns [] when unavailable)
"""

from __future__ import annotations

import gzip
import json
from unittest.mock import MagicMock

from app.gedcom_dual_read import (
    DEFAULT_COMMUNITY,
    FAMILY_THIN_FIELDS,
    INDIVIDUAL_RICH_FIELDS,
    INDIVIDUAL_THIN_FIELDS,
    get_family,
    get_individual,
    get_individual_history,
)


def _make_resp(rows):
    resp = MagicMock()
    resp.data = rows
    return resp


def _build_sb(*, table_name, rows):
    """Self-returning chain mock that returns `rows` for `table_name`."""
    sb = MagicMock()
    captured = {}

    def table(name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = _make_resp(rows if name == table_name else [])
        captured[name] = chain
        return chain

    sb.table.side_effect = table
    sb._captured = captured
    return sb


class TestGetIndividual:
    def test_found_returns_row(self):
        row = {"gedcom_id": "@I1@", "name": "Albert Fox", "given_name": "Albert", "surname": "Fox"}
        sb = _build_sb(table_name="gedcom_individuals", rows=[row])
        result = get_individual("@I1@", sb=sb)
        assert result == row
        called = [c.args[0] for c in sb.table.call_args_list]
        assert called == ["gedcom_individuals"]

    def test_absent_returns_none(self):
        sb = _build_sb(table_name="gedcom_individuals", rows=[])
        assert get_individual("@INOPE@", sb=sb) is None

    def test_empty_id_short_circuits(self):
        sb = MagicMock()
        assert get_individual("", sb=sb) is None
        assert get_individual(None, sb=sb) is None  # type: ignore[arg-type]
        sb.table.assert_not_called()

    def test_community_filter_applied(self):
        row = {"gedcom_id": "@I1@", "name": "X"}
        sb = _build_sb(table_name="gedcom_individuals", rows=[row])
        get_individual("@I1@", sb=sb)
        chain = sb._captured["gedcom_individuals"]
        eq_calls = {c.args for c in chain.eq.call_args_list}
        assert ("community_id", DEFAULT_COMMUNITY) in eq_calls
        assert ("gedcom_id", "@I1@") in eq_calls

    def test_custom_community(self):
        row = {"gedcom_id": "@I1@", "name": "X"}
        sb = _build_sb(table_name="gedcom_individuals", rows=[row])
        get_individual("@I1@", community_id="fox", sb=sb)
        chain = sb._captured["gedcom_individuals"]
        eq_calls = {c.args for c in chain.eq.call_args_list}
        assert ("community_id", "fox") in eq_calls

    def test_thin_fields_default(self):
        row = {"gedcom_id": "@I1@", "name": "X"}
        sb = _build_sb(table_name="gedcom_individuals", rows=[row])
        get_individual("@I1@", sb=sb)
        chain = sb._captured["gedcom_individuals"]
        chain.select.assert_called_with(INDIVIDUAL_THIN_FIELDS)
        assert "names_json" not in INDIVIDUAL_THIN_FIELDS

    def test_rich_fields_when_requested(self):
        row = {"gedcom_id": "@I1@", "name": "X"}
        sb = _build_sb(table_name="gedcom_individuals", rows=[row])
        get_individual("@I1@", include_rich=True, sb=sb)
        chain = sb._captured["gedcom_individuals"]
        chain.select.assert_called_with(INDIVIDUAL_RICH_FIELDS)
        assert "names_json" in INDIVIDUAL_RICH_FIELDS


class TestGetFamily:
    def test_found(self):
        row = {"family_gedcom_id": "@F1@", "husband_xref": "@I1@", "wife_xref": "@I2@"}
        sb = _build_sb(table_name="gedcom_families", rows=[row])
        assert get_family("@F1@", sb=sb) == row

    def test_absent(self):
        sb = _build_sb(table_name="gedcom_families", rows=[])
        assert get_family("@FNOPE@", sb=sb) is None

    def test_empty_id(self):
        sb = MagicMock()
        assert get_family("", sb=sb) is None
        sb.table.assert_not_called()

    def test_community_filter(self):
        row = {"family_gedcom_id": "@F1@"}
        sb = _build_sb(table_name="gedcom_families", rows=[row])
        get_family("@F1@", sb=sb)
        chain = sb._captured["gedcom_families"]
        eq_calls = {c.args for c in chain.eq.call_args_list}
        assert ("community_id", DEFAULT_COMMUNITY) in eq_calls
        assert ("family_gedcom_id", "@F1@") in eq_calls


def test_field_constants():
    expected_thin = {
        "gedcom_id", "name", "given_name", "surname", "gender",
        "birth_date", "birth_place", "death_date", "death_place",
    }
    assert set(INDIVIDUAL_THIN_FIELDS.split(",")) == expected_thin
    assert set(FAMILY_THIN_FIELDS.split(",")) == {"family_gedcom_id", "husband_xref", "wife_xref"}


class TestGetIndividualHistory:
    """Session 164: history is reconstructed from R2 diff artifacts."""

    def _versions_sb(self, version_rows):
        sb = MagicMock()

        def table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.order.return_value = chain
            if name == "gedcom_versions":
                chain.execute.return_value = _make_resp(version_rows)
            else:
                chain.execute.return_value = _make_resp([])
            return chain

        sb.table.side_effect = table
        return sb

    def _r2_with_diff(self, prefix_to_diff):
        """Fake R2 client returning gzipped diff.json for known prefixes."""
        r2 = MagicMock()

        def get_object(Bucket, Key):
            for prefix, diff_doc in prefix_to_diff.items():
                if Key == prefix + "diff.json.gz":
                    body = MagicMock()
                    body.read.return_value = gzip.compress(
                        json.dumps(diff_doc).encode("utf-8"), mtime=0
                    )
                    return {"Body": body}
            raise KeyError(Key)

        r2.get_object.side_effect = get_object
        return r2

    def test_empty_id_returns_empty(self):
        sb = MagicMock()
        assert get_individual_history("", sb=sb) == []
        sb.table.assert_not_called()

    def test_no_versions_returns_empty(self):
        sb = self._versions_sb([])
        assert get_individual_history("@I1@", sb=sb) == []

    def test_legacy_versions_skipped(self):
        sb = self._versions_sb([
            {"version_number": 7, "artifact_prefix": None, "artifact_format": "legacy", "status": "applied"},
        ])
        assert get_individual_history("@I1@", sb=sb) == []

    def test_reads_diff_timeline_from_r2(self):
        prefix = "gedcom-history/rhodesli/v0009-abc/"
        diff_doc = {
            "entities": {
                "individuals": {
                    "added": [
                        {
                            "entity_id": "@I1@",
                            "change_type": "baseline",
                            "before": None,
                            "after": {"gedcom_id": "@I1@", "name": "Albert"},
                            "before_hash": None,
                            "after_hash": "h1",
                        }
                    ],
                    "modified": [],
                    "removed": [],
                }
            }
        }
        sb = self._versions_sb([
            {"version_number": 9, "artifact_prefix": prefix, "artifact_format": "v1", "status": "applied"},
        ])
        r2 = self._r2_with_diff({prefix: diff_doc})
        result = get_individual_history("@I1@", sb=sb, r2_client=r2)
        assert len(result) == 1
        assert result[0]["version_number"] == 9
        assert result[0]["change_type"] == "baseline"
        assert result[0]["after"]["name"] == "Albert"

    def test_only_matching_entity_returned(self):
        prefix = "gedcom-history/rhodesli/v0009-abc/"
        diff_doc = {
            "entities": {
                "individuals": {
                    "added": [
                        {"entity_id": "@I1@", "change_type": "baseline", "after": {"name": "A"}, "after_hash": "h1"},
                        {"entity_id": "@I2@", "change_type": "baseline", "after": {"name": "B"}, "after_hash": "h2"},
                    ],
                    "modified": [],
                    "removed": [],
                }
            }
        }
        sb = self._versions_sb([
            {"version_number": 9, "artifact_prefix": prefix, "artifact_format": "v1", "status": "applied"},
        ])
        r2 = self._r2_with_diff({prefix: diff_doc})
        result = get_individual_history("@I2@", sb=sb, r2_client=r2)
        assert len(result) == 1
        assert result[0]["after"]["name"] == "B"

    def test_timeline_sorted_by_version(self):
        p9 = "gedcom-history/rhodesli/v0009-a/"
        p10 = "gedcom-history/rhodesli/v0010-b/"
        diff9 = {"entities": {"individuals": {"added": [
            {"entity_id": "@I1@", "change_type": "baseline", "after": {"v": 9}, "after_hash": "h9"}], "modified": [], "removed": []}}}
        diff10 = {"entities": {"individuals": {"added": [], "modified": [
            {"entity_id": "@I1@", "change_type": "modified", "before": {"v": 9}, "after": {"v": 10},
             "before_hash": "h9", "after_hash": "h10"}], "removed": []}}}
        sb = self._versions_sb([
            {"version_number": 9, "artifact_prefix": p9, "artifact_format": "v1", "status": "applied"},
            {"version_number": 10, "artifact_prefix": p10, "artifact_format": "v1", "status": "applied"},
        ])
        r2 = self._r2_with_diff({p9: diff9, p10: diff10})
        result = get_individual_history("@I1@", sb=sb, r2_client=r2)
        assert [r["version_number"] for r in result] == [9, 10]
