"""
Semi-Supervised Identity Registry.

A durable, versioned registry with state, provenance, and replay capabilities.
See docs/adr_004_identity_registry.md for design rationale.

Key principles:
- Immutable source data (PFE embeddings never modified)
- Append-only event log for full provenance
- Human-gated learning (only explicit confirmation updates anchors)
- State machine controls fusion behavior
- Safety Foundation: No merge may occur without validate_merge
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

# --- INSTRUMENTATION IMPORT ---
from core.event_recorder import get_event_recorder

if TYPE_CHECKING:
    from core.photo_registry import PhotoRegistry

logger = logging.getLogger(__name__)


def _levenshtein(s: str, t: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s) < len(t):
        return _levenshtein(t, s)
    if len(t) == 0:
        return len(s)
    prev_row = list(range(len(t) + 1))
    for i, sc in enumerate(s):
        curr_row = [i + 1]
        for j, tc in enumerate(t):
            cost = 0 if sc == tc else 1
            curr_row.append(
                min(
                    curr_row[j] + 1,  # insert
                    prev_row[j + 1] + 1,  # delete
                    prev_row[j] + cost,  # substitute
                )
            )
        prev_row = curr_row
    return prev_row[-1]


# --- Surname variant matching ---
_surname_variants_cache: dict | None = None


def _load_surname_variants() -> dict[str, list[str]]:
    """Load surname variant groups and build a lookup: lowercase name -> all variants (lowercase).

    Returns a dict where each key is a lowercase variant and the value is the
    full list of lowercase names in its group (including canonical).
    """
    global _surname_variants_cache
    if _surname_variants_cache is not None:
        return _surname_variants_cache

    variants_path = Path(__file__).resolve().parent.parent / "data" / "surname_variants.json"
    lookup: dict[str, list[str]] = {}
    if variants_path.exists():
        try:
            with open(variants_path) as f:
                data = json.load(f)
            for group in data.get("variant_groups", []):
                canonical = group.get("canonical", "")
                all_names = [canonical] + group.get("variants", [])
                all_lower = [n.lower() for n in all_names if n]
                for name_lower in all_lower:
                    lookup[name_lower] = all_lower
        except Exception:
            logger.warning("Failed to load surname variants from %s", variants_path)

    _surname_variants_cache = lookup
    return lookup


SCHEMA_VERSION = 1


class IdentityState(Enum):
    """Identity lifecycle states."""

    INBOX = "INBOX"  # Awaiting human review (from ingest pipeline)
    PROPOSED = "PROPOSED"  # Initial state, accepts changes
    CONFIRMED = "CONFIRMED"  # Authoritative but reversible
    CONTESTED = "CONTESTED"  # Frozen until reviewed
    REJECTED = "REJECTED"  # Explicitly rejected (soft state, reversible)
    SKIPPED = "SKIPPED"  # Reviewed but deferred for later


class ActionType(Enum):
    """Event action types."""

    CREATE = "create"
    CANDIDATE_ADD = "candidate_add"
    CANDIDATE_REMOVE = "candidate_remove"
    NEGATIVE_ADD = "negative_add"
    PROMOTE = "promote"
    REJECT = "reject"
    UNREJECT = "unreject"
    CONFIRM = "confirm"
    CONTEST = "contest"
    SKIP = "skip"
    RESET = "reset"
    STATE_CHANGE = "state_change"
    UNDO = "undo"
    MERGE = "merge"
    UNDO_MERGE = "undo_merge"
    RENAME = "rename"
    DETACH = "detach"


class IdentityRegistry:
    """
    Manages identities with full provenance and reversibility.

    Identities are stored as metadata over immutable PFE embeddings.
    All changes are recorded in an append-only event log.
    """

    def __init__(self):
        self._identities: dict[str, dict] = {}
        self._history: list[dict] = []

    def create_identity(
        self,
        anchor_ids: list[str],
        user_source: str,
        name: str = None,
        candidate_ids: list[str] = None,
        state: IdentityState = None,
        provenance: dict = None,
    ) -> str:
        """
        Create a new identity.

        Args:
            anchor_ids: Initial confirmed face IDs
            user_source: Who/what initiated this action
            name: Optional human-readable name
            candidate_ids: Optional suggested matches
            state: Optional initial state (default: PROPOSED)
            provenance: Optional provenance metadata (job_id, source, etc.)

        Returns:
            identity_id
        """
        identity_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Default to PROPOSED if no state specified
        initial_state = state if state else IdentityState.PROPOSED

        # Default name: generate from identity_id if not provided
        if not name:
            name = f"Unidentified Person {identity_id[:8]}"

        identity = {
            "identity_id": identity_id,
            "name": name,
            "state": initial_state.value,
            "anchor_ids": list(anchor_ids),
            "candidate_ids": list(candidate_ids) if candidate_ids else [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": now,
            "updated_at": now,
            "provenance": provenance,
        }

        self._identities[identity_id] = identity

        # Record event
        self._record_event(
            identity_id=identity_id,
            action=ActionType.CREATE.value,
            face_ids=list(anchor_ids),
            user_source=user_source,
            previous_version_id=0,
        )

        return identity_id

    def get_identity(self, identity_id: str) -> dict:
        """Get identity by ID."""
        if identity_id not in self._identities:
            raise KeyError(f"Identity not found: {identity_id}")
        return self._identities[identity_id].copy()

    def get_anchor_face_ids(self, identity_id: str) -> list[str]:
        """
        Extract face IDs from anchors (handles both legacy and structured formats).

        Args:
            identity_id: Identity ID

        Returns:
            List of face ID strings
        """
        identity = self.get_identity(identity_id)
        face_ids = []
        for anchor in identity["anchor_ids"]:
            if isinstance(anchor, str):
                face_ids.append(anchor)
            elif isinstance(anchor, dict):
                face_ids.append(anchor["face_id"])
        return face_ids

    def get_candidate_face_ids(self, identity_id: str) -> list[str]:
        """
        Extract face IDs from candidates.

        Used for B2 thumbnail fallback when identity has no anchors.

        Args:
            identity_id: Identity ID

        Returns:
            List of face ID strings

        Raises:
            KeyError: If identity not found
        """
        identity = self.get_identity(identity_id)
        return list(identity.get("candidate_ids", []))

    @staticmethod
    def _face_id_from_entry(face_entry) -> str | None:
        """Normalize legacy/string and structured face entries to a face_id."""
        if isinstance(face_entry, str):
            return face_entry
        if isinstance(face_entry, dict):
            return face_entry.get("face_id")
        return None

    @classmethod
    def _face_id_set(cls, entries: list) -> set[str]:
        """Collect comparable face IDs from mixed anchor/candidate entry formats."""
        face_ids = set()
        for entry in entries:
            face_id = cls._face_id_from_entry(entry)
            if face_id:
                face_ids.add(face_id)
        return face_ids

    @staticmethod
    def _remove_candidate_by_face_id(identity: dict, face_id: str) -> None:
        """Remove a candidate entry matching face_id, regardless of entry format."""
        for candidate in list(identity.get("candidate_ids", [])):
            if IdentityRegistry._face_id_from_entry(candidate) == face_id:
                identity["candidate_ids"].remove(candidate)
                return

    def _remove_anchor_by_face_id(self, identity: dict, face_id: str) -> None:
        """Remove anchor entry by face_id (handles both string and dict formats)."""
        to_remove = None
        for anchor in identity["anchor_ids"]:
            if isinstance(anchor, str) and anchor == face_id:
                to_remove = anchor
                break
            elif isinstance(anchor, dict) and anchor.get("face_id") == face_id:
                to_remove = anchor
                break
        if to_remove is not None:
            identity["anchor_ids"].remove(to_remove)

    def get_history(self, identity_id: str) -> list[dict]:
        """Get event history for an identity."""
        return [e for e in self._history if e["identity_id"] == identity_id]

    def list_identities(
        self,
        state: IdentityState = None,
        include_merged: bool = False,
    ) -> list[dict]:
        """
        List all identities, optionally filtered by state.

        Args:
            state: Optional state filter (PROPOSED, CONFIRMED, CONTESTED)
            include_merged: If False (default), exclude merged identities

        Returns:
            List of identity dicts (copies, not references)
        """
        identities = list(self._identities.values())

        # Exclude merged identities by default
        if not include_merged:
            identities = [i for i in identities if not i.get("merged_into")]

        if state:
            identities = [i for i in identities if i["state"] == state.value]

        return [i.copy() for i in identities]

    def list_identities_by_job(self, job_id: str) -> list[dict]:
        """
        List all identities created by a specific ingestion job.

        Used for job cleanup to find all artifacts from a failed upload.

        Args:
            job_id: Ingestion job identifier

        Returns:
            List of identity dicts where provenance.job_id matches (copies)
        """
        results = []
        for identity in self._identities.values():
            provenance = identity.get("provenance")
            if provenance and provenance.get("job_id") == job_id:
                results.append(identity.copy())
        return results

    @staticmethod
    def _is_real_name(name: str | None) -> bool:
        """Check if a name is a real human-assigned name (not auto-generated)."""
        if not name:
            return False
        return not name.startswith("Unidentified Person ")

    def find_confirmed_by_name(self, name: str, exclude_id: str = "") -> dict | None:
        """Find an existing non-merged CONFIRMED identity with the given name.

        Args:
            name: Name to search for (case-insensitive, stripped)
            exclude_id: Identity ID to exclude from the search

        Returns:
            The matching identity dict, or None if not found.
        """
        if not name:
            return None
        target = name.strip().lower()
        for iid, identity in self._identities.items():
            if iid == exclude_id:
                continue
            if identity.get("merged_into"):
                continue
            if identity.get("state") != IdentityState.CONFIRMED.value:
                continue
            if (identity.get("name") or "").strip().lower() == target:
                return identity.copy()
        return None

    @staticmethod
    def _state_priority(state: str) -> int:
        """Return trust priority for a state (higher = more trusted)."""
        priorities = {
            "CONFIRMED": 4,
            "PROPOSED": 3,
            "INBOX": 2,
            "SKIPPED": 1,
            "CONTESTED": 0,
            "REJECTED": 0,
        }
        return priorities.get(state, 0)

    def resolve_merge_direction(self, id_a: str, id_b: str) -> dict:
        """
        Determine correct merge direction based on name/state/face count.

        Rules (in order):
        1. If both have real names -> name_conflict (caller must resolve)
        2. Named identity always becomes target (keeps name)
        3. Higher-trust state becomes target
        4. More faces becomes target (tiebreaker)
        5. Fall through: id_a is target (preserve caller intent)

        Returns:
            Dict with keys:
            - target_id, source_id: resolved direction
            - swapped: bool (True if direction was auto-corrected)
            - conflict: "name_conflict" | None
        """
        a = self._identities[id_a]
        b = self._identities[id_b]

        a_named = self._is_real_name(a.get("name"))
        b_named = self._is_real_name(b.get("name"))

        # Rule 4: Two real names -> conflict (unless identical)
        if a_named and b_named:
            a_name = (a.get("name") or "").strip()
            b_name = (b.get("name") or "").strip()
            if a_name.lower() == b_name.lower():
                # Same name — no conflict, use higher-state / more-faces tiebreak
                # but keep a as target (preserves caller intent, name is same)
                a_priority = self._state_priority(a.get("state", "INBOX"))
                b_priority = self._state_priority(b.get("state", "INBOX"))
                if b_priority > a_priority:
                    return {
                        "target_id": id_b,
                        "source_id": id_a,
                        "swapped": True,
                        "conflict": None,
                    }
                if a_priority > b_priority:
                    return {
                        "target_id": id_a,
                        "source_id": id_b,
                        "swapped": False,
                        "conflict": None,
                    }
                # Same state — more faces wins
                a_faces = len(a.get("anchor_ids", [])) + len(a.get("candidate_ids", []))
                b_faces = len(b.get("anchor_ids", [])) + len(b.get("candidate_ids", []))
                if b_faces > a_faces:
                    return {
                        "target_id": id_b,
                        "source_id": id_a,
                        "swapped": True,
                        "conflict": None,
                    }
                return {
                    "target_id": id_a,
                    "source_id": id_b,
                    "swapped": False,
                    "conflict": None,
                }
            return {
                "target_id": id_a,
                "source_id": id_b,
                "swapped": False,
                "conflict": "name_conflict",
            }

        # Rule 1: Named always wins
        if b_named and not a_named:
            # b should be target, a should be source -> swap
            return {
                "target_id": id_b,
                "source_id": id_a,
                "swapped": True,
                "conflict": None,
            }
        if a_named and not b_named:
            # a is already target -> no swap
            return {
                "target_id": id_a,
                "source_id": id_b,
                "swapped": False,
                "conflict": None,
            }

        # Both unnamed: Rule 2 - higher state wins
        a_priority = self._state_priority(a.get("state", "INBOX"))
        b_priority = self._state_priority(b.get("state", "INBOX"))

        if b_priority > a_priority:
            return {
                "target_id": id_b,
                "source_id": id_a,
                "swapped": True,
                "conflict": None,
            }
        if a_priority > b_priority:
            return {
                "target_id": id_a,
                "source_id": id_b,
                "swapped": False,
                "conflict": None,
            }

        # Rule 3: More faces wins (tiebreaker)
        a_faces = len(a.get("anchor_ids", [])) + len(a.get("candidate_ids", []))
        b_faces = len(b.get("anchor_ids", [])) + len(b.get("candidate_ids", []))

        if b_faces > a_faces:
            return {
                "target_id": id_b,
                "source_id": id_a,
                "swapped": True,
                "conflict": None,
            }

        # Default: preserve caller intent (a is target)
        return {
            "target_id": id_a,
            "source_id": id_b,
            "swapped": False,
            "conflict": None,
        }

    def merge_identities(
        self,
        source_id: str,
        target_id: str,
        user_source: str,
        photo_registry: "PhotoRegistry",
        resolved_name: str = None,
        auto_correct_direction: bool = True,
        allow_co_occurrence: bool = False,
    ) -> dict:
        """
        Merge source identity INTO target identity.

        Safety Foundation: Calls validate_merge() first - merge is blocked if
        the two identities have faces appearing in the same photo.

        Enhanced behavior:
        - Auto-corrects merge direction (named identity always survives)
        - Detects name conflicts (both identities named) and returns 'name_conflict'
        - Records merge_history on target for undo capability
        - Promotes target state if source had higher-trust state

        Args:
            source_id: Identity to be absorbed
            target_id: Identity to absorb source
            user_source: Who initiated this action
            photo_registry: For co-occurrence validation
            resolved_name: Name to use when both identities have names (resolves conflict)
            auto_correct_direction: If True, swap source/target based on name/state heuristics

        Returns:
            Dict with:
            - success: bool
            - reason: str (on failure: co_occurrence, already_merged, name_conflict)
            - source_id, target_id, faces_merged: (on success)
            - direction_swapped: bool (on success, True if direction was auto-corrected)
            - name_conflict_details: dict (when reason is name_conflict)

        Raises:
            KeyError: If either identity not found
        """
        # --- INSTRUMENTATION HOOK ---
        get_event_recorder().record(
            "MERGE", {"source_id": source_id, "target_id": target_id, "user_source": user_source}
        )
        # ----------------------------

        # Validate (Safety Foundation - co-occurrence override for collages, PRD-048)
        can_merge, reason = validate_merge(
            source_id,
            target_id,
            self,
            photo_registry,
            allow_co_occurrence=allow_co_occurrence,
        )

        if not can_merge:
            logger.warning(f"Merge blocked ({reason}): {source_id} -> {target_id}")
            return {
                "success": False,
                "reason": reason,
                "message": f"Merge blocked: {reason}",
            }

        # Check if source is already merged (check both before direction swap)
        if self._identities[source_id].get("merged_into"):
            return {
                "success": False,
                "reason": "already_merged",
                "message": f"Source identity already merged into {self._identities[source_id]['merged_into']}",
            }
        if self._identities[target_id].get("merged_into"):
            return {
                "success": False,
                "reason": "already_merged",
                "message": f"Target identity already merged into {self._identities[target_id]['merged_into']}",
            }

        # Resolve merge direction
        direction_swapped = False
        if auto_correct_direction:
            resolution = self.resolve_merge_direction(target_id, source_id)

            # Check for name conflict
            if resolution["conflict"] == "name_conflict" and not resolved_name:
                # Return conflict details for the UI to handle
                target_data = self._identities[target_id]
                source_data = self._identities[source_id]
                return {
                    "success": False,
                    "reason": "name_conflict",
                    "message": "Both identities have names. Please choose which name to keep.",
                    "name_conflict_details": {
                        "identity_a": {
                            "id": target_id,
                            "name": target_data.get("name"),
                            "face_count": len(target_data.get("anchor_ids", []))
                            + len(target_data.get("candidate_ids", [])),
                            "state": target_data.get("state"),
                        },
                        "identity_b": {
                            "id": source_id,
                            "name": source_data.get("name"),
                            "face_count": len(source_data.get("anchor_ids", []))
                            + len(source_data.get("candidate_ids", [])),
                            "state": source_data.get("state"),
                        },
                    },
                }

            # Apply direction correction
            actual_target_id = resolution["target_id"]
            actual_source_id = resolution["source_id"]
            direction_swapped = resolution["swapped"]
        else:
            actual_target_id = target_id
            actual_source_id = source_id

        source = self._identities[actual_source_id]
        target = self._identities[actual_target_id]

        previous_version = target["version_id"]
        faces_merged = 0

        # Track which faces are being added (for merge_history / undo)
        anchors_added = []
        candidates_added = []
        negatives_added = []

        # Collect all existing face IDs in target to prevent duplicates (Lesson 118)
        target_anchor_face_ids = self._face_id_set(target.get("anchor_ids", []))
        target_candidate_face_ids = self._face_id_set(target.get("candidate_ids", []))
        target_all_faces = target_anchor_face_ids | target_candidate_face_ids

        # Move anchors from source to target
        for anchor in source["anchor_ids"]:
            anchor_face_id = self._face_id_from_entry(anchor)
            if not anchor_face_id:
                continue

            if anchor_face_id not in target_all_faces:
                target["anchor_ids"].append(anchor)
                anchors_added.append(anchor)
                target_all_faces.add(anchor_face_id)
                target_anchor_face_ids.add(anchor_face_id)
                faces_merged += 1
            elif anchor_face_id in target_candidate_face_ids:
                # Promote from candidate to anchor (anchor takes precedence)
                self._remove_candidate_by_face_id(target, anchor_face_id)
                target_candidate_face_ids.discard(anchor_face_id)
                if anchor_face_id not in target_anchor_face_ids:
                    target["anchor_ids"].append(anchor)
                    anchors_added.append(anchor)
                    target_anchor_face_ids.add(anchor_face_id)
                    faces_merged += 1

        # Move candidates from source to target
        for candidate in source["candidate_ids"]:
            candidate_face_id = self._face_id_from_entry(candidate)
            if not candidate_face_id:
                continue

            if candidate_face_id not in target_all_faces:
                target["candidate_ids"].append(candidate)
                candidates_added.append(candidate)
                target_all_faces.add(candidate_face_id)
                target_candidate_face_ids.add(candidate_face_id)
                faces_merged += 1

        # Preserve negative evidence
        for negative in source.get("negative_ids", []):
            if negative not in target.get("negative_ids", []):
                target.setdefault("negative_ids", []).append(negative)
                negatives_added.append(negative)

        # Mark source as merged (soft delete)
        now = datetime.now(timezone.utc).isoformat()
        source["merged_into"] = actual_target_id
        source["updated_at"] = now

        # State promotion: target gets max(target.state, source.state)
        source_priority = self._state_priority(source.get("state", "INBOX"))
        target_priority = self._state_priority(target.get("state", "INBOX"))
        if source_priority > target_priority:
            target["state"] = source["state"]

        # If a resolved_name was provided (name conflict resolution), apply it
        if resolved_name:
            target["name"] = resolved_name

        # Update target version
        target["version_id"] += 1
        target["updated_at"] = now

        # Record merge_history on target for undo capability (BE-005: full audit)
        merge_history_entry = {
            "merge_event_id": str(uuid.uuid4()),
            "timestamp": now,
            "source_id": actual_source_id,
            "source_name": source.get("name"),
            "source_state": source.get("state"),
            "source_snapshot": {
                "anchor_ids": list(source.get("anchor_ids", [])),
                "candidate_ids": list(source.get("candidate_ids", [])),
                "negative_ids": list(source.get("negative_ids", [])),
                "name": source.get("name"),
                "state": source.get("state"),
                "first_name": source.get("first_name", ""),
                "last_name": source.get("last_name", ""),
            },
            "target_snapshot_before": {
                "anchor_count": len(target.get("anchor_ids", [])) - len(anchors_added),
                "candidate_count": len(target.get("candidate_ids", [])) - len(candidates_added),
                "name": target.get("name"),
                "state": target.get("state"),
            },
            "faces_added": {
                "anchors": anchors_added,
                "candidates": candidates_added,
                "negatives": negatives_added,
            },
            "direction_auto_corrected": direction_swapped,
            "merged_by": user_source,
        }
        target.setdefault("merge_history", []).append(merge_history_entry)

        # Record merge event in global history
        self._record_event(
            identity_id=actual_target_id,
            action=ActionType.MERGE.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={
                "source_identity_id": actual_source_id,
                "faces_merged": faces_merged,
                "direction_swapped": direction_swapped,
                "merge_event_id": merge_history_entry["merge_event_id"],
            },
        )

        logger.info(
            f"Merged identity {actual_source_id} into {actual_target_id} "
            f"({faces_merged} faces transferred, swapped={direction_swapped})"
        )

        # POST-MERGE VERIFICATION (Session 131 — Lesson 154)
        # Verify ALL source faces are now in the target. If any are missing,
        # the merge succeeded in-memory but may fail to persist to Supabase.
        #
        # IMPORTANT (Codex P1-1): This reads source.anchor_ids/candidate_ids AFTER
        # merged_into is set (line 673). This works because merge never clears the
        # source lists — it only copies faces to the target. If a future change
        # clears source lists during merge, this safety net would silently break.
        # The source lists MUST remain populated for this verification to work.
        target_face_set = self._face_id_set(target.get("anchor_ids", [])) | self._face_id_set(
            target.get("candidate_ids", [])
        )
        source_face_ids = [self._face_id_from_entry(a) for a in source.get("anchor_ids", [])] + [
            self._face_id_from_entry(c) for c in source.get("candidate_ids", [])
        ]
        source_face_ids = [f for f in source_face_ids if f]
        orphaned = [f for f in source_face_ids if f not in target_face_set]
        if orphaned:
            logger.error(
                f"MERGE VERIFICATION FAILED: {len(orphaned)} faces from "
                f"{actual_source_id} not found in target {actual_target_id}: "
                f"{orphaned[:5]}{'...' if len(orphaned) > 5 else ''}"
            )
            # Force-add the orphaned faces to prevent data loss
            for fid in orphaned:
                target["anchor_ids"].append(fid)
                faces_merged += 1
            logger.warning(f"Force-added {len(orphaned)} orphaned faces to target {actual_target_id}")

        return {
            "success": True,
            "reason": "ok",
            "source_id": actual_source_id,
            "target_id": actual_target_id,
            "faces_merged": faces_merged,
            "direction_swapped": direction_swapped,
        }

    def undo_merge(self, identity_id: str, user_source: str) -> dict:
        """
        Undo the most recent merge on an identity.

        Reads the last entry from merge_history, removes the merged faces
        from the target, and restores the source identity.

        Args:
            identity_id: The target identity (that absorbed faces)
            user_source: Who initiated this undo

        Returns:
            Dict with:
            - success: bool
            - reason: str (on failure)
            - source_id: restored identity ID (on success)
            - faces_removed: number of faces moved back (on success)
        """
        target = self._identities.get(identity_id)
        if not target:
            return {"success": False, "reason": "not_found", "message": "Identity not found."}

        merge_history = target.get("merge_history", [])
        if not merge_history:
            return {"success": False, "reason": "no_merge_history", "message": "No merges to undo."}

        # Get the most recent merge
        last_merge = merge_history[-1]
        source_id = last_merge["source_id"]

        # Verify source still exists
        source = self._identities.get(source_id)
        if not source:
            return {"success": False, "reason": "source_not_found", "message": "Source identity no longer exists."}

        # Check that target itself is not merged into something else
        if target.get("merged_into"):
            return {
                "success": False,
                "reason": "target_is_merged",
                "message": "Cannot undo: this identity has been merged into another.",
            }

        faces_removed = 0
        faces_added = last_merge.get("faces_added", {})

        # Remove anchors that came from the merge (handle partial detach gracefully)
        for anchor in faces_added.get("anchors", []):
            if anchor in target["anchor_ids"]:
                target["anchor_ids"].remove(anchor)
                faces_removed += 1

        # Remove candidates that came from the merge
        for candidate in faces_added.get("candidates", []):
            if candidate in target["candidate_ids"]:
                target["candidate_ids"].remove(candidate)
                faces_removed += 1

        # Remove negatives that came from the merge
        for negative in faces_added.get("negatives", []):
            neg_list = target.get("negative_ids", [])
            if negative in neg_list:
                neg_list.remove(negative)

        # Restore source identity (clear merged_into)
        now = datetime.now(timezone.utc).isoformat()
        source.pop("merged_into", None)
        source["updated_at"] = now

        # Remove the merge_history entry
        merge_history.pop()

        # Update target version
        previous_version = target["version_id"]
        target["version_id"] += 1
        target["updated_at"] = now

        # Record undo event
        self._record_event(
            identity_id=identity_id,
            action=ActionType.UNDO_MERGE.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={
                "restored_source_id": source_id,
                "faces_removed": faces_removed,
                "merge_event_id": last_merge.get("merge_event_id"),
            },
        )

        logger.info(f"Undid merge on {identity_id}: restored {source_id} ({faces_removed} faces moved back)")

        return {
            "success": True,
            "reason": "ok",
            "source_id": source_id,
            "faces_removed": faces_removed,
        }

    def confirm_identity(self, identity_id: str, user_source: str) -> None:
        """
        Transition identity to CONFIRMED state.

        Can be called from INBOX or PROPOSED states.

        Args:
            identity_id: Identity ID
            user_source: Who initiated this action

        Raises:
            KeyError: If identity not found
            ValueError: If identity is not in INBOX or PROPOSED state
        """
        # --- INSTRUMENTATION HOOK ---
        get_event_recorder().record("CONFIRM", {"identity_id": identity_id, "user_source": user_source})
        # ----------------------------

        identity = self._identities[identity_id]

        # Only allow confirmation from reviewable states (INBOX, PROPOSED, SKIPPED)
        allowed_states = {IdentityState.INBOX.value, IdentityState.PROPOSED.value, IdentityState.SKIPPED.value}
        if identity["state"] not in allowed_states:
            raise ValueError(
                f"Identity {identity_id} cannot be confirmed from state "
                f"'{identity['state']}' (must be INBOX, PROPOSED, or SKIPPED)"
            )
        # Session 138 FB-006: Allow confirming unidentified persons.
        # User workflow: confirm cluster as real person first, identify (name) later.

        # Check for duplicate confirmed name (prevent creating two CONFIRMED
        # identities with the same REAL name — user should merge instead)
        # Skip this check for unidentified/placeholder names
        identity_name = identity.get("name", "")
        if self._is_real_name(identity_name):
            dup = self.find_confirmed_by_name(identity_name, exclude_id=identity_id)
            if dup:
                raise ValueError(
                    f"Another confirmed identity already has the name "
                    f"'{identity_name}' (ID: {dup['identity_id'][:8]}...). "
                    f"Merge instead of confirming a duplicate."
                )

        previous_state = identity["state"]
        previous_version = identity["version_id"]

        identity["state"] = IdentityState.CONFIRMED.value
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.STATE_CHANGE.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={
                "new_state": IdentityState.CONFIRMED.value,
                "previous_state": previous_state,
            },
        )

    def move_to_proposed(self, identity_id: str, user_source: str) -> None:
        """
        Transition identity from INBOX to PROPOSED state.

        Used when a user reviews an inbox item and moves it to the main workflow.

        Args:
            identity_id: Identity ID
            user_source: Who initiated this action

        Raises:
            KeyError: If identity not found
            ValueError: If identity is not in INBOX state
        """
        identity = self._identities[identity_id]

        if identity["state"] != IdentityState.INBOX.value:
            raise ValueError(f"Identity {identity_id} is not in INBOX state (current: {identity['state']})")

        previous_version = identity["version_id"]

        identity["state"] = IdentityState.PROPOSED.value
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.STATE_CHANGE.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={
                "new_state": IdentityState.PROPOSED.value,
                "previous_state": IdentityState.INBOX.value,
            },
        )

    def reject_identity(self, identity_id: str, user_source: str) -> None:
        """
        Transition identity from INBOX to REJECTED state.

        Used when a user explicitly rejects an inbox item during review.
        This is a soft state - the identity and its embeddings are preserved.

        Args:
            identity_id: Identity ID
            user_source: Who initiated this action

        Raises:
            KeyError: If identity not found
            ValueError: If identity is not in INBOX state
        """
        # --- INSTRUMENTATION HOOK ---
        get_event_recorder().record("REJECT_IDENTITY", {"identity_id": identity_id, "user_source": user_source})
        # ----------------------------

        identity = self._identities[identity_id]

        # Allow rejection from reviewable states (INBOX, PROPOSED, SKIPPED)
        allowed_states = {IdentityState.INBOX.value, IdentityState.PROPOSED.value, IdentityState.SKIPPED.value}
        if identity["state"] not in allowed_states:
            raise ValueError(
                f"Identity {identity_id} cannot be rejected from state "
                f"'{identity['state']}' (must be INBOX, PROPOSED, or SKIPPED)"
            )

        previous_state = identity["state"]
        previous_version = identity["version_id"]

        identity["state"] = IdentityState.REJECTED.value
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.STATE_CHANGE.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={
                "new_state": IdentityState.REJECTED.value,
                "previous_state": previous_state,
            },
        )

    def skip_identity(self, identity_id: str, user_source: str) -> None:
        """
        Transition identity to SKIPPED state (reviewed but deferred).

        Can be called from any reviewable state (INBOX, PROPOSED).
        This is a soft state - the identity can be returned to review later.

        Args:
            identity_id: Identity ID
            user_source: Who initiated this action

        Raises:
            KeyError: If identity not found
            ValueError: If identity is not in a reviewable state
        """
        get_event_recorder().record("SKIP_IDENTITY", {"identity_id": identity_id, "user_source": user_source})

        identity = self._identities[identity_id]

        # Allow skip from reviewable states
        reviewable_states = {IdentityState.INBOX.value, IdentityState.PROPOSED.value}
        if identity["state"] not in reviewable_states:
            raise ValueError(
                f"Identity {identity_id} cannot be skipped from state '{identity['state']}' (must be INBOX or PROPOSED)"
            )

        previous_state = identity["state"]
        previous_version = identity["version_id"]

        identity["state"] = IdentityState.SKIPPED.value
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.SKIP.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={
                "new_state": IdentityState.SKIPPED.value,
                "previous_state": previous_state,
            },
        )

    def reset_identity(self, identity_id: str, user_source: str) -> None:
        """
        Reset identity back to INBOX state for re-review.

        Can be called from any terminal state (CONFIRMED, SKIPPED, REJECTED, CONTESTED).
        This enables full reversibility of all workflow actions.

        Args:
            identity_id: Identity ID
            user_source: Who initiated this action

        Raises:
            KeyError: If identity not found
            ValueError: If identity is already in a reviewable state
        """
        get_event_recorder().record("RESET_IDENTITY", {"identity_id": identity_id, "user_source": user_source})

        identity = self._identities[identity_id]

        # Allow reset from terminal states back to INBOX
        terminal_states = {
            IdentityState.CONFIRMED.value,
            IdentityState.SKIPPED.value,
            IdentityState.REJECTED.value,
            IdentityState.CONTESTED.value,
        }
        if identity["state"] not in terminal_states:
            raise ValueError(
                f"Identity {identity_id} cannot be reset from state '{identity['state']}' (already in review queue)"
            )

        previous_state = identity["state"]
        previous_version = identity["version_id"]

        identity["state"] = IdentityState.INBOX.value
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.RESET.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={
                "new_state": IdentityState.INBOX.value,
                "previous_state": previous_state,
            },
        )

    def force_state(self, identity_id: str, new_state: str, user_source: str, reason: str | None = None) -> str:
        """Force an identity into a specific valid state while preserving history."""
        get_event_recorder().record(
            "FORCE_STATE_CHANGE",
            {
                "identity_id": identity_id,
                "new_state": new_state,
                "user_source": user_source,
                "reason": reason or "",
            },
        )

        valid_states = {state.value for state in IdentityState}
        if new_state not in valid_states:
            raise ValueError(f"Invalid state: {new_state}")

        identity = self._identities[identity_id]
        previous_state = identity["state"]
        if previous_state == new_state:
            return previous_state

        previous_version = identity["version_id"]
        identity["state"] = new_state
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        metadata = {
            "new_state": new_state,
            "previous_state": previous_state,
            "forced": True,
        }
        if reason:
            metadata["reason"] = reason

        self._record_event(
            identity_id=identity_id,
            action=ActionType.STATE_CHANGE.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata=metadata,
        )
        return previous_state

    def rename_identity(
        self,
        identity_id: str,
        new_name: str,
        user_source: str,
        annotation_id: str = "",
    ) -> str:
        """
        Rename an identity.

        Args:
            identity_id: Identity ID
            new_name: New name (will be stripped, max 100 chars)
            user_source: Who initiated this action

        Returns:
            The previous name (for audit trail)

        Raises:
            KeyError: If identity not found
            ValueError: If new_name is empty after stripping
        """
        identity = self._identities[identity_id]

        # Validate and sanitize
        new_name = new_name.strip()[:100] if new_name else ""
        if not new_name:
            raise ValueError("Name cannot be empty")

        # If identity is already CONFIRMED, check for duplicate name
        if identity.get("state") == IdentityState.CONFIRMED.value:
            dup = self.find_confirmed_by_name(new_name, exclude_id=identity_id)
            if dup:
                raise ValueError(
                    f"Another confirmed identity already has the name "
                    f"'{new_name}' (ID: {dup['identity_id'][:8]}...). "
                    f"Merge instead of renaming."
                )

        # Auto-parse structured name fields (BE-010)
        parts = new_name.rsplit(" ", 1)
        if len(parts) == 2:
            parsed_first_name = parts[0]
            parsed_last_name = parts[1]
        else:
            parsed_first_name = new_name
            parsed_last_name = ""

        previous_name = identity.get("name")
        if previous_name == new_name:
            identity["first_name"] = parsed_first_name
            identity["last_name"] = parsed_last_name
            return previous_name

        previous_version = identity["version_id"]

        identity["name"] = new_name
        identity["first_name"] = parsed_first_name
        identity["last_name"] = parsed_last_name
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        rename_metadata = {
            "previous_name": previous_name,
            "new_name": new_name,
        }
        if annotation_id:
            rename_metadata["annotation_id"] = annotation_id

        self._record_event(
            identity_id=identity_id,
            action=ActionType.RENAME.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata=rename_metadata,
        )

        return previous_name

    def set_metadata(
        self,
        identity_id: str,
        metadata: dict,
        user_source: str,
    ) -> None:
        """
        Set metadata fields on an identity (BE-011).

        All metadata fields are optional. Only provided keys are updated.
        Valid keys: birth_year, death_year, birth_place, death_place,
                    maiden_name, generation_qualifier, alternate_names,
                    relationship_notes, bio, name_source.

        Args:
            identity_id: Identity ID
            metadata: Dict of metadata fields to set
            user_source: Who initiated this action
        """
        identity = self._identities[identity_id]
        valid_keys = {
            "birth_year",
            "death_year",
            "birth_place",
            "death_place",
            "birth_date_full",
            "death_date_full",
            "gender",
            "maiden_name",
            "generation_qualifier",
            "alternate_names",
            "relationship_notes",
            "bio",
            "name_source",
            "first_name",
            "last_name",
        }
        for key, value in metadata.items():
            if key in valid_keys:
                identity[key] = value

        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

    def detach_face(
        self,
        identity_id: str,
        face_id: str,
        user_source: str,
    ) -> dict:
        """
        Detach a face from an identity into a new identity.

        This is the reverse of merge - useful for correcting grouping errors.
        The detached face becomes the sole anchor of a new identity.

        Args:
            identity_id: Source identity ID
            face_id: Face ID to detach
            user_source: Who initiated this action

        Returns:
            Dict with:
            - success: bool
            - reason: str (on failure: "only_face", "face_not_found")
            - from_identity_id, to_identity_id, face_id: (on success)

        Raises:
            KeyError: If identity not found
        """
        identity = self._identities[identity_id]

        # Get all face IDs in this identity (anchors + candidates)
        all_face_ids = self.get_all_face_ids(identity_id)

        # Check if face exists in identity
        if face_id not in all_face_ids:
            return {
                "success": False,
                "reason": "face_not_found",
                "message": f"Face {face_id} not found in identity {identity_id}",
            }

        # Cannot detach the only face
        if len(all_face_ids) <= 1:
            return {
                "success": False,
                "reason": "only_face",
                "message": "Cannot detach the only face from an identity",
            }

        previous_version = identity["version_id"]

        # Remove face from source identity (handles both string and dict formats)
        self._remove_anchor_by_face_id(identity, face_id)

        # Also check candidates
        if face_id in identity["candidate_ids"]:
            identity["candidate_ids"].remove(face_id)

        # Create new identity with the detached face
        new_identity_id = self.create_identity(
            anchor_ids=[face_id],
            user_source=user_source,
        )

        # Update source identity version
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Record detach event on source identity
        self._record_event(
            identity_id=identity_id,
            action=ActionType.DETACH.value,
            face_ids=[face_id],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={
                "to_identity_id": new_identity_id,
            },
        )

        logger.info(f"Detached face {face_id} from {identity_id} into new identity {new_identity_id}")

        return {
            "success": True,
            "reason": "ok",
            "from_identity_id": identity_id,
            "to_identity_id": new_identity_id,
            "face_id": face_id,
        }

    def contest_identity(
        self,
        identity_id: str,
        user_source: str,
        reason: str = None,
    ) -> None:
        """Transition identity to CONTESTED state."""
        identity = self._identities[identity_id]
        previous_version = identity["version_id"]

        identity["state"] = IdentityState.CONTESTED.value
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.STATE_CHANGE.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={"new_state": IdentityState.CONTESTED.value, "reason": reason},
        )

    def promote_candidate(
        self,
        identity_id: str,
        face_id: str,
        user_source: str,
        confidence_weight: float = 1.0,
        era_bin: str = None,
    ) -> None:
        """
        Move a candidate to anchor_ids.

        This is a human-confirmed action that affects fusion math.

        Args:
            identity_id: Identity ID
            face_id: Face ID to promote
            user_source: Who initiated this
            confidence_weight: Weight for fusion (default 1.0)
            era_bin: Optional era classification (e.g., "1910-1930")
        """
        identity = self._identities[identity_id]
        previous_version = identity["version_id"]

        if face_id not in identity["candidate_ids"]:
            raise ValueError(f"Face {face_id} is not a candidate for {identity_id}")

        identity["candidate_ids"].remove(face_id)

        # Create structured anchor entry
        anchor_entry = {
            "face_id": face_id,
            "weight": confidence_weight,
        }
        if era_bin:
            anchor_entry["era_bin"] = era_bin

        identity["anchor_ids"].append(anchor_entry)
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.PROMOTE.value,
            face_ids=[face_id],
            user_source=user_source,
            previous_version_id=previous_version,
            confidence_weight=confidence_weight,
        )

    def reject_candidate(
        self,
        identity_id: str,
        face_id: str,
        user_source: str,
    ) -> None:
        """
        Move a candidate to negative_ids.

        Negative evidence is stored but does not affect anchor fusion.
        """
        identity = self._identities[identity_id]
        previous_version = identity["version_id"]

        if face_id not in identity["candidate_ids"]:
            raise ValueError(f"Face {face_id} is not a candidate for {identity_id}")

        identity["candidate_ids"].remove(face_id)
        identity["negative_ids"].append(face_id)
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.REJECT.value,
            face_ids=[face_id],
            user_source=user_source,
            previous_version_id=previous_version,
        )

    def add_candidate_face(
        self,
        identity_id: str,
        face_id: str,
        user_source: str,
        metadata: dict | None = None,
    ) -> bool:
        """Append a candidate face with audit history if it is not already present."""
        identity = self._identities[identity_id]
        if face_id in self._face_id_set(identity.get("anchor_ids", [])):
            return False
        if face_id in self._face_id_set(identity.get("candidate_ids", [])):
            return False

        previous_version = identity["version_id"]
        identity.setdefault("candidate_ids", []).append(face_id)
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.CANDIDATE_ADD.value,
            face_ids=[face_id],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata=metadata or {},
        )
        return True

    def remove_candidate_face(
        self,
        identity_id: str,
        face_id: str,
        user_source: str,
        metadata: dict | None = None,
    ) -> bool:
        """Remove a candidate face with audit history if present."""
        identity = self._identities[identity_id]
        if face_id not in self._face_id_set(identity.get("candidate_ids", [])):
            return False

        previous_version = identity["version_id"]
        self._remove_candidate_by_face_id(identity, face_id)
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.CANDIDATE_REMOVE.value,
            face_ids=[face_id],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata=metadata or {},
        )
        return True

    def add_negative_reference(
        self,
        identity_id: str,
        negative_ref: str,
        user_source: str,
        metadata: dict | None = None,
    ) -> bool:
        """Append a negative reference with audit history if it is not already present."""
        identity = self._identities[identity_id]
        if negative_ref in identity.get("negative_ids", []):
            return False

        previous_version = identity["version_id"]
        identity.setdefault("negative_ids", []).append(negative_ref)
        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        event_metadata = {"negative_ref": negative_ref}
        if metadata:
            event_metadata.update(metadata)

        self._record_event(
            identity_id=identity_id,
            action=ActionType.NEGATIVE_ADD.value,
            face_ids=[],
            user_source=user_source,
            previous_version_id=previous_version,
            metadata=event_metadata,
        )
        return True

    def reject_identity_pair(
        self,
        source_id: str,
        target_id: str,
        user_source: str,
    ) -> None:
        """
        Record that two identities are NOT the same person.

        This is a strong negative signal from "Not Same Person" action (D2).
        Stored bidirectionally: A rejects B means B also rejects A.
        Rejected pairs will not appear in find_nearest_neighbors.

        Uses "identity:" prefix to distinguish from face_id rejections.

        Args:
            source_id: Identity making the rejection (user was viewing this)
            target_id: Identity being rejected as "not same person"
            user_source: Who initiated this action

        Raises:
            KeyError: If either identity not found
        """

        # --- INSTRUMENTATION HOOK ---
        get_event_recorder().record(
            "REJECT", {"source_id": source_id, "target_id": target_id, "user_source": user_source}
        )
        # ----------------------------

        # Validate both identities exist (will raise KeyError if not)
        source = self._identities[source_id]
        target = self._identities[target_id]

        now = datetime.now(timezone.utc).isoformat()
        previous_version_source = source["version_id"]
        previous_version_target = target["version_id"]

        # Add to negative_ids with identity: prefix (idempotent)
        source_negative = f"identity:{target_id}"
        target_negative = f"identity:{source_id}"

        if source_negative not in source["negative_ids"]:
            source["negative_ids"].append(source_negative)
            source["version_id"] += 1
            source["updated_at"] = now

            self._record_event(
                identity_id=source_id,
                action=ActionType.REJECT.value,
                face_ids=[],
                user_source=user_source,
                previous_version_id=previous_version_source,
                metadata={"rejected_identity_id": target_id, "type": "identity_pair"},
            )

        if target_negative not in target["negative_ids"]:
            target["negative_ids"].append(target_negative)
            target["version_id"] += 1
            target["updated_at"] = now

            self._record_event(
                identity_id=target_id,
                action=ActionType.REJECT.value,
                face_ids=[],
                user_source=user_source,
                previous_version_id=previous_version_target,
                metadata={"rejected_identity_id": source_id, "type": "identity_pair"},
            )

    def unreject_identity_pair(
        self,
        source_id: str,
        target_id: str,
        user_source: str,
    ) -> None:
        """
        Remove the bidirectional identity rejection between two identities.

        This is the "Undo" action for "Not Same Person" (D5).
        After unreject, the pair will appear in find_nearest_neighbors again.

        Idempotent: does nothing if pair was not rejected.

        Args:
            source_id: Identity making the unreject (user was viewing this)
            target_id: Identity being unrejected
            user_source: Who initiated this action

        Raises:
            KeyError: If either identity not found
        """
        # --- INSTRUMENTATION HOOK ---
        get_event_recorder().record(
            "UNREJECT", {"source_id": source_id, "target_id": target_id, "user_source": user_source}
        )
        # ----------------------------

        # Validate both identities exist (will raise KeyError if not)
        source = self._identities[source_id]
        target = self._identities[target_id]

        now = datetime.now(timezone.utc).isoformat()

        # Remove from negative_ids with identity: prefix (idempotent)
        source_negative = f"identity:{target_id}"
        target_negative = f"identity:{source_id}"

        if source_negative in source["negative_ids"]:
            previous_version_source = source["version_id"]
            source["negative_ids"].remove(source_negative)
            source["version_id"] += 1
            source["updated_at"] = now

            self._record_event(
                identity_id=source_id,
                action=ActionType.UNREJECT.value,
                face_ids=[],
                user_source=user_source,
                previous_version_id=previous_version_source,
                metadata={"unrejected_identity_id": target_id, "type": "identity_pair"},
            )

        if target_negative in target["negative_ids"]:
            previous_version_target = target["version_id"]
            target["negative_ids"].remove(target_negative)
            target["version_id"] += 1
            target["updated_at"] = now

            self._record_event(
                identity_id=target_id,
                action=ActionType.UNREJECT.value,
                face_ids=[],
                user_source=user_source,
                previous_version_id=previous_version_target,
                metadata={"unrejected_identity_id": source_id, "type": "identity_pair"},
            )

    def is_identity_rejected(self, id_a: str, id_b: str) -> bool:
        """
        Check if two identities have been rejected as "not same person".

        Args:
            id_a: First identity ID
            id_b: Second identity ID

        Returns:
            True if pair has been rejected, False otherwise.
        """
        try:
            identity_a = self.get_identity(id_a)
            return f"identity:{id_b}" in identity_a.get("negative_ids", [])
        except KeyError:
            return False

    def undo(self, identity_id: str, user_source: str) -> None:
        """
        Undo the most recent reversible action.

        Skips over undo events and already-undone actions to find the
        last action that can be reversed.
        """
        identity = self._identities[identity_id]
        history = self.get_history(identity_id)

        if len(history) < 2:
            raise ValueError("Nothing to undo")

        # Find the last undoable action (skip undos and already-undone actions)
        undone_event_ids = set()
        for evt in history:
            if evt["action"] == ActionType.UNDO.value:
                # Track which event was undone by this undo
                undone_ref = evt["metadata"].get("undone_event_id")
                if undone_ref:
                    undone_event_ids.add(undone_ref)

        # Find last undoable event (not an undo, not already undone)
        target_event = None
        for i in range(len(history) - 1, -1, -1):
            evt = history[i]
            if evt["action"] == ActionType.UNDO.value:
                continue
            if evt["event_id"] in undone_event_ids:
                continue
            if evt["action"] == ActionType.CREATE.value:
                # Can't undo create
                continue
            target_event = evt
            break

        if target_event is None:
            raise ValueError("Nothing to undo")

        previous_version = identity["version_id"]

        # Reverse the action
        if target_event["action"] == ActionType.PROMOTE.value:
            face_id = target_event["face_ids"][0]
            # Remove from anchors (handles both string and dict formats)
            self._remove_anchor_by_face_id(identity, face_id)
            if face_id not in identity["candidate_ids"]:
                identity["candidate_ids"].append(face_id)

        elif target_event["action"] == ActionType.CANDIDATE_ADD.value:
            face_id = target_event["face_ids"][0]
            self._remove_candidate_by_face_id(identity, face_id)

        elif target_event["action"] == ActionType.CANDIDATE_REMOVE.value:
            face_id = target_event["face_ids"][0]
            if face_id not in self._face_id_set(identity.get("candidate_ids", [])):
                identity.setdefault("candidate_ids", []).append(face_id)

        elif target_event["action"] == ActionType.NEGATIVE_ADD.value:
            negative_ref = (target_event.get("metadata") or {}).get("negative_ref")
            if negative_ref in identity.get("negative_ids", []):
                identity["negative_ids"].remove(negative_ref)

        elif target_event["action"] == ActionType.REJECT.value:
            face_id = target_event["face_ids"][0]
            if face_id in identity["negative_ids"]:
                identity["negative_ids"].remove(face_id)
            if face_id not in identity["candidate_ids"]:
                identity["candidate_ids"].append(face_id)

        elif target_event["action"] == ActionType.STATE_CHANGE.value:
            # Restore previous state by finding the state before this change
            prev_state = None
            for i in range(len(history) - 1, -1, -1):
                evt = history[i]
                if evt["event_id"] == target_event["event_id"]:
                    continue
                if evt["event_id"] in undone_event_ids:
                    continue
                if evt["action"] == ActionType.STATE_CHANGE.value:
                    prev_state = evt["metadata"].get("new_state")
                    break
                elif evt["action"] == ActionType.CREATE.value:
                    prev_state = IdentityState.PROPOSED.value
                    break
            if prev_state:
                identity["state"] = prev_state

        identity["version_id"] += 1
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()

        self._record_event(
            identity_id=identity_id,
            action=ActionType.UNDO.value,
            face_ids=target_event.get("face_ids", []),
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={
                "undone_action": target_event["action"],
                "undone_event_id": target_event["event_id"],
            },
        )

    def save(self, path: Path, backup_dir: Path = None) -> None:
        """
        Save registry to JSON file with atomic write and file locking.

        Guarantees:
        - Atomic: writes to temp file, fsyncs, then renames
        - Locked: exclusive lock prevents concurrent writes
        - Backed up: creates timestamped backup before overwrite

        Args:
            path: Target file path
            backup_dir: Optional directory for backups (default: path.parent/backups)
        """

        data = {
            "schema_version": SCHEMA_VERSION,
            "identities": self._identities,
            "history": self._history,
        }

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if file exists
        if path.exists():
            self._create_backup(path, backup_dir)

        # Atomic write with file locking
        self._atomic_write(path, data)

    def _create_backup(self, path: Path, backup_dir: Path = None) -> None:
        """Create timestamped backup of existing file."""
        import shutil

        if backup_dir is None:
            backup_dir = path.parent / "backups"

        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        backup_path = backup_dir / f"{path.name}.{timestamp}"

        shutil.copy2(path, backup_path)

    def _atomic_write(self, path: Path, data: dict) -> None:
        """
        Atomically write data to file.

        Single Writer Boundary: ALL writes flow through this method.

        Steps:
        1. Acquire exclusive lock on lock file
        2. Write to temp file
        3. fsync to ensure data is on disk
        4. Atomic rename to target path
        """
        import os

        import portalocker

        lock_path = path.with_suffix(".lock")
        temp_path = path.with_suffix(".tmp")

        # Ensure lock file exists
        lock_path.touch(exist_ok=True)

        # Acquire exclusive lock
        with open(lock_path, "r+") as lock_file:
            portalocker.lock(lock_file, portalocker.LOCK_EX)

            try:
                # Write to temp file
                with open(temp_path, "w") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                # Atomic rename
                os.rename(temp_path, path)

            finally:
                portalocker.unlock(lock_file)

    @classmethod
    def load_from_postgres(cls) -> "IdentityRegistry | None":
        """Load registry from Supabase Postgres.

        Queries the identities table and reconstructs the same in-memory
        structure as the JSON load() method.

        Returns:
            IdentityRegistry instance, or None if Supabase is unavailable.
        """
        try:
            from app.supabase_data import (
                get_supabase_client,
                load_identity_history_from_supabase,
            )
        except ImportError:
            logger.warning("supabase_data not available for Postgres load")
            return None

        client = get_supabase_client()
        if not client:
            return None

        try:
            # Paginate to handle >1000 identities (Supabase default limit)
            all_rows = []
            page_size = 1000
            offset = 0
            while True:
                result = (
                    client.table("identities")
                    .select(
                        "identity_id, name, display_name, state, anchor_ids, candidate_ids, "
                        "negative_ids, version_id, created_at, updated_at, merged_into, metadata, "
                        "primary_face_id"
                    )
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                if not result.data:
                    break
                all_rows.extend(result.data)
                if len(result.data) < page_size:
                    break
                offset += page_size

            registry = cls()
            for row in all_rows:
                identity_id = row["identity_id"]

                def _ensure_list(val):
                    """Coerce string-encoded JSON arrays to lists.

                    Some Supabase rows have anchor_ids/candidate_ids stored as
                    JSON text instead of JSONB arrays (caused by sync bugs).
                    """
                    if isinstance(val, list):
                        return val
                    if isinstance(val, str):
                        try:
                            parsed = json.loads(val)
                            if isinstance(parsed, list):
                                return parsed
                        except (json.JSONDecodeError, TypeError):
                            pass
                    return []

                identity = {
                    "identity_id": identity_id,
                    "name": row.get("name", ""),
                    "display_name": row.get("display_name"),
                    "state": row.get("state", "INBOX"),
                    "anchor_ids": _ensure_list(row.get("anchor_ids", [])),
                    "candidate_ids": _ensure_list(row.get("candidate_ids", [])),
                    "negative_ids": _ensure_list(row.get("negative_ids", [])),
                    "version_id": row.get("version_id", 1),
                    "created_at": row.get("created_at"),
                    "updated_at": row.get("updated_at"),
                }
                if row.get("merged_into"):
                    identity["merged_into"] = row["merged_into"]
                if row.get("primary_face_id"):
                    identity["primary_face_id"] = row["primary_face_id"]
                # Merge metadata JSONB if present
                metadata = row.get("metadata")
                if metadata and isinstance(metadata, dict):
                    identity["metadata"] = metadata
                    # Round-trip notes through metadata.notes (Session 156: notes
                    # are stored top-level in-memory but only persist via metadata
                    # JSONB on Supabase since shadow_write doesn't include "notes"
                    # at the row top-level).
                    if "notes" in metadata and isinstance(metadata["notes"], list):
                        identity["notes"] = metadata["notes"]
                registry._identities[identity_id] = identity

            # NOTE: Session 129 removed a legacy override layer here that
            # silently corrupted data by clobbering correct anchor_ids with
            # stale snapshots. The identities table is the sole source of truth.

            registry._history = load_identity_history_from_supabase() or []

            logger.info(f"IdentityRegistry loaded from Postgres ({len(registry._identities)} identities)")
            return registry

        except Exception as e:
            logger.warning(f"IdentityRegistry.load_from_postgres failed: {e}")
            return None

    @classmethod
    def load(cls, path: Path) -> "IdentityRegistry":
        """Load registry from JSON file.

        Raises:
            ValueError: If the file contains invalid JSON or is missing required keys.
        """
        path = Path(path)

        try:
            with open(path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"IdentityRegistry: corrupted JSON in {path}: {e}")
            raise ValueError(f"IdentityRegistry file is corrupted ({path}): {e}") from e

        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"Schema version mismatch: expected {SCHEMA_VERSION}, got {data.get('schema_version')}")

        try:
            registry = cls()
            registry._identities = data["identities"]
            registry._history = data["history"]
        except KeyError as e:
            logger.error(f"IdentityRegistry: missing required key {e} in {path}")
            raise ValueError(f"IdentityRegistry file is missing required key {e} ({path})") from e

        return registry

    def _record_event(
        self,
        identity_id: str,
        action: str,
        face_ids: list[str],
        user_source: str,
        previous_version_id: int,
        confidence_weight: float = 1.0,
        metadata: dict = None,
    ) -> None:
        """Record an event in the append-only history."""
        event = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "identity_id": identity_id,
            "action": action,
            "face_ids": face_ids,
            "user_source": user_source,
            "confidence_weight": confidence_weight,
            "previous_version_id": previous_version_id,
            "metadata": metadata or {},
        }
        self._history.append(event)
        try:
            from app.supabase_data import sync_identity_history_event

            sync_identity_history_event(event)
        except Exception as e:
            # Supabase audit sync is best-effort and must not block canonical writes.
            logger.warning(f"Supabase identity history sync failed: {e}")

    def get_all_face_ids(self, identity_id: str) -> list[str]:
        """
        Get ALL face IDs associated with an identity (anchors + candidates).

        This is used for merge validation - we must check ALL faces,
        not just anchors, to prevent co-occurrence violations.

        Args:
            identity_id: Identity ID

        Returns:
            List of all face ID strings (anchors + candidates)
        """
        identity = self.get_identity(identity_id)
        face_ids = []

        # Get anchor face IDs (handles both string and dict formats)
        for anchor in identity["anchor_ids"]:
            if isinstance(anchor, str):
                face_ids.append(anchor)
            elif isinstance(anchor, dict):
                face_ids.append(anchor["face_id"])

        # Add candidate face IDs
        face_ids.extend(identity["candidate_ids"])

        return face_ids

    def search_identities(
        self,
        query: str,
        limit: int = 10,
        exclude_id: str = None,
        states: list[str] | None = None,
        include_merged: bool = False,
    ) -> list[dict]:
        """
        Search for identities by name across all states.

        Used for sidebar search, face tagging, and merge search.

        Args:
            query: Search string (case-insensitive substring match)
            limit: Maximum results to return (default 10)
            exclude_id: Identity ID to exclude (e.g., the currently viewed identity)
            states: Optional list of states to include. None = all non-merged states.
            include_merged: If True, include merged identities with merged_into_name.
                Default False to avoid showing merged identities in tag/merge search.

        Returns:
            List of lightweight summaries: {identity_id, name, face_count,
            preview_face_id, state}. Ranked: CONFIRMED first, then by name.
        """
        # Empty or whitespace query returns nothing
        query = query.strip() if query else ""
        if not query:
            return []

        query_lower = query.lower()
        words = query_lower.split()

        # Build expanded term sets for each word (AND-of-ORs matching)
        # e.g. "Leon Capelluto" → [{"leon"}, {"capelluto","capeluto","capelouto",...}]
        variant_lookup = _load_surname_variants()
        word_term_sets: list[set[str]] = []
        for word in words:
            term_set = {word}
            if word in variant_lookup:
                term_set.update(variant_lookup[word])
            word_term_sets.append(term_set)

        # State priority for ranking (lower = higher priority)
        _state_rank = {
            "CONFIRMED": 0,
            "PROPOSED": 1,
            "INBOX": 2,
            "SKIPPED": 3,
            "CONTESTED": 4,
            "REJECTED": 5,
        }

        full_matches = []  # all words matched
        partial_matches = []  # some words matched (secondary results)
        fuzzy_candidates = []

        for identity in self._identities.values():
            merged_into = identity.get("merged_into")
            identity_state = identity.get("state", "INBOX")

            # Skip merged identities unless explicitly requested (FB-065)
            if merged_into and not include_merged:
                continue

            # Filter by requested states if specified
            if states is not None and identity_state not in states:
                continue

            # Skip excluded identity
            if exclude_id and identity["identity_id"] == exclude_id:
                continue

            name = identity.get("name") or ""

            # Build summary dict (shared between exact and fuzzy paths)
            def _build_summary(ident=identity, n=name, _merged=merged_into):
                anchor_ids = ident.get("anchor_ids", [])
                candidate_ids = ident.get("candidate_ids", [])
                face_count = len(anchor_ids) + len(candidate_ids)
                preview_face_id = None
                for face_list in [anchor_ids, candidate_ids]:
                    if face_list:
                        first_face = face_list[0]
                        if isinstance(first_face, str):
                            preview_face_id = first_face
                        elif isinstance(first_face, dict):
                            preview_face_id = first_face.get("face_id")
                        if preview_face_id:
                            break
                summary = {
                    "identity_id": ident["identity_id"],
                    "name": n,
                    "face_count": face_count,
                    "preview_face_id": preview_face_id,
                    "state": ident.get("state", "INBOX"),
                }
                if _merged:
                    target = self._identities.get(_merged)
                    summary["merged_into"] = _merged
                    summary["merged_into_name"] = target.get("name", "Unknown") if target else "Unknown"
                return summary

            # Also search aliases/alternate names
            searchable_texts = [name.lower()]
            for alias in identity.get("aliases", []):
                if isinstance(alias, str):
                    searchable_texts.append(alias.lower())
            for alias in identity.get("alternate_names", []):
                if isinstance(alias, str):
                    searchable_texts.append(alias.lower())

            # Count how many query words match (with variant expansion)
            words_matched = 0
            for term_set in word_term_sets:
                if any(term in text for term in term_set for text in searchable_texts):
                    words_matched += 1

            rank = _state_rank.get(identity_state, 9)
            # Merged identities sort after all non-merged results
            if merged_into:
                rank += 10
            if words_matched == len(word_term_sets):
                # All words matched — primary result
                full_matches.append((rank, name.lower(), _build_summary()))
            elif words_matched > 0:
                # Partial match — secondary result (lower priority)
                partial_matches.append((rank, name.lower(), _build_summary()))
            else:
                # No match — track for fuzzy fallback
                fuzzy_candidates.append((name, identity_state, _build_summary))

        # Primary: full matches sorted by state rank, then name
        full_matches.sort(key=lambda x: (x[0], x[1]))
        sorted_results = [r[2] for r in full_matches[:limit]]

        # Fill remaining slots with partial matches if needed
        remaining = limit - len(sorted_results)
        if remaining > 0 and partial_matches:
            partial_matches.sort(key=lambda x: (x[0], x[1]))
            sorted_results.extend(r[2] for r in partial_matches[:remaining])

        # Fuzzy fallback: if no exact/partial matches, try Levenshtein per-word
        if not sorted_results and fuzzy_candidates:
            scored = []
            for cand_name, id_state, builder in fuzzy_candidates:
                best_dist = 999
                for word in cand_name.lower().split():
                    for qword in words:
                        dist = _levenshtein(qword, word)
                        threshold = 2 if len(qword) <= 8 else 3
                        if dist <= threshold:
                            best_dist = min(best_dist, dist)
                if best_dist < 999:
                    fuzz_rank = _state_rank.get(id_state, 9)
                    scored.append((best_dist, fuzz_rank, builder()))
            scored.sort(key=lambda x: (x[0], x[1]))
            sorted_results = [s[2] for s in scored[:limit]]

        return sorted_results

    def add_note(self, identity_id: str, text: str, author: str = "") -> dict:
        """
        Add a note to an identity.

        Args:
            identity_id: Identity to add note to
            text: Note text content
            author: Email of the user adding the note

        Returns:
            The created note dict with id, text, author, timestamp
        """
        if identity_id not in self._identities:
            raise KeyError(f"Identity not found: {identity_id}")
        identity = self._identities[identity_id]
        if "notes" not in identity:
            identity["notes"] = []

        note = {
            "id": str(uuid.uuid4())[:8],
            "text": text,
            "author": author,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        identity["notes"].append(note)
        identity["updated_at"] = datetime.now(timezone.utc).isoformat()
        return note

    def get_notes(self, identity_id: str) -> list:
        """Get all notes for an identity."""
        identity = self.get_identity(identity_id)
        return identity.get("notes", [])

    def add_proposed_match(self, source_id: str, target_id: str, note: str = "", author: str = "") -> dict:
        """
        Propose a match between two identities without executing it.

        Stores the proposal on the source identity for later review.

        Args:
            source_id: Identity to propose match for
            target_id: Identity proposed as match
            note: Optional user note about the proposal
            author: Email of the user making the proposal

        Returns:
            The created proposal dict
        """
        # Validate both identities exist
        self.get_identity(source_id)
        target = self.get_identity(target_id)

        source = self._identities[source_id]
        if "proposed_matches" not in source:
            source["proposed_matches"] = []

        # Don't add duplicate proposals
        for pm in source["proposed_matches"]:
            if pm["target_id"] == target_id and pm.get("status") == "pending":
                return pm

        proposal = {
            "id": str(uuid.uuid4())[:8],
            "target_id": target_id,
            "target_name": target.get("name", ""),
            "note": note,
            "author": author,
            "status": "pending",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        source["proposed_matches"].append(proposal)
        source["updated_at"] = datetime.now(timezone.utc).isoformat()
        return proposal

    def list_proposed_matches(self) -> list:
        """
        List all pending proposed matches across all identities.

        Returns list of dicts with source identity info + proposal details.
        """
        proposals = []
        for identity in self._identities.values():
            if identity.get("merged_into"):
                continue
            for pm in identity.get("proposed_matches", []):
                if pm.get("status") == "pending":
                    proposals.append(
                        {
                            "source_id": identity["identity_id"],
                            "source_name": identity.get("name", ""),
                            **pm,
                        }
                    )
        return proposals

    def resolve_proposed_match(self, source_id: str, proposal_id: str, action: str):
        """
        Resolve a proposed match (accept or reject).

        Args:
            source_id: Identity with the proposal
            proposal_id: ID of the proposal to resolve
            action: "accept" or "reject"
        """
        if source_id not in self._identities:
            raise KeyError(f"Identity not found: {source_id}")
        identity = self._identities[source_id]
        for pm in identity.get("proposed_matches", []):
            if pm["id"] == proposal_id:
                pm["status"] = action
                pm["resolved_at"] = datetime.now(timezone.utc).isoformat()
                identity["updated_at"] = datetime.now(timezone.utc).isoformat()
                return pm
        raise KeyError(f"Proposal {proposal_id} not found on identity {source_id}")


def validate_merge(
    id_a: str,
    id_b: str,
    identity_registry: "IdentityRegistry",
    photo_registry: "PhotoRegistry",
    allow_co_occurrence: bool = False,
) -> tuple[bool, str]:
    """
    Validate whether two identities can be safely merged.

    CORE INVARIANT: A face appearing in the same photo as another face
    may NEVER belong to the same identity (they are physically distinct
    people in that moment).

    This function MUST be called by ALL merge entry points.
    No merge may proceed without explicit validation.

    Session 108b (PRD-048): Admin can override co-occurrence for collages,
    photos-of-albums, and composite images. Override requires explicit
    allow_co_occurrence=True + logged reason at the call site.

    Args:
        id_a: First identity ID
        id_b: Second identity ID
        identity_registry: IdentityRegistry instance
        photo_registry: PhotoRegistry instance
        allow_co_occurrence: If True, skip co-occurrence check (admin override for collages)

    Returns:
        (can_merge: bool, reason: str)
        - (False, "co_occurrence") if identities share ANY photo_id and override not set
        - (True, "ok") otherwise
        - (True, "co_occurrence_override") if override allowed
    """
    # Get ALL face IDs for both identities (anchors + candidates)
    faces_a = identity_registry.get_all_face_ids(id_a)
    faces_b = identity_registry.get_all_face_ids(id_b)

    # Get photo_ids for each identity's faces
    photos_a = photo_registry.get_photos_for_faces(faces_a)
    photos_b = photo_registry.get_photos_for_faces(faces_b)

    # Check for any photo overlap (co-occurrence)
    shared_photos = photos_a & photos_b

    if shared_photos:
        if allow_co_occurrence:
            logger.info(
                f"Merge co-occurrence OVERRIDDEN: identities {id_a} and {id_b} "
                f"share photo(s): {shared_photos} — admin override"
            )
            return (True, "co_occurrence_override")
        logger.warning(f"Merge blocked (co_occurrence): identities {id_a} and {id_b} share photo(s): {shared_photos}")
        return (False, "co_occurrence")

    return (True, "ok")
