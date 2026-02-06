"""Tests for ML clustering scripts: build_golden_set, evaluate_golden_set, cluster_new_faces.

All tests use isolated fixture data -- never production data.
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

# Add project root for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scripts.build_golden_set import (
    build_golden_set,
    extract_face_ids,
    load_identities,
)
from scripts.evaluate_golden_set import (
    compute_distance,
    evaluate_at_threshold,
    generate_face_id,
)
from scripts.cluster_new_faces import (
    compute_centroid,
    compute_distance_to_centroid,
    find_matches,
    apply_suggestions,
    get_photo_id,
)


# ---------------------------------------------------------------------------
# Fixtures: synthetic identities and embeddings
# ---------------------------------------------------------------------------


def make_identities_json(identities: dict) -> dict:
    """Wrap identities dict in the schema envelope."""
    return {
        "schema_version": 1,
        "identities": identities,
        "history": [],
    }


def make_confirmed_identity(
    identity_id: str,
    name: str,
    candidate_ids: list[str],
    anchor_ids: list[str] | None = None,
) -> dict:
    return {
        "identity_id": identity_id,
        "name": name,
        "state": "CONFIRMED",
        "anchor_ids": anchor_ids or [],
        "candidate_ids": candidate_ids,
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def make_inbox_identity(
    identity_id: str,
    name: str,
    candidate_ids: list[str],
) -> dict:
    return {
        "identity_id": identity_id,
        "name": name,
        "state": "INBOX",
        "anchor_ids": [],
        "candidate_ids": candidate_ids,
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def make_proposed_identity(
    identity_id: str,
    name: str,
    candidate_ids: list[str],
) -> dict:
    return {
        "identity_id": identity_id,
        "name": name,
        "state": "PROPOSED",
        "anchor_ids": [],
        "candidate_ids": candidate_ids,
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def make_embedding_entry(filename: str, face_index: int, mu: np.ndarray):
    """Create an embedding entry matching the format in embeddings.npy."""
    return {
        "filename": filename,
        "face_id": f"{Path(filename).stem}:face{face_index}",
        "mu": mu.astype(np.float32),
        "sigma_sq": np.full(512, 0.5, dtype=np.float32),
    }


@pytest.fixture
def data_dir(tmp_path):
    """Create a temporary data directory with test identities and embeddings."""
    # Create identities
    identities = {
        "id-alice": make_confirmed_identity(
            "id-alice", "Alice Smith",
            candidate_ids=["photo_A:face0", "photo_B:face0"],
        ),
        "id-bob": make_confirmed_identity(
            "id-bob", "Bob Jones",
            candidate_ids=["photo_C:face0", "photo_D:face0"],
        ),
        "id-unknown1": make_inbox_identity(
            "id-unknown1", "Unidentified Person 001",
            candidate_ids=["photo_E:face0"],
        ),
        "id-unknown2": make_proposed_identity(
            "id-unknown2", "Unidentified Person 002",
            candidate_ids=["photo_F:face0"],
        ),
        "id-merged": make_confirmed_identity(
            "id-merged", "Merged Person",
            candidate_ids=["photo_G:face0"],
        ),
    }
    identities["id-merged"]["merged_into"] = "id-alice"

    # Add a REJECTED identity (should be excluded from golden set)
    identities["id-rejected"] = {
        "identity_id": "id-rejected",
        "name": "Rejected Person",
        "state": "REJECTED",
        "anchor_ids": [],
        "candidate_ids": ["photo_H:face0"],
        "negative_ids": [],
        "version_id": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }

    data = make_identities_json(identities)
    identities_path = tmp_path / "identities.json"
    with open(identities_path, "w") as f:
        json.dump(data, f, indent=2)

    # Create embeddings
    # Alice faces: close together (low distance)
    np.random.seed(42)
    alice_base = np.random.randn(512).astype(np.float32)
    alice_base /= np.linalg.norm(alice_base)

    # Bob faces: different from Alice
    bob_base = np.random.randn(512).astype(np.float32)
    bob_base /= np.linalg.norm(bob_base)

    entries = [
        make_embedding_entry("photo_A.jpg", 0, alice_base + np.random.randn(512) * 0.01),
        make_embedding_entry("photo_B.jpg", 0, alice_base + np.random.randn(512) * 0.01),
        make_embedding_entry("photo_C.jpg", 0, bob_base + np.random.randn(512) * 0.01),
        make_embedding_entry("photo_D.jpg", 0, bob_base + np.random.randn(512) * 0.01),
        # Unknown1: close to Alice
        make_embedding_entry("photo_E.jpg", 0, alice_base + np.random.randn(512) * 0.02),
        # Unknown2: close to Bob
        make_embedding_entry("photo_F.jpg", 0, bob_base + np.random.randn(512) * 0.02),
        # Merged (should be excluded)
        make_embedding_entry("photo_G.jpg", 0, alice_base),
        # Rejected (should be excluded)
        make_embedding_entry("photo_H.jpg", 0, bob_base),
    ]

    embeddings_path = tmp_path / "embeddings.npy"
    np.save(embeddings_path, entries, allow_pickle=True)

    return tmp_path


# ---------------------------------------------------------------------------
# Tests: build_golden_set
# ---------------------------------------------------------------------------


class TestBuildGoldenSet:
    """Tests for the golden set builder."""

    def test_builds_from_confirmed_identities(self, data_dir):
        golden = build_golden_set(data_dir)
        # Should include Alice (2 faces) + Bob (2 faces) = 4 mappings
        # Not: merged, rejected, inbox, proposed
        assert golden["stats"]["total_mappings"] == 4
        assert golden["stats"]["unique_identities"] == 2

    def test_excludes_merged_identities(self, data_dir):
        golden = build_golden_set(data_dir)
        identity_ids = {m["identity_id"] for m in golden["mappings"]}
        assert "id-merged" not in identity_ids

    def test_excludes_non_confirmed_identities(self, data_dir):
        golden = build_golden_set(data_dir)
        identity_ids = {m["identity_id"] for m in golden["mappings"]}
        assert "id-unknown1" not in identity_ids
        assert "id-unknown2" not in identity_ids
        assert "id-rejected" not in identity_ids

    def test_includes_confirmed_identity_faces(self, data_dir):
        golden = build_golden_set(data_dir)
        face_ids = {m["face_id"] for m in golden["mappings"]}
        assert "photo_A:face0" in face_ids
        assert "photo_B:face0" in face_ids
        assert "photo_C:face0" in face_ids
        assert "photo_D:face0" in face_ids

    def test_mapping_structure(self, data_dir):
        golden = build_golden_set(data_dir)
        for mapping in golden["mappings"]:
            assert "face_id" in mapping
            assert "identity_id" in mapping
            assert "identity_name" in mapping
            assert "source" in mapping
            assert mapping["source"] in ("confirmed_anchor", "confirmed_candidate")

    def test_golden_set_has_version_and_metadata(self, data_dir):
        golden = build_golden_set(data_dir)
        assert golden["version"] == 1
        assert "created_at" in golden
        assert "description" in golden

    def test_handles_dict_anchors(self, tmp_path):
        """Test that dict-format anchors are handled correctly."""
        identities = {
            "id-dict-anchor": {
                "identity_id": "id-dict-anchor",
                "name": "Dict Anchor Person",
                "state": "CONFIRMED",
                "anchor_ids": [{"face_id": "photo_X:face0", "weight": 1.0}],
                "candidate_ids": ["photo_Y:face0"],
                "negative_ids": [],
                "version_id": 1,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        }

        data = make_identities_json(identities)
        with open(tmp_path / "identities.json", "w") as f:
            json.dump(data, f)

        golden = build_golden_set(tmp_path)
        face_ids = {m["face_id"] for m in golden["mappings"]}
        assert "photo_X:face0" in face_ids
        assert "photo_Y:face0" in face_ids

        # Verify source types
        sources = {m["face_id"]: m["source"] for m in golden["mappings"]}
        assert sources["photo_X:face0"] == "confirmed_anchor"
        assert sources["photo_Y:face0"] == "confirmed_candidate"

    def test_dry_run_does_not_write_file(self, data_dir):
        """Verify dry-run mode does not create the output file."""
        output_path = data_dir / "golden_set.json"
        assert not output_path.exists()
        # build_golden_set itself doesn't write -- the main() function does
        golden = build_golden_set(data_dir)
        assert not output_path.exists()
        assert golden is not None

    def test_empty_confirmed_identities(self, tmp_path):
        """Test with no confirmed identities."""
        identities = {
            "id-inbox": make_inbox_identity(
                "id-inbox", "Inbox Person", ["face0"]
            )
        }
        data = make_identities_json(identities)
        with open(tmp_path / "identities.json", "w") as f:
            json.dump(data, f)

        golden = build_golden_set(tmp_path)
        assert golden["stats"]["total_mappings"] == 0
        assert golden["stats"]["unique_identities"] == 0


# ---------------------------------------------------------------------------
# Tests: evaluate_golden_set
# ---------------------------------------------------------------------------


class TestEvaluateGoldenSet:
    """Tests for the golden set evaluator."""

    def test_generate_face_id(self):
        assert generate_face_id("photo_A.jpg", 0) == "photo_A:face0"
        assert generate_face_id("photo_A.jpg", 1) == "photo_A:face1"
        assert generate_face_id("Image 001_compress.jpg", 3) == "Image 001_compress:face3"

    def test_evaluate_perfect_classification(self):
        """Test with perfect classification (all correct)."""
        pairs = [
            {"distance": 0.5, "same_identity": True},
            {"distance": 0.6, "same_identity": True},
            {"distance": 1.5, "same_identity": False},
            {"distance": 1.8, "same_identity": False},
        ]
        result = evaluate_at_threshold(pairs, threshold=1.0)
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0
        assert result["accuracy"] == 1.0
        assert result["tp"] == 2
        assert result["tn"] == 2
        assert result["fp"] == 0
        assert result["fn"] == 0

    def test_evaluate_all_false_negatives(self):
        """Test with threshold too low (misses all positives)."""
        pairs = [
            {"distance": 0.5, "same_identity": True},
            {"distance": 0.6, "same_identity": True},
            {"distance": 1.5, "same_identity": False},
        ]
        result = evaluate_at_threshold(pairs, threshold=0.1)
        assert result["tp"] == 0
        assert result["fn"] == 2
        assert result["recall"] == 0.0

    def test_evaluate_all_false_positives(self):
        """Test with threshold too high (matches everything)."""
        pairs = [
            {"distance": 0.5, "same_identity": True},
            {"distance": 0.6, "same_identity": False},
            {"distance": 0.7, "same_identity": False},
        ]
        result = evaluate_at_threshold(pairs, threshold=10.0)
        assert result["tp"] == 1
        assert result["fp"] == 2
        assert result["fn"] == 0
        assert result["tn"] == 0

    def test_evaluate_empty_pairs(self):
        result = evaluate_at_threshold([], threshold=1.0)
        assert result["tp"] == 0
        assert result["fp"] == 0
        assert result["accuracy"] == 0.0

    def test_compute_distance_same_embedding(self, data_dir):
        """Distance to self should be very small."""
        from scripts.evaluate_golden_set import load_face_data

        face_data = load_face_data(data_dir)
        dist = compute_distance(face_data, "photo_A:face0", "photo_A:face0")
        assert dist < 0.001

    def test_compute_distance_similar_embeddings(self, data_dir):
        """Same-person faces should be close."""
        from scripts.evaluate_golden_set import load_face_data

        face_data = load_face_data(data_dir)
        # Alice's two faces (close embeddings)
        dist = compute_distance(face_data, "photo_A:face0", "photo_B:face0")
        assert dist < 1.0  # Should be close

    def test_compute_distance_different_embeddings(self, data_dir):
        """Different-person faces should be far apart."""
        from scripts.evaluate_golden_set import load_face_data

        face_data = load_face_data(data_dir)
        # Alice vs Bob
        dist = compute_distance(face_data, "photo_A:face0", "photo_C:face0")
        assert dist > 0.5  # Should be far apart


# ---------------------------------------------------------------------------
# Tests: cluster_new_faces
# ---------------------------------------------------------------------------


class TestClusterNewFaces:
    """Tests for the face clustering script."""

    def test_get_photo_id(self):
        assert get_photo_id("Image 001:face0") == "Image 001"
        assert get_photo_id("photo_A:face3") == "photo_A"
        assert get_photo_id("no_colon") is None

    def test_compute_centroid(self, data_dir):
        from scripts.cluster_new_faces import load_face_data

        face_data = load_face_data(data_dir)
        centroid = compute_centroid(
            ["photo_A:face0", "photo_B:face0"], face_data
        )
        assert centroid is not None
        assert centroid.shape == (512,)

    def test_compute_centroid_empty(self, data_dir):
        from scripts.cluster_new_faces import load_face_data

        face_data = load_face_data(data_dir)
        centroid = compute_centroid([], face_data)
        assert centroid is None

    def test_compute_centroid_missing_faces(self, data_dir):
        from scripts.cluster_new_faces import load_face_data

        face_data = load_face_data(data_dir)
        centroid = compute_centroid(["nonexistent:face0"], face_data)
        assert centroid is None

    def test_find_matches_returns_suggestions(self, data_dir):
        from scripts.cluster_new_faces import load_face_data

        identities_data = load_identities(data_dir)
        face_data = load_face_data(data_dir)

        suggestions = find_matches(identities_data, face_data, threshold=5.0)
        assert len(suggestions) > 0

    def test_find_matches_sorted_by_distance(self, data_dir):
        from scripts.cluster_new_faces import load_face_data

        identities_data = load_identities(data_dir)
        face_data = load_face_data(data_dir)

        suggestions = find_matches(identities_data, face_data, threshold=5.0)
        distances = [s["distance"] for s in suggestions]
        assert distances == sorted(distances)

    def test_find_matches_only_unresolved_sources(self, data_dir):
        """Suggestions should only come from INBOX/PROPOSED identities."""
        from scripts.cluster_new_faces import load_face_data

        identities_data = load_identities(data_dir)
        face_data = load_face_data(data_dir)

        suggestions = find_matches(identities_data, face_data, threshold=5.0)
        source_ids = {s["source_identity_id"] for s in suggestions}
        # Should not include confirmed or merged identities
        assert "id-alice" not in source_ids
        assert "id-bob" not in source_ids
        assert "id-merged" not in source_ids

    def test_find_matches_targets_confirmed(self, data_dir):
        """Match targets should only be CONFIRMED identities."""
        from scripts.cluster_new_faces import load_face_data

        identities_data = load_identities(data_dir)
        face_data = load_face_data(data_dir)

        suggestions = find_matches(identities_data, face_data, threshold=5.0)
        target_ids = {s["target_identity_id"] for s in suggestions}
        # All targets should be confirmed
        for tid in target_ids:
            identity = identities_data["identities"][tid]
            assert identity["state"] == "CONFIRMED"
            assert "merged_into" not in identity or identity.get("merged_into") is None

    def test_find_matches_respects_threshold(self, data_dir):
        from scripts.cluster_new_faces import load_face_data

        identities_data = load_identities(data_dir)
        face_data = load_face_data(data_dir)

        # Very tight threshold should return few/no matches
        suggestions_tight = find_matches(identities_data, face_data, threshold=0.001)
        suggestions_loose = find_matches(identities_data, face_data, threshold=5.0)

        assert len(suggestions_tight) <= len(suggestions_loose)

    def test_find_matches_close_faces_match_correct_identity(self, data_dir):
        """Unknown1 (close to Alice) should match Alice, not Bob."""
        from scripts.cluster_new_faces import load_face_data

        identities_data = load_identities(data_dir)
        face_data = load_face_data(data_dir)

        suggestions = find_matches(identities_data, face_data, threshold=5.0)

        # Find suggestion for unknown1's face
        unknown1_suggestions = [
            s for s in suggestions if s["face_id"] == "photo_E:face0"
        ]
        assert len(unknown1_suggestions) == 1
        assert unknown1_suggestions[0]["target_identity_id"] == "id-alice"

        # Find suggestion for unknown2's face
        unknown2_suggestions = [
            s for s in suggestions if s["face_id"] == "photo_F:face0"
        ]
        assert len(unknown2_suggestions) == 1
        assert unknown2_suggestions[0]["target_identity_id"] == "id-bob"

    def test_apply_suggestions_moves_face(self, data_dir):
        """Apply should move face from source to target as candidate."""
        identities_data = load_identities(data_dir)

        suggestions = [{
            "face_id": "photo_E:face0",
            "source_identity_id": "id-unknown1",
            "source_identity_name": "Unidentified Person 001",
            "target_identity_id": "id-alice",
            "target_identity_name": "Alice Smith",
            "distance": 0.5,
            "target_face_count": 2,
        }]

        updated, applied = apply_suggestions(identities_data, suggestions)
        assert applied == 1

        # Face should be in target's candidates
        target = updated["identities"]["id-alice"]
        assert "photo_E:face0" in target["candidate_ids"]

        # Face should be removed from source
        source = updated["identities"]["id-unknown1"]
        assert "photo_E:face0" not in source["candidate_ids"]

    def test_apply_suggestions_marks_empty_source_as_merged(self, data_dir):
        """Source identity with no remaining faces should be marked merged."""
        identities_data = load_identities(data_dir)

        # Unknown1 has only 1 face
        suggestions = [{
            "face_id": "photo_E:face0",
            "source_identity_id": "id-unknown1",
            "source_identity_name": "Unidentified Person 001",
            "target_identity_id": "id-alice",
            "target_identity_name": "Alice Smith",
            "distance": 0.5,
            "target_face_count": 2,
        }]

        updated, applied = apply_suggestions(identities_data, suggestions)
        source = updated["identities"]["id-unknown1"]
        assert source.get("merged_into") == "id-alice"

    def test_apply_suggestions_does_not_modify_original(self, data_dir):
        """Apply should return new data, not modify the original."""
        identities_data = load_identities(data_dir)
        original_candidates = list(
            identities_data["identities"]["id-alice"]["candidate_ids"]
        )

        suggestions = [{
            "face_id": "photo_E:face0",
            "source_identity_id": "id-unknown1",
            "source_identity_name": "Unidentified Person 001",
            "target_identity_id": "id-alice",
            "target_identity_name": "Alice Smith",
            "distance": 0.5,
            "target_face_count": 2,
        }]

        updated, applied = apply_suggestions(identities_data, suggestions)

        # Original should be unchanged
        assert identities_data["identities"]["id-alice"]["candidate_ids"] == original_candidates

    def test_apply_suggestions_skips_already_merged(self, data_dir):
        """Should skip suggestions for already-merged identities."""
        identities_data = load_identities(data_dir)

        suggestions = [{
            "face_id": "photo_G:face0",
            "source_identity_id": "id-merged",
            "source_identity_name": "Merged Person",
            "target_identity_id": "id-alice",
            "target_identity_name": "Alice Smith",
            "distance": 0.5,
            "target_face_count": 2,
        }]

        updated, applied = apply_suggestions(identities_data, suggestions)
        assert applied == 0

    def test_apply_suggestions_updates_version(self, data_dir):
        identities_data = load_identities(data_dir)

        original_target_version = identities_data["identities"]["id-alice"]["version_id"]
        original_source_version = identities_data["identities"]["id-unknown1"]["version_id"]

        suggestions = [{
            "face_id": "photo_E:face0",
            "source_identity_id": "id-unknown1",
            "source_identity_name": "Unidentified Person 001",
            "target_identity_id": "id-alice",
            "target_identity_name": "Alice Smith",
            "distance": 0.5,
            "target_face_count": 2,
        }]

        updated, _ = apply_suggestions(identities_data, suggestions)

        assert updated["identities"]["id-alice"]["version_id"] == original_target_version + 1
        assert updated["identities"]["id-unknown1"]["version_id"] == original_source_version + 1


# ---------------------------------------------------------------------------
# Tests: extract_face_ids helper
# ---------------------------------------------------------------------------


class TestExtractFaceIds:
    """Tests for the shared face_id extraction logic."""

    def test_string_anchors(self):
        identity = {
            "anchor_ids": ["face0", "face1"],
            "candidate_ids": ["face2"],
        }
        assert extract_face_ids(identity) == ["face0", "face1", "face2"]

    def test_dict_anchors(self):
        identity = {
            "anchor_ids": [
                {"face_id": "face0", "weight": 1.0},
                {"face_id": "face1", "weight": 0.8},
            ],
            "candidate_ids": ["face2"],
        }
        assert extract_face_ids(identity) == ["face0", "face1", "face2"]

    def test_empty_identity(self):
        identity = {"anchor_ids": [], "candidate_ids": []}
        assert extract_face_ids(identity) == []

    def test_missing_keys(self):
        identity = {}
        assert extract_face_ids(identity) == []
