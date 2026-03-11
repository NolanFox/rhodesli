#!/usr/bin/env python3
"""Comprehensive Data Integrity Audit for Rhodesli.

Detects and optionally repairs structural data issues across the identity,
photo, embedding, and community data layers.

Usage:
    python scripts/data_integrity_audit.py                    # Full audit, local data
    python scripts/data_integrity_audit.py --data-dir /path   # Custom data directory
    python scripts/data_integrity_audit.py --fix               # Auto-repair safe issues
    python scripts/data_integrity_audit.py --json              # Machine-readable output

Exit codes:
    0 = No critical issues
    1 = Critical issues found

Audit checks:
    1. Orphan faces — faces in photo_index with no identity
    2. Ghost identities — identities with faces not in any photo
    3. Missing identity face refs — identity anchors/candidates not in photo_index
    4. State consistency — CONFIRMED with no name or "Unidentified" name
    5. Supabase divergence — identity_overrides vs identities.json state mismatch
    6. Duplicate face assignments — same face_id in multiple identities
    7. Merged identity chains — merged_into pointing to another merged identity
    8. Upload date completeness — photos missing upload_date
    9. Community membership gaps — photos with faces but no community
    10. Embedding coverage — identity faces with no embedding

Created: Session 96e data integrity hardening
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.registry import IdentityRegistry, IdentityState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class AuditIssue:
    """A single data integrity issue."""

    check: str
    severity: str  # "critical", "warning", "info"
    message: str
    ids: list[str] = field(default_factory=list)
    fixable: bool = False


@dataclass
class AuditResult:
    """Full audit result."""

    issues: list[AuditIssue] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    @property
    def has_critical(self) -> bool:
        return any(i.severity == "critical" for i in self.issues)

    def add(self, check: str, severity: str, message: str, ids: list[str] | None = None, fixable: bool = False):
        self.issues.append(
            AuditIssue(
                check=check,
                severity=severity,
                message=message,
                ids=ids or [],
                fixable=fixable,
            )
        )


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def load_identities_json(data_dir: Path) -> dict:
    """Load raw identities dict from identities.json."""
    path = data_dir / "identities.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data.get("identities", {})


def load_photo_index_json(data_dir: Path) -> tuple[dict, dict]:
    """Load photos dict and face_to_photo dict from photo_index.json.

    Returns:
        (photos, face_to_photo) tuple
    """
    path = data_dir / "photo_index.json"
    if not path.exists():
        return {}, {}
    data = json.loads(path.read_text())
    return data.get("photos", {}), data.get("face_to_photo", {})


def load_embedding_face_ids(data_dir: Path) -> set[str]:
    """Load all face_ids from embeddings.npy.

    Uses the same logic as app/main.py load_embeddings_for_photos() to
    generate face_ids from entries that lack an explicit face_id field.
    """
    try:
        import numpy as np
    except ImportError:
        logger.warning("numpy not available, skipping embedding coverage check")
        return set()

    path = data_dir / "embeddings.npy"
    if not path.exists():
        return set()

    try:
        from app.utils import generate_face_id
    except ImportError:
        # Fallback inline implementation matching app/utils.py
        def generate_face_id(filename: str, face_index: int) -> str:
            stem = Path(filename).stem
            return f"{stem}:face{face_index}"

    embeddings = np.load(str(path), allow_pickle=True)
    face_ids = set()
    filename_counts: dict[str, int] = {}

    for entry in embeddings:
        filename = entry["filename"]
        if filename not in filename_counts:
            filename_counts[filename] = 0
        idx = filename_counts[filename]
        filename_counts[filename] += 1

        fid = entry.get("face_id") or generate_face_id(filename, idx)
        face_ids.add(fid)

    return face_ids


# ---------------------------------------------------------------------------
# Audit checks
# ---------------------------------------------------------------------------


def check_orphan_faces(photos: dict, face_to_photo: dict, identities: dict, result: AuditResult) -> set[str]:
    """Check 1: Faces in photo_index that have no identity assignment.

    Returns set of orphan face_ids for potential fix.
    """
    # Build set of all face_ids assigned to any identity
    assigned_faces: set[str] = set()
    for ident in identities.values():
        if ident.get("merged_into"):
            continue
        for anchor in ident.get("anchor_ids", []):
            fid = anchor if isinstance(anchor, str) else anchor.get("face_id", "")
            if fid:
                assigned_faces.add(fid)
        for cid in ident.get("candidate_ids", []):
            assigned_faces.add(cid)

    # All faces known in face_to_photo
    all_faces = set(face_to_photo.keys())
    # Also collect face_ids from photo entries
    for photo in photos.values():
        for fid in photo.get("face_ids", []):
            all_faces.add(fid)

    orphans = all_faces - assigned_faces
    if orphans:
        result.add(
            check="orphan_faces",
            severity="warning",
            message=f"{len(orphans)} faces in photo_index have no identity assignment",
            ids=sorted(orphans)[:20],
            fixable=True,
        )
    result.summary["orphan_faces"] = len(orphans)
    return orphans


def check_ghost_identities(face_to_photo: dict, identities: dict, result: AuditResult) -> list[str]:
    """Check 2: Identities whose faces don't exist in any photo.

    Returns list of ghost identity IDs.
    """
    all_known_faces = set(face_to_photo.keys())
    ghosts = []

    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue
        face_ids = []
        for anchor in ident.get("anchor_ids", []):
            fid = anchor if isinstance(anchor, str) else anchor.get("face_id", "")
            if fid:
                face_ids.append(fid)
        face_ids.extend(ident.get("candidate_ids", []))

        if not face_ids:
            continue  # identity with no faces — separate issue

        missing = [f for f in face_ids if f not in all_known_faces]
        if len(missing) == len(face_ids):
            # ALL faces are missing from photo_index
            ghosts.append(iid)

    if ghosts:
        result.add(
            check="ghost_identities",
            severity="critical",
            message=f"{len(ghosts)} identities have ALL faces missing from photo_index",
            ids=ghosts[:20],
        )
    result.summary["ghost_identities"] = len(ghosts)
    return ghosts


def check_missing_identity_faces(face_to_photo: dict, identities: dict, result: AuditResult) -> dict[str, dict[str, list[str]]]:
    """Check 3: Identity face refs missing from photo_index.face_to_photo."""
    all_known_faces = set(face_to_photo.keys())
    affected: dict[str, dict[str, list[str]]] = {}
    total_missing = 0

    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue

        missing_anchors = []
        for anchor in ident.get("anchor_ids", []):
            fid = anchor if isinstance(anchor, str) else anchor.get("face_id", "")
            if fid and fid not in all_known_faces:
                missing_anchors.append(fid)

        missing_candidates = []
        for candidate in ident.get("candidate_ids", []):
            fid = candidate if isinstance(candidate, str) else candidate.get("face_id", "")
            if fid and fid not in all_known_faces:
                missing_candidates.append(fid)

        if not missing_anchors and not missing_candidates:
            continue

        affected[iid] = {
            "anchor_ids": missing_anchors,
            "candidate_ids": missing_candidates,
        }
        total_missing += len(missing_anchors) + len(missing_candidates)

        name = ident.get("name", "?")
        state = ident.get("state", "")
        severity = "critical" if state == IdentityState.CONFIRMED.value and missing_anchors else "warning"
        parts = []
        if missing_anchors:
            parts.append(f"{len(missing_anchors)} anchor")
        if missing_candidates:
            parts.append(f"{len(missing_candidates)} candidate")
        result.add(
            check="missing_identity_faces",
            severity=severity,
            message=f"Identity {iid[:8]} ({name}) has {' and '.join(parts)} face refs missing from photo_index",
            ids=[iid, *missing_anchors[:3], *missing_candidates[:3]],
            fixable=True,
        )

    result.summary["missing_identity_faces"] = total_missing
    return affected


def check_state_consistency(identities: dict, result: AuditResult) -> list[str]:
    """Check 3: CONFIRMED identities with no name or 'Unidentified Person' name.

    Returns list of inconsistent identity IDs.
    """
    import re

    inconsistent = []
    valid_states = {state.value for state in IdentityState}

    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue

        state = ident.get("state", "")

        # Invalid state
        if state not in valid_states:
            result.add(
                check="state_consistency",
                severity="critical",
                message=f"Identity {iid[:8]} has invalid state '{state}'",
                ids=[iid],
            )
            continue

        # CONFIRMED but named "Unidentified Person ..."
        if state == "CONFIRMED":
            name = ident.get("name", "")
            if not name:
                inconsistent.append(iid)
                result.add(
                    check="state_consistency",
                    severity="critical",
                    message=f"CONFIRMED identity {iid[:8]} has no name",
                    ids=[iid],
                    fixable=True,
                )
            elif re.match(r"^Unidentified Person\b", name):
                inconsistent.append(iid)
                result.add(
                    check="state_consistency",
                    severity="warning",
                    message=f"CONFIRMED identity {iid[:8]} still named '{name}'",
                    ids=[iid],
                    fixable=True,
                )

    result.summary["state_inconsistencies"] = len(inconsistent)
    return inconsistent


def check_supabase_divergence(identities: dict, result: AuditResult) -> dict:
    """Check 4: Compare identity states between Supabase and JSON.

    Returns dict with divergence details.
    """
    divergence: dict = {"checked": False, "mismatches": []}

    try:
        from app.supabase_data import get_supabase_client
    except ImportError:
        result.add(
            check="supabase_divergence",
            severity="info",
            message="Supabase module not available, skipping divergence check",
        )
        return divergence

    client = get_supabase_client()
    if not client:
        result.add(
            check="supabase_divergence",
            severity="info",
            message="Supabase not configured, skipping divergence check",
        )
        return divergence

    divergence["checked"] = True

    try:
        # Load identity_overrides from Supabase
        all_overrides = []
        page_size = 1000
        offset = 0
        while True:
            resp = (
                client.table("identity_overrides")
                .select("identity_id, state, name, merged_into")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not resp.data:
                break
            all_overrides.extend(resp.data)
            if len(resp.data) < page_size:
                break
            offset += page_size

        sb_map = {r["identity_id"]: r for r in all_overrides}
        mismatches = []

        for iid, sb_data in sb_map.items():
            json_data = identities.get(iid)
            if not json_data:
                mismatches.append(
                    {
                        "identity_id": iid,
                        "type": "missing_in_json",
                        "supabase_state": sb_data.get("state"),
                    }
                )
                continue

            # State mismatch
            json_state = json_data.get("state", "")
            sb_state = sb_data.get("state", "")
            if json_state != sb_state:
                mismatches.append(
                    {
                        "identity_id": iid,
                        "type": "state_mismatch",
                        "json_state": json_state,
                        "supabase_state": sb_state,
                    }
                )

            # Merge status mismatch
            json_merged = json_data.get("merged_into")
            sb_merged = sb_data.get("merged_into")
            if json_merged != sb_merged:
                mismatches.append(
                    {
                        "identity_id": iid,
                        "type": "merge_mismatch",
                        "json_merged_into": json_merged,
                        "supabase_merged_into": sb_merged,
                    }
                )

        divergence["mismatches"] = mismatches
        divergence["override_count"] = len(sb_map)

        if mismatches:
            result.add(
                check="supabase_divergence",
                severity="critical",
                message=f"{len(mismatches)} state mismatches between JSON and Supabase",
                ids=[m["identity_id"] for m in mismatches[:20]],
            )
        result.summary["supabase_mismatches"] = len(mismatches)

    except Exception as e:
        result.add(
            check="supabase_divergence",
            severity="warning",
            message=f"Supabase query failed: {e}",
        )

    return divergence


def check_duplicate_face_assignments(identities: dict, result: AuditResult) -> dict[str, list[str]]:
    """Check 5: Same face_id assigned to multiple identities.

    Returns dict of {face_id: [identity_ids]}.
    """
    face_owners: dict[str, list[str]] = {}

    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue
        for anchor in ident.get("anchor_ids", []):
            fid = anchor if isinstance(anchor, str) else anchor.get("face_id", "")
            if fid:
                face_owners.setdefault(fid, []).append(iid)
        for cid in ident.get("candidate_ids", []):
            face_owners.setdefault(cid, []).append(iid)

    duplicates = {fid: owners for fid, owners in face_owners.items() if len(owners) > 1}

    if duplicates:
        result.add(
            check="duplicate_face_assignments",
            severity="critical",
            message=f"{len(duplicates)} faces assigned to multiple identities",
            ids=sorted(duplicates.keys())[:20],
        )
    result.summary["duplicate_faces"] = len(duplicates)
    return duplicates


def check_merged_chains(identities: dict, result: AuditResult) -> list[str]:
    """Check 6: merged_into pointing to another merged identity (should be flat).

    Returns list of identity IDs with chained merges.
    """
    chained = []

    for iid, ident in identities.items():
        target = ident.get("merged_into")
        if not target:
            continue

        target_data = identities.get(target)
        if target_data and target_data.get("merged_into"):
            chained.append(iid)

    if chained:
        result.add(
            check="merged_chains",
            severity="warning",
            message=f"{len(chained)} identities have chained merged_into references",
            ids=chained[:20],
            fixable=True,
        )
    result.summary["merged_chains"] = len(chained)
    return chained


def check_upload_date_completeness(photos: dict, result: AuditResult) -> list[str]:
    """Check 7: Photos missing upload_date.

    Returns list of photo IDs without upload_date.
    """
    missing = [pid for pid, p in photos.items() if not p.get("upload_date")]

    if missing:
        result.add(
            check="upload_date_completeness",
            severity="info",
            message=f"{len(missing)} photos missing upload_date",
            ids=sorted(missing)[:20],
        )
    result.summary["missing_upload_date"] = len(missing)
    return missing


def check_community_membership(photos: dict, result: AuditResult) -> list[str]:
    """Check 8: Photos with faces but no community assignment.

    Checks the photo_communities table in Supabase if available.
    Returns list of photo IDs without community.
    """
    # Get photos that have faces
    photos_with_faces = [pid for pid, p in photos.items() if len(p.get("face_ids", [])) > 0]

    try:
        from app.supabase_data import get_supabase_client

        client = get_supabase_client()
        if not client:
            result.add(
                check="community_membership",
                severity="info",
                message="Supabase not available, skipping community membership check",
            )
            return []

        # Get all photo_ids that have a community assignment
        all_community_photos: set[str] = set()
        page_size = 1000
        offset = 0
        while True:
            resp = client.table("photo_communities").select("photo_id").range(offset, offset + page_size - 1).execute()
            if not resp.data:
                break
            all_community_photos.update(r["photo_id"] for r in resp.data)
            if len(resp.data) < page_size:
                break
            offset += page_size

        unassigned = [pid for pid in photos_with_faces if pid not in all_community_photos]

        if unassigned:
            result.add(
                check="community_membership",
                severity="warning",
                message=f"{len(unassigned)} photos with faces have no community assignment",
                ids=sorted(unassigned)[:20],
            )
        result.summary["community_gaps"] = len(unassigned)
        return unassigned

    except Exception as e:
        result.add(
            check="community_membership",
            severity="info",
            message=f"Community membership check failed: {e}",
        )
        return []


def check_embedding_coverage(identities: dict, embedding_face_ids: set[str], result: AuditResult) -> list[str]:
    """Check 9: Identity faces that have no embedding in embeddings.npy.

    Returns list of face_ids missing embeddings.
    """
    if not embedding_face_ids:
        result.add(
            check="embedding_coverage",
            severity="info",
            message="No embeddings loaded, skipping coverage check",
        )
        return []

    missing = []
    for iid, ident in identities.items():
        if ident.get("merged_into"):
            continue
        for anchor in ident.get("anchor_ids", []):
            fid = anchor if isinstance(anchor, str) else anchor.get("face_id", "")
            if fid and fid not in embedding_face_ids:
                missing.append(fid)
        for cid in ident.get("candidate_ids", []):
            if cid not in embedding_face_ids:
                missing.append(cid)

    if missing:
        result.add(
            check="embedding_coverage",
            severity="warning",
            message=f"{len(missing)} identity faces have no embedding",
            ids=sorted(set(missing))[:20],
        )
    result.summary["missing_embeddings"] = len(missing)
    return missing


# ---------------------------------------------------------------------------
# Fix operations (safe, reversible)
# ---------------------------------------------------------------------------


def fix_orphan_faces(orphan_face_ids: set[str], data_dir: Path, result: AuditResult) -> int:
    """Create INBOX identities for orphan faces.

    Each orphan face gets its own INBOX identity with the face as anchor.
    """
    if not orphan_face_ids:
        return 0

    path = data_dir / "identities.json"
    if not path.exists():
        return 0
    registry = IdentityRegistry.load(path)

    count = 0
    for face_id in sorted(orphan_face_ids):
        registry.create_identity(
            anchor_ids=[face_id],
            user_source="data_integrity_audit",
            state=IdentityState.INBOX,
            provenance={"source": "data_integrity_audit", "action": "orphan_fix"},
        )
        count += 1

    registry.save(path)
    result.fixes_applied.append(f"Created {count} INBOX identities for orphan faces")
    return count


def fix_missing_identity_faces(missing_refs: dict[str, dict[str, list[str]]], data_dir: Path, result: AuditResult) -> int:
    """Quarantine and remove partial missing face refs from identities.

    Only fixes identities that still retain at least one valid face after cleanup.
    Full ghosts are left untouched for manual review.
    """
    if not missing_refs:
        return 0

    path = data_dir / "identities.json"
    if not path.exists():
        return 0

    registry = IdentityRegistry.load(path)
    timestamp = datetime.now(timezone.utc).isoformat()
    removed = 0

    for iid, missing in missing_refs.items():
        ident = registry._identities.get(iid)
        if not ident:
            continue

        current_face_ids = registry.get_all_face_ids(iid)
        missing_face_ids = set(missing.get("anchor_ids", []) + missing.get("candidate_ids", []))
        valid_remaining = [fid for fid in current_face_ids if fid not in missing_face_ids]
        if not valid_remaining:
            continue

        metadata = ident.setdefault("metadata", {})
        quarantine = metadata.setdefault("quarantined_missing_faces", [])
        changed = False

        for fid in missing.get("anchor_ids", []):
            if fid in registry._face_id_set(ident.get("anchor_ids", [])):
                registry._remove_anchor_by_face_id(ident, fid)
                if not any(entry.get("face_id") == fid and entry.get("removed_from") == "anchor_ids" for entry in quarantine):
                    quarantine.append(
                        {
                            "face_id": fid,
                            "removed_from": "anchor_ids",
                            "reason": "missing_from_photo_index_face_to_photo",
                            "quarantined_at": timestamp,
                        }
                    )
                removed += 1
                changed = True

        for fid in missing.get("candidate_ids", []):
            if fid in registry._face_id_set(ident.get("candidate_ids", [])):
                registry._remove_candidate_by_face_id(ident, fid)
                if not any(entry.get("face_id") == fid and entry.get("removed_from") == "candidate_ids" for entry in quarantine):
                    quarantine.append(
                        {
                            "face_id": fid,
                            "removed_from": "candidate_ids",
                            "reason": "missing_from_photo_index_face_to_photo",
                            "quarantined_at": timestamp,
                        }
                    )
                removed += 1
                changed = True

        if changed:
            ident["version_id"] = ident.get("version_id", 1) + 1
            ident["updated_at"] = timestamp
            result.fixes_applied.append(f"Quarantined missing face refs on {iid[:8]} ({ident.get('name', '?')})")

    if removed:
        registry.save(path)
    return removed


def fix_merged_chains(identities: dict, data_dir: Path, result: AuditResult) -> int:
    """Flatten chained merged_into references to point to final target."""
    path = data_dir / "identities.json"
    if not path.exists():
        return 0

    registry = IdentityRegistry.load(path)
    idents = registry._identities
    timestamp = datetime.now(timezone.utc).isoformat()

    count = 0
    for iid, ident in idents.items():
        target = ident.get("merged_into")
        if not target:
            continue

        # Follow the chain to the final target
        visited = {iid}
        current = target
        while current in idents and idents[current].get("merged_into"):
            if current in visited:
                # Cycle detected — break
                break
            visited.add(current)
            current = idents[current]["merged_into"]

        if current != target:
            metadata = ident.setdefault("metadata", {})
            repairs = metadata.setdefault("merge_chain_repairs", [])
            repairs.append(
                {
                    "source": "data_integrity_audit",
                    "flattened_at": timestamp,
                    "previous_merged_into": target,
                    "new_merged_into": current,
                }
            )
            ident["merged_into"] = current
            ident["version_id"] = ident.get("version_id", 1) + 1
            ident["updated_at"] = timestamp
            count += 1

    if count > 0:
        registry.save(path)
        result.fixes_applied.append(f"Flattened {count} chained merge references")

    return count


def fix_state_inconsistencies(inconsistent_ids: list[str], data_dir: Path, result: AuditResult) -> int:
    """Demote invalid CONFIRMED placeholders back to INBOX via audited state history."""
    if not inconsistent_ids:
        return 0

    path = data_dir / "identities.json"
    if not path.exists():
        return 0

    registry = IdentityRegistry.load(path)
    fixed = 0

    for iid in inconsistent_ids:
        ident = registry._identities.get(iid)
        if not ident or ident.get("state") != IdentityState.CONFIRMED.value:
            continue
        if registry._is_real_name(ident.get("name")):
            continue

        registry.force_state(
            iid,
            IdentityState.INBOX.value,
            user_source="data_integrity_audit",
            reason="confirmed_placeholder_name",
        )
        fixed += 1
        result.fixes_applied.append(
            f"Moved invalid confirmed placeholder {iid[:8]} back to INBOX"
        )

    if fixed:
        registry.save(path)
    return fixed


# ---------------------------------------------------------------------------
# Main audit runner
# ---------------------------------------------------------------------------


def run_audit(data_dir: Path, fix: bool = False) -> AuditResult:
    """Run all audit checks and optionally apply fixes.

    Args:
        data_dir: Path to data directory containing JSON files
        fix: If True, apply safe auto-repairs

    Returns:
        AuditResult with all findings
    """
    result = AuditResult()

    # Load data
    identities = load_identities_json(data_dir)
    photos, face_to_photo = load_photo_index_json(data_dir)
    embedding_face_ids = load_embedding_face_ids(data_dir)

    result.summary["total_identities"] = len(identities)
    result.summary["total_photos"] = len(photos)
    result.summary["total_faces_in_index"] = len(face_to_photo)
    result.summary["total_embeddings"] = len(embedding_face_ids)

    # Run checks
    orphans = check_orphan_faces(photos, face_to_photo, identities, result)
    check_ghost_identities(face_to_photo, identities, result)
    missing_face_refs = check_missing_identity_faces(face_to_photo, identities, result)
    inconsistent = check_state_consistency(identities, result)
    check_supabase_divergence(identities, result)
    duplicates = check_duplicate_face_assignments(identities, result)
    chained = check_merged_chains(identities, result)
    check_upload_date_completeness(photos, result)
    check_community_membership(photos, result)
    check_embedding_coverage(identities, embedding_face_ids, result)

    # Apply fixes if requested
    if fix:
        fix_orphan_faces(orphans, data_dir, result)
        fix_missing_identity_faces(missing_face_refs, data_dir, result)
        fix_merged_chains(identities, data_dir, result)
        fix_state_inconsistencies(inconsistent, data_dir, result)

    return result


def print_report(result: AuditResult, as_json: bool = False):
    """Print human-readable or JSON audit report."""
    if as_json:
        output = {
            "summary": result.summary,
            "issues": [
                {
                    "check": i.check,
                    "severity": i.severity,
                    "message": i.message,
                    "sample_ids": i.ids[:10],
                    "fixable": i.fixable,
                }
                for i in result.issues
            ],
            "fixes_applied": result.fixes_applied,
            "has_critical": result.has_critical,
        }
        print(json.dumps(output, indent=2))
        return

    print("=" * 64)
    print("  RHODESLI DATA INTEGRITY AUDIT")
    print("=" * 64)

    # Summary
    print("\n--- SUMMARY ---")
    for key, val in result.summary.items():
        print(f"  {key}: {val}")

    # Issues by severity
    for severity in ("critical", "warning", "info"):
        issues = [i for i in result.issues if i.severity == severity]
        if not issues:
            continue
        label = severity.upper()
        print(f"\n--- {label} ({len(issues)}) ---")
        for issue in issues:
            marker = {"critical": "!!", "warning": "!", "info": "i"}[severity]
            print(f"  [{marker}] {issue.check}: {issue.message}")
            if issue.ids:
                sample = issue.ids[:5]
                print(f"      Sample: {', '.join(str(s)[:16] for s in sample)}")
                if len(issue.ids) > 5:
                    print(f"      ... and {len(issue.ids) - 5} more")

    # Fixes
    if result.fixes_applied:
        print(f"\n--- FIXES APPLIED ({len(result.fixes_applied)}) ---")
        for fix_msg in result.fixes_applied:
            print(f"  [+] {fix_msg}")

    # Verdict
    print("\n" + "=" * 64)
    if result.has_critical:
        print("  RESULT: CRITICAL ISSUES FOUND")
    elif any(i.severity == "warning" for i in result.issues):
        print("  RESULT: WARNINGS (no critical issues)")
    else:
        print("  RESULT: ALL CHECKS PASSED")
    print("=" * 64)


def main():
    parser = argparse.ArgumentParser(
        description="Rhodesli Data Integrity Audit",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=PROJECT_ROOT / "data",
        help="Path to data directory (default: ./data)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-repair safe issues (orphan faces, merge chains)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )
    args = parser.parse_args()

    result = run_audit(args.data_dir, fix=args.fix)
    print_report(result, as_json=args.json)

    sys.exit(1 if result.has_critical else 0)


if __name__ == "__main__":
    main()
