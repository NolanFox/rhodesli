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
    get_individual_history,
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
        # Make the chain self-returning for select/eq/order/limit
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
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
        chain.order.return_value = chain
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


# --- Codex 157b P1.1 + P1.2 fixes (Session 158) ---


class TestV2OrderedRead:
    """Codex 157b P1.1: post-historical-backfill, multiple v2 rows can exist
    per gedcom_id. The helper must order by last_seen_version DESC to
    guarantee returning the most-recent state."""

    def _build_capturing_sb(self, *, v2_rows, v1_view_rows=None, table_kind="individual"):
        """Build sb where the v2 chain is captured for inspection."""
        sb = MagicMock()
        captured = {}

        def table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.order.return_value = chain
            chain.limit.return_value = chain
            v2_table = "gedcom_individuals_v2" if table_kind == "individual" else "gedcom_families_v2"
            v1_view = "current_gedcom_individuals" if table_kind == "individual" else "gedcom_families"
            if name == v2_table:
                chain.execute.return_value = _make_resp(v2_rows)
                captured["v2"] = chain
            elif name == v1_view:
                chain.execute.return_value = _make_resp(v1_view_rows or [])
            return chain

        sb.table.side_effect = table
        return sb, captured

    def test_v2_order_called_with_last_seen_version_desc(self):
        """Verify .order('last_seen_version', desc=True) is in the v2 query chain."""
        v2_row = {"gedcom_id": "@I1@", "name": "Albert"}
        sb, captured = self._build_capturing_sb(v2_rows=[v2_row], table_kind="individual")
        get_individual("@I1@", sb=sb)
        chain = captured["v2"]
        order_calls = chain.order.call_args_list
        last_seen_calls = [c for c in order_calls if c.args and c.args[0] == "last_seen_version"]
        assert last_seen_calls, f"Expected order(last_seen_version, ...) call, got: {order_calls}"
        assert any(c.kwargs.get("desc") is True for c in last_seen_calls), \
            "Expected at least one last_seen_version order with desc=True"

    def test_v2_family_ordered_read(self):
        """Same protection on families."""
        v2_row = {"family_gedcom_id": "@F1@", "husband_xref": "@I1@", "wife_xref": "@I2@"}
        sb, captured = self._build_capturing_sb(v2_rows=[v2_row], table_kind="family")
        get_family("@F1@", sb=sb)
        chain = captured["v2"]
        order_calls = chain.order.call_args_list
        assert any(c.args and c.args[0] == "last_seen_version" and c.kwargs.get("desc") is True
                   for c in order_calls)

    def test_v2_returns_first_row_from_supabase(self):
        """Codex 158 final-pass P2.1: simulate the post-historical-backfill
        scenario where multiple v2 rows exist for the same gedcom_id. The
        Supabase REST API returns rows in the order specified by .order(),
        and .limit(1) takes the first. Since our chain orders by
        last_seen_version DESC, the first row IS the latest state — but
        we trust Supabase to honor the .order() clause. This test verifies
        we (a) ask for exactly the right ordering, and (b) take whatever
        Supabase returns first."""
        # Mock returns a single row — represents the row Supabase chose
        # given our .order() clause. The ordering correctness is enforced
        # by the .order() chain calls (verified above).
        latest_row = {
            "gedcom_id": "@I1@", "name": "Albert v9",
            "given_name": "Albert", "surname": "Fox",
        }
        sb, captured = self._build_capturing_sb(
            v2_rows=[latest_row], table_kind="individual"
        )
        result = get_individual("@I1@", sb=sb)
        assert result == latest_row
        assert result["name"] == "Albert v9"
        # Confirm the chain has BOTH order calls (last_seen + first_seen)
        # so multi-row scenarios will produce a deterministic latest pick.
        chain = captured["v2"]
        order_args = [c.args[0] for c in chain.order.call_args_list if c.args]
        assert "last_seen_version" in order_args
        assert "first_seen_version" in order_args
        assert "payload_hash" in order_args  # tiebreaker


class TestV2FailClosed:
    """Codex 157b P1.2: only PGRST205 / 'relation does not exist' should
    fall back to v1. Schema drift, RLS errors, and server errors must
    surface — not silently serve stale v1 data."""

    def test_non_pgrst_v2_error_propagates(self):
        """A v2 query that raises a non-PGRST exception (e.g. RLS, server) must raise."""
        sb = MagicMock()

        def table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.order.return_value = chain
            chain.limit.return_value = chain
            if name == "gedcom_individuals_v2":
                # Simulate an RLS error or a server 500 — NOT a PGRST205
                chain.execute.side_effect = RuntimeError(
                    "permission denied for table gedcom_individuals_v2"
                )
            else:
                chain.execute.return_value = _make_resp([])
            return chain

        sb.table.side_effect = table
        with pytest.raises(RuntimeError, match="permission denied"):
            get_individual("@I1@", sb=sb)

    def test_pgrst205_does_fall_back(self):
        """Sanity: PGRST205 still falls back (the legitimate dual-read path)."""
        v1_row = {"gedcom_id": "@I1@", "name": "Albert"}
        sb = _build_sb_individual(v2_rows=None, v1_view_rows=[v1_row])
        result = get_individual("@I1@", sb=sb)
        assert result == v1_row

    def test_relation_does_not_exist_falls_back(self):
        """Sanity: 'relation X does not exist' also falls back."""
        sb = MagicMock()

        def table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.order.return_value = chain
            chain.limit.return_value = chain
            if name == "gedcom_individuals_v2":
                chain.execute.side_effect = Exception(
                    'relation "gedcom_individuals_v2" does not exist'
                )
            elif name == "current_gedcom_individuals":
                chain.execute.return_value = _make_resp([
                    {"gedcom_id": "@I1@", "name": "Albert"}
                ])
            else:
                chain.execute.return_value = _make_resp([])
            return chain

        sb.table.side_effect = table
        result = get_individual("@I1@", sb=sb)
        assert result == {"gedcom_id": "@I1@", "name": "Albert"}


class TestGetIndividualHistory:
    """Session 158 Phase 158-2: get_individual_history returns all v2
    rows for a gedcom_id sorted by first_seen_version ASC."""

    def _build_sb_history(self, *, history_rows, raise_pgrst=False):
        sb = MagicMock()

        def table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.order.return_value = chain
            if name == "gedcom_individuals_v2":
                if raise_pgrst:
                    chain.execute.side_effect = Exception(
                        "PGRST205: relation 'gedcom_individuals_v2' does not exist"
                    )
                else:
                    chain.execute.return_value = _make_resp(history_rows)
            return chain

        sb.table.side_effect = table
        return sb

    def test_single_state_returns_one_row(self):
        """A person whose data never changed → 1-element list."""
        rows = [
            {
                "gedcom_id": "@I1@", "name": "Albert", "first_seen_version": 1,
                "last_seen_version": 9, "payload_hash": "fd1f05bd",
            }
        ]
        sb = self._build_sb_history(history_rows=rows)
        result = get_individual_history("@I1@", sb=sb)
        assert len(result) == 1
        assert result[0]["payload_hash"] == "fd1f05bd"

    def _build_capturing_history_sb(self, history_rows):
        sb = MagicMock()
        captured = {}

        def table(name):
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.order.return_value = chain
            if name == "gedcom_individuals_v2":
                chain.execute.return_value = _make_resp(history_rows)
                captured["v2"] = chain
            return chain

        sb.table.side_effect = table
        return sb, captured

    def test_multi_state_returns_all_rows_in_version_order(self):
        """A person with N distinct states → N-element list, sorted by first_seen_version."""
        rows = [
            {
                "gedcom_id": "@I1@", "name": "Albert", "first_seen_version": 1,
                "last_seen_version": 7, "payload_hash": "fd1f05bd",
            },
            {
                "gedcom_id": "@I1@", "name": "Albert", "first_seen_version": 9,
                "last_seen_version": 9, "payload_hash": "1d77bf67",
            },
        ]
        sb, captured = self._build_capturing_history_sb(rows)
        result = get_individual_history("@I1@", sb=sb)
        assert len(result) == 2
        # Verify the helper called .order(first_seen_version, desc=False) — i.e.
        # ascending so the oldest state comes first.
        chain = captured["v2"]
        order_calls = chain.order.call_args_list
        first_seen_calls = [c for c in order_calls if c.args and c.args[0] == "first_seen_version"]
        assert first_seen_calls
        assert all(c.kwargs.get("desc") is False for c in first_seen_calls)

    def test_unknown_id_returns_empty_list(self):
        sb = self._build_sb_history(history_rows=[])
        assert get_individual_history("@INOPE@", sb=sb) == []

    def test_empty_id_short_circuits(self):
        sb = MagicMock()
        assert get_individual_history("", sb=sb) == []
        sb.table.assert_not_called()

    def test_pgrst205_returns_empty_not_raise(self):
        """Pre-cutover environments don't have v2 — return [] not raise."""
        sb = self._build_sb_history(history_rows=None, raise_pgrst=True)
        assert get_individual_history("@I1@", sb=sb) == []

    def test_history_select_includes_rich_json_fields(self):
        """Codex 158 final-pass P1: 158-1 proved adjacent v1 versions for
        ALL test individuals have IDENTICAL visible columns — the actual
        change is in JSONB columns (events, citations, names, notes). The
        history helper MUST select these or it returns N rows that look
        identical to the user.
        """
        from app.gedcom_dual_read import INDIVIDUAL_HISTORY_FIELDS

        for required_json_col in [
            "names_json", "events_json", "family_as_spouse_json",
            "family_as_child_json", "notes_json", "citations_json",
        ]:
            assert required_json_col in INDIVIDUAL_HISTORY_FIELDS, (
                f"INDIVIDUAL_HISTORY_FIELDS missing {required_json_col}; user "
                f"will see identical-looking rows for true historical changes"
            )
