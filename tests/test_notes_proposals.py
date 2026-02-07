"""Tests for Phase 5: Identity notes and proposed matches."""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestRegistryNotes:
    """Tests for the registry add_note/get_notes methods."""

    def _make_registry(self, tmp_path):
        """Create a test registry with one identity."""
        from core.registry import IdentityRegistry
        data = {
            "schema_version": 1,
            "identities": {
                "id-1": {
                    "identity_id": "id-1",
                    "name": "Test Person",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            },
            "history": [],
        }
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        return IdentityRegistry.load(path)

    def test_add_note(self, tmp_path):
        """Can add a note to an identity."""
        registry = self._make_registry(tmp_path)
        note = registry.add_note("id-1", "This might be young Moise", author="test@test.com")

        assert note["text"] == "This might be young Moise"
        assert note["author"] == "test@test.com"
        assert "timestamp" in note
        assert "id" in note

    def test_get_notes(self, tmp_path):
        """Can retrieve notes for an identity."""
        registry = self._make_registry(tmp_path)
        registry.add_note("id-1", "Note 1")
        registry.add_note("id-1", "Note 2")

        notes = registry.get_notes("id-1")
        assert len(notes) == 2
        assert notes[0]["text"] == "Note 1"
        assert notes[1]["text"] == "Note 2"

    def test_get_notes_empty(self, tmp_path):
        """Empty notes list for identity without notes."""
        registry = self._make_registry(tmp_path)
        notes = registry.get_notes("id-1")
        assert notes == []

    def test_add_note_updates_timestamp(self, tmp_path):
        """Adding a note updates identity's updated_at."""
        registry = self._make_registry(tmp_path)
        old_time = registry.get_identity("id-1")["updated_at"]
        registry.add_note("id-1", "New note")
        new_time = registry.get_identity("id-1")["updated_at"]
        assert new_time > old_time


class TestRegistryProposedMatches:
    """Tests for the registry proposed match methods."""

    def _make_registry(self, tmp_path):
        """Create a test registry with two identities."""
        from core.registry import IdentityRegistry
        data = {
            "schema_version": 1,
            "identities": {
                "id-1": {
                    "identity_id": "id-1",
                    "name": "Person A",
                    "state": "INBOX",
                    "anchor_ids": ["face-1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
                "id-2": {
                    "identity_id": "id-2",
                    "name": "Person B",
                    "state": "CONFIRMED",
                    "anchor_ids": ["face-2"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                },
            },
            "history": [],
        }
        path = tmp_path / "identities.json"
        path.write_text(json.dumps(data))
        return IdentityRegistry.load(path)

    def test_add_proposed_match(self, tmp_path):
        """Can propose a match between two identities."""
        registry = self._make_registry(tmp_path)
        proposal = registry.add_proposed_match(
            "id-1", "id-2", note="Looks like same person", author="test@test.com"
        )

        assert proposal["target_id"] == "id-2"
        assert proposal["note"] == "Looks like same person"
        assert proposal["status"] == "pending"

    def test_list_proposed_matches(self, tmp_path):
        """Can list all pending proposed matches."""
        registry = self._make_registry(tmp_path)
        registry.add_proposed_match("id-1", "id-2", note="Test")

        proposals = registry.list_proposed_matches()
        assert len(proposals) == 1
        assert proposals[0]["source_id"] == "id-1"
        assert proposals[0]["target_id"] == "id-2"

    def test_no_duplicate_proposals(self, tmp_path):
        """Adding same proposal twice returns existing one."""
        registry = self._make_registry(tmp_path)
        p1 = registry.add_proposed_match("id-1", "id-2")
        p2 = registry.add_proposed_match("id-1", "id-2")

        assert p1["id"] == p2["id"]  # Same proposal
        proposals = registry.list_proposed_matches()
        assert len(proposals) == 1

    def test_resolve_proposed_match(self, tmp_path):
        """Can accept or reject a proposal."""
        registry = self._make_registry(tmp_path)
        proposal = registry.add_proposed_match("id-1", "id-2")

        result = registry.resolve_proposed_match("id-1", proposal["id"], "rejected")
        assert result["status"] == "rejected"

        # Should no longer appear in pending list
        proposals = registry.list_proposed_matches()
        assert len(proposals) == 0


class TestNotesEndpoints:
    """Tests for the notes API endpoints."""

    def test_notes_get_endpoint(self, client, auth_disabled):
        """GET /api/identity/{id}/notes returns notes panel."""
        with patch("app.main.load_registry") as mock_reg:
            registry = MagicMock()
            registry.get_notes.return_value = [
                {"id": "n1", "text": "Test note", "author": "test@t.com", "timestamp": "2026-01-01T00:00:00Z"},
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/identity/id-1/notes")
            assert resp.status_code == 200
            assert "Test note" in resp.text
            assert "Notes" in resp.text

    def test_notes_add_requires_admin(self, client, auth_enabled, regular_user):
        """POST /api/identity/{id}/notes requires admin."""
        resp = client.post(
            "/api/identity/id-1/notes",
            data={"text": "Test"},
            headers={"HX-Request": "true"}
        )
        assert resp.status_code in (401, 403)


class TestProposedMatchesEndpoints:
    """Tests for the proposed matches API endpoints."""

    def test_proposed_matches_list(self, client, auth_disabled):
        """GET /api/proposed-matches returns pending proposals."""
        with patch("app.main.load_registry") as mock_reg, \
             patch("app.main.get_crop_files", return_value=set()):
            registry = MagicMock()
            registry.list_proposed_matches.return_value = [
                {
                    "source_id": "id-1",
                    "source_name": "Person A",
                    "target_id": "id-2",
                    "target_name": "Person B",
                    "id": "p1",
                    "note": "Looks similar",
                    "author": "test@t.com",
                    "status": "pending",
                    "timestamp": "2026-01-01T00:00:00Z",
                },
            ]
            mock_reg.return_value = registry

            resp = client.get("/api/proposed-matches")
            assert resp.status_code == 200
            assert "Person A" in resp.text
            assert "Person B" in resp.text
            assert "Accept" in resp.text

    def test_proposed_matches_empty(self, client, auth_disabled):
        """Empty proposals shows empty state."""
        with patch("app.main.load_registry") as mock_reg:
            registry = MagicMock()
            registry.list_proposed_matches.return_value = []
            mock_reg.return_value = registry

            resp = client.get("/api/proposed-matches")
            assert "No pending proposals" in resp.text


class TestNotesInExpandedCard:
    """Tests for notes section in the expanded identity card."""

    def test_expanded_card_has_notes_section(self):
        """Expanded identity card includes a notes button."""
        from app.main import identity_card_expanded, to_xml

        identity = {
            "identity_id": "test-id",
            "name": "Test Person",
            "state": "INBOX",
            "anchor_ids": ["face-1"],
            "candidate_ids": [],
        }

        html = to_xml(identity_card_expanded(identity, set(), is_admin=True))
        assert "Notes" in html
        assert "/api/identity/test-id/notes" in html
