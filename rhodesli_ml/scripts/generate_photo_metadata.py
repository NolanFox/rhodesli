"""Compatibility alias for generate_date_labels.py.

This script now extracts both date labels AND rich photo metadata (AD-048)
in a single Gemini Vision API pass. The original name is kept for backward
compatibility.

Usage:
    python -m rhodesli_ml.scripts.generate_photo_metadata --dry-run
    python -m rhodesli_ml.scripts.generate_photo_metadata --model gemini-3-pro-preview
"""

from rhodesli_ml.scripts.generate_date_labels import main

if __name__ == "__main__":
    main()
