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
            Img(
                src=f"/crops/{filename}",
                alt=filename,
                cls="w-full h-auto border border-stone-200"
            ),
            P(
                f"Quality: {quality:.2f}",
                cls="mt-2 text-sm font-serif italic text-stone-600"
            ),
            Textarea(
                placeholder="Research notes...",
                disabled=True,
                cls="w-full mt-2 p-2 text-sm font-serif bg-amber-50 border border-stone-300 resize-y h-16 placeholder:italic placeholder:text-stone-400"
            ),
            cls="bg-stone-50 border border-stone-300 p-3 shadow-sm"
        )
        cards.append(card)

    gallery = Div(
        *cards,
        cls="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 max-w-7xl mx-auto"
    )

    # Minimal CSS for body background (Tailwind handles the rest)
    style = Style("""
        body {
            background-color: #f5f5f4;
            margin: 0;
        }
    """)

    return Title("Leon Capeluto Gallery"), style, Main(
        H1(
            "Leon Capeluto - Face Gallery",
            cls="text-center text-3xl md:text-4xl font-serif font-bold text-stone-800 tracking-wide mb-6"
        ),
        gallery,
        cls="p-4 md:p-8"
    )


if __name__ == "__main__":
    serve()
