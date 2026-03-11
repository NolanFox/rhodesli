# Session 97 Lineage Coverage

**Date:** 2026-03-11  
**Scope:** Touched AI/ML and state-mutation paths in Session 97

## Covered In This Session

- Gemini prompt lineage
  - date estimation call logging carries prompt-manifest identity plus raw prompt / response
  - face-alignment Gemini logging carries prompt-manifest identity plus raw prompt / response
- Offline matcher lineage
  - Phase 2 shadow reranker writes versioned report and prototype-bank artifacts
  - Phase 4 adapter harness writes split-aware experiment reports and optional artifacts
- Calibration lineage
  - production hooks remain write-only
  - calibration rows carry `label_type`, `active`, `state_event_id`, `linked_event_id`, and reversal metadata
  - calibration events now mirror to local `audit_log.json` as well as Supabase when available
- Active-learning lineage
  - offline queue artifact in `data/active_learning_queue.json`
  - current-state label cache in `data/active_learning_labels.json`
  - label and revert actions emit calibration-style lineage and audit events
- Canonical identity review actions touched by Session 97
  - cluster-review confirm / reject still flow through registry history
  - active-learning labels remain non-canonical and do not mutate identity truth directly

## Partial / Deferred

- App-wide canonical mutation envelopes are still uneven outside the routes touched in Phase 0 and Phase 3
- Local-only active-learning labels need explicit merge into recalibration when Supabase is unavailable
- Historical clustering proposal sets are still not fully replayable across every older run because `proposals.json` remains a latest-run artifact

## Session 97 Position

Session 97 materially improved replayability for:

- Gemini prompt variants
- calibration and active-learning labels
- offline scorer experiments

It did **not** fully solve global app-state lineage for every existing route. That remains broader than PRD-038 and should be handled as a follow-on cross-app audit if needed.
