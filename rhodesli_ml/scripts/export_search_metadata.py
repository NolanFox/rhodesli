"""Export a search index from labeled photos.

Combines date labels and rich metadata into a flat search document per photo,
suitable for full-text search and faceted filtering.

Output format: data/photo_search_index.json with one document per labeled photo.

Usage:
    python -m rhodesli_ml.scripts.export_search_metadata
    python rhodesli_ml/scripts/export_search_metadata.py
    python rhodesli_ml/scripts/export_search_metadata.py --dry-run
    python rhodesli_ml/scripts/export_search_metadata.py --output /alt/path.json
"""

import argparse
import json
import sys
from pathlib import Path

# Allow direct invocation: python rhodesli_ml/scripts/export_search_metadata.py
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Default file paths
DEFAULT_DATE_LABELS = Path(__file__).resolve().parent.parent / "data" / "date_labels.json"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent.parent / "data" / "photo_search_index.json"


def _green(text: str) -> str:
    return f"{GREEN}{text}{RESET}"


def _yellow(text: str) -> str:
    return f"{YELLOW}{text}{RESET}"


def _red(text: str) -> str:
    return f"{RED}{text}{RESET}"


def _cyan(text: str) -> str:
    return f"{CYAN}{text}{RESET}"


def _bold(text: str) -> str:
    return f"{BOLD}{text}{RESET}"


def load_date_labels(path: str | Path) -> list[dict]:
    """Load date labels and return the labels list."""
    path = Path(path)
    if not path.exists():
        print(_red(f"ERROR: {path} not found"))
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("labels", [])


def build_search_document(label: dict) -> dict:
    """Build a search document from a single date label entry.

    Combines scene_description, visible_text, and keywords into a single
    searchable_text field for full-text search. Preserves structured fields
    for faceted filtering.

    Args:
        label: A single entry from date_labels.json.

    Returns:
        A search document dict.
    """
    # Build searchable text from available metadata
    text_parts = []

    scene = label.get("scene_description")
    if scene:
        text_parts.append(scene)

    visible_text = label.get("visible_text")
    if visible_text:
        text_parts.append(visible_text)

    keywords = label.get("keywords", [])
    if keywords:
        text_parts.append(" ".join(keywords))

    clothing = label.get("clothing_notes")
    if clothing:
        text_parts.append(clothing)

    location = label.get("location_estimate")
    if location:
        text_parts.append(location)

    searchable_text = " ".join(text_parts).strip()

    return {
        "photo_id": label["photo_id"],
        "searchable_text": searchable_text,
        "controlled_tags": label.get("controlled_tags", []),
        "estimated_decade": label.get("estimated_decade"),
        "best_year_estimate": label.get("best_year_estimate"),
        "people_count": label.get("people_count"),
        "source_method": label.get("source_method", ""),
    }


def export_search_metadata(
    labels: list[dict],
    output_path: str | Path,
    dry_run: bool = False,
) -> dict:
    """Build search documents from labels and write to output file.

    Args:
        labels: List of label entries from date_labels.json.
        output_path: Path to write the search index.
        dry_run: If True, print what would be written without writing.

    Returns:
        Summary dict with counts.
    """
    documents = []
    skipped = 0

    for label in labels:
        photo_id = label.get("photo_id")
        if not photo_id:
            skipped += 1
            continue

        doc = build_search_document(label)
        documents.append(doc)

    # Compute stats
    with_text = sum(1 for d in documents if d["searchable_text"])
    with_tags = sum(1 for d in documents if d["controlled_tags"])
    with_decade = sum(1 for d in documents if d["estimated_decade"] is not None)
    with_people = sum(1 for d in documents if d["people_count"] is not None)

    # Decade distribution
    decade_counts: dict[int, int] = {}
    for doc in documents:
        decade = doc.get("estimated_decade")
        if decade is not None:
            decade_counts[decade] = decade_counts.get(decade, 0) + 1

    # Source method distribution
    method_counts: dict[str, int] = {}
    for doc in documents:
        method = doc.get("source_method") or "unknown"
        method_counts[method] = method_counts.get(method, 0) + 1

    summary = {
        "total_documents": len(documents),
        "skipped": skipped,
        "with_searchable_text": with_text,
        "with_controlled_tags": with_tags,
        "with_decade": with_decade,
        "with_people_count": with_people,
        "decade_distribution": decade_counts,
        "source_method_distribution": method_counts,
        "written": False,
    }

    # Write output
    if not dry_run and documents:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_data = {
            "schema_version": 1,
            "documents": documents,
        }
        with open(output_path, "w") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        summary["written"] = True

    return summary, documents


def print_report(summary: dict, output_path: str | Path, dry_run: bool) -> None:
    """Print the export summary report."""
    print(f"\n{'=' * 55}")
    print(f"  {_bold('Search Metadata Export Summary')}")
    print(f"{'=' * 55}")
    print(f"  Total documents:      {summary['total_documents']}")

    if summary["skipped"] > 0:
        print(_yellow(f"  Skipped (no photo_id): {summary['skipped']}"))
    else:
        print(_green(f"  Skipped:               0"))

    print(f"  With searchable text:  {summary['with_searchable_text']}")
    print(f"  With controlled tags:  {summary['with_controlled_tags']}")
    print(f"  With decade estimate:  {summary['with_decade']}")
    print(f"  With people count:     {summary['with_people_count']}")

    # Decade distribution
    decade_dist = summary.get("decade_distribution", {})
    if decade_dist:
        print(f"\n  Decade distribution:")
        for decade in sorted(decade_dist.keys()):
            count = decade_dist[decade]
            bar = "#" * min(count, 40)
            print(f"    {decade}s: {count:3d}  {bar}")

    # Source method distribution
    method_dist = summary.get("source_method_distribution", {})
    if method_dist:
        print(f"\n  Source methods:")
        for method, count in sorted(method_dist.items(), key=lambda x: -x[1]):
            print(f"    {method}: {count}")

    if dry_run:
        print(_yellow(f"\n  Mode: DRY RUN (no file written)"))
    elif summary["written"]:
        print(_green(f"\n  Written to: {output_path}"))
    else:
        print(_yellow(f"\n  No documents to write."))

    print(f"{'=' * 55}")


def main():
    parser = argparse.ArgumentParser(
        description="Export search metadata index from labeled photos",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary without writing the output file",
    )
    parser.add_argument(
        "--date-labels",
        type=str,
        default=str(DEFAULT_DATE_LABELS),
        help=f"Path to date_labels.json (default: {DEFAULT_DATE_LABELS})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help=f"Output path for search index (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    print(_bold("Loading date labels..."))

    labels = load_date_labels(args.date_labels)
    if not labels:
        print(_red("No labels found. Exiting."))
        sys.exit(1)
    print(f"  Loaded {len(labels)} labels from {args.date_labels}")

    # Export
    summary, _documents = export_search_metadata(
        labels, args.output, dry_run=args.dry_run,
    )

    # Report
    print_report(summary, args.output, args.dry_run)

    sys.exit(0)


if __name__ == "__main__":
    main()
