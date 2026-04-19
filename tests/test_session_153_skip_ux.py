"""
Session 153 — Accidental-skip UX regression tests.

Bug: an admin could accidentally tap the 24x24 amber skip pill inside a face
bbox while trying to click the face itself, flipping the identity to SKIPPED
with no visible undo affordance. The restore endpoint explicitly blocked
SKIPPED, so the only recovery path was a backend script.

These tests lock in the fixed behavior:

1. Restore endpoint accepts SKIPPED and transitions SKIPPED -> INBOX.
2. Quick-action skip response embeds undo metadata (data-undo-url,
   data-undo-type="skip", Undo button) pointing at /api/identity/{id}/restore.
3. The person page renders a "Restore (was skipped)" button when
   state == "SKIPPED".
4. The identity_card component renders a Restore pill for SKIPPED (in
   addition to REJECTED/CONTESTED).
5. The inline skip pill in the photo viewer is at least 36x36 px, lives
   outside the face bbox, carries hx_confirm, and ships data-undo-* hooks
   for the Z-key undo stack.

See docs/feedback/session-153-skip-ux-investigation.md and
docs/feedback/session-153-codex-audit.md (P1 finding: "UX undo proposal
incomplete").
"""

from unittest.mock import MagicMock, patch

import pytest
from fasthtml.common import to_xml
from starlette.testclient import TestClient

from core.registry import IdentityRegistry, IdentityState


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_skipped_registry(name: str = "Accidentally Skipped"):
    """Create a registry with one SKIPPED identity for restore tests."""
    registry = IdentityRegistry()
    identity_id = registry.create_identity(
        anchor_ids=["face_skip_a"], user_source="test", name=name
    )
    # INBOX -> SKIPPED simulates an admin quick-action skip
    registry.skip_identity(identity_id, user_source="test")
    assert registry.get_identity(identity_id)["state"] == "SKIPPED"
    return registry, identity_id


def _make_photo_meta(face_ids=None):
    """Mock photo metadata matching the shape expected by photo_view_content."""
    faces = []
    for i, fid in enumerate(face_ids or []):
        faces.append(
            {
                "face_id": fid,
                "bbox": [10 + i * 50, 10, 60 + i * 50, 100],
            }
        )
    return {
        "filename": "test_photo.jpg",
        "faces": faces,
        "source": "Test",
    }


def _make_identity_dict(identity_id: str, name: str, state: str, face_ids=None):
    return {
        "identity_id": identity_id,
        "name": name,
        "state": state,
        "anchor_ids": face_ids if state == "CONFIRMED" else [],
        "candidate_ids": face_ids if state != "CONFIRMED" else [],
        "negative_ids": [],
    }


# ---------------------------------------------------------------------------
# 1. Restore endpoint accepts SKIPPED
# ---------------------------------------------------------------------------


class TestRestoreAcceptsSkipped:
    """Regression: /api/identity/{id}/restore used to 400 on SKIPPED."""

    _PATCH_PREFIX = "app.identity_routes._main_mod"

    def test_restore_skipped_to_inbox(self):
        """Restoring a SKIPPED identity should transition it to INBOX."""
        import app.main as main_mod

        registry, identity_id = _make_skipped_registry()

        with (
            patch(f"{self._PATCH_PREFIX}.load_registry", return_value=registry),
            patch(f"{self._PATCH_PREFIX}.save_registry"),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=None),
            patch(f"{self._PATCH_PREFIX}.is_auth_enabled", return_value=False),
            patch(f"{self._PATCH_PREFIX}.log_user_action"),
            patch(
                f"{self._PATCH_PREFIX}._check_merged_identity",
                return_value=(False, None),
            ),
            patch(f"{self._PATCH_PREFIX}.get_current_user", return_value=None),
            patch("app.identity_routes._check_origin", return_value=None),
            patch("app.identity_routes._log_audit") as mock_audit,
        ):
            client = TestClient(main_mod.app)
            response = client.post(
                f"/api/identity/{identity_id}/restore?from_person_page=true"
            )

        assert response.status_code == 200
        assert registry.get_identity(identity_id)["state"] == "INBOX"
        # Audit log row must be emitted for SKIPPED -> INBOX transitions
        assert mock_audit.called, "restore must write an audit_log row"
        audit_call = mock_audit.call_args
        assert audit_call.args[0] == "restore"
        old_value = audit_call.kwargs.get("old_value", {})
        new_value = audit_call.kwargs.get("new_value", {})
        assert old_value.get("state") == "SKIPPED"
        assert new_value.get("state") == "INBOX"

    def test_restore_skipped_error_message_mentions_skipped(self):
        """Error message for invalid restore must mention the SKIPPED allowlist."""
        import app.main as main_mod

        # CONFIRMED is still not restorable
        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_c"], user_source="test", name="Confirmed Person"
        )
        registry.confirm_identity(identity_id, user_source="test")

        with (
            patch(f"{self._PATCH_PREFIX}.load_registry", return_value=registry),
            patch(f"{self._PATCH_PREFIX}.save_registry"),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=None),
            patch(f"{self._PATCH_PREFIX}.is_auth_enabled", return_value=False),
            patch(
                f"{self._PATCH_PREFIX}._check_merged_identity",
                return_value=(False, None),
            ),
            patch("app.identity_routes._check_origin", return_value=None),
        ):
            client = TestClient(main_mod.app)
            response = client.post(f"/api/identity/{identity_id}/restore")

        assert response.status_code == 400
        # New error message advertises the expanded allowlist
        assert "SKIPPED" in response.text
        assert "REJECTED" in response.text

    def test_restore_contested_still_works(self):
        """Regression: restore must still accept CONTESTED (previous behavior)."""
        import app.main as main_mod

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_ct"], user_source="test", name="Contested Person"
        )
        registry.contest_identity(identity_id, user_source="test", reason="test")

        with (
            patch(f"{self._PATCH_PREFIX}.load_registry", return_value=registry),
            patch(f"{self._PATCH_PREFIX}.save_registry"),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=None),
            patch(f"{self._PATCH_PREFIX}.is_auth_enabled", return_value=False),
            patch(f"{self._PATCH_PREFIX}.log_user_action"),
            patch(
                f"{self._PATCH_PREFIX}._check_merged_identity",
                return_value=(False, None),
            ),
            patch(f"{self._PATCH_PREFIX}.get_current_user", return_value=None),
            patch("app.identity_routes._check_origin", return_value=None),
            patch("app.identity_routes._log_audit"),
        ):
            client = TestClient(main_mod.app)
            response = client.post(f"/api/identity/{identity_id}/restore")

        assert response.status_code == 200
        assert registry.get_identity(identity_id)["state"] == "INBOX"


# ---------------------------------------------------------------------------
# 2. quick-action skip response carries undo metadata
# ---------------------------------------------------------------------------


class TestQuickActionSkipUndoMetadata:
    """Regression: accidental-skip must surface an inline Undo path."""

    _PATCH_PREFIX = "app.identity_routes._main_mod"

    def test_skip_response_includes_undo_button(self):
        """Response toast for action=skip carries an Undo button POSTing to restore."""
        import app.main as main_mod

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a"], user_source="test", name="Test Person"
        )
        # Current state is PROPOSED (default). action=skip will flip to SKIPPED.

        # photo_view_content re-render is heavy; stub it out so the test focuses
        # on the undo metadata the route adds to the OOB toast.
        def _fake_photo_content(*args, **kwargs):
            from fasthtml.common import Div

            return (Div("stub", id="photo-modal-content"),)

        with (
            patch(f"{self._PATCH_PREFIX}.load_registry", return_value=registry),
            patch(f"{self._PATCH_PREFIX}.save_registry"),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=None),
            patch(f"{self._PATCH_PREFIX}.is_auth_enabled", return_value=False),
            patch(f"{self._PATCH_PREFIX}.get_current_user", return_value=None),
            patch(
                f"{self._PATCH_PREFIX}.photo_view_content", side_effect=_fake_photo_content
            ),
            patch("app.identity_routes._log_audit"),
        ):
            client = TestClient(main_mod.app)
            response = client.post(
                "/api/face/quick-action"
                f"?identity_id={identity_id}&action=skip&photo_id=test-photo"
            )

        assert response.status_code == 200
        html = response.text
        # The undo button must POST to the restore endpoint for this identity
        assert f"/api/identity/{identity_id}/restore" in html
        # Data hooks for the window._undoStack (Z-key undo)
        assert 'data-undo-type="skip"' in html
        assert f'data-undo-identity="{identity_id}"' in html
        assert 'data-undo-url=' in html
        assert 'data-undo-label=' in html
        # Human-visible Undo affordance
        assert "Undo" in html
        # Registry state actually changed
        assert registry.get_identity(identity_id)["state"] == "SKIPPED"

    def test_confirm_response_has_no_undo_metadata(self):
        """Regression guard: non-skip actions must not leak undo-skip metadata."""
        import app.main as main_mod

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_a"], user_source="test", name="Confirm Me"
        )

        def _fake_photo_content(*args, **kwargs):
            from fasthtml.common import Div

            return (Div("stub", id="photo-modal-content"),)

        with (
            patch(f"{self._PATCH_PREFIX}.load_registry", return_value=registry),
            patch(f"{self._PATCH_PREFIX}.save_registry"),
            patch(f"{self._PATCH_PREFIX}._check_admin", return_value=None),
            patch(f"{self._PATCH_PREFIX}.is_auth_enabled", return_value=False),
            patch(f"{self._PATCH_PREFIX}.get_current_user", return_value=None),
            patch(
                f"{self._PATCH_PREFIX}.photo_view_content", side_effect=_fake_photo_content
            ),
            patch("app.identity_routes._log_audit"),
        ):
            client = TestClient(main_mod.app)
            response = client.post(
                "/api/face/quick-action"
                f"?identity_id={identity_id}&action=confirm&photo_id=test-photo"
            )

        assert response.status_code == 200
        html = response.text
        # The confirm toast should NOT have the skip-undo metadata
        assert 'data-undo-type="skip"' not in html
        assert "/restore" not in html


# ---------------------------------------------------------------------------
# 3. Person page renders "Restore" for SKIPPED
# ---------------------------------------------------------------------------


class TestPersonPageRestoreForSkipped:
    """The person page must offer a Restore affordance for SKIPPED identities."""

    def test_skipped_person_page_has_restore_button(self):
        """person/{id} renders a visible Restore button when state=SKIPPED."""
        import app.main as main_mod

        registry, identity_id = _make_skipped_registry(name="Skipped Person")

        # Minimal photo registry (no faces linked)
        from core.photo_registry import PhotoRegistry

        photo_reg = PhotoRegistry()

        with (
            patch("app.main.load_registry", return_value=registry),
            patch("app.main.load_photo_registry", return_value=photo_reg),
            patch("app.main.is_auth_enabled", return_value=False),
        ):
            client = TestClient(main_mod.app)
            response = client.get(f"/person/{identity_id}")

        assert response.status_code == 200
        html = response.text
        # Amber "Restore (was skipped)" button with the new testid
        assert 'data-testid="person-restore-skipped"' in html
        assert "Restore" in html
        # Should POST to the restore endpoint, from_person_page=true
        assert f"/api/identity/{identity_id}/restore" in html
        assert "from_person_page=true" in html


# ---------------------------------------------------------------------------
# 4. Identity card renders Restore for SKIPPED
# ---------------------------------------------------------------------------


class TestIdentityCardRestoreForSkipped:
    """identity_card must show a Restore pill for SKIPPED admins."""

    def test_identity_card_skipped_shows_restore(self):
        """identity_card for SKIPPED admin view renders the Restore pill."""
        from app.components.identity_cards import identity_card

        registry, identity_id = _make_skipped_registry(name="Skipped Person")
        identity = registry.get_identity(identity_id)

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch(
                "app.main._get_best_match_for_identity",
                return_value=None,
            ),
            patch(
                "app.main.load_registry",
                return_value=registry,
            ),
        ):
            card = identity_card(identity, crop_files=[], show_actions=True)
            html = to_xml(card)

        assert "Restore" in html
        assert 'data-testid="identity-card-restore-skipped"' in html
        assert f"/api/identity/{identity_id}/restore" in html

    def test_identity_card_rejected_still_shows_restore(self):
        """Regression: REJECTED still shows Restore (pre-Session-153 behavior)."""
        from app.components.identity_cards import identity_card

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_r"], user_source="test", name="Rejected Person"
        )
        registry.reject_identity(identity_id, user_source="test")
        identity = registry.get_identity(identity_id)

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch(
                "app.main._get_best_match_for_identity",
                return_value=None,
            ),
            patch(
                "app.main.load_registry",
                return_value=registry,
            ),
        ):
            card = identity_card(identity, crop_files=[], show_actions=True)
            html = to_xml(card)

        assert "Restore" in html
        assert 'data-testid="identity-card-restore-rejected"' in html

    def test_identity_card_confirmed_has_no_restore(self):
        """CONFIRMED identities must NOT show a Restore button."""
        from app.components.identity_cards import identity_card

        registry = IdentityRegistry()
        identity_id = registry.create_identity(
            anchor_ids=["face_cf"], user_source="test", name="Confirmed Person"
        )
        registry.confirm_identity(identity_id, user_source="test")
        identity = registry.get_identity(identity_id)

        with (
            patch("app.main.is_auth_enabled", return_value=False),
            patch(
                "app.main._get_best_match_for_identity",
                return_value=None,
            ),
            patch(
                "app.main.load_registry",
                return_value=registry,
            ),
        ):
            card = identity_card(identity, crop_files=[], show_actions=True)
            html = to_xml(card)

        # No restore testid for CONFIRMED
        assert 'data-testid="identity-card-restore-' not in html


# ---------------------------------------------------------------------------
# 5. Inline skip pill sizing + undo hooks
# ---------------------------------------------------------------------------


class TestInlineSkipPillRegression:
    """Skip pill in the photo viewer must be >=36x36, outside bbox, hx-confirm + undo."""

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_skip_pill_has_larger_hitbox(self, mock_reg, mock_dim, mock_meta):
        """Skip pill must use min-h-[36px] / min-w-[72px] (WCAG-closer target)."""
        from app.main import photo_view_content

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity_dict("id1", "Test", "PROPOSED", face_ids=["f1"])
        mock_reg.return_value = MagicMock()

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        # Skip pill uses a distinctive CSS class
        assert "skip-pill" in html
        # Enlarged hitbox
        assert "min-h-[36px]" in html
        assert "min-w-[72px]" in html
        # Positioned OUTSIDE the face bbox (below it)
        assert "-bottom-10" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_skip_pill_has_hx_confirm(self, mock_reg, mock_dim, mock_meta):
        """Skip pill must prompt the admin before firing the POST."""
        from app.main import photo_view_content

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity_dict("id1", "Test", "PROPOSED", face_ids=["f1"])
        mock_reg.return_value = MagicMock()

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        # hx_confirm renders as hx-confirm="..."
        assert "hx-confirm" in html
        assert "Skip this face" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_skip_pill_feeds_undo_stack(self, mock_reg, mock_dim, mock_meta):
        """Skip pill must carry data-undo-* hooks for window._undoStack."""
        from app.main import photo_view_content

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity_dict("id1", "Test", "INBOX", face_ids=["f1"])
        mock_reg.return_value = MagicMock()

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        assert 'data-undo-type="skip"' in html
        assert 'data-undo-identity="id1"' in html
        # URL points at the restore endpoint so the Z-handler can POST it
        assert "/api/identity/id1/restore" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_skip_pill_uses_text_label_not_pause_glyph(self, mock_reg, mock_dim, mock_meta):
        """The ambiguous U+23F8 pause glyph must be replaced with a text label."""
        from app.main import photo_view_content

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity_dict("id1", "Test", "PROPOSED", face_ids=["f1"])
        mock_reg.return_value = MagicMock()

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        # Text label "Skip" present; the raw pause glyph must not be used for
        # the skip pill (confirm/reject still use their glyph badges).
        assert ">Skip<" in html

    @patch("app.main.get_photo_metadata")
    @patch("app.main.get_photo_dimensions", return_value=(800, 600))
    @patch("app.main.load_registry")
    def test_skipped_state_has_no_skip_pill(self, mock_reg, mock_dim, mock_meta):
        """Regression: SKIPPED overlays must not offer another Skip action."""
        from app.main import photo_view_content

        mock_meta.return_value = _make_photo_meta(["f1"])
        identity = _make_identity_dict("id1", "Test", "SKIPPED", face_ids=["f1"])
        mock_reg.return_value = MagicMock()

        with patch("app.main.get_identity_for_face", return_value=identity):
            result = photo_view_content("p1", is_partial=True, is_admin=True)
            html = to_xml(result)

        # Neither the pill class nor the skip action may appear
        assert "skip-pill" not in html
        assert "action=skip" not in html


# ---------------------------------------------------------------------------
# 6. Z-handler case for skip — structural assertion on the emitted JS
# ---------------------------------------------------------------------------


class TestZHandlerSkipPostsToRestore:
    """The global Z-undo handler JS must POST to the restore URL for skip+url."""

    def test_z_handler_posts_when_skip_has_undo_url(self):
        """Session 153: type=='skip' with a url must fetch the url, not redirect."""
        from pathlib import Path

        # Read the source directly — the handler lives inside a Script() call
        # emitted by photo_viewer_page(). Parsing rendered HTML would require a
        # full request with a real photo, which other suites already cover.
        src = Path("app/page_routes.py").read_text(encoding="utf-8")

        # Find the Z-handler block
        idx = src.find("Z = Undo last action")
        assert idx != -1, "Z-undo handler block not found — did it move?"
        block = src[idx : idx + 2000]

        # Must POST when a restore URL is available for the skip (fetch call)
        assert "last.type === 'skip' && last.url" in block
        assert "fetch(last.url" in block
        # Legacy skipped-focus fallback must still redirect
        assert "section=skipped&view=focus" in block
