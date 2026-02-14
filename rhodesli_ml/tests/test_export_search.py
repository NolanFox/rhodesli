"""Tests for the search metadata export script.

Tests cover:
- Search document building from labels
- Searchable text concatenation
- Output file writing and schema
- Dry run mode
- Edge cases: missing fields, empty labels, no metadata
- Summary statistics (decade distribution, source methods)
"""

import json
from pathlib import Path

import pytest

from rhodesli_ml.scripts.export_search_metadata import (
    build_search_document,
    export_search_metadata,
    load_date_labels,
)


# ============================================================
# Fixtures
# ============================================================

def _make_label(
    photo_id="photo-001",
    estimated_decade=1940,
    best_year_estimate=1942,
    people_count=3,
    scene_description="A formal studio portrait of a family.",
    visible_text=None,
    keywords=None,
    controlled_tags=None,
    clothing_notes=None,
    location_estimate=None,
    source_method="api",
):
    """Build a test date label entry with rich metadata."""
    return {
        "photo_id": photo_id,
        "estimated_decade": estimated_decade,
        "best_year_estimate": best_year_estimate,
        "people_count": people_count,
        "scene_description": scene_description,
        "visible_text": visible_text,
        "keywords": keywords or ["portrait", "studio", "family"],
        "controlled_tags": controlled_tags or ["Studio", "Formal_Event"],
        "clothing_notes": clothing_notes,
        "location_estimate": location_estimate,
        "source_method": source_method,
        "source": "gemini",
        "confidence": "medium",
    }


def _write_json(path, data):
    """Write a JSON file."""
    with open(path, "w") as f:
        json.dump(data, f)


# ============================================================
# File Loading Tests
# ============================================================

class TestLoadDateLabels:
    def test_loads_labels(self, tmp_path):
        """Loads labels list from file."""
        path = tmp_path / "labels.json"
        _write_json(path, {
            "labels": [
                {"photo_id": "p1", "estimated_decade": 1940},
                {"photo_id": "p2", "estimated_decade": 1950},
            ]
        })
        result = load_date_labels(path)
        assert len(result) == 2

    def test_returns_empty_for_missing_file(self, tmp_path):
        """Returns empty list for nonexistent file."""
        result = load_date_labels(tmp_path / "missing.json")
        assert result == []


# ============================================================
# Search Document Building Tests
# ============================================================

class TestBuildSearchDocument:
    def test_basic_document(self):
        """Builds a document with all fields."""
        label = _make_label()
        doc = build_search_document(label)
        assert doc["photo_id"] == "photo-001"
        assert doc["estimated_decade"] == 1940
        assert doc["best_year_estimate"] == 1942
        assert doc["people_count"] == 3
        assert doc["controlled_tags"] == ["Studio", "Formal_Event"]
        assert doc["source_method"] == "api"

    def test_searchable_text_includes_scene(self):
        """Searchable text includes scene description."""
        label = _make_label(scene_description="A wedding photo on the beach.")
        doc = build_search_document(label)
        assert "wedding" in doc["searchable_text"].lower()
        assert "beach" in doc["searchable_text"].lower()

    def test_searchable_text_includes_visible_text(self):
        """Searchable text includes visible_text (inscriptions)."""
        label = _make_label(visible_text="A mi querida hermana Estrella")
        doc = build_search_document(label)
        assert "Estrella" in doc["searchable_text"]

    def test_searchable_text_includes_keywords(self):
        """Searchable text includes joined keywords."""
        label = _make_label(keywords=["fez", "traditional", "outdoor"])
        doc = build_search_document(label)
        assert "fez" in doc["searchable_text"]
        assert "traditional" in doc["searchable_text"]
        assert "outdoor" in doc["searchable_text"]

    def test_searchable_text_includes_clothing_notes(self):
        """Searchable text includes clothing notes."""
        label = _make_label(clothing_notes="Dark three-piece suit with pocket watch chain.")
        doc = build_search_document(label)
        assert "pocket watch" in doc["searchable_text"]

    def test_searchable_text_includes_location(self):
        """Searchable text includes location estimate."""
        label = _make_label(location_estimate="Rhodes, Greece")
        doc = build_search_document(label)
        assert "Rhodes" in doc["searchable_text"]

    def test_searchable_text_empty_when_no_metadata(self):
        """Searchable text is empty when label has no metadata fields."""
        label = {
            "photo_id": "bare-label",
            "estimated_decade": 1940,
            "source_method": "api",
        }
        doc = build_search_document(label)
        assert doc["searchable_text"] == ""
        assert doc["photo_id"] == "bare-label"
        assert doc["controlled_tags"] == []

    def test_searchable_text_concatenation_order(self):
        """Text parts are concatenated in order: scene, visible, keywords, clothing, location."""
        label = _make_label(
            scene_description="Scene first.",
            visible_text="Then text.",
            keywords=["keyword_here"],
            clothing_notes="Clothing last.",
            location_estimate="Location end.",
        )
        doc = build_search_document(label)
        text = doc["searchable_text"]
        assert text.index("Scene") < text.index("Then text")
        assert text.index("Then text") < text.index("keyword_here")
        assert text.index("keyword_here") < text.index("Clothing")
        assert text.index("Clothing") < text.index("Location")

    def test_handles_null_visible_text(self):
        """visible_text=None is handled gracefully."""
        label = _make_label(visible_text=None)
        doc = build_search_document(label)
        assert doc["searchable_text"]  # Still has scene + keywords
        assert "None" not in doc["searchable_text"]

    def test_source_method_default(self):
        """source_method defaults to empty string when missing."""
        label = {"photo_id": "p1", "estimated_decade": 1940}
        doc = build_search_document(label)
        assert doc["source_method"] == ""


# ============================================================
# Export Function Tests
# ============================================================

class TestExportSearchMetadata:
    def test_exports_documents(self, tmp_path):
        """Exports documents to output file."""
        labels = [_make_label("p1"), _make_label("p2")]
        output = tmp_path / "index.json"
        summary, docs = export_search_metadata(labels, output)
        assert summary["total_documents"] == 2
        assert summary["written"] is True
        assert output.exists()

        # Verify file contents
        with open(output) as f:
            data = json.load(f)
        assert data["schema_version"] == 1
        assert len(data["documents"]) == 2

    def test_dry_run_does_not_write(self, tmp_path):
        """Dry run computes summary without writing file."""
        labels = [_make_label("p1")]
        output = tmp_path / "index.json"
        summary, docs = export_search_metadata(labels, output, dry_run=True)
        assert summary["total_documents"] == 1
        assert summary["written"] is False
        assert not output.exists()

    def test_skips_labels_without_photo_id(self, tmp_path):
        """Labels missing photo_id are skipped."""
        labels = [
            _make_label("p1"),
            {"estimated_decade": 1940},  # No photo_id
        ]
        output = tmp_path / "index.json"
        summary, docs = export_search_metadata(labels, output)
        assert summary["total_documents"] == 1
        assert summary["skipped"] == 1

    def test_empty_labels(self, tmp_path):
        """Empty labels list produces no output file."""
        output = tmp_path / "index.json"
        summary, docs = export_search_metadata([], output)
        assert summary["total_documents"] == 0
        assert summary["written"] is False
        assert not output.exists()

    def test_creates_parent_directories(self, tmp_path):
        """Creates parent directories if they don't exist."""
        output = tmp_path / "subdir" / "nested" / "index.json"
        labels = [_make_label("p1")]
        summary, docs = export_search_metadata(labels, output)
        assert summary["written"] is True
        assert output.exists()

    def test_summary_statistics(self, tmp_path):
        """Summary includes correct statistics."""
        labels = [
            _make_label("p1", estimated_decade=1940, people_count=3,
                         controlled_tags=["Studio"], source_method="api"),
            _make_label("p2", estimated_decade=1940, people_count=2,
                         controlled_tags=[], source_method="api"),
            _make_label("p3", estimated_decade=1950, people_count=None,
                         controlled_tags=["Outdoor"], source_method="web_manual"),
        ]
        output = tmp_path / "index.json"
        summary, docs = export_search_metadata(labels, output)

        assert summary["total_documents"] == 3
        assert summary["with_searchable_text"] == 3
        assert summary["with_controlled_tags"] == 3  # _make_label defaults [] to ["Studio", "Formal_Event"]
        assert summary["with_decade"] == 3
        assert summary["with_people_count"] == 2  # p3 has None

    def test_decade_distribution(self, tmp_path):
        """Summary includes decade distribution."""
        labels = [
            _make_label("p1", estimated_decade=1940),
            _make_label("p2", estimated_decade=1940),
            _make_label("p3", estimated_decade=1950),
        ]
        output = tmp_path / "index.json"
        summary, docs = export_search_metadata(labels, output)
        assert summary["decade_distribution"] == {1940: 2, 1950: 1}

    def test_source_method_distribution(self, tmp_path):
        """Summary includes source method distribution."""
        labels = [
            _make_label("p1", source_method="api"),
            _make_label("p2", source_method="api"),
            _make_label("p3", source_method="web_manual"),
        ]
        output = tmp_path / "index.json"
        summary, docs = export_search_metadata(labels, output)
        assert summary["source_method_distribution"] == {"api": 2, "web_manual": 1}

    def test_returns_documents_list(self, tmp_path):
        """Returns the documents list for inspection."""
        labels = [_make_label("p1"), _make_label("p2")]
        output = tmp_path / "index.json"
        summary, docs = export_search_metadata(labels, output)
        assert len(docs) == 2
        assert docs[0]["photo_id"] == "p1"
        assert docs[1]["photo_id"] == "p2"

    def test_output_has_trailing_newline(self, tmp_path):
        """Output file ends with a newline."""
        labels = [_make_label("p1")]
        output = tmp_path / "index.json"
        export_search_metadata(labels, output)
        content = output.read_text()
        assert content.endswith("\n")
