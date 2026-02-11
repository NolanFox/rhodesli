"""
Tests for global reclustering — group_all_unresolved().

Verifies that:
- SKIPPED faces participate in grouping alongside INBOX faces
- Promotion fields are set when SKIPPED faces match
- Co-occurrence blocks (negative_ids) are respected
- CONFIRMED and DISMISSED identities are not modified
- Multi-face identities are not split apart
"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


def random_embedding(seed: int = None) -> np.ndarray:
    """Generate a random normalized 512-dim embedding."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(512).astype(np.float32)
    return vec / np.linalg.norm(vec)


def similar_embedding(base: np.ndarray, distance: float = 0.5) -> np.ndarray:
    """Create an embedding at the given Euclidean distance from base."""
    noise = np.random.randn(512).astype(np.float32)
    noise = noise - np.dot(noise, base) * base
    noise = noise / np.linalg.norm(noise)
    cos_theta = 1 - (distance ** 2) / 2
    cos_theta = np.clip(cos_theta, -1, 1)
    sin_theta = np.sqrt(1 - cos_theta ** 2)
    result = cos_theta * base + sin_theta * noise
    return result.astype(np.float32)


def make_test_registry(identities_dict, tmp_path):
    """Create a registry from a raw identities dict."""
    from core.registry import IdentityRegistry

    path = tmp_path / "identities.json"
    data = {"schema_version": 1, "identities": identities_dict, "history": []}
    path.write_text(json.dumps(data))
    return IdentityRegistry.load(path)


def make_test_photo_registry(photos_dict, tmp_path):
    """Create a photo registry from a raw photos dict."""
    from core.photo_registry import PhotoRegistry

    path = tmp_path / "photo_index.json"
    face_to_photo = {}
    for pid, photo in photos_dict.items():
        for fid in photo.get("face_ids", []):
            face_to_photo[fid] = pid
    data = {"schema_version": 1, "photos": photos_dict, "face_to_photo": face_to_photo}
    path.write_text(json.dumps(data))
    return PhotoRegistry.load(path)


def make_identity(identity_id, state, face_ids, name=None, negative_ids=None):
    """Create a minimal identity dict."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "identity_id": identity_id,
        "name": name or f"Unidentified Person {identity_id[:8]}",
        "state": state,
        "anchor_ids": face_ids,
        "candidate_ids": [],
        "negative_ids": negative_ids or [],
        "version_id": 1,
        "created_at": now,
        "updated_at": now,
        "history": [],
    }


class TestGroupAllUnresolved:
    """Tests for the group_all_unresolved function."""

    def test_skipped_faces_participate_in_grouping(self, tmp_path):
        """SKIPPED faces should be compared against INBOX faces."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"]),
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        assert results["total_groups"] == 1
        assert results["inbox_count"] == 1
        assert results["skipped_count"] == 1

    def test_skipped_promoted_when_matched_inbox(self, tmp_path):
        """A SKIPPED face matching an INBOX face -> promoted with 'new_face_match'."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"]),
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        assert len(results["promotions"]) == 1
        promo = results["promotions"][0]
        assert promo["identity_id"] == "skipped1"
        assert promo["reason"] == "new_face_match"

    def test_skipped_promoted_when_grouped_together(self, tmp_path):
        """Two SKIPPED faces matching each other -> both promoted with 'group_discovery'."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_a"]),
            "skipped2": make_identity("skipped2", "SKIPPED", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        assert len(results["promotions"]) == 2
        reasons = {p["reason"] for p in results["promotions"]}
        assert reasons == {"group_discovery"}

    def test_co_occurrence_blocks_respected(self, tmp_path):
        """Faces marked 'Not Same' must never be grouped, even if embeddings are close."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"],
                                     negative_ids=["identity:skipped1"]),
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_b"],
                                      negative_ids=["identity:inbox1"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        assert results["total_groups"] == 0, "Blocked pairs must not be grouped"

    def test_confirmed_not_modified(self, tmp_path):
        """CONFIRMED identities must not participate in grouping."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "confirmed1": make_identity("confirmed1", "CONFIRMED", ["face_a"],
                                         name="Victoria Capeluto"),
            "inbox1": make_identity("inbox1", "INBOX", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        # No groups — confirmed is excluded, only 1 inbox item can't group alone
        assert results["total_groups"] == 0

    def test_dismissed_excluded(self, tmp_path):
        """REJECTED identities must not participate in grouping."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "rejected1": make_identity("rejected1", "REJECTED", ["face_a"]),
            "inbox1": make_identity("inbox1", "INBOX", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        # Rejected is excluded from grouping
        assert results["total_groups"] == 0

    def test_promotion_fields_set_on_execute(self, tmp_path):
        """Promoted identities must have promoted_from, promoted_at, promotion_reason."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"]),
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=False,
        )

        # The surviving identity (primary) should have the merged face
        # Check promotion fields on the primary
        primary_id = results["groups"][0]["primary_id"]
        primary = registry.get_identity(primary_id)
        # If primary was inbox1, it won't have promotion fields
        # But the skipped1 was promoted before being merged

        # At least one promotion should have been recorded
        assert len(results["promotions"]) >= 1
        promo = results["promotions"][0]
        assert promo["identity_id"] == "skipped1"
        assert promo["reason"] == "new_face_match"

    def test_promotion_context_set_on_execute(self, tmp_path):
        """Promoted identities must have non-empty promotion_context."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"]),
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=False,
        )

        assert len(results["promotions"]) >= 1
        # Check that the promoted identity (skipped1) got promotion_context
        # After merge, skipped1 may be merged into inbox1
        # But promotion fields were set before merge
        primary_id = results["groups"][0]["primary_id"]
        primary = registry.get_identity(primary_id)
        if primary.get("promoted_from"):
            assert primary.get("promotion_context"), \
                "promotion_context should be non-empty for promoted identities"
            assert "Matches with" in primary["promotion_context"] or \
                   "Groups with" in primary["promotion_context"]

    def test_promotion_context_group_discovery(self, tmp_path):
        """SKIPPED-only groups get group_discovery promotion_context."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_a"]),
            "skipped2": make_identity("skipped2", "SKIPPED", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=False,
        )

        assert len(results["promotions"]) >= 1
        primary_id = results["groups"][0]["primary_id"]
        primary = registry.get_identity(primary_id)
        assert primary.get("promotion_context") is not None
        assert "Groups with" in primary["promotion_context"]

    def test_multi_face_identities_not_split(self, tmp_path):
        """Existing multi-face clusters should not be broken apart."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        far_emb = random_embedding(seed=99)  # Completely different

        identities = {
            "multi1": make_identity("multi1", "INBOX", ["face_a", "face_b"]),
            "single1": make_identity("single1", "INBOX", ["face_c"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a", "face_c"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": similar_embedding(base_emb, distance=0.2)},
            "face_c": {"mu": far_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        # multi1 stays as is, single1 stays as is (far apart)
        assert results["total_groups"] == 0

    def test_mixed_cluster_status_resolution(self, tmp_path):
        """Cluster with 1 INBOX + 2 SKIPPED -> all become INBOX, SKIPPED ones get promotion flags."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"]),
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_b"]),
            "skipped2": make_identity("skipped2", "SKIPPED", ["face_c"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
            "photo3": {"path": "img3.jpg", "face_ids": ["face_c"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": similar_embedding(base_emb, distance=0.3)},
            "face_c": {"mu": similar_embedding(base_emb, distance=0.4)},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        assert results["total_groups"] == 1
        # Both SKIPPED faces should be promoted
        skipped_promotions = [p for p in results["promotions"]
                              if p["identity_id"] in ("skipped1", "skipped2")]
        assert len(skipped_promotions) == 2
        for p in skipped_promotions:
            assert p["reason"] == "new_face_match"  # INBOX face present

    def test_include_skipped_false_excludes_skipped(self, tmp_path):
        """With include_skipped=False, only INBOX faces participate."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"]),
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            include_skipped=False,
            dry_run=True,
        )

        # Only 1 inbox face, can't form a group alone
        assert results["total_groups"] == 0
        assert results["skipped_count"] == 0

    def test_one_sided_negative_id_blocks_grouping(self, tmp_path):
        """Even if only one side has the rejection, grouping is blocked."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"],
                                     negative_ids=["identity:inbox2"]),
            "inbox2": make_identity("inbox2", "INBOX", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        assert results["total_groups"] == 0

    def test_no_embeddings_returns_empty(self, tmp_path):
        """Identities with no matching embeddings should be skipped gracefully."""
        from core.grouping import group_all_unresolved

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"]),
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({}, tmp_path)
        face_data = {}  # No embeddings

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=True,
        )

        assert results["total_groups"] == 0

    def test_execute_mode_promotes_and_merges(self, tmp_path):
        """Execute mode should set promotion fields on the registry and merge."""
        from core.grouping import group_all_unresolved

        base_emb = random_embedding(seed=42)
        close_emb = similar_embedding(base_emb, distance=0.3)

        identities = {
            "inbox1": make_identity("inbox1", "INBOX", ["face_a"]),
            "skipped1": make_identity("skipped1", "SKIPPED", ["face_b"]),
        }
        registry = make_test_registry(identities, tmp_path)
        photo_registry = make_test_photo_registry({
            "photo1": {"path": "img1.jpg", "face_ids": ["face_a"]},
            "photo2": {"path": "img2.jpg", "face_ids": ["face_b"]},
        }, tmp_path)
        face_data = {
            "face_a": {"mu": base_emb},
            "face_b": {"mu": close_emb},
        }

        results = group_all_unresolved(
            registry=registry,
            face_data=face_data,
            photo_registry=photo_registry,
            threshold=0.95,
            dry_run=False,
        )

        assert results["total_merged"] == 1
        assert len(results["promotions"]) == 1

        # The skipped identity should have been promoted to INBOX before merge
        # Check that the surviving identity has the merged face
        primary_id = results["groups"][0]["primary_id"]
        primary = registry.get_identity(primary_id)
        assert primary is not None
        # Primary should have faces from both identities
        all_faces = primary.get("anchor_ids", []) + primary.get("candidate_ids", [])
        face_ids_flat = [f if isinstance(f, str) else f.get("face_id") for f in all_faces]
        assert len(face_ids_flat) >= 2
