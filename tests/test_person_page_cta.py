"""Tests for Session 127 Phase 2D: Person page CTA + Confirmed merge friction.

Tests cover:
- "Can you help?" CTA for CONFIRMED persons with unknown fields (non-admin)
- CTA hidden for admin users
- CTA hidden for non-CONFIRMED persons
- CTA hidden when all fields are known
- Merge confirmation gate rendered for CONFIRMED persons (admin)
- Merge confirmation gate NOT rendered for non-CONFIRMED persons
"""

from unittest.mock import MagicMock, patch

import pytest
from fastcore.xml import to_xml


def _make_identity(
    person_id="test-person-id",
    name="Vida Capeluto",
    state="CONFIRMED",
    birth_year=None,
    death_year=None,
    birth_place=None,
):
    identity = {
        "identity_id": person_id,
        "name": name,
        "state": state,
        "anchor_ids": ["face1"],
        "candidate_ids": [],
        "negative_ids": [],
        "metadata": {},
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    if birth_year:
        identity["birth_year"] = birth_year
    if death_year:
        identity["death_year"] = death_year
    if birth_place:
        identity["birth_place"] = birth_place
    return identity


def _render_person_page(identity, is_admin=False):
    """Render the person page with standard mocks and return HTML string."""
    from app.main import public_person_page

    person_id = identity["identity_id"]

    with (
        patch("app.main.load_registry") as mock_reg,
        patch("app.main.load_photo_registry") as mock_photo_reg,
        patch("app.main.get_crop_files", return_value={}),
        patch("app.main.get_photo_metadata", return_value=None),
        patch("app.main.get_best_face_id", return_value=None),
        patch("app.main.resolve_face_image_url", return_value=None),
        patch("app.main.get_identity_for_face", return_value=None),
        patch("app.main.get_photo_id_for_face", return_value=None),
        patch("app.main._load_birth_year_estimates", return_value={}),
        patch("app.main._load_ml_review_decisions", return_value={}),
        patch("app.main._load_annotations", return_value={"annotations": {}}),
    ):
        mock_reg.return_value.get_identity.return_value = identity
        mock_photo_reg.return_value.get_photos_for_faces.return_value = []

        result = public_person_page(person_id, is_admin=is_admin)
        return to_xml(result)


# ============================================================
# "Can you help?" CTA tests
# ============================================================


class TestCanYouHelpCTA:
    """Tests for the community CTA on confirmed person pages."""

    def test_cta_shown_for_confirmed_person_with_unknown_birth(self):
        """CONFIRMED person with no birth year shows CTA to non-admin."""
        identity = _make_identity(state="CONFIRMED", birth_year=None)
        html = _render_person_page(identity, is_admin=False)
        assert 'data-testid="can-you-help-cta"' in html
        assert "when they were born" in html
        assert "Share what you know" in html

    def test_cta_shown_for_confirmed_person_with_unknown_death(self):
        """CONFIRMED person with no death year shows CTA to non-admin."""
        identity = _make_identity(state="CONFIRMED", death_year=None)
        html = _render_person_page(identity, is_admin=False)
        assert 'data-testid="can-you-help-cta"' in html
        assert "when they passed away" in html

    def test_cta_shown_for_confirmed_person_with_unknown_birthplace(self):
        """CONFIRMED person with no birth place shows CTA to non-admin."""
        identity = _make_identity(state="CONFIRMED", birth_place=None)
        html = _render_person_page(identity, is_admin=False)
        assert 'data-testid="can-you-help-cta"' in html
        assert "where they were from" in html

    def test_cta_combines_multiple_unknown_fields(self):
        """CTA lists multiple unknown fields with 'or' conjunction."""
        identity = _make_identity(state="CONFIRMED", birth_year=None, death_year=None, birth_place=None)
        html = _render_person_page(identity, is_admin=False)
        assert 'data-testid="can-you-help-cta"' in html
        assert "when they were born" in html
        assert "when they passed away" in html
        assert "where they were from" in html

    def test_cta_hidden_when_all_fields_known(self):
        """No CTA when birth year, death year, and birth place are all set."""
        identity = _make_identity(state="CONFIRMED", birth_year=1905, death_year=1985, birth_place="Rhodes, Greece")
        html = _render_person_page(identity, is_admin=False)
        assert 'data-testid="can-you-help-cta"' not in html

    def test_cta_hidden_for_admin(self):
        """Admin users do not see the CTA (they have edit controls instead)."""
        identity = _make_identity(state="CONFIRMED", birth_year=None)
        html = _render_person_page(identity, is_admin=True)
        assert 'data-testid="can-you-help-cta"' not in html

    def test_cta_hidden_for_proposed_person(self):
        """PROPOSED persons do not show the CTA."""
        identity = _make_identity(name="Unidentified Person 42", state="PROPOSED", birth_year=None)
        html = _render_person_page(identity, is_admin=False)
        assert 'data-testid="can-you-help-cta"' not in html

    def test_cta_hidden_for_inbox_person(self):
        """INBOX persons do not show the CTA."""
        identity = _make_identity(name="Unidentified Person 99", state="INBOX", birth_year=None)
        html = _render_person_page(identity, is_admin=False)
        assert 'data-testid="can-you-help-cta"' not in html

    def test_cta_includes_person_name(self):
        """CTA text includes the person's display name."""
        identity = _make_identity(name="Vida Capeluto", state="CONFIRMED", birth_year=None)
        html = _render_person_page(identity, is_admin=False)
        assert "Vida Capeluto" in html
        assert "complete" in html.lower()


# ============================================================
# Merge confirmation friction tests
# ============================================================


class TestMergeConfirmationFriction:
    """Tests for merge confirmation gate on confirmed person pages."""

    def test_merge_confirm_gate_shown_for_confirmed_person(self):
        """CONFIRMED person pages have a merge confirmation gate (admin only)."""
        identity = _make_identity(state="CONFIRMED")
        html = _render_person_page(identity, is_admin=True)
        assert 'data-testid="merge-confirm-gate"' in html
        assert "This person is confirmed" in html
        assert "Yes, merge anyway" in html

    def test_merge_confirm_gate_hidden_for_proposed_person(self):
        """PROPOSED person pages do not have the merge confirmation gate."""
        identity = _make_identity(name="Unidentified Person 42", state="PROPOSED")
        html = _render_person_page(identity, is_admin=True)
        assert 'data-testid="merge-confirm-gate"' not in html

    def test_merge_confirm_gate_hidden_for_inbox_person(self):
        """INBOX person pages do not have the merge confirmation gate."""
        identity = _make_identity(name="Unidentified Person 99", state="INBOX")
        html = _render_person_page(identity, is_admin=True)
        assert 'data-testid="merge-confirm-gate"' not in html

    def test_merge_search_still_present_for_confirmed(self):
        """Merge search input is still present even with confirmation gate."""
        identity = _make_identity(state="CONFIRMED")
        html = _render_person_page(identity, is_admin=True)
        assert 'data-testid="merge-search"' in html
        assert "Search to merge" in html

    def test_merge_confirm_gate_has_cancel_button(self):
        """Confirmation gate has a Cancel button to dismiss without merging."""
        identity = _make_identity(state="CONFIRMED")
        html = _render_person_page(identity, is_admin=True)
        # The gate should have both confirm and cancel
        assert "Yes, merge anyway" in html
        assert "Cancel" in html
