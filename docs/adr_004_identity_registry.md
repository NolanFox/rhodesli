# ADR-004: Semi-Supervised Identity Registry

**Status:** Accepted
**Date:** 2026-01-28
**Author:** Rhodesli Project
**Depends On:** ADR-001 (MLS), ADR-002 (Temporal Priors), ADR-003 (Clustering)

## Context

Static clustering produces initial identity groupings, but historical identity research requires:
1. **Cumulative truth**: Knowledge builds over time through human expertise
2. **Revisable claims**: Initial groupings may be wrong and must be correctable
3. **Disputed identities**: Multiple researchers may disagree
4. **Auditability**: Every decision must be traceable and reversible

The system must model CLAIMS, EVIDENCE, and DISAGREEMENT as first-class concepts, not just face similarity scores.

## Decision

We implement a **Semi-Supervised Identity Registry** with:
- Immutable source embeddings (PFE data never modified)
- Mutable identity metadata layer
- Append-only event log for full provenance
- State machine controlling fusion behavior
- Human-gated learning (only explicit confirmations update math)

### Registry Schema

```json
{
  "identities": {
    "<identity_id>": {
      "identity_id": "uuid",
      "name": "string | null",
      "state": "PROPOSED | CONFIRMED | CONTESTED",
      "anchor_ids": ["face_id", ...],
      "candidate_ids": ["face_id", ...],
      "negative_ids": ["face_id", ...],
      "version_id": 1,
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  },
  "history": [
    {
      "event_id": "uuid",
      "timestamp": "ISO8601",
      "identity_id": "uuid",
      "action": "create | promote | confirm | reject | undo | state_change | merge",
      "face_ids": ["face_id", ...],
      "user_source": "string",
      "confidence_weight": 1.0,
      "previous_version_id": 0,
      "metadata": {}
    }
  ],
  "schema_version": 1
}
```

**SQLite Compatibility Notes:**
- `identities` → table with JSON columns for array fields
- `history` → append-only table with foreign key to identities
- `schema_version` → migrations table

### State Machine

```
                    ┌─────────────┐
      create()      │   PROPOSED  │◄──── Initial state
                    └──────┬──────┘
                           │
           confirm()       │        contest()
                           ▼              │
                    ┌─────────────┐       │
                    │  CONFIRMED  │◄──────┘
                    └──────┬──────┘
                           │
           contest()       │
                           ▼
                    ┌─────────────┐
                    │  CONTESTED  │
                    └─────────────┘
                           │
           resolve()       │
                           ▼
                    ┌─────────────┐
                    │  CONFIRMED  │
                    └─────────────┘
```

**State Semantics:**
- **PROPOSED**: Accepts anchors, candidates, rejections. Fusion is tentative.
- **CONFIRMED**: Fusion is authoritative but reversible.
- **CONTESTED**: Fusion is frozen. No automatic updates until reviewed.

### Fusion Math (Phase 2)

Bayesian-inspired weighted fusion for anchor embeddings only:

```
fused_μ  = Σ(μ_i / σ_i² × w_i) / Σ(1 / σ_i² × w_i)
fused_σ² = 1 / Σ(1 / σ_i² × w_i)
```

Where:
- `μ_i`, `σ_i²` are per-anchor PFE parameters
- `w_i` is confidence_weight (default 1.0)
- Only `anchor_ids` participate in fusion
- `candidate_ids`, `negative_ids`, and "unsure" inputs are EXCLUDED

### Variance Explosion Guardrail

Before any merge operation:
1. Compute hypothetical `fused_σ`
2. If `fused_σ > max(input_σ) × K` where K=1.5:
   - Reject the merge
   - Record rejection event
   - Transition identity to CONTESTED state

This prevents dissimilar faces from being merged and preserves uncertainty.

### Negative Evidence Semantics

Negative evidence (explicit "this is NOT X" claims):
- Stored in `negative_ids` array
- Respected during candidate scoring (negative faces excluded)
- Reversible via undo operation
- Does NOT poison anchor fusion
- May be re-evaluated if anchor changes significantly

### Re-evaluation Logic (Type II Safety)

When anchor fusion materially changes (σ shrinks by >10%):
1. Previously rejected candidates MAY be re-scored
2. High-scoring candidates are surfaced for human review
3. Auto-merge is NEVER performed
4. Events are logged for audit

### Event Types

| Action | Description | Affects Fusion |
|--------|-------------|----------------|
| create | New identity from cluster | No |
| promote | Move candidate to anchor | Yes |
| confirm | Change state to CONFIRMED | No |
| reject | Move candidate to negative_ids | No |
| undo | Reverse previous action | Varies |
| state_change | Transition between states | No |
| merge | Combine two identities | Yes |

### Immutability Guarantees

1. **PFE Source Data**: `embeddings.npy` is NEVER modified
2. **Event Log**: Append-only, events are never deleted
3. **State Transitions**: All captured in history
4. **Replay**: System state can be reconstructed from event log

## Alternatives Considered

### 1. Mutable Embedding Store
**Rejected.** Modifying source embeddings would destroy provenance and make errors unrecoverable.

### 2. Simple Merge Without Variance Check
**Rejected.** Would allow dissimilar faces to be merged, corrupting identity anchors.

### 3. Automatic Learning from Clusters
**Rejected.** Violates human-gated learning principle. Only explicit confirmation updates math.

### 4. Voting/Consensus System
**Out of scope.** Could be added later but not needed for initial single-researcher use.

## Consequences

### Positive
- Full auditability and reversibility
- Human expertise preserved and respected
- Uncertainty propagated, not hidden
- Safe from catastrophic merge errors

### Negative
- More complex than simple clustering
- Requires human interaction for learning
- Storage grows with event history

### Risks
- Event log could grow large (mitigate: periodic snapshots)
- Complex state machine (mitigate: comprehensive tests)

## Open Questions

1. **Snapshot frequency**: When to create state snapshots for faster replay?
2. **Conflict resolution**: How to handle simultaneous edits (future multi-user)?
3. **Export format**: How to share identities with external systems?
