"""Tests for Session 120: upload grouping loads from JSON, not Supabase.

The root cause of the "POST-SYNC VALIDATION FAILED" Sentry alert was that
the grouping step loaded identities from Supabase (which didn't have the
new faces yet), then save_registry() overwrote JSON with stale data.

Fix: Load from JSON directly in the grouping and cross-batch steps.
"""

import re

from pathlib import Path


class TestGroupingLoadsFromJSON:
    """Verify the grouping step in _background_ingest loads from JSON, not Supabase."""

    def test_grouping_uses_json_load_not_load_registry(self):
        """The grouping step must use IdentityRegistry.load() not _main_mod.load_registry()."""
        upload_routes = Path("app/upload_routes.py").read_text()

        # Find the grouping section (AD-216)
        grouping_section = upload_routes[
            upload_routes.index("AD-216: Group similar unknown faces") : upload_routes.index(
                "PRD-049: Cross-batch matching"
            )
        ]

        # Must NOT use _main_mod.load_registry() — that reads from Supabase
        assert "_main_mod.load_registry()" not in grouping_section, (
            "Grouping step must load from JSON, not Supabase via load_registry(). "
            "process_directory() writes to JSON; Supabase doesn't have new data yet."
        )

        # Must NOT use _main_mod.load_photo_registry()
        assert "_main_mod.load_photo_registry()" not in grouping_section, (
            "Grouping step must load photo registry from JSON, not Supabase."
        )

        # Must use direct JSON load
        assert "IdentityRegistry" in grouping_section or "_IR_grp" in grouping_section, (
            "Grouping step must import and use IdentityRegistry.load() for JSON loading."
        )

    def test_cross_batch_uses_json_photo_registry(self):
        """Cross-batch matching must load photo registry from JSON, not Supabase."""
        upload_routes = Path("app/upload_routes.py").read_text()

        # Find the cross-batch section (PRD-049)
        xb_start = upload_routes.index("PRD-049: Cross-batch matching")
        # Find the next major section (Supabase sync)
        xb_end = upload_routes.index("Supabase sync", xb_start)
        xb_section = upload_routes[xb_start:xb_end]

        # Must NOT use _main_mod.load_photo_registry()
        assert "_main_mod.load_photo_registry()" not in xb_section, (
            "Cross-batch matching must load photo registry from JSON. "
            "Supabase doesn't have new photos until after the sync step."
        )

    def test_post_sync_validation_uses_warning_not_error(self):
        """Post-sync validation should use warning level (orphan repair is non-critical)."""
        upload_routes = Path("app/upload_routes.py").read_text()
        lines = upload_routes.splitlines()

        # Find the line with the POST-SYNC VALIDATION log message (not comments)
        for i, line in enumerate(lines):
            if "POST-SYNC VALIDATION" in line and 'f"' in line:
                # Check the preceding line for .warning( vs .error(
                context = "\n".join(lines[max(0, i - 3) : i + 1])
                assert ".warning(" in context, (
                    f"Post-sync validation should use warning level, not error. Found at line {i + 1}: {context}"
                )
                return

        raise AssertionError("Could not find POST-SYNC VALIDATION log message in upload_routes.py")
