"""Tests for scripts/data_integrity_audit.py — comprehensive data integrity audit.

Covers all 9 audit checks plus fix operations.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers to create test data files
# ---------------------------------------------------------------------------


def write_identities(tmp_path: Path, identities: dict, history: list | None = None):
    """Write identities.json to tmp_path."""
    data = {
        "schema_version": 1,
        "identities": identities,
        "history": history or [],
    }
    (tmp_path / "identities.json").write_text(json.dumps(data, indent=2))


def write_photo_index(tmp_path: Path, photos: dict, face_to_photo: dict):
    """Write photo_index.json to tmp_path."""
    data = {
        "schema_version": 1,
        "photos": photos,
        "face_to_photo": face_to_photo,
    }
    (tmp_path / "photo_index.json").write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Check 1: Orphan faces
# ---------------------------------------------------------------------------


class TestOrphanFaces:
    """Faces in photo_index that have no identity assignment."""

    def test_no_orphans(self, tmp_path):
        """All faces are assigned to an identity."""
        from scripts.data_integrity_audit import AuditResult, check_orphan_faces

        photos = {"p1": {"path": "a.jpg", "face_ids": ["f1", "f2"], "collection": "C"}}
        f2p = {"f1": "p1", "f2": "p1"}
        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": ["f2"]},
        }
        result = AuditResult()
        orphans = check_orphan_faces(photos, f2p, identities, result)
        assert len(orphans) == 0
        assert result.summary["orphan_faces"] == 0

    def test_finds_orphan(self, tmp_path):
        """Detects face in photo_index with no identity."""
        from scripts.data_integrity_audit import AuditResult, check_orphan_faces

        photos = {"p1": {"path": "a.jpg", "face_ids": ["f1", "f2", "f3"], "collection": "C"}}
        f2p = {"f1": "p1", "f2": "p1", "f3": "p1"}
        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": []},
        }
        result = AuditResult()
        orphans = check_orphan_faces(photos, f2p, identities, result)
        assert "f2" in orphans
        assert "f3" in orphans
        assert result.summary["orphan_faces"] == 2

    def test_skips_merged_identities(self, tmp_path):
        """Faces in merged identities are NOT counted as assigned."""
        from scripts.data_integrity_audit import AuditResult, check_orphan_faces

        f2p = {"f1": "p1", "f2": "p1"}
        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": [], "merged_into": "id2"},
            "id2": {"anchor_ids": ["f2"], "candidate_ids": []},
        }
        result = AuditResult()
        orphans = check_orphan_faces({}, f2p, identities, result)
        # f1 is in a merged identity, so not counted as assigned
        assert "f1" in orphans

    def test_handles_dict_anchors(self):
        """Handles anchor_ids that are dicts with face_id key."""
        from scripts.data_integrity_audit import AuditResult, check_orphan_faces

        f2p = {"f1": "p1"}
        identities = {
            "id1": {"anchor_ids": [{"face_id": "f1"}], "candidate_ids": []},
        }
        result = AuditResult()
        orphans = check_orphan_faces({}, f2p, identities, result)
        assert len(orphans) == 0


# ---------------------------------------------------------------------------
# Check 2: Ghost identities
# ---------------------------------------------------------------------------


class TestGhostIdentities:
    """Identities whose faces don't exist in any photo."""

    def test_no_ghosts(self):
        """All identity faces exist in face_to_photo."""
        from scripts.data_integrity_audit import AuditResult, check_ghost_identities

        f2p = {"f1": "p1", "f2": "p1"}
        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": ["f2"]},
        }
        result = AuditResult()
        ghosts = check_ghost_identities(f2p, identities, result)
        assert len(ghosts) == 0

    def test_finds_ghost(self):
        """Detects identity where ALL faces are missing from photo_index."""
        from scripts.data_integrity_audit import AuditResult, check_ghost_identities

        f2p = {"f1": "p1"}
        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": []},
            "id_ghost": {"anchor_ids": ["f_missing"], "candidate_ids": ["f_also_missing"]},
        }
        result = AuditResult()
        ghosts = check_ghost_identities(f2p, identities, result)
        assert "id_ghost" in ghosts
        assert result.has_critical

    def test_partial_missing_not_ghost(self):
        """Identity with SOME faces missing is NOT a ghost (only ALL missing counts)."""
        from scripts.data_integrity_audit import AuditResult, check_ghost_identities

        f2p = {"f1": "p1"}
        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": ["f_missing"]},
        }
        result = AuditResult()
        ghosts = check_ghost_identities(f2p, identities, result)
        assert len(ghosts) == 0

    def test_skips_merged(self):
        """Merged identities are ignored."""
        from scripts.data_integrity_audit import AuditResult, check_ghost_identities

        f2p = {"f1": "p1"}
        identities = {
            "id1": {"anchor_ids": ["f_gone"], "candidate_ids": [], "merged_into": "id2"},
        }
        result = AuditResult()
        ghosts = check_ghost_identities(f2p, identities, result)
        assert len(ghosts) == 0

    def test_identity_with_no_faces(self):
        """Identity with empty face lists is not a ghost (separate issue)."""
        from scripts.data_integrity_audit import AuditResult, check_ghost_identities

        f2p = {}
        identities = {
            "id1": {"anchor_ids": [], "candidate_ids": []},
        }
        result = AuditResult()
        ghosts = check_ghost_identities(f2p, identities, result)
        assert len(ghosts) == 0


# ---------------------------------------------------------------------------
# Check 3: Missing identity face refs
# ---------------------------------------------------------------------------


class TestMissingIdentityFaces:
    """Identity face refs missing from photo_index.face_to_photo."""

    def test_no_missing_identity_faces(self):
        from scripts.data_integrity_audit import AuditResult, check_missing_identity_faces

        f2p = {"f1": "p1", "f2": "p1"}
        identities = {
            "id1": {"state": "CONFIRMED", "anchor_ids": ["f1"], "candidate_ids": ["f2"], "name": "Known"},
        }
        result = AuditResult()
        missing = check_missing_identity_faces(f2p, identities, result)
        assert missing == {}
        assert result.summary["missing_identity_faces"] == 0

    def test_confirmed_missing_anchor_is_critical(self):
        from scripts.data_integrity_audit import AuditResult, check_missing_identity_faces

        f2p = {"f1": "p1"}
        identities = {
            "id1": {"state": "CONFIRMED", "anchor_ids": ["f1", "f_missing"], "candidate_ids": [], "name": "Known"},
        }
        result = AuditResult()
        missing = check_missing_identity_faces(f2p, identities, result)
        assert missing["id1"]["anchor_ids"] == ["f_missing"]
        assert any(i.check == "missing_identity_faces" and i.severity == "critical" for i in result.issues)

    def test_missing_candidate_is_warning(self):
        from scripts.data_integrity_audit import AuditResult, check_missing_identity_faces

        f2p = {"f1": "p1"}
        identities = {
            "id1": {"state": "INBOX", "anchor_ids": ["f1"], "candidate_ids": ["f_missing"], "name": "Unknown"},
        }
        result = AuditResult()
        missing = check_missing_identity_faces(f2p, identities, result)
        assert missing["id1"]["candidate_ids"] == ["f_missing"]
        assert any(i.check == "missing_identity_faces" and i.severity == "warning" for i in result.issues)


# ---------------------------------------------------------------------------
# Check 4: State consistency
# ---------------------------------------------------------------------------


class TestStateConsistency:
    """CONFIRMED identities with missing or placeholder names."""

    def test_valid_confirmed(self):
        """CONFIRMED with a real name is fine."""
        from scripts.data_integrity_audit import AuditResult, check_state_consistency

        identities = {
            "id1": {"state": "CONFIRMED", "name": "David Capeluto"},
        }
        result = AuditResult()
        check_state_consistency(identities, result)
        assert result.summary["state_inconsistencies"] == 0

    def test_confirmed_no_name(self):
        """CONFIRMED with no name is critical."""
        from scripts.data_integrity_audit import AuditResult, check_state_consistency

        identities = {
            "id1": {"state": "CONFIRMED", "name": ""},
        }
        result = AuditResult()
        check_state_consistency(identities, result)
        assert result.has_critical

    def test_confirmed_unidentified(self):
        """CONFIRMED with 'Unidentified Person' name is a warning."""
        from scripts.data_integrity_audit import AuditResult, check_state_consistency

        identities = {
            "id1": {"state": "CONFIRMED", "name": "Unidentified Person abc12345"},
        }
        result = AuditResult()
        inconsistent = check_state_consistency(identities, result)
        assert len(inconsistent) == 1
        assert any(i.severity == "warning" for i in result.issues)

    def test_invalid_state(self):
        """Invalid state value is critical."""
        from scripts.data_integrity_audit import AuditResult, check_state_consistency

        identities = {
            "id1": {"state": "BOGUS", "name": "Test"},
        }
        result = AuditResult()
        check_state_consistency(identities, result)
        assert result.has_critical

    def test_inbox_unidentified_ok(self):
        """INBOX with 'Unidentified Person' name is fine (expected)."""
        from scripts.data_integrity_audit import AuditResult, check_state_consistency

        identities = {
            "id1": {"state": "INBOX", "name": "Unidentified Person abc12345"},
        }
        result = AuditResult()
        check_state_consistency(identities, result)
        assert result.summary["state_inconsistencies"] == 0

    def test_skips_merged(self):
        """Merged identities are ignored."""
        from scripts.data_integrity_audit import AuditResult, check_state_consistency

        identities = {
            "id1": {"state": "CONFIRMED", "name": "", "merged_into": "id2"},
        }
        result = AuditResult()
        check_state_consistency(identities, result)
        assert result.summary["state_inconsistencies"] == 0


# ---------------------------------------------------------------------------
# Check 4: Supabase divergence
# ---------------------------------------------------------------------------


class TestSupabaseDivergence:
    """Compare identity states between JSON and Supabase."""

    def test_no_supabase_is_info(self):
        """Without Supabase, reports info, not error."""
        from scripts.data_integrity_audit import AuditResult, check_supabase_divergence

        with patch.dict("sys.modules", {"app.supabase_data": None}):
            result = AuditResult()
            check_supabase_divergence({}, result)
            assert not result.has_critical
            assert any(i.check == "supabase_divergence" for i in result.issues)

    def test_state_mismatch_detected(self):
        """Detects state mismatch between JSON and Supabase."""
        from scripts.data_integrity_audit import AuditResult, check_supabase_divergence

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [
            {"identity_id": "id1", "state": "CONFIRMED", "name": "Test", "merged_into": None},
        ]
        mock_client.table.return_value.select.return_value.range.return_value.execute.return_value = mock_resp

        # Second call returns empty to end pagination
        def range_side_effect(start, end):
            mock_exec = MagicMock()
            if start == 0:
                mock_exec.execute.return_value = mock_resp
            else:
                empty = MagicMock()
                empty.data = []
                mock_exec.execute.return_value = empty
            return mock_exec

        mock_client.table.return_value.select.return_value.range = range_side_effect

        identities = {
            "id1": {"state": "PROPOSED", "name": "Test"},  # JSON says PROPOSED, SB says CONFIRMED
        }

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = AuditResult()
            div = check_supabase_divergence(identities, result)
            assert div["checked"]
            assert len(div["mismatches"]) >= 1
            assert result.has_critical

    def test_in_sync(self):
        """No issues when JSON and Supabase agree."""
        from scripts.data_integrity_audit import AuditResult, check_supabase_divergence

        mock_client = MagicMock()

        def range_side_effect(start, end):
            mock_exec = MagicMock()
            if start == 0:
                resp = MagicMock()
                resp.data = [
                    {"identity_id": "id1", "state": "CONFIRMED", "name": "Test", "merged_into": None},
                ]
                mock_exec.execute.return_value = resp
            else:
                empty = MagicMock()
                empty.data = []
                mock_exec.execute.return_value = empty
            return mock_exec

        mock_client.table.return_value.select.return_value.range = range_side_effect

        identities = {
            "id1": {"state": "CONFIRMED", "name": "Test"},
        }

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = AuditResult()
            div = check_supabase_divergence(identities, result)
            assert len(div["mismatches"]) == 0
            assert not result.has_critical


# ---------------------------------------------------------------------------
# Check 5: Duplicate face assignments
# ---------------------------------------------------------------------------


class TestDuplicateFaceAssignments:
    """Same face_id in multiple identities."""

    def test_no_duplicates(self):
        """Each face assigned to exactly one identity."""
        from scripts.data_integrity_audit import AuditResult, check_duplicate_face_assignments

        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": []},
            "id2": {"anchor_ids": ["f2"], "candidate_ids": ["f3"]},
        }
        result = AuditResult()
        dups = check_duplicate_face_assignments(identities, result)
        assert len(dups) == 0

    def test_finds_duplicate(self):
        """Detects face assigned to two identities."""
        from scripts.data_integrity_audit import AuditResult, check_duplicate_face_assignments

        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": []},
            "id2": {"anchor_ids": ["f1"], "candidate_ids": []},  # f1 is in both!
        }
        result = AuditResult()
        dups = check_duplicate_face_assignments(identities, result)
        assert "f1" in dups
        assert len(dups["f1"]) == 2
        assert result.has_critical

    def test_anchor_and_candidate_duplicate(self):
        """Face as anchor in one identity and candidate in another."""
        from scripts.data_integrity_audit import AuditResult, check_duplicate_face_assignments

        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": []},
            "id2": {"anchor_ids": [], "candidate_ids": ["f1"]},
        }
        result = AuditResult()
        dups = check_duplicate_face_assignments(identities, result)
        assert "f1" in dups

    def test_skips_merged(self):
        """Merged identities are excluded."""
        from scripts.data_integrity_audit import AuditResult, check_duplicate_face_assignments

        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": [], "merged_into": "id2"},
            "id2": {"anchor_ids": ["f1"], "candidate_ids": []},
        }
        result = AuditResult()
        dups = check_duplicate_face_assignments(identities, result)
        assert len(dups) == 0  # id1 is merged, so f1 only in id2


# ---------------------------------------------------------------------------
# Check 6: Merged identity chains
# ---------------------------------------------------------------------------


class TestMergedChains:
    """merged_into pointing to another merged identity."""

    def test_no_chains(self):
        """Flat merge references are fine."""
        from scripts.data_integrity_audit import AuditResult, check_merged_chains

        identities = {
            "id1": {"merged_into": "id3"},
            "id2": {"merged_into": "id3"},
            "id3": {"state": "CONFIRMED"},
        }
        result = AuditResult()
        chained = check_merged_chains(identities, result)
        assert len(chained) == 0

    def test_finds_chain(self):
        """Detects A->B->C chain."""
        from scripts.data_integrity_audit import AuditResult, check_merged_chains

        identities = {
            "id1": {"merged_into": "id2"},
            "id2": {"merged_into": "id3"},
            "id3": {"state": "CONFIRMED"},
        }
        result = AuditResult()
        chained = check_merged_chains(identities, result)
        assert "id1" in chained
        assert result.summary["merged_chains"] == 1

    def test_no_merge(self):
        """Identities without merged_into are fine."""
        from scripts.data_integrity_audit import AuditResult, check_merged_chains

        identities = {
            "id1": {"state": "CONFIRMED"},
            "id2": {"state": "INBOX"},
        }
        result = AuditResult()
        chained = check_merged_chains(identities, result)
        assert len(chained) == 0


# ---------------------------------------------------------------------------
# Check 7: Upload date completeness
# ---------------------------------------------------------------------------


class TestUploadDateCompleteness:
    """Photos missing upload_date."""

    def test_all_have_dates(self):
        from scripts.data_integrity_audit import AuditResult, check_upload_date_completeness

        photos = {
            "p1": {"upload_date": "2026-01-01"},
            "p2": {"upload_date": "2026-02-01"},
        }
        result = AuditResult()
        missing = check_upload_date_completeness(photos, result)
        assert len(missing) == 0

    def test_finds_missing(self):
        from scripts.data_integrity_audit import AuditResult, check_upload_date_completeness

        photos = {
            "p1": {"upload_date": "2026-01-01"},
            "p2": {"path": "b.jpg"},  # no upload_date
        }
        result = AuditResult()
        missing = check_upload_date_completeness(photos, result)
        assert "p2" in missing
        assert result.summary["missing_upload_date"] == 1


# ---------------------------------------------------------------------------
# Check 8: Community membership gaps
# ---------------------------------------------------------------------------


class TestCommunityMembership:
    """Photos with faces but no community assignment."""

    def test_no_supabase_skips(self):
        """Without Supabase, reports info and returns empty."""
        from scripts.data_integrity_audit import AuditResult, check_community_membership

        photos = {"p1": {"face_ids": ["f1"]}}
        with patch("app.supabase_data.get_supabase_client", return_value=None):
            result = AuditResult()
            gaps = check_community_membership(photos, result)
            assert len(gaps) == 0

    def test_finds_gap(self):
        """Detects photo with faces but no community."""
        from scripts.data_integrity_audit import AuditResult, check_community_membership

        mock_client = MagicMock()

        def range_side_effect(start, end):
            mock_exec = MagicMock()
            if start == 0:
                resp = MagicMock()
                resp.data = [{"photo_id": "p1"}]  # only p1 has community
                mock_exec.execute.return_value = resp
            else:
                empty = MagicMock()
                empty.data = []
                mock_exec.execute.return_value = empty
            return mock_exec

        mock_client.table.return_value.select.return_value.range = range_side_effect

        photos = {
            "p1": {"face_ids": ["f1"]},
            "p2": {"face_ids": ["f2"]},  # no community
        }

        with patch("app.supabase_data.get_supabase_client", return_value=mock_client):
            result = AuditResult()
            gaps = check_community_membership(photos, result)
            assert "p2" in gaps
            assert result.summary["community_gaps"] == 1


# ---------------------------------------------------------------------------
# Check 9: Embedding coverage
# ---------------------------------------------------------------------------


class TestEmbeddingCoverage:
    """Identity faces that have no embedding."""

    def test_all_covered(self):
        from scripts.data_integrity_audit import AuditResult, check_embedding_coverage

        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": ["f2"]},
        }
        embedding_fids = {"f1", "f2", "f3"}
        result = AuditResult()
        missing = check_embedding_coverage(identities, embedding_fids, result)
        assert len(missing) == 0

    def test_finds_missing(self):
        from scripts.data_integrity_audit import AuditResult, check_embedding_coverage

        identities = {
            "id1": {"anchor_ids": ["f1"], "candidate_ids": ["f_no_embed"]},
        }
        embedding_fids = {"f1"}
        result = AuditResult()
        missing = check_embedding_coverage(identities, embedding_fids, result)
        assert "f_no_embed" in missing

    def test_empty_embeddings_skips(self):
        from scripts.data_integrity_audit import AuditResult, check_embedding_coverage

        identities = {"id1": {"anchor_ids": ["f1"], "candidate_ids": []}}
        result = AuditResult()
        check_embedding_coverage(identities, set(), result)
        assert any(i.check == "embedding_coverage" and i.severity == "info" for i in result.issues)

    def test_skips_merged(self):
        from scripts.data_integrity_audit import AuditResult, check_embedding_coverage

        identities = {
            "id1": {"anchor_ids": ["f_missing"], "candidate_ids": [], "merged_into": "id2"},
        }
        embedding_fids = {"f_other"}
        result = AuditResult()
        missing = check_embedding_coverage(identities, embedding_fids, result)
        assert len(missing) == 0


# ---------------------------------------------------------------------------
# Fix operations
# ---------------------------------------------------------------------------


class TestFixOrphanFaces:
    """Auto-create INBOX identities for orphan faces."""

    def test_creates_inbox_identities(self, tmp_path):
        from scripts.data_integrity_audit import AuditResult, fix_orphan_faces

        write_identities(tmp_path, {"id1": {"anchor_ids": ["f1"], "candidate_ids": [], "state": "INBOX"}})

        result = AuditResult()
        count = fix_orphan_faces({"f2", "f3"}, tmp_path, result)
        assert count == 2

        # Verify written
        data = json.loads((tmp_path / "identities.json").read_text())
        idents = data["identities"]
        assert len(idents) == 3  # original + 2 new
        new_ids = [iid for iid in idents if iid != "id1"]
        for nid in new_ids:
            assert idents[nid]["state"] == "INBOX"
            assert len(idents[nid]["anchor_ids"]) == 1

    def test_no_orphans_no_write(self, tmp_path):
        from scripts.data_integrity_audit import AuditResult, fix_orphan_faces

        write_identities(tmp_path, {})
        result = AuditResult()
        count = fix_orphan_faces(set(), tmp_path, result)
        assert count == 0
        assert len(result.fixes_applied) == 0


class TestFixMergedChains:
    """Flatten chained merge references."""

    def test_flattens_chain(self, tmp_path):
        from scripts.data_integrity_audit import AuditResult, fix_merged_chains

        identities = {
            "id1": {"merged_into": "id2", "state": "INBOX"},
            "id2": {"merged_into": "id3", "state": "INBOX"},
            "id3": {"state": "CONFIRMED"},
        }
        write_identities(tmp_path, identities)

        result = AuditResult()
        count = fix_merged_chains(identities, tmp_path, result)
        assert count == 1  # id1 was chained

        data = json.loads((tmp_path / "identities.json").read_text())
        assert data["identities"]["id1"]["merged_into"] == "id3"

    def test_no_chains_no_write(self, tmp_path):
        from scripts.data_integrity_audit import AuditResult, fix_merged_chains

        identities = {
            "id1": {"merged_into": "id3"},
            "id3": {"state": "CONFIRMED"},
        }
        write_identities(tmp_path, identities)

        result = AuditResult()
        count = fix_merged_chains(identities, tmp_path, result)
        assert count == 0

    def test_handles_cycle(self, tmp_path):
        """Cycle in merge chain doesn't cause infinite loop."""
        from scripts.data_integrity_audit import AuditResult, fix_merged_chains

        identities = {
            "id1": {"merged_into": "id2"},
            "id2": {"merged_into": "id1"},  # cycle!
        }
        write_identities(tmp_path, identities)

        result = AuditResult()
        # Should not hang
        count = fix_merged_chains(identities, tmp_path, result)
        # At least doesn't crash
        assert isinstance(count, int)


class TestFixMissingIdentityFaces:
    """Quarantine partial missing face refs without losing undo context."""

    def test_quarantines_and_removes_partial_missing_faces(self, tmp_path):
        from scripts.data_integrity_audit import AuditResult, fix_missing_identity_faces

        write_identities(
            tmp_path,
            {
                "id1": {
                    "state": "CONFIRMED",
                    "name": "Known",
                    "anchor_ids": ["f1", "f_missing"],
                    "candidate_ids": ["c_missing"],
                    "metadata": {},
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            },
        )

        result = AuditResult()
        count = fix_missing_identity_faces(
            {"id1": {"anchor_ids": ["f_missing"], "candidate_ids": ["c_missing"]}},
            tmp_path,
            result,
        )
        assert count == 2

        data = json.loads((tmp_path / "identities.json").read_text())
        ident = data["identities"]["id1"]
        assert ident["anchor_ids"] == ["f1"]
        assert ident["candidate_ids"] == []
        quarantined = ident["metadata"]["quarantined_missing_faces"]
        assert {entry["face_id"] for entry in quarantined} == {"f_missing", "c_missing"}

    def test_skips_full_ghost_identity(self, tmp_path):
        from scripts.data_integrity_audit import AuditResult, fix_missing_identity_faces

        write_identities(
            tmp_path,
            {
                "id1": {
                    "state": "CONFIRMED",
                    "name": "Known",
                    "anchor_ids": ["f_missing"],
                    "candidate_ids": [],
                    "metadata": {},
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            },
        )

        result = AuditResult()
        count = fix_missing_identity_faces(
            {"id1": {"anchor_ids": ["f_missing"], "candidate_ids": []}},
            tmp_path,
            result,
        )
        assert count == 0


class TestFixStateInconsistencies:
    """Demote invalid placeholder confirmations via audited state history."""

    def test_moves_confirmed_placeholder_back_to_inbox(self, tmp_path):
        from scripts.data_integrity_audit import AuditResult, fix_state_inconsistencies

        write_identities(
            tmp_path,
            {
                "id1": {
                    "state": "CONFIRMED",
                    "name": "Unidentified Person 494",
                    "anchor_ids": ["f1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            },
        )

        result = AuditResult()
        count = fix_state_inconsistencies(["id1"], tmp_path, result)
        assert count == 1

        data = json.loads((tmp_path / "identities.json").read_text())
        ident = data["identities"]["id1"]
        assert ident["state"] == "INBOX"
        assert data["history"][-1]["action"] == "state_change"
        assert data["history"][-1]["metadata"]["reason"] == "confirmed_placeholder_name"

    def test_skips_named_confirmed_identity(self, tmp_path):
        from scripts.data_integrity_audit import AuditResult, fix_state_inconsistencies

        write_identities(
            tmp_path,
            {
                "id1": {
                    "state": "CONFIRMED",
                    "name": "Known Person",
                    "anchor_ids": ["f1"],
                    "candidate_ids": [],
                    "negative_ids": [],
                    "version_id": 1,
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            },
        )

        result = AuditResult()
        count = fix_state_inconsistencies(["id1"], tmp_path, result)
        assert count == 0


# ---------------------------------------------------------------------------
# Integration: run_audit
# ---------------------------------------------------------------------------


class TestRunAudit:
    """End-to-end audit runner."""

    def test_clean_data(self, tmp_path):
        """Audit passes on clean, consistent data."""
        from scripts.data_integrity_audit import run_audit

        identities = {
            "id1": {
                "state": "CONFIRMED",
                "name": "David Capeluto",
                "anchor_ids": ["f1"],
                "candidate_ids": [],
            },
            "id2": {
                "state": "INBOX",
                "name": "Unidentified Person abc12345",
                "anchor_ids": ["f2"],
                "candidate_ids": [],
            },
        }
        photos = {
            "p1": {"path": "a.jpg", "face_ids": ["f1", "f2"], "collection": "C", "upload_date": "2026-01-01"},
        }
        f2p = {"f1": "p1", "f2": "p1"}

        write_identities(tmp_path, identities)
        write_photo_index(tmp_path, photos, f2p)

        result = run_audit(tmp_path)
        assert not result.has_critical
        assert result.summary["total_identities"] == 2
        assert result.summary["total_photos"] == 1

    def test_detects_multiple_issues(self, tmp_path):
        """Audit detects multiple issue types simultaneously."""
        from scripts.data_integrity_audit import run_audit

        identities = {
            "id1": {
                "state": "CONFIRMED",
                "name": "",  # issue: empty name
                "anchor_ids": ["f1"],
                "candidate_ids": [],
            },
            "id_ghost": {
                "state": "INBOX",
                "name": "Ghost",
                "anchor_ids": ["f_gone"],
                "candidate_ids": [],
            },
            "id_dup": {
                "state": "INBOX",
                "name": "Dup",
                "anchor_ids": ["f1"],  # duplicate with id1
                "candidate_ids": [],
            },
        }
        photos = {
            "p1": {"path": "a.jpg", "face_ids": ["f1", "f_orphan"], "collection": "C"},
        }
        f2p = {"f1": "p1", "f_orphan": "p1"}

        write_identities(tmp_path, identities)
        write_photo_index(tmp_path, photos, f2p)

        result = run_audit(tmp_path)
        assert result.has_critical
        checks_found = {i.check for i in result.issues}
        assert "state_consistency" in checks_found
        assert "ghost_identities" in checks_found
        assert "duplicate_face_assignments" in checks_found
        assert "orphan_faces" in checks_found

    def test_fix_mode(self, tmp_path):
        """Audit with --fix creates INBOX identities and flattens chains."""
        from scripts.data_integrity_audit import run_audit

        identities = {
            "id1": {
                "state": "INBOX",
                "name": "Person",
                "anchor_ids": ["f1"],
                "candidate_ids": [],
                "merged_into": "id2",
            },
            "id2": {
                "state": "INBOX",
                "name": "Person 2",
                "anchor_ids": ["f2"],
                "candidate_ids": [],
                "merged_into": "id3",
            },
            "id3": {
                "state": "CONFIRMED",
                "name": "Final",
                "anchor_ids": ["f3"],
                "candidate_ids": [],
            },
        }
        photos = {
            "p1": {"path": "a.jpg", "face_ids": ["f1", "f2", "f3", "f_orphan"], "collection": "C"},
        }
        f2p = {"f1": "p1", "f2": "p1", "f3": "p1", "f_orphan": "p1"}

        write_identities(tmp_path, identities)
        write_photo_index(tmp_path, photos, f2p)

        result = run_audit(tmp_path, fix=True)
        assert len(result.fixes_applied) > 0

    def test_missing_files_graceful(self, tmp_path):
        """Audit handles missing data files gracefully."""
        from scripts.data_integrity_audit import run_audit

        result = run_audit(tmp_path)
        assert result.summary["total_identities"] == 0
        assert result.summary["total_photos"] == 0


# ---------------------------------------------------------------------------
# AuditResult dataclass
# ---------------------------------------------------------------------------


class TestAuditResult:
    """AuditResult helper methods."""

    def test_has_critical_false_when_empty(self):
        from scripts.data_integrity_audit import AuditResult

        result = AuditResult()
        assert not result.has_critical

    def test_has_critical_true(self):
        from scripts.data_integrity_audit import AuditResult

        result = AuditResult()
        result.add("test", "critical", "bad")
        assert result.has_critical

    def test_has_critical_false_with_warnings(self):
        from scripts.data_integrity_audit import AuditResult

        result = AuditResult()
        result.add("test", "warning", "mild")
        assert not result.has_critical


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


class TestDataLoading:
    """Test data loading functions."""

    def test_load_identities_json(self, tmp_path):
        from scripts.data_integrity_audit import load_identities_json

        write_identities(tmp_path, {"id1": {"state": "INBOX"}})
        idents = load_identities_json(tmp_path)
        assert "id1" in idents

    def test_load_identities_missing(self, tmp_path):
        from scripts.data_integrity_audit import load_identities_json

        idents = load_identities_json(tmp_path)
        assert idents == {}

    def test_load_photo_index(self, tmp_path):
        from scripts.data_integrity_audit import load_photo_index_json

        write_photo_index(tmp_path, {"p1": {"path": "a.jpg"}}, {"f1": "p1"})
        photos, f2p = load_photo_index_json(tmp_path)
        assert "p1" in photos
        assert f2p["f1"] == "p1"

    def test_load_photo_index_missing(self, tmp_path):
        from scripts.data_integrity_audit import load_photo_index_json

        photos, f2p = load_photo_index_json(tmp_path)
        assert photos == {}
        assert f2p == {}


# ---------------------------------------------------------------------------
# Report output
# ---------------------------------------------------------------------------


class TestReportOutput:
    """Test report formatting."""

    def test_json_output(self, capsys):
        from scripts.data_integrity_audit import AuditResult, print_report

        result = AuditResult()
        result.summary = {"total": 5}
        result.add("test_check", "warning", "something happened", ["id1", "id2"])

        print_report(result, as_json=True)
        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["summary"]["total"] == 5
        assert len(output["issues"]) == 1
        assert output["has_critical"] is False

    def test_text_output(self, capsys):
        from scripts.data_integrity_audit import AuditResult, print_report

        result = AuditResult()
        result.summary = {"total": 5}
        result.add("test_check", "critical", "bad thing")

        print_report(result, as_json=False)
        captured = capsys.readouterr()
        assert "RHODESLI DATA INTEGRITY AUDIT" in captured.out
        assert "CRITICAL" in captured.out
        assert "CRITICAL ISSUES FOUND" in captured.out
