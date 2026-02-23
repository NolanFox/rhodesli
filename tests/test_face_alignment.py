"""Tests for face alignment coordinate bridging — PRD-015 core module."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.face_alignment import (
    AlignedFaceDescription,
    AlignmentResult,
    FaceDetection,
    build_alignment_prompt,
    cache_alignment,
    format_faces_for_gemini,
    get_cached_alignment,
    load_alignments_from_file,
    parse_alignment_response,
    save_alignment_to_file,
)


# --- Test fixtures ---

def _make_faces(n=3, start_x=100, spacing=200):
    """Create N test face detections at regular x intervals."""
    return [
        FaceDetection(
            face_id=f"face_{i}",
            bbox=[start_x + i * spacing, 50, start_x + i * spacing + 150, 300],
            face_index=i,
            det_score=0.95,
        )
        for i in range(n)
    ]


def _make_gemini_response(n=3, extra_faces=0, skip_indices=None):
    """Create a mock Gemini response for N faces."""
    skip_indices = skip_indices or []
    faces = []
    for i in range(n):
        if i in skip_indices:
            continue
        faces.append({
            "face_index": i,
            "estimated_age": 30 + i * 10,
            "gender": "male" if i % 2 == 0 else "female",
            "description": f"Person {i} description",
            "clothing": f"Outfit {i}",
            "position": f"Position {i}",
            "identifying_features": f"Feature {i}",
            "is_subject": True,
        })

    extra = []
    for j in range(extra_faces):
        extra.append({
            "description": f"Extra face {j}",
            "approximate_location": f"edge {j}",
        })

    return {
        "faces": faces,
        "additional_faces_not_in_coordinates": extra,
        "scene_context": "Test photo scene",
    }


# --- format_faces_for_gemini ---

class TestFormatFacesForGemini:
    def test_basic_formatting(self):
        """Formats face detections as coordinate block."""
        faces = _make_faces(3)
        result = format_faces_for_gemini(faces)
        assert "3 face(s)" in result
        assert "Face 0:" in result
        assert "Face 1:" in result
        assert "Face 2:" in result
        assert "[100, 50, 250, 300]" in result

    def test_empty_list(self):
        """Empty face list returns empty string."""
        assert format_faces_for_gemini([]) == ""

    def test_single_face(self):
        """Single face formats correctly."""
        faces = _make_faces(1)
        result = format_faces_for_gemini(faces)
        assert "1 face(s)" in result
        assert "Face 0:" in result

    def test_sorted_by_x_coordinate(self):
        """Faces are sorted left-to-right by x1."""
        faces = [
            FaceDetection(face_id="right", bbox=[500, 50, 650, 300], face_index=0),
            FaceDetection(face_id="left", bbox=[100, 50, 250, 300], face_index=1),
        ]
        result = format_faces_for_gemini(faces)
        # Left face should be Face 0, right face should be Face 1
        lines = result.split("\n")
        face_0_line = [l for l in lines if "Face 0:" in l][0]
        face_1_line = [l for l in lines if "Face 1:" in l][0]
        assert "100" in face_0_line
        assert "500" in face_1_line

    def test_many_faces(self):
        """Handles photos with many faces (12+)."""
        faces = _make_faces(12, spacing=80)
        result = format_faces_for_gemini(faces)
        assert "12 face(s)" in result
        assert "Face 11:" in result


# --- build_alignment_prompt ---

class TestBuildAlignmentPrompt:
    def test_includes_coordinates(self):
        """Prompt includes face coordinate block."""
        faces = _make_faces(2)
        prompt = build_alignment_prompt(faces)
        assert "bounding box coordinates" in prompt
        assert "Face 0:" in prompt
        assert "Face 1:" in prompt

    def test_includes_analysis_instructions(self):
        """Prompt requests per-face analysis."""
        faces = _make_faces(1)
        prompt = build_alignment_prompt(faces)
        assert "estimated_age" in prompt
        assert "gender" in prompt
        assert "clothing" in prompt
        assert "is_subject" in prompt

    def test_includes_json_schema(self):
        """Prompt includes JSON response schema."""
        faces = _make_faces(1)
        prompt = build_alignment_prompt(faces)
        assert "Response Format (JSON only)" in prompt
        assert '"faces"' in prompt

    def test_additional_context_included(self):
        """Additional context is appended to prompt."""
        faces = _make_faces(1)
        prompt = build_alignment_prompt(faces, additional_context="GEDCOM data here")
        assert "GEDCOM data here" in prompt
        assert "Additional Context" in prompt

    def test_no_additional_context(self):
        """Prompt works without additional context."""
        faces = _make_faces(1)
        prompt = build_alignment_prompt(faces)
        assert "Additional Context" not in prompt

    def test_requests_gemini_only_faces(self):
        """Prompt asks for faces Gemini sees but InsightFace didn't detect."""
        faces = _make_faces(1)
        prompt = build_alignment_prompt(faces)
        assert "additional faces" in prompt.lower() or "NOT in my" in prompt


# --- parse_alignment_response ---

class TestParseAlignmentResponse:
    def test_perfect_match(self):
        """All faces described correctly."""
        faces = _make_faces(3)
        response = _make_gemini_response(3)
        result = parse_alignment_response(response, faces, "photo_123", "gemini-pro")

        assert result.photo_id == "photo_123"
        assert result.faces_detected == 3
        assert result.faces_described == 3
        assert len(result.aligned_faces) == 3
        assert len(result.unmatched_faces) == 0
        assert result.model_used == "gemini-pro"

    def test_partial_match(self):
        """Gemini skips some faces."""
        faces = _make_faces(4)
        response = _make_gemini_response(4, skip_indices=[2, 3])
        result = parse_alignment_response(response, faces, "photo_456")

        assert result.faces_detected == 4
        assert len(result.aligned_faces) == 2
        assert len(result.unmatched_faces) == 2

    def test_extra_faces(self):
        """Gemini sees faces InsightFace missed."""
        faces = _make_faces(2)
        response = _make_gemini_response(2, extra_faces=2)
        result = parse_alignment_response(response, faces, "photo_789")

        assert result.faces_detected == 2
        assert len(result.aligned_faces) == 2
        assert len(result.gemini_only_faces) == 2

    def test_face_id_mapping(self):
        """Aligned faces retain correct face_ids from InsightFace."""
        faces = _make_faces(2)
        response = _make_gemini_response(2)
        result = parse_alignment_response(response, faces, "test")

        face_ids = {f.face_id for f in result.aligned_faces}
        assert "face_0" in face_ids
        assert "face_1" in face_ids

    def test_age_assignment(self):
        """Ages are correctly assigned per face."""
        faces = _make_faces(2)
        response = _make_gemini_response(2)
        result = parse_alignment_response(response, faces, "test")

        ages = {f.face_id: f.estimated_age for f in result.aligned_faces}
        assert ages["face_0"] == 30
        assert ages["face_1"] == 40

    def test_non_subject_faces(self):
        """Non-subject faces are correctly flagged."""
        faces = _make_faces(3)
        response = _make_gemini_response(3)
        # Mark face 2 as non-subject
        response["faces"][2]["is_subject"] = False
        response["faces"][2]["not_subject_reason"] = "Newspaper face"

        result = parse_alignment_response(response, faces, "test")
        subjects = result.subject_faces()
        assert len(subjects) == 2

    def test_empty_response(self):
        """Handles empty Gemini response gracefully."""
        faces = _make_faces(3)
        response = {"faces": [], "scene_context": ""}
        result = parse_alignment_response(response, faces, "test")

        assert result.faces_detected == 3
        assert result.faces_described == 0
        assert len(result.unmatched_faces) == 3

    def test_scene_context_captured(self):
        """Scene context is captured from response."""
        faces = _make_faces(1)
        response = _make_gemini_response(1)
        result = parse_alignment_response(response, faces, "test")
        assert result.scene_context == "Test photo scene"

    def test_identity_name_preserved(self):
        """Pre-existing identity name from InsightFace is preserved."""
        faces = [
            FaceDetection(
                face_id="face_0", bbox=[100, 50, 250, 300],
                face_index=0, identity_name="Leon Capeluto"
            )
        ]
        response = _make_gemini_response(1)
        result = parse_alignment_response(response, faces, "test")
        assert result.aligned_faces[0].identity_name == "Leon Capeluto"


# --- AlignmentResult ---

class TestAlignmentResult:
    def test_to_dict(self):
        """Serializes to JSON-safe dict."""
        result = AlignmentResult(
            photo_id="test_123",
            faces_detected=3,
            faces_described=3,
            model_used="gemini-pro",
        )
        d = result.to_dict()
        assert d["photo_id"] == "test_123"
        assert isinstance(d["aligned_faces"], list)
        # Verify it's JSON-serializable
        json.dumps(d)

    def test_subject_faces_filter(self):
        """subject_faces() filters non-subjects."""
        result = AlignmentResult(
            photo_id="test",
            aligned_faces=[
                AlignedFaceDescription(
                    face_id="a", bbox=[0, 0, 10, 10], face_index=0, is_subject=True
                ),
                AlignedFaceDescription(
                    face_id="b", bbox=[20, 0, 30, 10], face_index=1, is_subject=False
                ),
                AlignedFaceDescription(
                    face_id="c", bbox=[40, 0, 50, 10], face_index=2, is_subject=True
                ),
            ],
        )
        subjects = result.subject_faces()
        assert len(subjects) == 2
        assert {s.face_id for s in subjects} == {"a", "c"}


# --- Storage ---

class TestStorage:
    def test_cache_and_retrieve(self):
        """Cache stores and retrieves alignment results."""
        from app.face_alignment import _ALIGNMENT_CACHE
        _ALIGNMENT_CACHE.clear()

        result = AlignmentResult(photo_id="photo_abc", faces_detected=2)
        cache_alignment(result)

        cached = get_cached_alignment("photo_abc")
        assert cached is not None
        assert cached.photo_id == "photo_abc"

        _ALIGNMENT_CACHE.clear()

    def test_cache_miss(self):
        """Cache returns None for unknown photo."""
        from app.face_alignment import _ALIGNMENT_CACHE
        _ALIGNMENT_CACHE.clear()
        assert get_cached_alignment("nonexistent") is None
        _ALIGNMENT_CACHE.clear()

    def test_save_to_file(self, tmp_path):
        """Saves alignment to JSON file."""
        result = AlignmentResult(
            photo_id="photo_xyz",
            faces_detected=3,
            model_used="gemini-pro",
        )
        path = save_alignment_to_file(result, output_dir=tmp_path)

        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert "photo_xyz" in data
        assert data["photo_xyz"]["faces_detected"] == 3

    def test_save_upserts(self, tmp_path):
        """Saving twice updates existing entry."""
        r1 = AlignmentResult(photo_id="p1", faces_detected=2)
        r2 = AlignmentResult(photo_id="p2", faces_detected=5)
        save_alignment_to_file(r1, output_dir=tmp_path)
        save_alignment_to_file(r2, output_dir=tmp_path)

        data = load_alignments_from_file(tmp_path)
        assert "p1" in data
        assert "p2" in data

    def test_load_missing_file(self, tmp_path):
        """Loading from missing file returns empty dict."""
        data = load_alignments_from_file(tmp_path)
        assert data == {}


# --- run_face_alignment (async, mocked) ---

class TestRunFaceAlignment:
    def test_full_pipeline(self):
        """Full pipeline with mocked Gemini call."""
        from app.face_alignment import run_face_alignment

        faces = _make_faces(2)
        mock_response = _make_gemini_response(2)

        # Create simple test image bytes
        import io
        from PIL import Image
        img = Image.new("RGB", (800, 600))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        with patch("app.face_alignment.call_gemini_alignment", new_callable=AsyncMock) as mock:
            mock.return_value = (mock_response, 100, 50)
            result = asyncio.get_event_loop().run_until_complete(
                run_face_alignment("photo_test", image_bytes, faces, api_key="test-key")
            )

        assert result.photo_id == "photo_test"
        assert result.faces_detected == 2
        assert len(result.aligned_faces) == 2
        assert result.error is None

    def test_no_faces(self):
        """Returns error result when no faces provided."""
        from app.face_alignment import run_face_alignment

        result = asyncio.get_event_loop().run_until_complete(
            run_face_alignment("photo_test", b"fake", [])
        )
        assert result.error == "No faces to align"
        assert result.faces_detected == 0

    def test_api_failure(self):
        """Returns error result when Gemini fails."""
        from app.face_alignment import run_face_alignment

        faces = _make_faces(2)
        import io
        from PIL import Image
        img = Image.new("RGB", (800, 600))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        image_bytes = buf.getvalue()

        with patch("app.face_alignment.call_gemini_alignment", new_callable=AsyncMock) as mock:
            mock.return_value = (None, 0, 0)
            result = asyncio.get_event_loop().run_until_complete(
                run_face_alignment("photo_fail", image_bytes, faces, api_key="test-key")
            )

        assert result.error == "Gemini API call failed"
        assert result.faces_detected == 2
