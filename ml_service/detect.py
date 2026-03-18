"""Face detection and embedding extraction endpoint.

Replicates the detection logic from core/ingest_inbox.py as a standalone
service endpoint. Uses InsightFace buffalo_l model with detection+recognition
modules only (matching AD-119).
"""

import io
import logging
import time

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ml_service.main import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["detection"])

# Lazy-loaded model singleton
_face_analyzer = None


def get_face_analyzer():
    """Get or create the cached InsightFace FaceAnalysis instance.

    The buffalo_l model (~300MB) takes 30-60s to load. This singleton
    ensures it loads once on first request and is reused for all
    subsequent face detection calls.

    Only loads detection + recognition modules (AD-119). Landmarks and
    gender/age are not needed.
    """
    global _face_analyzer
    if _face_analyzer is None:
        from insightface.app import FaceAnalysis

        _face_analyzer = FaceAnalysis(
            name="buffalo_l",
            allowed_modules=["detection", "recognition"],
            providers=["CPUExecutionProvider"],
        )
        _face_analyzer.prepare(ctx_id=-1, det_size=(640, 640))
        logger.info("InsightFace buffalo_l model loaded (detection+recognition only)")
    return _face_analyzer


def is_model_loaded() -> bool:
    """Check if the face analyzer model has been loaded."""
    return _face_analyzer is not None


@router.post("/detect-and-embed")
async def detect_and_embed(
    file: UploadFile = File(...),
    _token: str = Depends(verify_token),
):
    """Detect faces in an uploaded image and return embeddings.

    Accepts a single image as multipart upload. Returns bounding boxes,
    detection scores, quality metrics, 512-dim PFE embeddings, and
    landmarks for each detected face.
    """
    import cv2
    from PIL import Image

    start_ms = time.time() * 1000

    # Validate content type
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Expected image file, got {content_type}",
        )

    # Read and decode image
    try:
        contents = await file.read()
        pil_image = Image.open(io.BytesIO(contents))
        pil_image.verify()
        # Re-open after verify (verify exhausts the stream)
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
        img_array = np.array(pil_image)
        # Convert RGB to BGR for OpenCV/InsightFace
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not decode image: {e}",
        )

    image_height, image_width = img_bgr.shape[:2]

    # Run face detection
    analyzer = get_face_analyzer()
    faces = analyzer.get(img_bgr)

    # Close-crop fallback (AD-204): pad small/tight crops and retry
    if not faces:
        pad_ratio = 0.4
        pad_h = int(image_height * pad_ratio)
        pad_w = int(image_width * pad_ratio)
        padded = cv2.copyMakeBorder(
            img_bgr,
            pad_h,
            pad_h,
            pad_w,
            pad_w,
            cv2.BORDER_CONSTANT,
            value=(128, 128, 128),
        )
        faces = analyzer.get(padded)
        if faces:
            logger.info(f"Close-crop fallback: padded {pad_ratio:.0%}, found {len(faces)} face(s)")
            for face in faces:
                face.bbox[0] -= pad_w
                face.bbox[1] -= pad_h
                face.bbox[2] -= pad_w
                face.bbox[3] -= pad_h

    # Build response
    face_results = []
    for face in faces:
        embedding = face.normed_embedding
        raw_norm = float(np.linalg.norm(face.embedding))
        det_score = float(face.det_score)
        bbox = face.bbox.tolist()

        face_entry = {
            "bbox": bbox,
            "det_score": det_score,
            "quality": raw_norm,
            "embedding": embedding.tolist(),
        }

        # Include landmarks if available
        if hasattr(face, "landmark_2d_106") and face.landmark_2d_106 is not None:
            face_entry["landmarks"] = face.landmark_2d_106.tolist()
        elif hasattr(face, "kps") and face.kps is not None:
            face_entry["landmarks"] = face.kps.tolist()

        face_results.append(face_entry)

    elapsed_ms = time.time() * 1000 - start_ms

    # Get InsightFace version for model_info
    try:
        import insightface

        insightface_version = insightface.__version__
    except (ImportError, AttributeError):
        insightface_version = "unknown"

    return {
        "faces": face_results,
        "image_size": {"width": image_width, "height": image_height},
        "processing_time_ms": round(elapsed_ms, 1),
        "model_info": {
            "name": "buffalo_l",
            "modules": ["detection", "recognition"],
            "embedding_dim": 512,
            "insightface_version": insightface_version,
        },
    }
