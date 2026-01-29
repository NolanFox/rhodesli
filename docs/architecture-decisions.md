# Architecture Decisions: Identity Registry Hardening

**Date:** 2026-01-28
**Status:** Implemented

## Summary

This document explains key architectural decisions made during the Identity Registry hardening phase, prior to adding a Web UI.

---

## 1. JSON + File Locking over SQLite

### Decision
We chose JSON files with `portalocker` file locking instead of migrating to SQLite.

### Rationale

**Why JSON:**
- **Simplicity**: No database driver dependencies
- **Inspectability**: Human-readable files can be viewed/edited in any text editor
- **Git-friendly**: Easy to diff and track changes
- **Portability**: Works on any platform without installation

**Why not SQLite (yet):**
- Current data volume is small (<1000 identities expected)
- No need for complex queries or joins
- Single-writer access pattern is sufficient for initial Web UI
- Migration complexity not justified for current scale

**Why file locking:**
- Prevents corruption from concurrent CLI + Web writes
- `portalocker` provides cross-platform exclusive locking
- Lock file approach allows reads during writes

### Trade-offs
- **Pro**: Zero infrastructure, easy debugging
- **Con**: No atomic transactions across entities
- **Con**: Full file rewrite on every save (acceptable at current scale)

### Future Migration Path
If we need SQLite later:
1. Schema is already normalized (identities + history tables)
2. Event log structure maps directly to SQL
3. Lock file pattern can be replaced with SQLite WAL mode

---

## 2. Undo Determinism and Event Sourcing

### Decision
The registry uses append-only event sourcing with deterministic undo.

### Rationale

**Why event sourcing:**
- **Full auditability**: Every action is recorded with timestamp and user
- **Reversibility**: Any action can be undone by replaying history
- **Provenance**: Complete chain of custody for forensic claims

**Why deterministic undo:**
- Genealogical research requires being able to "take back" incorrect claims
- Multiple researchers may disagree; history preserves all perspectives
- Fusion math must produce identical results given identical anchor sets

### Implementation

The undo operation:
1. Finds the last non-undone, undoable action
2. Records `undone_event_id` in the undo event metadata
3. Reverses the action (remove from anchors, restore to candidates, etc.)
4. Produces mathematically identical fusion to pre-action state

**Tested invariant:**
```
promote(A) → promote(B) → promote(C) → undo() → undo() → undo()
⟹ final_fusion == original_fusion (within 1e-6 tolerance)
```

### Trade-offs
- **Pro**: Never lose data, always recoverable
- **Con**: History grows unbounded (mitigate: periodic snapshots)
- **Con**: Undo of undo requires careful event tracking

---

## 3. Atomic Writes and Backup Strategy

### Decision
All writes use atomic rename and create timestamped backups.

### Rationale

**Why atomic writes:**
- Partial writes would corrupt the entire registry
- Power loss or process kill must leave valid state
- Write to temp file → fsync → rename is standard pattern

**Why automatic backups:**
- "System of Record" means data is irreplaceable
- Even with undo, catastrophic errors need recovery path
- Timestamped backups allow point-in-time recovery

### Implementation

```
save(path):
  1. Create backup at backups/identities.json.<timestamp>
  2. Acquire exclusive lock on identities.json.lock
  3. Write to identities.json.tmp
  4. fsync to ensure data is on disk
  5. Atomic rename to identities.json
  6. Release lock
```

### Trade-offs
- **Pro**: Zero data loss on crash
- **Pro**: Full backup history for recovery
- **Con**: Disk usage grows with each save
- **Con**: Backup cleanup not yet implemented (manual for now)

---

## 4. Schema Evolution Strategy

### Decision
Schema evolution is non-destructive with backward-compatible formats.

### Rationale

**Why backward compatibility:**
- Existing data must continue to work
- No forced migrations for simple changes
- Gradual rollout of new features

**Current example: anchor_ids format**

Legacy (still works):
```json
"anchor_ids": ["face_001", "face_002"]
```

Structured (new capability):
```json
"anchor_ids": [
  {"face_id": "face_001", "era_bin": "1910-1930", "weight": 1.0}
]
```

Both formats:
- Persist and load correctly
- Work with fusion calculations
- Survive save/load cycle

### Implementation

- `get_anchor_face_ids()` abstracts format differences
- `_extract_face_id()` handles both string and dict
- `promote_candidate()` creates structured entries with optional `era_bin`

### Trade-offs
- **Pro**: No migration scripts needed
- **Pro**: Gradual adoption of new features
- **Con**: Code must handle multiple formats
- **Con**: Slight complexity in accessor methods

---

## Non-Goals

The following were explicitly out of scope for this hardening phase:

1. **SQLite migration**: Deferred until scale requires it
2. **Vector search (FAISS/Annoy)**: Not needed for current matching workflow
3. **Age-weighted fusion**: Era metadata stored but not used in math
4. **Web UI changes**: This phase focused only on backend safety

---

## Verification

All invariants are tested:

| Test File | Tests | Purpose |
|-----------|-------|---------|
| `test_persistence.py` | 7 | Atomic writes, locking, backups |
| `test_integrity.py` | 7 | Undo determinism, replay proof |
| `test_schema.py` | 7 | Backward compatibility |

Total: 130 tests passing.
