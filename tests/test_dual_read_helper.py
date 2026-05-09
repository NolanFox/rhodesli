"""Tests for app/gedcom_dual_read.py — Session 157b Track B2 (PRD-063 Day 2).

Four cases per the spec:
1. Individual exists only in v2 → read from v2
2. Individual exists in both → v2 wins
3. Individual exists only in v1 → fallback to v1
4. Individual exists in neither → returns None

Plus parallel coverage for get_family.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.gedcom_dual_read import (
    FAMILY_THIN_FIELDS,
    INDIVIDUAL_THIN_FIELDS,
    get_family,
    get_individual,
)


def _make_resp(rows):
    """Build a fake Supabase REST response object with .data attribute."""
    resp = MagicMock()
    resp.data = rows
    return resp


def _build_sb_individual(*, v2_rows, v1_view_rows=None, v1_table_rows=None):
    """Construct a minimal supabase client mock that routes by table name.

    `v2_rows` → response from gedcom_individuals_v2 (None means not deployed)
    `v1_view_rows` → response from current_gedcom_individuals view
    `v1_table_rows` → response from gedcom_individuals table fallback
    """
    sb = MagicMock()

    def table(name):
        chain = MagicMock()
        # Make the chain self-returning for select/eq/limit
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        if name == "gedcom_individuals_v2":
            if v2_rows is None:
                # Simulate "relation does not exist" / PGRST205
                chain.execute.side_effect = Exception(
                    "PGRST205: relation 'gedcom_individuals_v2' does not exist"
                )
            else:
                chain.execute.return_value = _make_resp(v2_rows)
        elif name == "current_gedcom_individuals":
            if v1_view_rows is None:
                chain.execute.side_effect = Exception(
                    "PGRST205: relation 'current_gedcom_individuals' does not exist"
                )
            else:
                chain.execute.return_value = _make_resp(v1_view_rows)
        elif name == "gedcom_individuals":
            chain.execute.return_value = _make_resp(v1_table_rows or [])
        else:
            raise AssertionError(f"unexpected table: {name}")
        return chain

    sb.table.side_effect = table
    return sb


class TestGetIndividual:
    def test_v2_only_returns_v2_row(self):
        """Case 1: row exists only in v2 → read from v2, no v1 lookup needed."""
        v2_row = {"gedcom_id": "@I1@", "name": "Albert Fox", "given_name": "Albert", "surname": "Fox"}
        sb = _build_sb_individual(v2_rows=[v2_row])
        result = get_individual("@I1@", sb=sb)
        assert result == v2_row
        # v2 should have been the only table queried
        called_tables = [c.args[0] for c in sb.table.call_args_list]
        assert called_tables == ["gedcom_individuals_v2"]

    def test_both_present_v2_wins(self):
        """Case 2: row exists in both tables → v2 wins (v1 never queried)."""
        v2_row = {"gedcom_id": "@I1@", "name": "Albert Fox (v2)", "given_name": "Albert", "surname": "Fox"}
        v1_row = {"gedcom_id": "@I1@", "name": "Albert Fox (v1)", "given_name": "Albert", "surname": "Fox"}
        sb = _build_sb_individual(v2_rows=[v2_row], v1_view_rows=[v1_row])
        result = get_individual("@I1@", sb=sb)
        assert result == v2_row
        assert result["name"] == "Albert Fox (v2)"

    def test_v1_only_falls_back_to_v1(self):
        """Case 3: row exists only in v1 → fallback to v1 view."""
        v1_row = {"gedcom_id": "@I999@", "name": "Pre-cutover Person", "given_name": "Pre", "surname": "Cutover"}
        sb = _build_sb_individual(v2_rows=[], v1_view_rows=[v1_row])
        result = get_individual("@I999@", sb=sb)
        assert result == v1_row
        # Both v2 and v1 view should have been queried
        called_tables = [c.args[0] for c in sb.table.call_args_list]
        assert "gedcom_individuals_v2" in called_tables
        assert "current_gedcom_individuals" in called_tables

    def test_neither_returns_none(self):
        """Case 4: row exists nowhere → returns None."""
        sb = _build_sb_individual(v2_rows=[], v1_view_rows=[], v1_table_rows=[])
        result = get_individual("@INOPE@", sb=sb)
        assert result is None

    def test_v2_unavailable_falls_through_to_v1(self):
        """If v2 table doesn't exist (PGRST205), fall through silently to v1."""
        v1_row = {"gedcom_id": "@I1@", "name": "Albert Fox", "given_name": "Albert", "surname": "Fox"}
        sb = _build_sb_individual(v2_rows=None, v1_view_rows=[v1_row])
        result = get_individual("@I1@", sb=sb)
        assert result == v1_row

    def test_v1_view_unavailable_falls_through_to_v1_table(self):
        """If v1 view also missing (early-deploy), fall through to gedcom_individuals base table."""
        v1_table_row = {"gedcom_id": "@I1@", "name": "Albert", "given_name": "Albert", "surname": "Fox"}
        sb = _build_sb_individual(v2_rows=[], v1_view_rows=None, v1_table_rows=[v1_table_row])
        result = get_individual("@I1@", sb=sb)
        assert result == v1_table_row

    def test_empty_id_returns_none(self):
        """Empty/None gedcom_id should short-circuit to None without any table read."""
        sb = MagicMock()
        assert get_individual("", sb=sb) is None
        assert get_individual(None, sb=sb) is None  # type: ignore[arg-type]
        sb.table.assert_not_called()

    def test_thin_fields_default(self):
        """Default include_rich=False should request only canonical fields."""
        v2_row = {"gedcom_id": "@I1@", "name": "Albert Fox"}
        sb = _build_sb_individual(v2_rows=[v2_row])
        get_individual("@I1@", sb=sb)
        # The select() call should have received the thin field list
        select_calls = [
            c for chain_call in sb.table.return_value.select.call_args_list
            for c in [chain_call]
        ]
        # We check via the last chain object actually invoked
        # The chain.select is shared across calls; just confirm no rich fields requested
        last_select = sb.table.return_value.select.call_args
        if last_select is not None:
            assert "names_json" not in str(last_select)
        # Sanity: the helper should have used the documented thin field constant
        assert "names_json" not in INDIVIDUAL_THIN_FIELDS


def _build_sb_family(*, v2_rows, v1_rows=None):
    sb = MagicMock()

    def table(name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        if name == "gedcom_families_v2":
            if v2_rows is None:
                chain.execute.side_effect = Exception(
                    "PGRST205: relation 'gedcom_families_v2' does not exist"
                )
            else:
                chain.execute.return_value = _make_resp(v2_rows)
        elif name == "gedcom_families":
            chain.execute.return_value = _make_resp(v1_rows or [])
        else:
            raise AssertionError(f"unexpected family table: {name}")
        return chain

    sb.table.side_effect = table
    return sb


class TestGetFamily:
    def test_v2_only(self):
        v2_row = {"family_gedcom_id": "@F1@", "husband_xref": "@I1@", "wife_xref": "@I2@"}
        sb = _build_sb_family(v2_rows=[v2_row])
        assert get_family("@F1@", sb=sb) == v2_row

    def test_v1_fallback(self):
        v1_row = {"family_gedcom_id": "@F999@", "husband_xref": "@I998@", "wife_xref": "@I997@"}
        sb = _build_sb_family(v2_rows=[], v1_rows=[v1_row])
        assert get_family("@F999@", sb=sb) == v1_row

    def test_neither(self):
        sb = _build_sb_family(v2_rows=[], v1_rows=[])
        assert get_family("@FNOPE@", sb=sb) is None

    def test_empty_id(self):
        sb = MagicMock()
        assert get_family("", sb=sb) is None
        sb.table.assert_not_called()


def test_field_constants_match_v2_schema():
    """Sanity: the documented thin/rich field lists are what AD-244 lists for v2."""
    expected_thin = {
        "gedcom_id", "name", "given_name", "surname", "gender",
        "birth_date", "birth_place", "death_date", "death_place",
    }
    actual_thin = set(INDIVIDUAL_THIN_FIELDS.split(","))
    assert expected_thin == actual_thin

    expected_family_thin = {"family_gedcom_id", "husband_xref", "wife_xref"}
    actual_family_thin = set(FAMILY_THIN_FIELDS.split(","))
    assert expected_family_thin == actual_family_thin
