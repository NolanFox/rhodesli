"""
Face cropping script for Leon Capeluto Gallery.
Extracts face crops from source images using bounding boxes from embeddings.
"""

import re
from pathlib import Path


def add_padding(bbox: list, image_shape: tuple, padding: float = 0.10) -> tuple:
    """
    Add percentage-based padding to bounding box, clamped to image bounds.

    Args:
        bbox: [x1, y1, x2, y2] bounding box coordinates
        image_shape: (height, width, channels) from cv2.imread
        padding: Padding percentage (0.10 = 10%)

    Returns:
        (x1, y1, x2, y2) padded and clamped coordinates as integers
    """
    x1, y1, x2, y2 = bbox
    height, width = image_shape[:2]

    box_width = x2 - x1
    box_height = y2 - y1

    pad_x = box_width * padding
    pad_y = box_height * padding

    x1_padded = max(0, int(x1 - pad_x))
    y1_padded = max(0, int(y1 - pad_y))
    x2_padded = min(width, int(x2 + pad_x))
    y2_padded = min(height, int(y2 + pad_y))

    return x1_padded, y1_padded, x2_padded, y2_padded


def sanitize_filename(original_name: str) -> str:
    """
    Convert filename to lowercase with underscores, removing extension.

    Args:
        original_name: Original filename (e.g., "Brass_Rail_Restaurant.jpg")

    Returns:
        Sanitized name (e.g., "brass_rail_restaurant")
    """
    stem = Path(original_name).stem
    sanitized = stem.lower()
    sanitized = re.sub(r'[^a-z0-9]+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized


def main():
    """Main function to crop faces from embeddings."""
    import cv2
    import numpy as np

    project_root = Path(__file__).resolve().parent.parent
    embeddings_path = project_root / "data" / "embeddings.npy"
    output_dir = project_root / "app" / "static" / "crops"

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading embeddings from {embeddings_path}")
    embeddings = np.load(embeddings_path, allow_pickle=True)
    print(f"Found {len(embeddings)} face entries")

    filename_counts = {}

    for entry in embeddings:
        filepath = project_root / entry['filepath']
        bbox = entry['bbox']
        quality = entry['quality']
        original_filename = entry['filename']

        image = cv2.imread(str(filepath))
        if image is None:
            print(f"Warning: Could not read {filepath}")
            continue

        x1, y1, x2, y2 = add_padding(bbox, image.shape)
        face_crop = image[y1:y2, x1:x2]

        base_name = sanitize_filename(original_filename)

        if base_name not in filename_counts:
            filename_counts[base_name] = 0
        idx = filename_counts[base_name]
        filename_counts[base_name] += 1

        output_filename = f"{base_name}_{quality:.2f}_{idx}.jpg"
        output_path = output_dir / output_filename

        cv2.imwrite(str(output_path), face_crop)
        print(f"Saved: {output_filename}")

    print(f"\nDone! Cropped {len(embeddings)} faces to {output_dir}")


if __name__ == "__main__":
    main()
