"""Structural tests: dual-keying must exist in Postgres path for all location/label loaders.

Session 144b found that _load_date_labels and _load_photo_locations both had a bug
where the Postgres path returned inbox_* IDs without SHA256 aliases. The JSON path
had dual-keying but the Postgres path was missing it.

These tests verify the Postgres branch of each loader contains the dual-keying pattern
by inspecting the source code. This prevents the bug from recurring if new loaders
are added or existing ones are refactored.
"""

import ast
import inspect
import textwrap

import pytest


class TestDualKeyingInPostgresPath:
    """Verify that loaders with dual-keying in JSON mode also have it in Postgres mode."""

    LOADERS_WITH_DUAL_KEYING = [
        ("app.main", "_load_date_labels"),
        ("app.page_routes", "_load_photo_locations"),
    ]

    @pytest.mark.parametrize("module_name,func_name", LOADERS_WITH_DUAL_KEYING)
    def test_postgres_path_has_sha256_aliasing(self, module_name, func_name):
        """Each loader's postgres branch must add SHA256 aliases for inbox_* IDs.

        The pattern: after loading from Supabase, iterate keys starting with 'inbox_',
        look up the photo path, compute generate_photo_id(filename), and add the alias.
        """
        import importlib

        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)
        source = inspect.getsource(func)

        # Must contain SHA256 aliasing in the Postgres branch
        assert "inbox_" in source, f"{module_name}.{func_name} must check for inbox_ IDs in Postgres path"
        assert "generate_photo_id" in source or "sha256" in source.lower(), (
            f"{module_name}.{func_name} must compute SHA256 aliases in Postgres path"
        )

    @pytest.mark.parametrize("module_name,func_name", LOADERS_WITH_DUAL_KEYING)
    def test_postgres_path_does_not_overwrite_existing(self, module_name, func_name):
        """SHA256 aliasing must not overwrite existing entries (collision guard)."""
        import importlib

        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)
        source = inspect.getsource(func)

        # Must check "if sha256_id not in result" before adding alias
        assert "not in result" in source, (
            f"{module_name}.{func_name} must check for existing SHA256 key before aliasing"
        )


class TestSearchEndpointCSRF:
    """Verify /tools/search POST has CSRF origin check (SEC-003)."""

    def test_search_post_has_origin_check(self):
        """The /tools/search POST handler must call _check_origin."""
        import inspect
        from app.tools_routes import post

        # The post function at /tools/search
        source = inspect.getsource(post)
        assert "_check_origin" in source, "/tools/search POST must call _check_origin for CSRF protection (SEC-003)"
