"""Data layer invariant tests — NEVER allow multiple sources of truth.

Session 129: identity_overrides table silently corrupted production data for
4 days (Sessions 112-129) by overwriting correct identities with stale
snapshots. This is the 9th occurrence of the split-brain data pattern.

These tests enforce structural invariants that prevent this class of bug.
"""

import ast
import inspect

import pytest


class TestNoOverrideLayers:
    """Ensure no code path applies an override/shadow layer on top of
    the identities table read. The identities table is the SOLE source
    of truth — any override mechanism will eventually go stale and
    silently corrupt data."""

    def test_load_from_postgres_has_no_override_application(self):
        """load_from_postgres must NOT apply identity_overrides."""
        from core.registry import IdentityRegistry

        source = inspect.getsource(IdentityRegistry.load_from_postgres)
        # Check non-comment lines only
        lines = source.split("\n")
        code_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
        code_text = "\n".join(code_lines).lower()
        assert "load_identity_overrides" not in code_text, (
            "load_from_postgres must not call load_identity_overrides. "
            "Override layer removed Session 129 — caused stale data corruption."
        )

    def test_save_registry_does_not_sync_overrides(self):
        """save_registry must NOT write to identity_overrides."""
        from app.main import save_registry

        source = inspect.getsource(save_registry)
        assert "sync_identity_overrides" not in source, (
            "save_registry must not call sync_identity_overrides. This function was removed in Session 129."
        )

    def test_no_import_of_override_functions(self):
        """No production code should import override functions."""
        import app.main
        import core.registry

        main_source = inspect.getsource(app.main)
        registry_source = inspect.getsource(core.registry)

        for source, name in [(main_source, "app.main"), (registry_source, "core.registry")]:
            assert "load_identity_overrides_from_supabase" not in source, (
                f"{name} must not import load_identity_overrides_from_supabase. "
                "The identity_overrides table is deprecated (Session 129)."
            )

    def test_identities_table_is_sole_read_source(self):
        """load_from_postgres should read from exactly ONE table for identity data."""
        from core.registry import IdentityRegistry

        source = inspect.getsource(IdentityRegistry.load_from_postgres)
        # Count distinct table references (excluding comments)
        lines = [l.strip() for l in source.split("\n") if l.strip() and not l.strip().startswith("#")]
        table_refs = [l for l in lines if '.table("' in l or ".table('" in l]
        identity_tables = [l for l in table_refs if "identit" in l.lower()]

        # Should only reference the identities table, not identity_overrides
        for ref in identity_tables:
            assert "override" not in ref.lower(), f"Found override table reference in load_from_postgres: {ref}"

    def test_startup_sync_does_not_read_overrides(self):
        """sync_from_supabase_on_startup must NOT read identity_overrides.

        Session 130: Found that Session 129 removed the write but left the
        startup read. Every deploy was still applying stale overrides."""
        from app.supabase_data import sync_from_supabase_on_startup

        source = inspect.getsource(sync_from_supabase_on_startup)
        lines = source.split("\n")
        code_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
        code_text = "\n".join(code_lines)
        assert "identity_overrides" not in code_text, (
            "sync_from_supabase_on_startup must not read identity_overrides. "
            "This table is deprecated — reads were removed in Session 130."
        )

    def test_no_production_code_queries_identity_overrides_table(self):
        """No production Python file should query the identity_overrides table.

        Session 130: Complete removal of identity_overrides as a data layer.
        Only test files and docs may reference it (for invariant checks)."""
        import glob
        import os

        app_files = glob.glob("app/**/*.py", recursive=True)
        core_files = glob.glob("core/**/*.py", recursive=True)
        prod_files = app_files + core_files

        for filepath in prod_files:
            with open(filepath) as f:
                source = f.read()
            lines = source.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                if "identity_overrides" in stripped and ".table(" in stripped:
                    pytest.fail(
                        f"{filepath}:{i} queries identity_overrides table: {stripped}\n"
                        "This table is deprecated (Session 130). Remove the query."
                    )


class TestDataIntegrityInvariants:
    """Structural tests that catch data corruption patterns before they ship."""

    def test_anchor_ids_are_lists_not_strings(self):
        """anchor_ids must always be parsed as lists, never left as JSON strings."""
        from core.registry import IdentityRegistry

        source = inspect.getsource(IdentityRegistry.load_from_postgres)
        assert "_ensure_list" in source, (
            "load_from_postgres must use _ensure_list on anchor_ids to guard "
            "against JSONB columns storing string-encoded arrays (Lesson 142)."
        )
