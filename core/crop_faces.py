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
    raise NotImplementedError("TDD: implement add_padding")


def sanitize_filename(original_name: str) -> str:
    """
    Convert filename to lowercase with underscores, removing extension.

    Args:
        original_name: Original filename (e.g., "Brass_Rail_Restaurant.jpg")

    Returns:
        Sanitized name (e.g., "brass_rail_restaurant")
    """
    raise NotImplementedError("TDD: implement sanitize_filename")


def main():
    """Main function to crop faces from embeddings."""
    raise NotImplementedError("TDD: implement main")


if __name__ == "__main__":
    main()
