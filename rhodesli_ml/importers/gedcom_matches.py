"""GEDCOM match persistence — save/load/update proposed matches.

Stores match state in data/gedcom_matches.json so the admin
can review matches across sessions.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rhodesli_ml.importers.identity_matcher import MatchProposal


def save_gedcom_matches(matches: list, filepath: Optional[str] = None, source_file: str = ""):
    """Save GEDCOM match proposals to JSON.

    Args:
        matches: List of MatchProposal objects
        filepath: Path to save (default: data/gedcom_matches.json)
        source_file: Original GEDCOM filename
    """
    if filepath is None:
        filepath = Path(__file__).resolve().parent.parent.parent / "data" / "gedcom_matches.json"
    else:
        filepath = Path(filepath)

    filepath.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "schema_version": 1,
        "source_file": source_file,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "matches": [m.to_dict() for m in matches],
    }

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_gedcom_matches(filepath: Optional[str] = None) -> dict:
    """Load GEDCOM match proposals from JSON."""
    if filepath is None:
        filepath = Path(__file__).resolve().parent.parent.parent / "data" / "gedcom_matches.json"
    else:
        filepath = Path(filepath)

    if not filepath.exists():
        return {"schema_version": 1, "matches": [], "source_file": ""}

    with open(filepath) as f:
        return json.load(f)


def update_match_status(filepath: Optional[str] = None, gedcom_xref: str = "", status: str = ""):
    """Update the status of a specific match proposal.

    Args:
        filepath: Path to gedcom_matches.json
        gedcom_xref: The GEDCOM xref ID of the individual
        status: New status (confirmed, rejected, skipped)
    """
    if filepath is None:
        filepath = Path(__file__).resolve().parent.parent.parent / "data" / "gedcom_matches.json"
    else:
        filepath = Path(filepath)

    data = load_gedcom_matches(str(filepath))

    for match in data.get("matches", []):
        if match.get("gedcom_xref") == gedcom_xref:
            match["status"] = status
            match["updated_at"] = datetime.now(timezone.utc).isoformat()
            break

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    return data
