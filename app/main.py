import json
import re
from pathlib import Path

from fasthtml.common import *

static_path = Path(__file__).resolve().parent / "static"
data_path = Path(__file__).resolve().parent.parent / "data"
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


def load_clusters():
    """Load cluster data from JSON file."""
    clusters_path = data_path / "clusters.json"
    if not clusters_path.exists():
        return None
    with open(clusters_path) as f:
        return json.load(f)


def make_face_card(filename: str, quality: float, era: str = None) -> Div:
    """Create a single face card."""
    era_badge = None
    if era:
        era_badge = Span(
            era,
            cls="absolute top-2 right-2 bg-amber-600 text-white text-xs px-2 py-1 font-serif"
        )

    return Div(
        Div(
            Img(
                src=f"/crops/{filename}",
                alt=filename,
                cls="w-full h-auto sepia hover:sepia-0 transition-all duration-500"
            ),
            era_badge,
            cls="relative p-[10%] border border-stone-200 bg-white"
        ),
        P(
            f"Quality: {quality:.2f}",
            cls="mt-2 text-sm font-serif italic text-stone-600"
        ),
        Label(
            "Research Notes",
            cls="sr-only",
            **{"for": f"notes-{filename}"}
        ),
        Textarea(
            placeholder="Research notes...",
            name="notes",
            id=f"notes-{filename}",
            cls="w-full mt-2 p-2 text-sm font-serif bg-amber-50 border border-stone-300 resize-y h-16 placeholder:italic placeholder:text-stone-400 focus:outline-none focus:ring-2 focus:ring-amber-600 focus:border-amber-600"
        ),
        cls="bg-stone-50 border border-stone-300 p-3 shadow-sm hover:shadow-md hover:border-stone-400 transition-all duration-200"
    )


def make_cluster_section(cluster: dict, crop_files: set):
    """Create a section for an identity cluster."""
    # Filter to faces that have crop files
    valid_faces = []
    for face in cluster["faces"]:
        # Match filename pattern (lowercase with underscores)
        for crop in crop_files:
            if face["filename"].lower().replace(" ", "_").split(".")[0] in crop.lower():
                valid_faces.append((crop, face))
                break

    if not valid_faces:
        return None

    cards = []
    for crop_filename, face in valid_faces:
        quality = face.get("quality", parse_quality_from_filename(crop_filename))
        era = face.get("era")
        cards.append(make_face_card(crop_filename, quality, era))

    match_range = cluster.get("match_range", "N/A")
    face_count = len(valid_faces)

    return Div(
        Div(
            H2(
                f"Identity Group {cluster['cluster_id']}",
                cls="text-xl font-serif font-bold text-stone-700"
            ),
            Span(
                f"Match Probability: {match_range}",
                cls="ml-4 text-sm font-serif text-amber-700 bg-amber-100 px-3 py-1 rounded"
            ),
            Span(
                f"{face_count} face{'s' if face_count != 1 else ''}",
                cls="ml-2 text-sm font-serif text-stone-500"
            ),
            cls="flex items-center flex-wrap gap-2 mb-4 pb-2 border-b border-stone-300"
        ),
        Div(
            *cards,
            cls="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4"
        ),
        cls="mb-8"
    )


@rt("/")
def get():
    crops_dir = static_path / "crops"
    crop_files = {f.name for f in crops_dir.glob("*.jpg")}

    clusters = load_clusters()

    # Minimal CSS for body background (Tailwind handles the rest)
    style = Style("""
        body {
            background-color: #f5f5f4;
            margin: 0;
        }
    """)

    if clusters:
        # Clustered view with match probability ranges
        sections = []
        for cluster in clusters:
            section = make_cluster_section(cluster, crop_files)
            if section:
                sections.append(section)

        content = Div(*sections, cls="max-w-7xl mx-auto")
    else:
        # Fallback: simple gallery view (no clusters.json)
        faces = []
        for f in crops_dir.glob("*.jpg"):
            quality = parse_quality_from_filename(f.name)
            faces.append((f.name, quality))

        faces.sort(key=lambda x: x[1], reverse=True)

        cards = [make_face_card(filename, quality) for filename, quality in faces]
        content = Div(
            *cards,
            cls="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 max-w-7xl mx-auto"
        )

    return Title("Leon Capeluto Gallery"), style, Main(
        Header(
            H1(
                "Leon Capeluto - Face Gallery",
                cls="text-3xl md:text-4xl font-serif font-bold text-stone-800 tracking-wide"
            ),
            P(
                "Forensic Identity Engine - Truth-Seeker Protocol",
                cls="text-sm font-serif text-stone-500 mt-2"
            ),
            cls="text-center border-b-2 border-stone-800 pb-4 mb-8"
        ),
        content,
        cls="p-4 md:p-8"
    )


if __name__ == "__main__":
    serve()
