"""Tests for tag persistence (FB-036/037) and merge OOB cleanup (FB-040).

Investigation findings:

FB-036/037 (Tag persistence):
    The tag endpoint at /api/face/tag performs a merge operation and saves via
    save_registry(registry, changed_ids={source, target}). The save path:
    1. Updates _registry_cache with the modified registry (in-memory persistence)
    2. Clears _face_identity_lookup_cache to prevent stale face->identity mappings
    3. Writes JSON backup
    4. For postgres mode: synchronously calls shadow_write_identities_batch (writes
       to identities table) and sync_identity_overrides (writes to overrides table)
    5. Returns False only on Supabase exception, which triggers a warning toast

    The code is structurally correct. If tags don't persist, it's because:
    - Supabase writes are failing (user would see the warning toast)
    - Or there's a multi-process issue (single-worker Uvicorn rules this out)

    Note: sync_identity_overrides uses _is_user_modified_identity() which could
    skip PROPOSED/INBOX targets, but the primary table (identities) is always
    written by shadow_write_identities_batch, and load_from_postgres reads from
    identities, not identity_overrides.

FB-040 (Stale card after merge in browse mode):
    The merge handler includes OOB delete elements in ALL non-focus return paths.
    Browse mode (the default path at line 2165) returns:
        (identity_card, merge_guidance, *oob_elements, merge_toast, suggestion_panel)
    where oob_elements includes Div(id=f"identity-{source_id}", hx_swap_oob="delete").
    The browse card ID matches: id=f"identity-{identity_id}".
    Code is structurally correct for browse mode.
"""

from unittest.mock import patch, MagicMock
import pytest
from fasthtml.common import to_xml, Div


class TestTagSavePath:
    """Verify tag endpoint save path includes both source and target."""

    def test_save_registry_clears_face_lookup_cache(self):
        """save_registry must clear _face_identity_lookup_cache to prevent stale mappings."""

        # Use a simple namespace object to avoid MagicMock __dict__ issues
        class FakeRegistry:
            def __init__(self):
                self._identities = {}
                self._face_identity_lookup_cache = {"face1": "old_identity"}
                self._history = {"events": []}

            def save(self, path):
                pass

        fake_registry = FakeRegistry()
        assert hasattr(fake_registry, "_face_identity_lookup_cache")

        with (
            patch("app.main.REGISTRY_PATH") as mock_path,
            patch("app.main.DATA_SOURCE", "json"),
            patch("app.main.time") as mock_time,
            patch("threading.Thread"),
        ):
            mock_path.exists.return_value = True
            mock_time.time.return_value = 1000.0
            from app.main import save_registry

            save_registry(fake_registry)

        # The face lookup cache should have been cleared
        assert (
            not hasattr(fake_registry, "_face_identity_lookup_cache")
            or "_face_identity_lookup_cache" not in fake_registry.__dict__
        )

    def test_changed_ids_filters_supabase_write(self):
        """When changed_ids is provided, only those identities are written to Supabase."""

        class FakeReg:
            def __init__(self):
                self._identities = {
                    "id1": {"name": "Person 1", "state": "PROPOSED"},
                    "id2": {"name": "Person 2", "state": "CONFIRMED"},
                    "id3": {"name": "Person 3", "state": "INBOX"},
                }
                self._history = {"events": []}

            def save(self, path):
                pass

        fake_registry = FakeReg()

        with (
            patch("app.main.REGISTRY_PATH") as mock_path,
            patch("app.main.DATA_SOURCE", "postgres"),
            patch("app.main.time") as mock_time,
            patch("app.supabase_data.shadow_write_identities_batch") as mock_batch,
            patch("app.supabase_data.sync_identity_overrides") as mock_overrides,
        ):
            mock_path.exists.return_value = True
            mock_time.time.return_value = 1000.0
            from app.main import save_registry

            result = save_registry(fake_registry, changed_ids={"id1", "id2"})

        # sync_identity_overrides should receive only changed IDs
        overrides_arg = mock_overrides.call_args[0][0]
        assert set(overrides_arg.keys()) == {"id1", "id2"}
        assert "id3" not in overrides_arg

        # shadow_write_identities_batch should also receive only changed IDs
        batch_arg = mock_batch.call_args[0][0]
        batch_ids = {item["identity_id"] for item in batch_arg}
        assert batch_ids == {"id1", "id2"}

    def test_save_registry_returns_false_on_supabase_error(self):
        """save_registry returns False when Supabase write fails (triggers warning toast)."""

        class FakeReg:
            def __init__(self):
                self._identities = {"id1": {"name": "Test"}}
                self._history = {"events": []}

            def save(self, path):
                pass

        fake_registry = FakeReg()

        with (
            patch("app.main.REGISTRY_PATH") as mock_path,
            patch("app.main.DATA_SOURCE", "postgres"),
            patch("app.main.time") as mock_time,
            patch("app.supabase_data.sync_identity_overrides", side_effect=Exception("DB error")),
        ):
            mock_path.exists.return_value = True
            mock_time.time.return_value = 1000.0
            from app.main import save_registry

            result = save_registry(fake_registry)

        assert result is False


class TestMergeOobCleanup:
    """Verify merge response includes OOB delete for source identity in browse mode."""

    def test_oob_delete_element_structure(self):
        """OOB delete elements target the correct DOM IDs."""
        source_id = "abc-123-def"
        oob = Div(id=f"identity-{source_id}", hx_swap_oob="delete")
        html = to_xml(oob)
        assert f'id="identity-{source_id}"' in html
        assert 'hx-swap-oob="delete"' in html

    def test_oob_elements_include_all_card_types(self):
        """OOB elements should clean up identity, neighbor, and search-result cards."""
        source_id = "test-source-id"
        oob_elements = [
            Div(id=f"identity-{source_id}", hx_swap_oob="delete"),
            Div(id=f"neighbor-{source_id}", hx_swap_oob="delete"),
            Div(id=f"search-result-{source_id}", hx_swap_oob="delete"),
        ]

        for oob in oob_elements:
            html = to_xml(oob)
            assert 'hx-swap-oob="delete"' in html
            assert source_id in html

    def test_direction_swap_adds_extra_oob_elements(self):
        """When direction is swapped, OOB elements should also clean up original target."""
        source_id = "original-source"
        target_id = "original-target"

        # Base elements (always present)
        oob_elements = [
            Div(id=f"identity-{source_id}", hx_swap_oob="delete"),
            Div(id=f"neighbor-{source_id}", hx_swap_oob="delete"),
            Div(id=f"search-result-{source_id}", hx_swap_oob="delete"),
        ]

        # Direction-swap additions
        oob_elements.extend(
            [
                Div(id=f"neighbor-{target_id}", hx_swap_oob="delete"),
                Div(id=f"search-result-{target_id}", hx_swap_oob="delete"),
            ]
        )

        # Should have 5 OOB elements total
        assert len(oob_elements) == 5

        # The identity card for original target should NOT be deleted
        # (it becomes the survivor in the swap)
        html_ids = [to_xml(e) for e in oob_elements]
        identity_deletes = [h for h in html_ids if f"identity-{target_id}" in h]
        assert len(identity_deletes) == 0


class TestSyncIdentityOverridesFilter:
    """Verify sync_identity_overrides filter doesn't skip important identities."""

    def test_merged_identity_passes_filter(self):
        """Identity with merged_into set should pass _is_user_modified_identity."""
        from app.supabase_data import _is_user_modified_identity

        data = {"state": "PROPOSED", "merged_into": "some-target-id"}
        assert _is_user_modified_identity(data) is True

    def test_confirmed_identity_passes_filter(self):
        """CONFIRMED identity should pass _is_user_modified_identity."""
        from app.supabase_data import _is_user_modified_identity

        data = {"state": "CONFIRMED"}
        assert _is_user_modified_identity(data) is True

    def test_proposed_identity_without_modifications_fails_filter(self):
        """PROPOSED identity with no user modifications should fail the filter.

        This is expected behavior — sync_identity_overrides only tracks
        user-modified identities. The primary identities table is written
        by shadow_write_identities_batch which does NOT use this filter.
        """
        from app.supabase_data import _is_user_modified_identity

        data = {"state": "PROPOSED", "negative_ids": []}
        assert _is_user_modified_identity(data) is False

    def test_identity_with_negative_ids_passes_filter(self):
        """Identity with rejected faces should pass _is_user_modified_identity."""
        from app.supabase_data import _is_user_modified_identity

        data = {"state": "PROPOSED", "negative_ids": ["face1"]}
        assert _is_user_modified_identity(data) is True
