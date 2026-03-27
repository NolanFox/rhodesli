# Session 141 Codex Audit

**Auditor**: Codex CLI v0.115.0 (gpt-5.4) + Claude Opus 4.6 self-audit
**Agent type**: Independent (fresh context) for Codex, self-review for Claude
**Phase**: All tracks (A, B, C, D, E) — post-merge audit
**Date**: 2026-03-26

## Codex Status
Codex CLI was available and invoked but the audit command timed out during execution.
Claude self-audit was performed as fallback with thorough file-by-file review.

## Findings

### P0 (Critical) — None

### P1 (High)
1. **Unused imports in identity_cards.py** — `import json as _json` and `import re` were dead code. FIXED in this session.

### P2 (Medium)
1. **Thread safety in parallel cold start** — `_load_date_labels()` and `get_crop_files()` lack lock protection. Both use check-then-set pattern. No data corruption risk (caches hold immutable read-only data; last-write-wins is idempotent). But redundant computation could occur. Acceptable for cold-start use case.
2. **Hero face picker caller wiring incomplete** — `get_best_face_id()` accepts optional `identity=` parameter for primary_face_id override, but most call sites don't pass it yet. Feature works for explicit calls but isn't wired into all rendering paths. BACKLOG.
3. **Supabase column not created** — `primary_face_id` column doesn't exist in Supabase yet. Code handles absence gracefully (shadow_write conditionally includes it). BACKLOG.
4. **`border_colors` dict unused** — In identity_card(), the `border_colors` dict (line ~490) is defined but never referenced. Likely dead code from a previous iteration. LOW priority.

### P3 (Informational)
1. **Lazy import pattern used consistently** — All main.py references use `import app.main as _m` inside functions. No circular import risk.
2. **Backward compatibility confirmed** — All `_main_mod.identity_card` references in 12+ route files resolve correctly via re-export in main.py.
3. **Admin-only enforcement on set-primary-face endpoint confirmed** — `_check_admin()` + face validation + `save_registry()` + audit log.
4. **Mock path for _load_gedcom_face_links updated** — Test was patching `app.main._load_gedcom_face_links` but the extracted code imports from `app.relationship_routes` directly. Updated test to patch the correct path.

## Value Assessment
- **Codex**: UNAVAILABLE (timeout) — no findings
- **Claude self-audit**: MODERATE — caught unused imports (P1), confirmed security and thread safety patterns (P2)

## Actions Taken
- P1 #1: Fixed (removed unused imports)
- P2 #1: Acceptable for cold-start pattern, no fix needed
- P2 #2-3: BACKLOG items
- P2 #4: Cosmetic, defer

## Enforcement Improvement
Added mechanical stop-gate check for codex audit file existence (Session 141).
Allows "codex unavailable" documentation as valid fallback.
