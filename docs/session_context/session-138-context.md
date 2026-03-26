# Session 138 Context — Refactor Phase 2 + Cleanup + Harness

**Predecessor:** Session 137 (v0.99.48) — Parallel refactor + tests + design
**Date:** 2026-03-25

## What Session 137 Delivered
- 7 `app/components/` modules: badges, forms, layouts, modals, nav, toasts, __init__
- 1,127 lines extracted from main.py (11,765 → 10,638)
- 68 new ML tests (658 total), 13 xfail TOOLS-005 skeletons
- Flaky xdist cache reset expansion (30+ caches)
- Dual audit: Claude subagent (Opus 4.6) + Codex CLI (gpt-5.4)

## Audit Comparison (Session 137)
| Aspect | Claude Subagent | Codex CLI |
|--------|----------------|-----------|
| Model | Claude Opus 4.6 | gpt-5.4 |
| Independence | NO (shared context) | YES (fresh) |
| Unique findings | Duplicate function, brittle cache reset | cwd-relative regression, wrong patch target, mobile `|` |
| Reproduced issues | No | Yes (DATA_DIR, mobile `|`) |
| Value | MODERATE | STRONG |

**Key insight**: Claude finds design issues, Codex finds runtime issues. Use both.

## Phase 2 Detailed Scope (from research agent)

### cards.py — 7 functions + 4 helpers (~2,077 lines)

| Function | Lines | Start | Dependencies | Risk |
|---|---|---|---|---|
| identity_card | 574 | 9647 | get_best_face_id, resolve_face_image_url, _sequential_display_name, _cross_community_badge | HIGH |
| identity_card_expanded | 287 | 5748 | get_best_face_id, resolve_face_image_url, _sequential_display_name | MEDIUM |
| neighbor_card | 279 | 8884 | match_info_bar, compute_face_confidence, share_button | MEDIUM |
| face_card | 126 | 8696 | resolve_face_image_url, get_face_quality | LOW |
| identity_card_mini | 55 | 6035 | get_best_face_id, resolve_face_image_url, state_badge | LOW |
| search_result_card | 101 | 9163 | match_info_bar, compute_face_confidence, share_button | LOW |
| match_info_bar | 20 | 8822 | _confidence_tier_label (already in badges.py) | LOW |

Helpers: `_build_face_cards_for_entries` (39 lines), `_face_pagination_controls` (52 lines)

### photo.py — render_photos_section (611 lines)

| Function | Lines | Start | Dependencies | Risk |
|---|---|---|---|---|
| render_photos_section | 611 | 7795 | _photo_cache, _face_to_photo_cache, _get_community_photo_ids, section_header | HIGH |

### Module-Level Globals Referenced
- `_photo_cache` — photo metadata dict
- `_face_to_photo_cache` — face→photo ID mapping
- `FACES_PER_PAGE` — pagination constant
- `_build_caches()` — lazy cache init

### _main_mod Call Sites (20+ total)
- `identity_routes.py` — 13 calls
- `page_routes.py` — 5 calls
- `photo_routes.py` — 2 calls

## Codex CLI Findings to Address in Session 138

### P2-1: DATA_DIR cwd-relative — FIXED in Session 137
- Used `is_absolute()` check + `__file__`-relative fallback

### P2-2: xfail tests patch wrong rate-limit symbol
- Patch `app.rate_limit.check_rate_limit` but route imports alias
- **Fix**: Change to `app.estimate_routes.check_rate_limit`

### P2-3: Placeholder test assertions
- Some xfail tests assert wrong things (gedcom_context vs text_hints)
- **Action**: Fix when implementing TOOLS-005, not now

### P3-1: Mobile nav renders clickable `|` separator
- `_public_nav_links()` includes `Span("|")`, mobile clone makes it an anchor
- **Fix**: Filter Span elements in mobile nav clone

## xpassed Tests
Confirmed: 0 xpassed when run alone. The 2 xpassed under xdist are cache-bleed artifacts. No fix needed.

## Supabase Status
User upgrading to Pro ($25/mo) to restore service immediately. Session 138 can deploy.

## Cross-references
- BACKLOG: REFACTOR-001 (in progress, Phase 2)
- PRD: docs/prds/056_mainpy_refactoring.md
- Audit: docs/session_context/session-137-codex-audit.md
- Lessons: 88 (monolithic app prevents parallel worktrees)
