"""Tests for golden set diversity analysis (ML-011).

All tests use isolated fixture data — never production data.
"""

import json
import sys
from pathlib import Path

import pytest

# Add project root for imports
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scripts.analyze_golden_set import analyze_golden_set, _auto_generate_mappings


def _make_identities_json(identities: dict) -> dict:
    return {"schema_version": 1, "identities": identities}


def _make_golden_set(mappings: list) -> dict:
    return {
        "version": 1,
        "mappings": mappings,
        "stats": {"total_mappings": len(mappings)},
    }


@pytest.fixture
def rich_data_dir(tmp_path):
    """Data dir with a golden set containing multiple identities and faces."""
    mappings = [
        # Alice: 6 faces (rich identity)
        *[{"face_id": f"photo_A{i}:face0", "identity_id": "id-alice",
           "identity_name": "Alice", "source": "confirmed_anchor"}
          for i in range(6)],
        # Bob: 3 faces
        *[{"face_id": f"photo_B{i}:face0", "identity_id": "id-bob",
           "identity_name": "Bob", "source": "confirmed_anchor"}
          for i in range(3)],
        # Charlie: 1 face (single-face)
        {"face_id": "photo_C0:face0", "identity_id": "id-charlie",
         "identity_name": "Charlie", "source": "confirmed_anchor"},
    ]
    with open(tmp_path / "golden_set.json", "w") as f:
        json.dump(_make_golden_set(mappings), f)

    identities = {
        "id-alice": {"identity_id": "id-alice", "name": "Alice", "state": "CONFIRMED",
                     "anchor_ids": [f"photo_A{i}:face0" for i in range(6)],
                     "candidate_ids": [], "negative_ids": []},
        "id-bob": {"identity_id": "id-bob", "name": "Bob", "state": "CONFIRMED",
                   "anchor_ids": [f"photo_B{i}:face0" for i in range(3)],
                   "candidate_ids": [], "negative_ids": []},
        "id-charlie": {"identity_id": "id-charlie", "name": "Charlie", "state": "CONFIRMED",
                       "anchor_ids": ["photo_C0:face0"],
                       "candidate_ids": [], "negative_ids": []},
    }
    with open(tmp_path / "identities.json", "w") as f:
        json.dump(_make_identities_json(identities), f)

    return tmp_path


class TestAnalyzeGoldenSetReportStructure:
    """Report includes identity count, pair counts, and diversity score."""

    def test_report_has_required_keys(self, rich_data_dir):
        report = analyze_golden_set(rich_data_dir)
        required = [
            "total_mappings", "unique_identities", "single_face_identities",
            "multi_face_identities", "rich_identities", "same_person_pairs",
            "different_person_pairs", "collections", "collection_breakdown",
            "gaps", "identity_distribution",
        ]
        for key in required:
            assert key in report, f"Missing key: {key}"

    def test_report_counts_correct(self, rich_data_dir):
        report = analyze_golden_set(rich_data_dir)
        assert report["total_mappings"] == 10
        assert report["unique_identities"] == 3
        assert report["single_face_identities"] == 1  # Charlie
        assert report["multi_face_identities"] == 2   # Alice, Bob
        assert report["rich_identities"] == 1          # Alice (6 faces)

    def test_pairwise_counts(self, rich_data_dir):
        report = analyze_golden_set(rich_data_dir)
        # Alice: C(6,2)=15, Bob: C(3,2)=3, Charlie: C(1,2)=0 → 18 same pairs
        assert report["same_person_pairs"] == 18
        # Different pairs: 6*3 + 6*1 + 3*1 = 27
        assert report["different_person_pairs"] == 27

    def test_identity_distribution_present(self, rich_data_dir):
        report = analyze_golden_set(rich_data_dir)
        dist = report["identity_distribution"]
        assert dist["Alice"] == 6
        assert dist["Bob"] == 3
        assert dist["Charlie"] == 1


class TestAnalyzeGoldenSetEmptyGraceful:
    """Script handles empty or missing golden set without crashing."""

    def test_empty_golden_set(self, tmp_path):
        with open(tmp_path / "golden_set.json", "w") as f:
            json.dump({"version": 1, "mappings": []}, f)
        report = analyze_golden_set(tmp_path)
        assert report["total_mappings"] == 0
        assert report["unique_identities"] == 0
        assert len(report["gaps"]) == 1
        assert "CRITICAL" in report["gaps"][0]

    def test_missing_golden_set_no_identities(self, tmp_path):
        """No golden set and no identities file — returns empty report."""
        report = analyze_golden_set(tmp_path)
        assert report["total_mappings"] == 0
        assert "CRITICAL" in report["gaps"][0]

    def test_missing_golden_set_with_identities_auto_generates(self, tmp_path):
        """When golden set is missing but identities exist, auto-generates."""
        identities = {
            "id-alice": {
                "identity_id": "id-alice", "name": "Alice", "state": "CONFIRMED",
                "anchor_ids": ["face1", "face2"], "candidate_ids": ["face3"],
                "negative_ids": [],
            },
        }
        with open(tmp_path / "identities.json", "w") as f:
            json.dump(_make_identities_json(identities), f)

        report = analyze_golden_set(tmp_path)
        assert report["total_mappings"] == 3  # 2 anchors + 1 candidate
        assert report["unique_identities"] == 1

    def test_missing_photo_index_still_works(self, rich_data_dir):
        """Analysis works even without photo_index.json — just no collection info."""
        (rich_data_dir / "photo_index.json").unlink(missing_ok=True)
        report = analyze_golden_set(rich_data_dir)
        assert report["total_mappings"] == 10
        assert report["collections"] >= 1  # "Unknown" collection


class TestAnalyzeGoldenSetRecommendations:
    """Script suggests additions when coverage is poor."""

    def test_recommends_when_many_single_face(self, tmp_path):
        """Flags when >30% of identities have only 1 face."""
        mappings = [
            {"face_id": "a:face0", "identity_id": "id1",
             "identity_name": "One", "source": "confirmed_anchor"},
            {"face_id": "b:face0", "identity_id": "id2",
             "identity_name": "Two", "source": "confirmed_anchor"},
            {"face_id": "c:face0", "identity_id": "id3",
             "identity_name": "Three", "source": "confirmed_anchor"},
        ]
        with open(tmp_path / "golden_set.json", "w") as f:
            json.dump(_make_golden_set(mappings), f)

        report = analyze_golden_set(tmp_path)
        high_gaps = [g for g in report["gaps"] if g.startswith("HIGH:")]
        assert len(high_gaps) == 1
        assert "only 1 face" in high_gaps[0].lower()

    def test_recommends_when_few_same_pairs(self, tmp_path):
        """Flags when same-person pairs < 50."""
        mappings = [
            {"face_id": "a:face0", "identity_id": "id1",
             "identity_name": "One", "source": "confirmed_anchor"},
            {"face_id": "a:face1", "identity_id": "id1",
             "identity_name": "One", "source": "confirmed_anchor"},
        ]
        with open(tmp_path / "golden_set.json", "w") as f:
            json.dump(_make_golden_set(mappings), f)

        report = analyze_golden_set(tmp_path)
        low_gaps = [g for g in report["gaps"] if g.startswith("LOW:")]
        assert len(low_gaps) == 1
        assert "same-person pairs" in low_gaps[0].lower()

    def test_no_gaps_when_well_covered(self, tmp_path):
        """No gaps when golden set has excellent coverage."""
        mappings = []
        # 10 identities, 10 faces each → 450 same-person pairs, 0 single-face
        for i in range(10):
            for j in range(10):
                mappings.append({
                    "face_id": f"p{i}_{j}:face0",
                    "identity_id": f"id-{i}",
                    "identity_name": f"Person {i}",
                    "source": "confirmed_anchor",
                })
        with open(tmp_path / "golden_set.json", "w") as f:
            json.dump(_make_golden_set(mappings), f)

        # Also need photo_index with 3+ collections
        photos = {}
        face_to_photo = {}
        collections = ["Col A", "Col B", "Col C"]
        for i in range(10):
            for j in range(10):
                pid = f"photo_{i}_{j}"
                fid = f"p{i}_{j}:face0"
                photos[pid] = {"path": f"{pid}.jpg", "face_ids": [fid],
                               "source": collections[i % 3]}
                face_to_photo[fid] = pid
        with open(tmp_path / "photo_index.json", "w") as f:
            json.dump({"schema_version": 1, "photos": photos,
                       "face_to_photo": face_to_photo}, f)

        report = analyze_golden_set(tmp_path)
        assert len(report["gaps"]) == 0


class TestAutoGenerateGoldenSet:
    """Script can auto-generate golden set from confirmed identities."""

    def test_generates_from_confirmed(self, tmp_path):
        identities = {
            "id-confirmed": {
                "identity_id": "id-confirmed", "name": "Confirmed",
                "state": "CONFIRMED",
                "anchor_ids": ["face1"], "candidate_ids": ["face2"],
                "negative_ids": [],
            },
            "id-proposed": {
                "identity_id": "id-proposed", "name": "Proposed",
                "state": "PROPOSED",
                "anchor_ids": ["face3"], "candidate_ids": [],
                "negative_ids": [],
            },
        }
        with open(tmp_path / "identities.json", "w") as f:
            json.dump(_make_identities_json(identities), f)

        mappings = _auto_generate_mappings(tmp_path / "identities.json")
        assert len(mappings) == 2  # Only confirmed: face1 + face2
        ids = {m["identity_id"] for m in mappings}
        assert "id-confirmed" in ids
        assert "id-proposed" not in ids

    def test_excludes_merged(self, tmp_path):
        identities = {
            "id-merged": {
                "identity_id": "id-merged", "name": "Merged",
                "state": "CONFIRMED", "merged_into": "id-other",
                "anchor_ids": ["face1"], "candidate_ids": [],
                "negative_ids": [],
            },
        }
        with open(tmp_path / "identities.json", "w") as f:
            json.dump(_make_identities_json(identities), f)

        mappings = _auto_generate_mappings(tmp_path / "identities.json")
        assert len(mappings) == 0

    def test_handles_dict_anchors(self, tmp_path):
        identities = {
            "id-dict": {
                "identity_id": "id-dict", "name": "DictAnchors",
                "state": "CONFIRMED",
                "anchor_ids": [{"face_id": "face1"}, {"face_id": "face2"}],
                "candidate_ids": [],
                "negative_ids": [],
            },
        }
        with open(tmp_path / "identities.json", "w") as f:
            json.dump(_make_identities_json(identities), f)

        mappings = _auto_generate_mappings(tmp_path / "identities.json")
        assert len(mappings) == 2
        face_ids = {m["face_id"] for m in mappings}
        assert "face1" in face_ids
        assert "face2" in face_ids

    def test_no_identities_file_returns_empty(self, tmp_path):
        mappings = _auto_generate_mappings(tmp_path / "identities.json")
        assert mappings == []
