"""Tests for core/auto_cluster.py — AD-179 two-tier auto-clustering."""

import json
import os
import tempfile

import numpy as np
import pytest


def _make_mu(vals=None, dim=512):
    """Create a 512-dim mu vector. If vals is a list, pad to 512."""
    if vals is None:
        return np.random.randn(dim).astype(np.float32)
    mu = np.zeros(dim, dtype=np.float32)
    for i, v in enumerate(vals):
        mu[i] = v
    return mu


def _make_face_data_entry(mu):
    """Create a face_data entry dict."""
    return {"mu": np.asarray(mu, dtype=np.float32)}


def _make_identities_data(confirmed=None, inbox=None):
    """Build identities_data dict from simplified specs.

    confirmed: list of (identity_id, name, face_ids)
    inbox: list of (identity_id, name, face_ids)
    """
    identities = {}
    for iid, name, fids in (confirmed or []):
        identities[iid] = {
            "identity_id": iid,
            "name": name,
            "state": "CONFIRMED",
            "anchor_ids": list(fids),
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
        }
    for iid, name, fids in (inbox or []):
        identities[iid] = {
            "identity_id": iid,
            "name": name,
            "state": "INBOX",
            "anchor_ids": list(fids),
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
        }
    return {"identities": identities}


class TestAutoClusterFace:
    """Tests for auto_cluster_face() — tier classification."""

    def test_tier_1_very_close_match(self):
        """Face very close to confirmed identity should be Tier 1."""
        from core.auto_cluster import auto_cluster_face

        confirmed_mu = _make_mu([1.0, 0.0, 0.0])
        query_mu = _make_mu([0.95, 0.0, 0.0])  # Very close

        confirmed_clusters = {
            "conf-1": {
                "name": "Test Person",
                "embeddings": confirmed_mu.reshape(1, -1),
                "face_ids": ["face_a"],
            }
        }

        tier, target_id, distance = auto_cluster_face(
            "query_face", query_mu, confirmed_clusters, {}
        )

        assert tier == "tier_1"
        assert target_id == "conf-1"
        assert distance < 0.85
        assert distance == pytest.approx(0.05, abs=0.01)

    def test_tier_2_moderate_match(self):
        """Face at moderate distance should be Tier 2."""
        from core.auto_cluster import auto_cluster_face

        confirmed_mu = _make_mu([1.0, 0.0, 0.0])
        # Create query at distance ~0.95 (between 0.85 and 1.10)
        query_mu = _make_mu([0.1, 0.2, 0.0])
        # Compute actual distance to verify it's in tier 2 range
        dist = np.linalg.norm(confirmed_mu - query_mu)

        confirmed_clusters = {
            "conf-1": {
                "name": "Test Person",
                "embeddings": confirmed_mu.reshape(1, -1),
                "face_ids": ["face_a"],
            }
        }

        tier, target_id, distance = auto_cluster_face(
            "query_face", query_mu, confirmed_clusters, {}
        )

        assert tier == "tier_2"
        assert target_id == "conf-1"
        assert 0.85 <= distance < 1.10

    def test_no_match_far_distance(self):
        """Face far from all confirmed identities should be no_match."""
        from core.auto_cluster import auto_cluster_face

        confirmed_mu = _make_mu([1.0, 0.0, 0.0])
        query_mu = _make_mu([-1.0, 0.0, 0.0])  # Very far

        confirmed_clusters = {
            "conf-1": {
                "name": "Test Person",
                "embeddings": confirmed_mu.reshape(1, -1),
                "face_ids": ["face_a"],
            }
        }

        tier, target_id, distance = auto_cluster_face(
            "query_face", query_mu, confirmed_clusters, {}
        )

        assert tier == "no_match"
        assert target_id is None
        assert distance is None

    def test_no_confirmed_clusters(self):
        """No confirmed clusters should return no_match."""
        from core.auto_cluster import auto_cluster_face

        query_mu = _make_mu([1.0, 0.0, 0.0])
        tier, target_id, distance = auto_cluster_face(
            "query_face", query_mu, {}, {}
        )

        assert tier == "no_match"
        assert target_id is None
        assert distance is None

    def test_none_face_mu(self):
        """None face_mu should return no_match."""
        from core.auto_cluster import auto_cluster_face

        tier, target_id, distance = auto_cluster_face(
            "query_face", None, {"x": {"embeddings": np.zeros((1, 512))}}, {}
        )

        assert tier == "no_match"

    def test_best_linkage_multi_anchor(self):
        """With multiple anchors, should use min distance (best-linkage)."""
        from core.auto_cluster import auto_cluster_face

        # Two anchors: one far, one close
        anchor_far = _make_mu([-1.0, 0.0, 0.0])
        anchor_close = _make_mu([1.0, 0.0, 0.0])
        query_mu = _make_mu([0.97, 0.0, 0.0])

        confirmed_clusters = {
            "conf-1": {
                "name": "Test Person",
                "embeddings": np.vstack([anchor_far, anchor_close]),
                "face_ids": ["far", "close"],
            }
        }

        tier, target_id, distance = auto_cluster_face(
            "query_face", query_mu, confirmed_clusters, {}
        )

        # Should match to close anchor (distance ~0.03), not average
        assert tier == "tier_1"
        assert distance < 0.1

    def test_picks_closest_identity(self):
        """When multiple confirmed identities exist, picks the closest one."""
        from core.auto_cluster import auto_cluster_face

        mu_a = _make_mu([1.0, 0.0, 0.0])
        mu_b = _make_mu([0.0, 1.0, 0.0])
        query_mu = _make_mu([0.98, 0.0, 0.0])  # Much closer to A

        confirmed_clusters = {
            "conf-a": {
                "name": "Person A",
                "embeddings": mu_a.reshape(1, -1),
                "face_ids": ["face_a"],
            },
            "conf-b": {
                "name": "Person B",
                "embeddings": mu_b.reshape(1, -1),
                "face_ids": ["face_b"],
            },
        }

        tier, target_id, distance = auto_cluster_face(
            "query_face", query_mu, confirmed_clusters, {}
        )

        assert target_id == "conf-a"
        assert tier == "tier_1"


class TestDedupInbox:
    """Tests for dedup_inbox() — per-face deduplication (Session 78)."""

    def test_finds_full_duplicates(self):
        """Inbox identity with all face_ids in one confirmed should be full dup."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a", "face_b"])],
            inbox=[("inbox-1", "Unidentified 1", ["face_a"])],
        )

        result = dedup_inbox(identities_data, dry_run=True)

        assert len(result["full_duplicates"]) == 1
        inbox_id, conf_id, shared = result["full_duplicates"][0]
        assert inbox_id == "inbox-1"
        assert conf_id == "conf-1"
        assert "face_a" in shared
        assert result["total_face_dups"] == 1

    def test_no_duplicates_when_different_faces(self):
        """Inbox with unique faces should not be flagged as duplicate."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a"])],
            inbox=[("inbox-1", "Unidentified 1", ["face_x"])],
        )

        result = dedup_inbox(identities_data, dry_run=True)
        assert len(result["full_duplicates"]) == 0
        assert len(result["partial_duplicates"]) == 0
        assert result["total_face_dups"] == 0

    def test_partial_overlap_single_target_detected(self):
        """Inbox with some faces in one confirmed should be partial dup."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a"])],
            inbox=[("inbox-1", "Unidentified 1", ["face_a", "face_x"])],
        )

        result = dedup_inbox(identities_data, dry_run=True)
        # Not a full duplicate (face_x is unique)
        assert len(result["full_duplicates"]) == 0
        # But should be detected as partial duplicate
        assert len(result["partial_duplicates"]) == 1
        partial = result["partial_duplicates"][0]
        assert partial["inbox_id"] == "inbox-1"
        assert partial["action"] == "remove_duplicate_faces"
        assert "face_a" in partial["shared_faces"]
        assert "face_x" in partial["unshared_faces"]
        assert result["total_face_dups"] == 1

    def test_partial_overlap_multi_target_review_needed(self):
        """Faces in DIFFERENT confirmed identities should need review."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[
                ("conf-1", "Person A", ["face_a"]),
                ("conf-2", "Person B", ["face_b"]),
            ],
            inbox=[("inbox-1", "Unidentified", ["face_a", "face_b", "face_x"])],
        )

        result = dedup_inbox(identities_data, dry_run=True)
        assert len(result["full_duplicates"]) == 0
        assert len(result["partial_duplicates"]) == 1
        partial = result["partial_duplicates"][0]
        assert partial["action"] == "review_needed"
        assert result["total_face_dups"] == 2

    def test_all_faces_multi_target_review_needed(self):
        """ALL faces belonging to DIFFERENT confirmed identities => review."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[
                ("conf-1", "Person A", ["face_a"]),
                ("conf-2", "Person B", ["face_b"]),
            ],
            inbox=[("inbox-1", "Unidentified", ["face_a", "face_b"])],
        )

        result = dedup_inbox(identities_data, dry_run=True)
        # All faces are dups, but to different confirmed identities
        assert len(result["full_duplicates"]) == 0
        assert len(result["partial_duplicates"]) == 1
        assert result["partial_duplicates"][0]["action"] == "review_needed"

    def test_dry_run_does_not_modify(self):
        """Dry run should not modify the identities data."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a"])],
            inbox=[("inbox-1", "Unidentified 1", ["face_a"])],
        )

        dedup_inbox(identities_data, dry_run=True)

        # Identity should NOT be marked as merged
        assert "merged_into" not in identities_data["identities"]["inbox-1"]

    def test_dry_run_partial_does_not_modify(self):
        """Dry run should not remove faces from partial duplicates."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a"])],
            inbox=[("inbox-1", "Unidentified 1", ["face_a", "face_x"])],
        )

        dedup_inbox(identities_data, dry_run=True)

        inbox = identities_data["identities"]["inbox-1"]
        # face_a should still be present (dry_run)
        assert "face_a" in inbox["anchor_ids"]

    def test_execute_marks_full_dup_merged(self):
        """Execute mode should mark full duplicate as merged_into."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a"])],
            inbox=[("inbox-1", "Unidentified 1", ["face_a"])],
        )

        dedup_inbox(identities_data, dry_run=False)

        inbox = identities_data["identities"]["inbox-1"]
        assert inbox["merged_into"] == "conf-1"
        assert inbox["version_id"] == 2

    def test_execute_removes_partial_dup_faces(self):
        """Execute mode should remove duplicate faces from partial dup."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a"])],
            inbox=[("inbox-1", "Unidentified 1", ["face_a", "face_x"])],
        )

        result = dedup_inbox(identities_data, dry_run=False)

        inbox = identities_data["identities"]["inbox-1"]
        # face_a should be removed, face_x should remain
        assert "face_a" not in inbox["anchor_ids"]
        assert "face_x" in inbox["anchor_ids"]
        assert inbox["version_id"] == 2
        assert "merged_into" not in inbox  # Not fully merged

    def test_execute_partial_multi_target_no_action(self):
        """Execute mode should NOT modify multi-target partial dups."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[
                ("conf-1", "Person A", ["face_a"]),
                ("conf-2", "Person B", ["face_b"]),
            ],
            inbox=[("inbox-1", "Unidentified", ["face_a", "face_b", "face_x"])],
        )

        dedup_inbox(identities_data, dry_run=False)

        inbox = identities_data["identities"]["inbox-1"]
        # Multi-target review_needed should not be auto-modified
        assert "face_a" in inbox["anchor_ids"]
        assert "face_b" in inbox["anchor_ids"]

    def test_skips_already_merged(self):
        """Already-merged identities should be skipped."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a"])],
            inbox=[("inbox-1", "Unidentified 1", ["face_a"])],
        )
        identities_data["identities"]["inbox-1"]["merged_into"] = "conf-1"

        result = dedup_inbox(identities_data, dry_run=True)
        assert len(result["full_duplicates"]) == 0
        assert len(result["partial_duplicates"]) == 0

    def test_handles_candidate_ids_dedup(self):
        """Face in confirmed candidate_ids should also be detected."""
        from core.auto_cluster import dedup_inbox

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", [])],
            inbox=[("inbox-1", "Unidentified", ["face_a"])],
        )
        # Add face_a as candidate on confirmed identity
        identities_data["identities"]["conf-1"]["candidate_ids"] = ["face_a"]

        result = dedup_inbox(identities_data, dry_run=True)
        assert len(result["full_duplicates"]) == 1


class TestBuildConfirmedClusters:
    """Tests for build_confirmed_clusters()."""

    def test_builds_clusters_from_confirmed(self):
        """Should build cluster data from confirmed identities."""
        from core.auto_cluster import build_confirmed_clusters

        mu_a = _make_mu([1.0, 0.0, 0.0])
        face_data = {"face_a": _make_face_data_entry(mu_a)}
        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a"])],
        )

        clusters = build_confirmed_clusters(identities_data, face_data)

        assert "conf-1" in clusters
        assert clusters["conf-1"]["name"] == "Big Leon"
        assert len(clusters["conf-1"]["face_ids"]) == 1

    def test_skips_merged_identities(self):
        """Merged confirmed identities should be excluded."""
        from core.auto_cluster import build_confirmed_clusters

        mu_a = _make_mu([1.0, 0.0, 0.0])
        face_data = {"face_a": _make_face_data_entry(mu_a)}
        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["face_a"])],
        )
        identities_data["identities"]["conf-1"]["merged_into"] = "other"

        clusters = build_confirmed_clusters(identities_data, face_data)
        assert len(clusters) == 0

    def test_skips_inbox_identities(self):
        """Only CONFIRMED identities should be included."""
        from core.auto_cluster import build_confirmed_clusters

        mu_a = _make_mu([1.0, 0.0, 0.0])
        face_data = {"face_a": _make_face_data_entry(mu_a)}
        identities_data = _make_identities_data(
            inbox=[("inbox-1", "Unknown", ["face_a"])],
        )

        clusters = build_confirmed_clusters(identities_data, face_data)
        assert len(clusters) == 0

    def test_handles_dict_anchor_format(self):
        """Should handle anchor_ids that are dicts with face_id key."""
        from core.auto_cluster import build_confirmed_clusters

        mu_a = _make_mu([1.0, 0.0, 0.0])
        face_data = {"face_a": _make_face_data_entry(mu_a)}
        identities_data = {
            "identities": {
                "conf-1": {
                    "identity_id": "conf-1",
                    "name": "Big Leon",
                    "state": "CONFIRMED",
                    "anchor_ids": [{"face_id": "face_a", "provenance": "human"}],
                    "candidate_ids": [],
                    "negative_ids": [],
                }
            }
        }

        clusters = build_confirmed_clusters(identities_data, face_data)
        assert "conf-1" in clusters
        assert "face_a" in clusters["conf-1"]["face_ids"]


class TestLogDiscovery:
    """Tests for log_discovery() — discovery log persistence."""

    def test_creates_log_file(self):
        """Should create log file if it doesn't exist."""
        from core.auto_cluster import log_discovery

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            entry = {
                "face_id": "test_face",
                "tier": 1,
                "action": "auto_clustered",
            }

            log_discovery(entry, log_path=log_path)

            assert os.path.exists(log_path)
            with open(log_path) as f:
                data = json.load(f)
            assert data["schema_version"] == 1
            assert len(data["entries"]) == 1
            assert data["entries"][0]["face_id"] == "test_face"

    def test_appends_to_existing_log(self):
        """Should append to existing log, not overwrite."""
        from core.auto_cluster import log_discovery

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")

            log_discovery({"face_id": "face_1"}, log_path=log_path)
            log_discovery({"face_id": "face_2"}, log_path=log_path)

            with open(log_path) as f:
                data = json.load(f)
            assert len(data["entries"]) == 2


class TestRunBackfill:
    """Tests for run_backfill() — full pipeline."""

    def test_full_backfill_dry_run(self):
        """Full backfill should classify faces without modifying data."""
        from core.auto_cluster import run_backfill

        # Confirmed identity with one face
        conf_mu = _make_mu([1.0, 0.0, 0.0])
        # Inbox face very close (Tier 1)
        inbox_mu_close = _make_mu([0.97, 0.0, 0.0])
        # Inbox face moderate distance (Tier 2)
        inbox_mu_moderate = _make_mu([0.1, 0.2, 0.0])
        # Inbox face far (no match)
        inbox_mu_far = _make_mu([-1.0, 0.0, 0.0])

        face_data = {
            "conf_face": _make_face_data_entry(conf_mu),
            "inbox_close": _make_face_data_entry(inbox_mu_close),
            "inbox_moderate": _make_face_data_entry(inbox_mu_moderate),
            "inbox_far": _make_face_data_entry(inbox_mu_far),
        }

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["conf_face"])],
            inbox=[
                ("inbox-1", "Close Person", ["inbox_close"]),
                ("inbox-2", "Moderate Person", ["inbox_moderate"]),
                ("inbox-3", "Far Person", ["inbox_far"]),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            results = run_backfill(
                identities_data, face_data, log_path=log_path, dry_run=True
            )

        assert results["total_processed"] == 3
        assert len(results["tier_1_results"]) == 1
        assert len(results["tier_2_results"]) == 1
        assert results["no_match_count"] == 1
        assert results["tier_1_results"][0]["face_id"] == "inbox_close"
        assert results["tier_2_results"][0]["face_id"] == "inbox_moderate"

    def test_backfill_execute_adds_candidates(self):
        """Execute mode should add Tier 1 faces as candidates on target."""
        from core.auto_cluster import run_backfill

        conf_mu = _make_mu([1.0, 0.0, 0.0])
        inbox_mu = _make_mu([0.97, 0.0, 0.0])

        face_data = {
            "conf_face": _make_face_data_entry(conf_mu),
            "inbox_face": _make_face_data_entry(inbox_mu),
        }

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["conf_face"])],
            inbox=[("inbox-1", "Unknown", ["inbox_face"])],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            results = run_backfill(
                identities_data, face_data, log_path=log_path, dry_run=False
            )

        # Tier 1 face should be added as candidate on confirmed identity
        conf_identity = identities_data["identities"]["conf-1"]
        assert "inbox_face" in conf_identity["candidate_ids"]
        assert conf_identity["version_id"] == 2

    def test_backfill_dry_run_no_modification(self):
        """Dry run should NOT modify identities data."""
        from core.auto_cluster import run_backfill

        conf_mu = _make_mu([1.0, 0.0, 0.0])
        inbox_mu = _make_mu([0.97, 0.0, 0.0])

        face_data = {
            "conf_face": _make_face_data_entry(conf_mu),
            "inbox_face": _make_face_data_entry(inbox_mu),
        }

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["conf_face"])],
            inbox=[("inbox-1", "Unknown", ["inbox_face"])],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            run_backfill(identities_data, face_data, log_path=log_path, dry_run=True)

        # Confirmed identity should NOT have inbox_face as candidate
        conf_identity = identities_data["identities"]["conf-1"]
        assert "inbox_face" not in conf_identity["candidate_ids"]
        assert conf_identity["version_id"] == 1

    def test_backfill_skips_merged_identities(self):
        """Merged inbox identities should be skipped."""
        from core.auto_cluster import run_backfill

        conf_mu = _make_mu([1.0, 0.0, 0.0])
        inbox_mu = _make_mu([0.97, 0.0, 0.0])

        face_data = {
            "conf_face": _make_face_data_entry(conf_mu),
            "inbox_face": _make_face_data_entry(inbox_mu),
        }

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["conf_face"])],
            inbox=[("inbox-1", "Unknown", ["inbox_face"])],
        )
        identities_data["identities"]["inbox-1"]["merged_into"] = "some-id"

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            results = run_backfill(
                identities_data, face_data, log_path=log_path, dry_run=True
            )

        assert results["total_processed"] == 0

    def test_backfill_with_no_confirmed(self):
        """Should return empty results when no confirmed identities exist."""
        from core.auto_cluster import run_backfill

        inbox_mu = _make_mu([0.97, 0.0, 0.0])
        face_data = {"inbox_face": _make_face_data_entry(inbox_mu)}

        identities_data = _make_identities_data(
            inbox=[("inbox-1", "Unknown", ["inbox_face"])],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            results = run_backfill(
                identities_data, face_data, log_path=log_path, dry_run=True
            )

        assert results["total_processed"] == 0
        assert len(results["tier_1_results"]) == 0
        assert len(results["tier_2_results"]) == 0

    def test_backfill_includes_skipped_identities(self):
        """SKIPPED identities should also be processed."""
        from core.auto_cluster import run_backfill

        conf_mu = _make_mu([1.0, 0.0, 0.0])
        skipped_mu = _make_mu([0.97, 0.0, 0.0])

        face_data = {
            "conf_face": _make_face_data_entry(conf_mu),
            "skipped_face": _make_face_data_entry(skipped_mu),
        }

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["conf_face"])],
        )
        # Add SKIPPED identity manually
        identities_data["identities"]["skip-1"] = {
            "identity_id": "skip-1",
            "name": "Skipped Person",
            "state": "SKIPPED",
            "anchor_ids": ["skipped_face"],
            "candidate_ids": [],
            "negative_ids": [],
            "version_id": 1,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            results = run_backfill(
                identities_data, face_data, log_path=log_path, dry_run=True
            )

        assert results["total_processed"] == 1
        assert len(results["tier_1_results"]) == 1

    def test_backfill_dedup_and_distance_combined(self):
        """Dedup and distance-based clustering should work together."""
        from core.auto_cluster import run_backfill

        conf_mu = _make_mu([1.0, 0.0, 0.0])
        # inbox-dup has exact same face_id as confirmed
        # inbox-close has different face_id but close embedding
        close_mu = _make_mu([0.97, 0.0, 0.0])

        face_data = {
            "shared_face": _make_face_data_entry(conf_mu),
            "close_face": _make_face_data_entry(close_mu),
        }

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["shared_face"])],
            inbox=[
                ("inbox-dup", "Duplicate", ["shared_face"]),
                ("inbox-close", "Close Match", ["close_face"]),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            results = run_backfill(
                identities_data, face_data, log_path=log_path, dry_run=True
            )

        assert len(results["dedup_results"]["full_duplicates"]) == 1
        assert results["total_processed"] >= 1

    def test_discovery_log_written(self):
        """Discovery log should be written with correct entries."""
        from core.auto_cluster import run_backfill

        conf_mu = _make_mu([1.0, 0.0, 0.0])
        inbox_mu = _make_mu([0.97, 0.0, 0.0])

        face_data = {
            "conf_face": _make_face_data_entry(conf_mu),
            "inbox_face": _make_face_data_entry(inbox_mu),
        }

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["conf_face"])],
            inbox=[("inbox-1", "Unknown", ["inbox_face"])],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            run_backfill(
                identities_data, face_data, log_path=log_path, dry_run=True
            )

            assert os.path.exists(log_path)
            with open(log_path) as f:
                log_data = json.load(f)

            assert log_data["schema_version"] == 1
            assert len(log_data["entries"]) >= 1

            entry = log_data["entries"][0]
            assert "face_id" in entry
            assert "tier" in entry
            assert "action" in entry
            assert "timestamp" in entry

    def test_no_duplicate_candidate_ids(self):
        """Running backfill twice should not add duplicate candidate_ids."""
        from core.auto_cluster import run_backfill

        conf_mu = _make_mu([1.0, 0.0, 0.0])
        inbox_mu = _make_mu([0.97, 0.0, 0.0])

        face_data = {
            "conf_face": _make_face_data_entry(conf_mu),
            "inbox_face": _make_face_data_entry(inbox_mu),
        }

        identities_data = _make_identities_data(
            confirmed=[("conf-1", "Big Leon", ["conf_face"])],
            inbox=[("inbox-1", "Unknown", ["inbox_face"])],
        )
        # Pre-add inbox_face as candidate (simulating previous run)
        identities_data["identities"]["conf-1"]["candidate_ids"] = ["inbox_face"]

        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "discovery_log.json")
            run_backfill(
                identities_data, face_data, log_path=log_path, dry_run=False
            )

        # Should still have only one entry, not duplicated
        conf = identities_data["identities"]["conf-1"]
        assert conf["candidate_ids"].count("inbox_face") == 1


class TestThresholds:
    """Tests for threshold constants and boundaries."""

    def test_tier_1_threshold_value(self):
        """Tier 1 threshold should be 0.85."""
        from core.auto_cluster import TIER_1_THRESHOLD
        assert TIER_1_THRESHOLD == 0.85

    def test_tier_2_threshold_value(self):
        """Tier 2 threshold should be 1.10."""
        from core.auto_cluster import TIER_2_THRESHOLD
        assert TIER_2_THRESHOLD == 1.10

    def test_boundary_at_tier_1(self):
        """Face just above 0.85 should be Tier 2, not Tier 1."""
        from core.auto_cluster import auto_cluster_face, TIER_1_THRESHOLD

        # Create face slightly above Tier 1 boundary
        confirmed_mu = _make_mu([1.0])
        # Distance = 0.86 (just above 0.85)
        query_mu = np.zeros(512, dtype=np.float32)
        query_mu[0] = 1.0 - 0.86  # distance = 0.86

        confirmed_clusters = {
            "conf-1": {
                "name": "Test",
                "embeddings": confirmed_mu.reshape(1, -1),
                "face_ids": ["face_a"],
            }
        }

        tier, _, distance = auto_cluster_face(
            "q", query_mu, confirmed_clusters, {}
        )

        # Distance 0.86 > 0.85, should be Tier 2
        assert tier == "tier_2"
        assert distance > TIER_1_THRESHOLD

    def test_boundary_at_tier_2(self):
        """Face at exactly 1.10 should be no_match."""
        from core.auto_cluster import auto_cluster_face

        confirmed_mu = _make_mu([1.0])
        query_mu = np.zeros(512, dtype=np.float32)
        query_mu[0] = 1.0 - 1.10  # = -0.10, distance = 1.10

        confirmed_clusters = {
            "conf-1": {
                "name": "Test",
                "embeddings": confirmed_mu.reshape(1, -1),
                "face_ids": ["face_a"],
            }
        }

        tier, _, distance = auto_cluster_face(
            "q", query_mu, confirmed_clusters, {}
        )

        # At exactly 1.10, should be no_match (not strictly less than 1.10)
        assert tier == "no_match"


class TestExtractFaceIds:
    """Tests for _extract_face_ids helper."""

    def test_string_anchors(self):
        """Should extract face IDs from string anchor format."""
        from core.auto_cluster import _extract_face_ids

        identity = {
            "anchor_ids": ["face_a", "face_b"],
            "candidate_ids": ["face_c"],
        }
        result = _extract_face_ids(identity)
        assert result == ["face_a", "face_b", "face_c"]

    def test_dict_anchors(self):
        """Should extract face IDs from dict anchor format."""
        from core.auto_cluster import _extract_face_ids

        identity = {
            "anchor_ids": [{"face_id": "face_a", "provenance": "human"}],
            "candidate_ids": [],
        }
        result = _extract_face_ids(identity)
        assert result == ["face_a"]

    def test_empty_identity(self):
        """Should handle identity with no faces."""
        from core.auto_cluster import _extract_face_ids

        identity = {"anchor_ids": [], "candidate_ids": []}
        result = _extract_face_ids(identity)
        assert result == []

    def test_missing_keys(self):
        """Should handle identity with missing anchor/candidate keys."""
        from core.auto_cluster import _extract_face_ids

        identity = {}
        result = _extract_face_ids(identity)
        assert result == []


class TestRemoveFaceIdsFromIdentity:
    """Tests for _remove_face_ids_from_identity helper (Session 78)."""

    def test_removes_string_anchors(self):
        """Should remove matching string anchor_ids."""
        from core.auto_cluster import _remove_face_ids_from_identity

        identity = {
            "anchor_ids": ["face_a", "face_b", "face_c"],
            "candidate_ids": [],
        }
        _remove_face_ids_from_identity(identity, ["face_a", "face_c"])
        assert identity["anchor_ids"] == ["face_b"]

    def test_removes_dict_anchors(self):
        """Should remove matching dict-format anchor_ids."""
        from core.auto_cluster import _remove_face_ids_from_identity

        identity = {
            "anchor_ids": [
                {"face_id": "face_a", "provenance": "human"},
                {"face_id": "face_b", "provenance": "model"},
            ],
            "candidate_ids": [],
        }
        _remove_face_ids_from_identity(identity, ["face_a"])
        assert len(identity["anchor_ids"]) == 1
        assert identity["anchor_ids"][0]["face_id"] == "face_b"

    def test_removes_candidate_ids(self):
        """Should remove matching candidate_ids."""
        from core.auto_cluster import _remove_face_ids_from_identity

        identity = {
            "anchor_ids": [],
            "candidate_ids": ["face_a", "face_b"],
        }
        _remove_face_ids_from_identity(identity, ["face_a"])
        assert identity["candidate_ids"] == ["face_b"]

    def test_removes_from_both_lists(self):
        """Should remove from both anchors and candidates."""
        from core.auto_cluster import _remove_face_ids_from_identity

        identity = {
            "anchor_ids": ["face_a"],
            "candidate_ids": ["face_b"],
        }
        _remove_face_ids_from_identity(identity, ["face_a", "face_b"])
        assert identity["anchor_ids"] == []
        assert identity["candidate_ids"] == []

    def test_no_op_when_no_matches(self):
        """Should not modify identity when no faces match."""
        from core.auto_cluster import _remove_face_ids_from_identity

        identity = {
            "anchor_ids": ["face_a"],
            "candidate_ids": ["face_b"],
        }
        _remove_face_ids_from_identity(identity, ["face_z"])
        assert identity["anchor_ids"] == ["face_a"]
        assert identity["candidate_ids"] == ["face_b"]

    def test_handles_missing_keys(self):
        """Should handle identity with missing keys gracefully."""
        from core.auto_cluster import _remove_face_ids_from_identity

        identity = {}
        _remove_face_ids_from_identity(identity, ["face_a"])
        assert identity["anchor_ids"] == []
        assert identity["candidate_ids"] == []
