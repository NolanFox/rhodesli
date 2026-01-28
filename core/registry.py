"""
Semi-Supervised Identity Registry.

A durable, versioned registry with state, provenance, and replay capabilities.
See docs/adr_004_identity_registry.md for design rationale.

Key principles:
- Immutable source data (PFE embeddings never modified)
- Append-only event log for full provenance
- Human-gated learning (only explicit confirmation updates anchors)
- State machine controls fusion behavior
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


class IdentityState(Enum):
    """Identity lifecycle states."""
    PROPOSED = "PROPOSED"    # Initial state, accepts changes
    CONFIRMED = "CONFIRMED"  # Authoritative but reversible
    CONTESTED = "CONTESTED"  # Frozen until reviewed


class ActionType(Enum):
    """Event action types."""
    CREATE = "create"
    PROMOTE = "promote"
    REJECT = "reject"
    CONFIRM = "confirm"
    CONTEST = "contest"
    STATE_CHANGE = "state_change"
    UNDO = "undo"
    MERGE = "merge"


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
    ) -> str:
        """
        Create a new identity in PROPOSED state.

        Args:
            anchor_ids: Initial confirmed face IDs
            user_source: Who/what initiated this action
            name: Optional human-readable name
            candidate_ids: Optional suggested matches

        Returns:
            identity_id
        """
        identity_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        identity = {
            "identity_id": identity_id,
            "name": name,
            "state": IdentityState.PROPOSED.value,
            "anchor_ids": list(anchor_ids),
            "candidate_ids": list(candidate_ids) if candidate_ids else [],
            "negative_ids": [],
            "version_id": 1,
            "created_at": now,
            "updated_at": now,
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

    def get_history(self, identity_id: str) -> list[dict]:
        """Get event history for an identity."""
        return [e for e in self._history if e["identity_id"] == identity_id]

    def list_identities(self, state: IdentityState = None) -> list[dict]:
        """List all identities, optionally filtered by state."""
        identities = list(self._identities.values())
        if state:
            identities = [i for i in identities if i["state"] == state.value]
        return [i.copy() for i in identities]

    def confirm_identity(self, identity_id: str, user_source: str) -> None:
        """Transition identity to CONFIRMED state."""
        identity = self._identities[identity_id]
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
            metadata={"new_state": IdentityState.CONFIRMED.value},
        )

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
    ) -> None:
        """
        Move a candidate to anchor_ids.

        This is a human-confirmed action that affects fusion math.
        """
        identity = self._identities[identity_id]
        previous_version = identity["version_id"]

        if face_id not in identity["candidate_ids"]:
            raise ValueError(f"Face {face_id} is not a candidate for {identity_id}")

        identity["candidate_ids"].remove(face_id)
        identity["anchor_ids"].append(face_id)
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

    def undo(self, identity_id: str, user_source: str) -> None:
        """
        Undo the most recent reversible action.

        Replays events up to (but not including) the last action.
        """
        identity = self._identities[identity_id]
        history = self.get_history(identity_id)

        if len(history) < 2:
            raise ValueError("Nothing to undo")

        # Get the last action to undo
        last_event = history[-1]
        previous_version = identity["version_id"]

        # Reverse the action
        if last_event["action"] == ActionType.PROMOTE.value:
            face_id = last_event["face_ids"][0]
            if face_id in identity["anchor_ids"]:
                identity["anchor_ids"].remove(face_id)
            if face_id not in identity["candidate_ids"]:
                identity["candidate_ids"].append(face_id)

        elif last_event["action"] == ActionType.REJECT.value:
            face_id = last_event["face_ids"][0]
            if face_id in identity["negative_ids"]:
                identity["negative_ids"].remove(face_id)
            if face_id not in identity["candidate_ids"]:
                identity["candidate_ids"].append(face_id)

        elif last_event["action"] == ActionType.STATE_CHANGE.value:
            # Restore previous state by finding the state before this change
            prev_state = None
            for i in range(len(history) - 2, -1, -1):
                evt = history[i]
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
            face_ids=last_event.get("face_ids", []),
            user_source=user_source,
            previous_version_id=previous_version,
            metadata={"undone_action": last_event["action"]},
        )

    def save(self, path: Path) -> None:
        """Save registry to JSON file."""
        data = {
            "schema_version": SCHEMA_VERSION,
            "identities": self._identities,
            "history": self._history,
        }

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "IdentityRegistry":
        """Load registry from JSON file."""
        path = Path(path)

        with open(path) as f:
            data = json.load(f)

        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                f"Schema version mismatch: expected {SCHEMA_VERSION}, "
                f"got {data.get('schema_version')}"
            )

        registry = cls()
        registry._identities = data["identities"]
        registry._history = data["history"]

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
