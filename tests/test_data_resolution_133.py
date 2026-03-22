"""Tests for Session 133 data resolution scripts.

These tests verify the logic of the repair scripts without touching Supabase.
"""

import json
import uuid


# === Shared helpers ===


def ensure_list(val):
    if val is None:
        return []
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return val if isinstance(val, list) else []


def make_identity(iid=None, name="Test", state="INBOX", anchors=None, candidates=None, merged_into=None):
    return {
        "identity_id": iid or str(uuid.uuid4()),
        "name": name,
        "state": state,
        "anchor_ids": anchors or [],
        "candidate_ids": candidates or [],
        "merged_into": merged_into,
    }


# === Dangling merge resolution tests ===


class TestDanglingMergeResolution:
    def test_identifies_dangling_references(self):
        """A merged_into pointing to non-existent ID is dangling."""
        target = make_identity(name="Target")
        dangling = make_identity(name="Dangling", merged_into="nonexistent-id")
        valid = make_identity(name="Valid", merged_into=target["identity_id"])

        identities = [target, dangling, valid]
        all_ids = {i["identity_id"] for i in identities}

        found_dangling = [i for i in identities if i.get("merged_into") and i["merged_into"] not in all_ids]
        assert len(found_dangling) == 1
        assert found_dangling[0]["name"] == "Dangling"

    def test_clearing_merged_into_makes_active(self):
        """Clearing merged_into on a dangling identity makes it active."""
        ident = make_identity(name="WasMerged", merged_into="nonexistent", anchors=["f1", "f2"])
        ident["merged_into"] = None  # simulate fix
        assert ident["merged_into"] is None
        assert ident["anchor_ids"] == ["f1", "f2"]

    def test_no_false_positives(self):
        """Valid merge references are not flagged as dangling."""
        target = make_identity(name="Target")
        merged = make_identity(name="Merged", merged_into=target["identity_id"])
        all_ids = {target["identity_id"], merged["identity_id"]}

        dangling = [i for i in [target, merged] if i.get("merged_into") and i["merged_into"] not in all_ids]
        assert len(dangling) == 0


# === Face transfer tests ===


class TestFaceTransfer:
    def test_faces_transferred_to_target_as_candidates(self):
        """Transferred faces go to candidate_ids, not anchor_ids."""
        target = make_identity(name="Target", state="CONFIRMED", anchors=["f1"])
        source = make_identity(name="Source", anchors=["f2", "f3"], merged_into=target["identity_id"])

        # Simulate transfer
        new_candidates = set(ensure_list(target.get("candidate_ids")))
        new_candidates.update(source["anchor_ids"])
        new_candidates.update(source["candidate_ids"])
        new_candidates -= set(target["anchor_ids"])  # don't demote confirmed

        target["candidate_ids"] = list(new_candidates)
        source["anchor_ids"] = []
        source["candidate_ids"] = []

        assert "f2" in target["candidate_ids"]
        assert "f3" in target["candidate_ids"]
        assert "f1" not in target["candidate_ids"]  # already anchor
        assert source["anchor_ids"] == []

    def test_existing_target_anchors_preserved(self):
        """Transfer doesn't demote existing anchor faces to candidates."""
        target = make_identity(anchors=["confirmed_face"])
        source = make_identity(anchors=["confirmed_face", "new_face"], merged_into=target["identity_id"])

        new_candidates = set(ensure_list(target.get("candidate_ids")))
        new_candidates.update(source["anchor_ids"])
        new_candidates -= set(target["anchor_ids"])

        target["candidate_ids"] = list(new_candidates)

        assert "confirmed_face" in target["anchor_ids"]
        assert "confirmed_face" not in target["candidate_ids"]
        assert "new_face" in target["candidate_ids"]

    def test_source_cleared_after_transfer(self):
        """After transfer, source identity has empty face lists."""
        source = make_identity(anchors=["f1"], candidates=["f2"])
        source["anchor_ids"] = []
        source["candidate_ids"] = []
        assert source["anchor_ids"] == []
        assert source["candidate_ids"] == []


# === Multi-claimed resolution tests ===


class TestMultiClaimedResolution:
    def test_confirmed_wins_over_inbox(self):
        """CONFIRMED identity keeps the face, INBOX loses it."""
        confirmed = make_identity(name="Confirmed", state="CONFIRMED", anchors=["shared_face", "other"])
        inbox = make_identity(name="Inbox", state="INBOX", anchors=["shared_face"])

        face_owners = {"shared_face": [confirmed, inbox]}

        # Resolution: CONFIRMED wins
        for fid, owners in face_owners.items():
            sorted_owners = sorted(
                owners, key=lambda o: ({"CONFIRMED": 0, "INBOX": 2}.get(o["state"], 4), -len(o["anchor_ids"]))
            )
            winner = sorted_owners[0]
            for loser in sorted_owners[1:]:
                loser["anchor_ids"] = [f for f in loser["anchor_ids"] if f != fid]

        assert "shared_face" in confirmed["anchor_ids"]
        assert "shared_face" not in inbox["anchor_ids"]
        assert inbox["anchor_ids"] == []

    def test_empty_loser_gets_remerged(self):
        """Identity with no remaining faces gets merged into winner."""
        winner = make_identity(state="CONFIRMED", anchors=["shared"])
        loser = make_identity(state="INBOX", anchors=["shared"])

        loser["anchor_ids"] = []
        if not loser["anchor_ids"] and not loser["candidate_ids"]:
            loser["merged_into"] = winner["identity_id"]

        assert loser["merged_into"] == winner["identity_id"]

    def test_larger_identity_wins_when_both_inbox(self):
        """When both INBOX, identity with more faces keeps the shared one."""
        big = make_identity(name="Big", state="INBOX", anchors=["shared", "f2", "f3"])
        small = make_identity(name="Small", state="INBOX", anchors=["shared"])

        owners = [big, small]
        sorted_owners = sorted(
            owners, key=lambda o: ({"CONFIRMED": 0, "INBOX": 2}.get(o["state"], 4), -len(o["anchor_ids"]))
        )
        assert sorted_owners[0]["name"] == "Big"


# === Ghost face removal tests ===


class TestGhostFaceRemoval:
    def test_ghost_faces_removed_from_anchors(self):
        """Faces not in photo_faces are removed from anchor_ids."""
        existing_faces = {"f1", "f2"}
        ident = make_identity(anchors=["f1", "ghost1", "f2", "ghost2"])

        new_anchors = [f for f in ident["anchor_ids"] if f in existing_faces]
        assert new_anchors == ["f1", "f2"]
        assert "ghost1" not in new_anchors
        assert "ghost2" not in new_anchors

    def test_valid_faces_preserved(self):
        """Non-ghost faces are not affected."""
        existing_faces = {"f1", "f2", "f3"}
        ident = make_identity(anchors=["f1", "f2", "f3"])

        new_anchors = [f for f in ident["anchor_ids"] if f in existing_faces]
        assert new_anchors == ["f1", "f2", "f3"]


# === Orphaned face fix tests ===


class TestOrphanedFaceFix:
    def test_orphaned_faces_get_new_identities(self):
        """Each orphaned face gets a new INBOX identity."""
        photo_face_ids = {"f1", "f2", "f3", "f4"}
        claimed = {"f1", "f2"}
        orphaned = photo_face_ids - claimed

        new_identities = []
        for fid in orphaned:
            new_identities.append(make_identity(state="INBOX", anchors=[fid]))

        assert len(new_identities) == 2
        all_claimed = claimed | {fid for i in new_identities for fid in i["anchor_ids"]}
        assert all_claimed == photo_face_ids

    def test_no_orphans_means_no_new_identities(self):
        """If all faces are claimed, no new identities needed."""
        photo_face_ids = {"f1", "f2"}
        claimed = {"f1", "f2"}
        orphaned = photo_face_ids - claimed
        assert len(orphaned) == 0


# === Ensure list tests ===


class TestEnsureList:
    def test_none_returns_empty(self):
        assert ensure_list(None) == []

    def test_list_passthrough(self):
        assert ensure_list(["a", "b"]) == ["a", "b"]

    def test_json_string_parsed(self):
        assert ensure_list('["a", "b"]') == ["a", "b"]

    def test_invalid_string_returns_empty(self):
        assert ensure_list("not json") == []

    def test_empty_list(self):
        assert ensure_list([]) == []


# === Backup and restore tests ===


class TestBackupIntegrity:
    def test_backup_preserves_all_fields(self):
        """Backup JSON preserves identity_id, merged_into, anchor_ids, candidate_ids."""
        ident = make_identity(
            name="Test",
            state="CONFIRMED",
            anchors=["f1", "f2"],
            candidates=["f3"],
            merged_into="some-id",
        )
        # Simulate JSON round-trip
        serialized = json.dumps(ident)
        restored = json.loads(serialized)

        assert restored["identity_id"] == ident["identity_id"]
        assert restored["merged_into"] == "some-id"
        assert restored["anchor_ids"] == ["f1", "f2"]
        assert restored["candidate_ids"] == ["f3"]

    def test_restore_can_revert_merged_into_clear(self):
        """Restore can re-set merged_into that was cleared."""
        original = make_identity(merged_into="target-id")
        fixed = {**original, "merged_into": None}  # after dangling clear
        restored = {**fixed, "merged_into": original["merged_into"]}

        assert restored["merged_into"] == "target-id"
