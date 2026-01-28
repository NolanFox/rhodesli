import re
from pathlib import Path

from fasthtml.common import *

static_path = Path(__file__).resolve().parent / "static"
app, rt = fast_app(
    pico=False,
    hdrs=(
        Script(src="https://cdn.tailwindcss.com"),
    ),
    static_path=str(static_path),
)


def parse_quality_from_filename(filename: str) -> float:
    """Extract quality score from filename like 'brass_rail_21.98_0.jpg'."""
    match = re.search(r'_(\d+\.\d+)_\d+\.jpg$', filename)
    if match:
        return float(match.group(1))
    return 0.0


@rt("/")
def get():
    crops_dir = static_path / "crops"

    faces = []
    for f in crops_dir.glob("*.jpg"):
        quality = parse_quality_from_filename(f.name)
        faces.append((f.name, quality))

    faces.sort(key=lambda x: x[1], reverse=True)

    cards = []
    for filename, quality in faces:
        card = Div(
            Img(src=f"/crops/{filename}", alt=filename, cls="face-img"),
            P(f"Quality: {quality:.2f}", cls="quality-score"),
            Textarea(placeholder="Research notes...", disabled=True, cls="notes"),
            cls="face-card"
        )
        cards.append(card)

    gallery = Div(*cards, cls="gallery")

    style = Style("""
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 1rem;
        }
        h1 {
            text-align: center;
            color: #333;
        }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
            max-width: 1200px;
            margin: 0 auto;
        }
        .face-card {
            background: white;
            border-radius: 8px;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .face-img {
            width: 100%;
            height: auto;
            border-radius: 4px;
        }
        .quality-score {
            margin: 0.5rem 0;
            font-weight: bold;
            color: #666;
        }
        .notes {
            width: 100%;
            height: 60px;
            resize: vertical;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 0.5rem;
            font-size: 0.875rem;
            box-sizing: border-box;
        }
    """)

    return Title("Leon Capeluto Gallery"), style, Main(
        H1("Leon Capeluto - Face Gallery"),
        gallery
    )


if __name__ == "__main__":
    serve()
