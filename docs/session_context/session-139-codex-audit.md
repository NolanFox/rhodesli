# Session 139 Codex CLI Audit

**Auditor**: Codex CLI v0.115.0 (gpt-5.4)
**Agent type**: Independent (fresh context)
**Scope**: Session 139 merged changes — perf_cache.py, identity_routes.py, person_routes.py, browse_routes.py, page_routes.py, main.py
**Date**: 2026-03-26

## Findings

### P0: None

### P1: None

### P2: best_face_id cache tie-breaking semantics
- Cache key `tuple(sorted(ids))` normalizes order, but the uncached function breaks ties by first occurrence in the list
- After caching, a call with the same faces in different order returns the cached result (which may differ from what the function would compute for that specific order)
- **Assessment**: REJECT — tie-breaking for equal-quality faces is inherently arbitrary. Showing a different face of equal quality is harmless. The cache correctness for the dominant case (different quality scores) is correct.

### P3: Sidebar "0 named" display
- When all confirmed identities are unidentified, sidebar shows "0 named · N unidentified"
- Minor cosmetic — could suppress "0 named" text
- **Assessment**: NOTE — acceptable for now, would clean up in a polish pass

## Assessment
- **Value**: MODERATE — no critical issues found. The P2 finding is technically interesting but not actionable.
- **Would we have found this ourselves?**: The tie-breaking edge case — unlikely to notice. The sidebar text — would catch during browser verification.
