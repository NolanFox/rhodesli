# Session 113 Context — Audit Logging + Embeddings Single Source of Truth

**Predecessor:** Session 112 (PRD-051 Phase 1 — Supabase SSOT for identities/photos)
**Investigation:** [investigation-4063-harry-fox.md](investigation-4063-harry-fox.md)

## Problem Statement

An ad-hoc investigation between Sessions 112 and 113 exposed two critical platform gaps:

1. **No audit trail for identity mutations.** When investigating Person 4063's cluster, we could not determine who merged two identities into it, when, or why. `registry.merge_identities()` and all other mutation functions write no `audit_log` entries. The `audit_log` table exists but only has "approved" actions from the upload pipeline.

2. **Embeddings from web uploads are invisible to local analysis.** The Harry Fox naturalization form (`IMG_2570.jpeg`) was uploaded via the web UI. Its embedding was saved to production `embeddings.npy` (2957 entries) but the local copy only has 2872 entries. This is the 8th occurrence of the local-production data divergence pattern (Lessons 56→69→78→85→141→144→147→now). Session 112 fixed identities/photos reads but explicitly deferred embeddings (PRD-051 Phase 3).

## Investigation Summary

**Person 4063** (f1fa51b2): 3 faces from Fox Family beach photos. Not Harry Fox (nat form distance 1.35-1.40). Not Albert Fox (Photo 2 distance 0.89 to cluster vs 1.24 to Albert). Separate unidentified person in Fox family orbit. Cluster was formed by merges on 2026-03-17 with zero audit trail.

**Harry Fox** (d74cb556): 5 faces — 1 naturalization form (ground truth) + 4 Dayton photos. Using production embeddings, 3 of 4 Dayton faces are closer to Albert Fox than to the naturalization form. Only H1 (01811) is closer to Harry by a margin of 0.017. The cluster may contain misattributed Albert Fox photos. Brothers create inherent ambiguity at these distances (0.96-1.12).

## What Session 112 Shipped

- PRD-051 Phase 1: Supabase-only reads for identities and photos
- DATA_SOURCE default "json" → "postgres"
- JSON writes kept as backup only
- 14 new tests, 4584 pass
- Acknowledged Supabase disk IO budget warning (email received 2026-03-17) — monitored, not fixed

## What Session 112 Deferred

- PRD-051 Phase 2: proposals, annotations, etc. → Supabase
- PRD-051 Phase 3: ML pipeline Supabase reads (including embeddings)
- PRD-051 Phase 4: Remove JSON from deploy pipeline
- EGRESS-004: Investigate which queries consume most IO

## Scope for Session 113

### In Scope
1. **AUDIT-001 (P0):** Add audit_log writes to all identity mutation routes — merge, confirm, reject, skip, rename, detach. Each row: action, entity_id, user_email or "system", old_value, new_value, metadata (route, distance, session).
2. **Embeddings sync:** Sync production embeddings.npy to local so all face data is available for analysis. Endpoint exists at `/api/sync/embeddings`.
3. **Embeddings verification:** With synced embeddings, verify Harry Fox cluster quality and document findings.

### Out of Scope (future sessions)
- PRD-051 Phase 2 (proposals/annotations → Supabase)
- Full embeddings-in-Supabase migration (Phase 3) — too large for one session
- Supabase disk IO optimization (EGRESS-001 through EGRESS-004)
- Stop hook fix for non-session conversations

## Key Files

| File | Purpose |
|------|---------|
| `app/identity_routes.py` | All identity mutation routes (merge, confirm, reject, etc.) |
| `core/registry.py` | `merge_identities()`, `confirm_identity()`, etc. |
| `app/main.py` | `save_registry()`, face data loading |
| `data/embeddings.npy` | Local face embeddings (needs sync from production) |
| `scripts/sync_from_production.py` | Production sync script |

## Supabase Disk IO Warning

Email received 2026-03-17. Session 112 noted as low risk due to TTL caches. Session 113 should check Supabase dashboard after deploy. If IO spikes, existing TTL caches (registry 120s, suggestions 30s) are the mitigation.

## Related Decisions

- AD-227: Single source of truth (Session 112)
- Lesson 147: Local-production data divergence (8th occurrence)
- Lesson 149: NEVER click action buttons on production
- Lesson 150: Three-source data causes recurring split-brain

## User Feedback (verbatim)

- "With so many actions on the app we need good logging so I know what I did vs what was done automatically"
- "I want you to record all the work... make it so we can pick up this Harry Fox/Albert Fox/4063 issue again"
- "Session 112 did not fully fix the problem... it only fixed phase one"
