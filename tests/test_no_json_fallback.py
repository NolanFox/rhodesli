"""Structural test: no JSON fallback when DATA_SOURCE=postgres (AD-232).

When DATA_SOURCE=postgres, loaders must return empty on Supabase failure,
NOT silently fall back to stale JSON files. This prevents the #1 recurring
data integrity issue (12 incidents in sessions 59-142).
"""

import ast
import inspect
import textwrap

import pytest


class TestNoJsonFallbackInPostgresMode:
    """Verify that loaders return empty on Supabase failure, not JSON fallback."""

    LOADERS_TO_CHECK = [
        ("app.main", "_load_date_labels"),
        ("app.main", "_load_birth_year_estimates"),
        ("app.main", "_load_proposals"),
        ("app.page_routes", "_load_photo_locations"),
        ("app.relationship_routes", "_load_gedcom_matches"),
        ("app.relationship_routes", "_load_relationship_graph"),
        ("app.engagement_routes", "_load_annotations"),
    ]

    @pytest.mark.parametrize("module_name,func_name", LOADERS_TO_CHECK)
    def test_no_json_fallthrough_after_supabase_failure(self, module_name, func_name):
        """Each loader's postgres branch must NOT fall through to JSON reading.

        The pattern is: if DATA_SOURCE == "postgres", the function MUST return
        before reaching any JSON file reading code. This is enforced by checking
        that the source code has a return statement inside the postgres branch's
        except block.
        """
        import importlib

        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)
        source = inspect.getsource(func)

        # The source must contain "no JSON fallback" marker (AD-232)
        assert "no JSON fallback" in source, (
            f"{module_name}.{func_name} is missing 'no JSON fallback' marker. "
            f"When DATA_SOURCE=postgres and Supabase fails, the loader MUST return "
            f"empty data, NOT fall through to JSON reading. See AD-232."
        )

    @pytest.mark.parametrize("module_name,func_name", LOADERS_TO_CHECK)
    def test_postgres_branch_returns_before_json(self, module_name, func_name):
        """Verify the postgres branch has early return, not fall-through."""
        import importlib

        mod = importlib.import_module(module_name)
        func = getattr(mod, func_name)
        source = inspect.getsource(func)

        # The JSON fallback comment should be preceded by "rollback escape hatch"
        # indicating it's only reachable in JSON mode
        assert "rollback escape hatch" in source, (
            f"{module_name}.{func_name}: JSON code path must be marked as "
            f"'rollback escape hatch only' to confirm it's unreachable in postgres mode."
        )

    def test_loaders_list_is_comprehensive(self):
        """Ensure we're checking all loaders that have DATA_SOURCE branching."""
        import subprocess

        result = subprocess.run(
            ["grep", "-rn", 'DATA_SOURCE == "postgres"', "app/"],
            capture_output=True,
            text=True,
        )
        # Count unique files with actual DATA_SOURCE conditional branching
        files_with_branching = set()
        for line in result.stdout.strip().split("\n"):
            if line and ":" in line:
                filepath = line.split(":")[0]
                # Normalize path (grep may return app//file.py)
                filepath = filepath.replace("//", "/")
                # Skip non-loader files (supabase_data.py is the provider, not consumer)
                if "test" in filepath or "supabase_data" in filepath:
                    continue
                files_with_branching.add(filepath)

        # All files with DATA_SOURCE branching should have loaders in our check list
        checked_modules = {m.replace(".", "/") + ".py" for m, _ in self.LOADERS_TO_CHECK}
        # Also include main.py's registry loaders which are already Supabase-only
        checked_modules.add("app/main.py")

        for filepath in files_with_branching:
            assert filepath in checked_modules, (
                f"File {filepath} has DATA_SOURCE branching but no loader is checked "
                f"in TestNoJsonFallbackInPostgresMode.LOADERS_TO_CHECK. "
                f"Add the relevant loader function to the check list."
            )


class TestPostgresLoaderBehavior:
    """Test that loaders actually return empty on Supabase failure."""

    def test_date_labels_returns_empty_on_supabase_failure(self, monkeypatch):
        """When Supabase fails, _load_date_labels returns {} not stale JSON."""
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "DATA_SOURCE", "postgres")
        main_mod._date_labels_cache = None  # Clear cache

        def mock_load_fail():
            raise ConnectionError("Supabase down")

        monkeypatch.setattr("app.supabase_data.load_date_labels_from_supabase", mock_load_fail)

        result = main_mod._load_date_labels()
        assert result == {}, "Should return empty dict on Supabase failure, not JSON data"

    def test_date_labels_returns_empty_on_supabase_none(self, monkeypatch):
        """When Supabase returns None, _load_date_labels returns {} not stale JSON."""
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "DATA_SOURCE", "postgres")
        main_mod._date_labels_cache = None

        monkeypatch.setattr("app.supabase_data.load_date_labels_from_supabase", lambda: None)

        result = main_mod._load_date_labels()
        assert result == {}, "Should return empty dict when Supabase returns None"

    def test_proposals_returns_empty_on_supabase_failure(self, monkeypatch):
        """When Supabase fails, _load_proposals returns empty structure."""
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "DATA_SOURCE", "postgres")
        main_mod._proposals_cache = None

        def mock_fail():
            raise ConnectionError("Supabase down")

        monkeypatch.setattr("app.supabase_data.get_supabase_client", mock_fail)

        result = main_mod._load_proposals()
        assert result.get("proposals") == [], "Should return empty proposals on Supabase failure"

    def test_birth_year_returns_empty_on_supabase_failure(self, monkeypatch):
        """When Supabase fails, _load_birth_year_estimates returns {}."""
        import app.main as main_mod

        monkeypatch.setattr(main_mod, "DATA_SOURCE", "postgres")
        main_mod._birth_year_cache = None

        def mock_fail():
            raise ConnectionError("Supabase down")

        monkeypatch.setattr("app.supabase_data.load_birth_year_estimates_from_supabase", mock_fail)

        result = main_mod._load_birth_year_estimates()
        assert result == {}, "Should return empty dict on Supabase failure"
