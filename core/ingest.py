"""
Rhodesli Ingestion Pipeline

Extracts face embeddings from photos using InsightFace.
Stores embedding, quality score (embedding norm), and bounding box.

Note: Standard ArcFace models normalize embeddings, so the norm is not a
true quality indicator (unlike MagFace/AdaFace). We store it anyway for
potential future use with quality-aware models.
"""

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from insightface.app import FaceAnalysis


def get_image_files(input_path: Path) -> list[Path]:
    """Get all supported image files from input path."""
    extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in extensions else []
    return [f for f in input_path.rglob("*") if f.suffix.lower() in extensions]


def process_image(app: FaceAnalysis, image_path: Path) -> list[dict]:
    """Extract faces from a single image."""
    img = cv2.imread(str(image_path))
    if img is None:
        print(f"Warning: Could not read {image_path}", file=sys.stderr)
        return []

    faces = app.get(img)
    results = []

    for face in faces:
        embedding = face.normed_embedding  # 512-D unit vector for matching
        raw_norm = float(np.linalg.norm(face.embedding))  # Raw embedding norm
        det_score = float(face.det_score)  # Detection confidence
        bbox = face.bbox.tolist()  # [x1, y1, x2, y2]

        results.append({
            "filename": image_path.name,
            "filepath": str(image_path),
            "embedding": embedding,
            "quality": raw_norm,  # Note: Not a true quality metric for ArcFace
            "det_score": det_score,
            "bbox": bbox,
        })

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Extract face embeddings from photos"
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Input directory or image file",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Output .npy file path",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="buffalo_l",
        help="InsightFace model name (default: buffalo_l)",
    )
    parser.add_argument(
        "--det-size",
        type=int,
        default=640,
        help="Detection size (default: 640)",
    )
    args = parser.parse_args()

    # Validate input
    if not args.input.exists():
        print(f"Error: Input path does not exist: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Get image files
    image_files = get_image_files(args.input)
    if not image_files:
        print(f"Error: No image files found in {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(image_files)} image(s)")

    # Initialize InsightFace
    print(f"Loading InsightFace model: {args.model}")
    app = FaceAnalysis(name=args.model, providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(args.det_size, args.det_size))

    # Process images
    all_faces = []
    for i, image_path in enumerate(image_files, 1):
        print(f"[{i}/{len(image_files)}] Processing: {image_path.name}")
        faces = process_image(app, image_path)
        all_faces.extend(faces)
        if faces:
            print(f"  Found {len(faces)} face(s)")

    print(f"\nTotal faces extracted: {len(all_faces)}")

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Save results
    np.save(args.output, all_faces, allow_pickle=True)
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()
