"""
PRD-015: Gemini-InsightFace Face Alignment via Coordinate Bridging

Approach B (chosen): Feed InsightFace bounding box coordinates to Gemini
as part of the analysis prompt. Gemini describes each face using the IDs
we provide, guaranteeing 1:1 correspondence.

AD-144: Why Approach B over A
- Guaranteed 1:1 mapping (no IoU matching needed)
- Robust to face count mismatches
- No post-hoc coordinate matching thresholds

Novel: No known prior work combining VLM spatial understanding with
face detection embeddings for heritage photo analysis.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FaceDetection:
    """InsightFace detection result for one face in a photo."""
    face_id: str
    bbox: list[int]        # [x1, y1, x2, y2] in pixels
    face_index: int = 0
    det_score: float = 0.0
    quality: float = 0.0
    identity_name: Optional[str] = None


@dataclass
class AlignedFaceDescription:
    """Gemini's description aligned to a specific InsightFace detection."""
    face_id: str
    bbox: list[int]
    face_index: int
    gemini_description: str = ""
    estimated_age: Optional[int] = None
    gender: Optional[str] = None
    clothing: Optional[str] = None
    position_in_photo: Optional[str] = None
    identifying_features: Optional[str] = None
    identity_name: Optional[str] = None
    is_subject: bool = True
    not_subject_reason: Optional[str] = None
    matched: bool = True


@dataclass
class AlignmentResult:
    """Full alignment result for one photo."""
    photo_id: str
    faces_detected: int = 0
    faces_described: int = 0
    aligned_faces: list[AlignedFaceDescription] = field(default_factory=list)
    gemini_only_faces: list[dict] = field(default_factory=list)
    unmatched_faces: list[str] = field(default_factory=list)
    scene_context: str = ""
    model_used: str = ""
    cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict."""
        return asdict(self)

    def subject_faces(self) -> list[AlignedFaceDescription]:
        """Return only faces marked as real subjects."""
        return [f for f in self.aligned_faces if f.is_subject]


# --- Prompt formatting ---

def format_faces_for_gemini(faces: list[FaceDetection]) -> str:
    """
    Format InsightFace detections as a coordinate block for Gemini.

    Output example:
    "I have detected 4 faces in this photo at these bounding box
    coordinates (in pixels, format [x1, y1, x2, y2]):
    Face 0: [120, 80, 280, 310]
    Face 1: [350, 60, 490, 290]
    ..."
    """
    if not faces:
        return ""

    lines = [
        f"I have detected {len(faces)} face(s) in this photo at these "
        "bounding box coordinates (in pixels, format [x1, y1, x2, y2]):"
    ]

    # Sort by x1 coordinate for consistent left-to-right ordering
    sorted_faces = sorted(faces, key=lambda f: f.bbox[0] if len(f.bbox) >= 1 else 0)

    for i, face in enumerate(sorted_faces):
        bbox_str = str(face.bbox)
        lines.append(f"  Face {i}: {bbox_str}")

    return "\n".join(lines)


def build_alignment_prompt(faces: list[FaceDetection],
                           additional_context: str = "") -> str:
    """
    Build the full Gemini prompt for face alignment.

    Uses the unified extraction architecture (AD-143) with face_analysis type.
    Includes coordinate block, per-face analysis request, and JSON output schema.
    """
    coords_block = format_faces_for_gemini(faces)

    prompt_parts = [
        "You are a forensic photo analyst specializing in heritage photographs.",
        "",
        "## Face Coordinate Analysis",
        coords_block,
        "",
        "For EACH face listed above, provide:",
        "1. estimated_age: integer age estimate",
        "2. gender: 'male' or 'female'",
        "3. description: brief physical description (hair, facial features)",
        "4. clothing: clothing/attire description visible in the photo",
        "5. position: where this person is in the photo (e.g., 'center, standing')",
        "6. identifying_features: distinctive features useful for identification",
        "7. is_subject: true if this is a real person in the scene, false if it's a",
        "   face in a background poster, newspaper, reflection, or too small/blurry",
        "",
        "If a face bounding box doesn't correspond to a clearly visible person,",
        "set is_subject to false and explain in not_subject_reason.",
        "",
        "Also report any additional faces you can see that were NOT in my",
        "detected face list (Gemini-only faces).",
    ]

    if additional_context:
        prompt_parts.extend(["", "## Additional Context", additional_context])

    prompt_parts.extend([
        "",
        "## Response Format (JSON only)",
        """{
  "faces": [
    {
      "face_index": 0,
      "estimated_age": 45,
      "gender": "male",
      "description": "Middle-aged man with dark mustache",
      "clothing": "Dark three-piece suit with white shirt",
      "position": "Center of group, standing",
      "identifying_features": "Prominent mustache, slightly receding hairline",
      "is_subject": true
    }
  ],
  "additional_faces_not_in_coordinates": [
    {
      "description": "Partially visible face at far right edge",
      "approximate_location": "right edge, partially cropped"
    }
  ],
  "scene_context": "Formal group portrait, likely studio setting"
}""",
    ])

    return "\n".join(prompt_parts)


# --- Response parsing ---

def parse_alignment_response(
    response_data: dict,
    faces: list[FaceDetection],
    photo_id: str,
    model_used: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> AlignmentResult:
    """
    Parse Gemini's structured response and align to InsightFace faces.

    Handles:
    - Perfect match (Gemini described all faces)
    - Partial match (Gemini skipped some small/blurry faces)
    - Extra faces (Gemini saw faces InsightFace missed)
    """
    result = AlignmentResult(
        photo_id=photo_id,
        faces_detected=len(faces),
        model_used=model_used,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    # Sort faces by x1 for consistent indexing (matches prompt order)
    sorted_faces = sorted(faces, key=lambda f: f.bbox[0] if len(f.bbox) >= 1 else 0)

    gemini_faces = response_data.get("faces", [])
    result.faces_described = len(gemini_faces)

    # Build index map: face_index -> FaceDetection
    face_by_index = {i: f for i, f in enumerate(sorted_faces)}

    described_indices = set()

    for gf in gemini_faces:
        face_index = gf.get("face_index")
        if face_index is None:
            continue

        described_indices.add(face_index)

        detection = face_by_index.get(face_index)
        if detection is None:
            # Gemini referenced a face index we don't have
            continue

        is_subject = gf.get("is_subject", True)

        aligned = AlignedFaceDescription(
            face_id=detection.face_id,
            bbox=detection.bbox,
            face_index=face_index,
            gemini_description=gf.get("description", ""),
            estimated_age=gf.get("estimated_age"),
            gender=gf.get("gender"),
            clothing=gf.get("clothing"),
            position_in_photo=gf.get("position"),
            identifying_features=gf.get("identifying_features"),
            identity_name=detection.identity_name,
            is_subject=is_subject,
            not_subject_reason=gf.get("not_subject_reason"),
            matched=True,
        )
        result.aligned_faces.append(aligned)

    # Track unmatched faces (InsightFace detected but Gemini didn't describe)
    for i, face in enumerate(sorted_faces):
        if i not in described_indices:
            result.unmatched_faces.append(face.face_id)

    # Gemini-only faces
    result.gemini_only_faces = response_data.get(
        "additional_faces_not_in_coordinates", []
    )

    result.scene_context = response_data.get("scene_context", "")

    return result


# --- Gemini API call ---

async def call_gemini_alignment(
    image_bytes: bytes,
    prompt: str,
    model: str | None = None,
    api_key: str | None = None,
    photo_id: str | None = None,
    call_type: str = "alignment",
    batch_id: str | None = None,
) -> tuple[dict | None, int, int]:
    """
    Call Gemini API with image and alignment prompt.

    Returns: (parsed_response_dict, input_tokens, output_tokens)
    Returns (None, 0, 0) on failure.
    """
    import os
    import time as _time

    from rhodesli_ml.gemini_config import GEMINI_MODEL

    if model is None:
        model = GEMINI_MODEL

    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("No GEMINI_API_KEY available")
        return None, 0, 0

    start_ms = int(_time.time() * 1000)
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options={"timeout": 60_000},
        )

        response = client.models.generate_content(
            model=model,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        text = response.text
        if not text:
            _log_call(photo_id, model, call_type, 0, 0, 0, start_ms, "error",
                       error_message="Empty response", batch_id=batch_id)
            return None, 0, 0

        parsed = json.loads(text)

        # Extract token counts from usage metadata
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
            output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0

        # Estimate cost
        from rhodesli_ml.gemini_config import get_model_pricing
        pricing = get_model_pricing(model)
        cost = (input_tokens * pricing["input"] / 1_000_000) + (output_tokens * pricing["output"] / 1_000_000)

        _log_call(photo_id, model, call_type, input_tokens, output_tokens, cost,
                   start_ms, "success", batch_id=batch_id)

        return parsed, input_tokens, output_tokens

    except Exception as e:
        error_msg = str(e)
        status = "error"
        rate_limit_type = None
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            status = "rate_limited"
            if "per day" in error_msg.lower() or "rpd" in error_msg.lower():
                rate_limit_type = "rpd"
            elif "per minute" in error_msg.lower() or "rpm" in error_msg.lower():
                rate_limit_type = "rpm"
            else:
                rate_limit_type = "unknown"

        _log_call(photo_id, model, call_type, 0, 0, 0, start_ms, status,
                   error_message=error_msg, rate_limit_type=rate_limit_type, batch_id=batch_id)
        logger.error(f"Gemini face alignment call failed: {e}")
        return None, 0, 0


def _log_call(photo_id, model, call_type, prompt_tokens, completion_tokens,
              cost_usd, start_ms, status, error_message=None,
              rate_limit_type=None, batch_id=None):
    """Best-effort log of Gemini API call to Supabase."""
    import time as _time
    if not photo_id:
        return
    try:
        from app.supabase_data import log_gemini_call
        latency_ms = int(_time.time() * 1000) - start_ms
        log_gemini_call(
            photo_id=photo_id,
            model_used=model,
            call_type=call_type,
            prompt_tokens=prompt_tokens or None,
            completion_tokens=completion_tokens or None,
            cost_usd=cost_usd or None,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message,
            rate_limit_type=rate_limit_type,
            batch_id=batch_id,
        )
    except Exception as e:
        logger.debug(f"Gemini call logging failed (non-blocking): {e}")


# --- Full pipeline ---

async def run_face_alignment(
    photo_id: str,
    image_bytes: bytes,
    faces: list[FaceDetection],
    model: str | None = None,
    additional_context: str = "",
    api_key: str | None = None,
    call_type: str = "alignment",
    batch_id: str | None = None,
) -> AlignmentResult:
    """
    Full face alignment pipeline for one photo:
    1. Normalize EXIF orientation
    2. Format faces for Gemini
    3. Build prompt (with optional additional context)
    4. Call Gemini API
    5. Parse response
    6. Return aligned result
    """
    from app.exif_handler import normalize_orientation

    if not faces:
        return AlignmentResult(
            photo_id=photo_id,
            faces_detected=0,
            error="No faces to align",
        )

    # Step 1: Normalize EXIF orientation
    try:
        normalized_bytes = normalize_orientation(image_bytes)
    except Exception as e:
        logger.warning(f"EXIF normalization failed for {photo_id}: {e}")
        normalized_bytes = image_bytes

    # Step 2-3: Build prompt with coordinates
    prompt = build_alignment_prompt(faces, additional_context)

    # Step 4: Call Gemini
    response_data, input_tokens, output_tokens = await call_gemini_alignment(
        normalized_bytes, prompt, model=model, api_key=api_key,
        photo_id=photo_id, call_type=call_type, batch_id=batch_id,
    )

    if response_data is None:
        return AlignmentResult(
            photo_id=photo_id,
            faces_detected=len(faces),
            model_used=model,
            error="Gemini API call failed",
        )

    # Step 5: Parse and align
    result = parse_alignment_response(
        response_data, faces, photo_id,
        model_used=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    return result


# --- Storage (Supabase-first with JSON fallback, AD-152) ---

_ALIGNMENT_CACHE: dict[str, AlignmentResult] = {}


def get_cached_alignment(photo_id: str) -> AlignmentResult | None:
    """Get cached face alignment result for a photo."""
    return _ALIGNMENT_CACHE.get(photo_id)


def cache_alignment(result: AlignmentResult) -> None:
    """Cache a face alignment result."""
    _ALIGNMENT_CACHE[result.photo_id] = result


def save_alignment(result: AlignmentResult, output_dir: str | Path = "data") -> bool:
    """Save alignment result. Tries Supabase first, then JSON fallback.

    Returns True if saved to Supabase, False if JSON-only.
    """
    from app.supabase_data import save_face_alignment_to_supabase

    alignment_dict = result.to_dict()
    saved_to_supabase = save_face_alignment_to_supabase(
        photo_id=result.photo_id,
        alignment_data=alignment_dict,
        model_used=result.model_used,
        cost=result.cost,
        tokens=result.input_tokens + result.output_tokens if result.input_tokens and result.output_tokens else None,
    )

    # Always save to JSON as cache
    save_alignment_to_file(result, output_dir)

    return saved_to_supabase


def save_alignment_to_file(result: AlignmentResult, output_dir: str | Path = "data") -> Path:
    """Save alignment result to JSON file (cache layer)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    alignments_file = output_dir / "face_alignments.json"

    # Load existing data
    existing = {}
    if alignments_file.exists():
        try:
            with open(alignments_file) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    # Upsert this photo's alignment
    existing[result.photo_id] = result.to_dict()

    # Atomic write
    tmp_path = alignments_file.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(existing, f, indent=2, default=str)
    tmp_path.rename(alignments_file)

    return alignments_file


def load_alignments(data_dir: str | Path = "data") -> dict[str, dict]:
    """Load all alignment results. Tries Supabase first, falls back to JSON.

    Returns dict of {photo_id: alignment_data_dict}.
    """
    from app.supabase_data import load_all_face_alignments_from_supabase

    supabase_data = load_all_face_alignments_from_supabase()
    if supabase_data is not None and len(supabase_data) > 0:
        return supabase_data

    # Fallback to JSON
    return load_alignments_from_file(data_dir)


def load_alignments_from_file(input_dir: str | Path = "data") -> dict[str, dict]:
    """Load all alignment results from JSON file (cache/fallback)."""
    alignments_file = Path(input_dir) / "face_alignments.json"
    if not alignments_file.exists():
        return {}
    try:
        with open(alignments_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
