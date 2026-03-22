# Session 134 — Clean Sweep + Performance + Codex Collaboration

## Predecessor
- Assessment: `docs/assessments/session-133-assessment.md`
- Context: `docs/session_context/session-134-context.md`

## Goal
Sweep ALL known gaps, bugs, and concerns clean before user shifts to triage/labeling mode. Fix 15+ UX bugs, run collaborative Codex audit (security + performance), verify features on production.

**Read first:** `docs/session_context/session-134-context.md` for full state.

---

## Phase 0: Session Init (5 min)
```bash
echo "134" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate && make test-fast
```
Create `docs/session_logs/session-134-log.md`.

---

## Phase 1: BACKLOG Housekeeping + Codex Launch (15 min)

**1A: Mark resolved items DONE in `docs/BACKLOG.md`:**
- DATA-021 (691 dangling merges) → DONE 2026-03-22, Session 133
- DATA-022 (1858 merged retaining faces) → DONE 2026-03-22, Session 133
- DATA-023 (212 orphaned faces) → DONE 2026-03-22, Session 133
- DATA-024 (3 multi-claimed faces) → DONE 2026-03-22, Session 133
- DATA-025 (2 ghost faces) → DONE 2026-03-22, Session 133
- HARNESS-001 (worktree hook scoping) → DONE 2026-03-22, Session 133

**1B: Update BACKLOG header:**
- Version: v0.99.43 → v0.99.44 (will be after this session)
- Tests: 3674 app, 590 ML
- Stats: 972 photos, 3757 identities (1863 non-merged), ~154 confirmed

**1C: Launch Codex audits (background subagents):**
- **Security audit**: `app/nl_query_executor.py`, `app/auth_routes.py` (signup wiring), `app/tools_routes.py` (search route). Focus: SQL injection, auth bypass, input validation, rate limiting.
- **Performance audit**: `app/main.py`, `app/page_routes.py`, `app/perf_cache.py`. Focus: N+1 queries, missing caches, heavy computation in request path. IMPORTANT: Push back on items already fixed in Sessions 111f-125. Only suggest NEW improvements.

**Acceptance:**
- [ ] 6 BACKLOG items marked DONE
- [ ] Header stats current
- [ ] 2 Codex audits launched

Commit, /clear.

---

## Phase 2: FB-016 Root Cause — Photo ID Format Mismatch (45 min)

**Root cause:** `photo_faces` stores inbox IDs, photo URLs use SHA256. Face lookup fails for batch-uploaded photos.
**Impact:** Fixes FB-002, FB-003, FB-006, FB-010.
**Context file:** `docs/session_context/session-134-context.md` § "FB-016 Root Cause Analysis"

**Key files:**
- `app/page_routes.py` — photo page face overlay builder
- `app/main.py` — `get_identity_for_face()`
- `core/photo_registry.py` — `_sha256_reverse_index` (Session 131)

**Approach:** When face lookup by SHA256 photo_id returns no results, use `_sha256_reverse_index` to find original filename, derive inbox photo_id, retry lookup.

**Acceptance:**
- [ ] Fox Family photo (10a7d40eb3bf94f7) shows all 18 faces correctly tagged
- [ ] Face overlays clickable for batch-uploaded photos
- [ ] Speed loop checkmarks visible for all tagged faces
- [ ] 5+ tests (both ID formats, legacy regression)

Commit, /clear.

---

## Phase 3: Parallel UX Bug Sprint (30 min, 3 worktree subagents)

| Track | Branch | Files | Bugs | Tests |
|-------|--------|-------|------|-------|
| A | `session-134/speed-run-ux` | `cluster_review_routes.py` | FB-100 (cross-community badge on suggestions), FB-113 ("Under Review" → "Identified" for CONFIRMED) | 3+ |
| B | `session-134/photo-grid-ux` | `page_routes.py` (people grid §4003-4200), `browse_routes.py` | FB-005/007 (face cards clickable), FB-008 (state borders), FB-009 (4-col grid) | 3+ |
| C | `session-134/identify-ux` | `identity_routes.py` | FB-004 (community-scoped name dropdown) | 2+ |

**Track A acceptance:**
- [ ] Suggestions show "From [Community]" badge for cross-community people
- [ ] CONFIRMED person pages show "Identified" not "Under Review"

**Track B acceptance:**
- [ ] Face crops in "People in photo" link to `/person/{id}`
- [ ] Green border for CONFIRMED, amber for PROPOSED, dashed for INBOX
- [ ] Grid: `grid-cols-2 sm:grid-cols-3 lg:grid-cols-4`

**Track C acceptance:**
- [ ] Quick Identify dropdown filters names by current community
- [ ] "Show all communities" option available

Merge all tracks → `./scripts/merge.sh session-134/speed-run-ux session-134/photo-grid-ux session-134/identify-ux`

Commit, /clear.

---

## Phase 4: Speed-Run Flow Fixes (30 min, sequential)

All touch `cluster_review_routes.py` — MUST be sequential (same file as Track A after merge).

- **FB-103**: Merge confirmation — show "Merged N faces into [Name]" inline message
- **FB-104**: Reorder enrichment panel: merge search → name input → GEDCOM link
- **FB-106**: Speed-run person links use admin context (`nav_prefix`)
- **FB-110**: Add GEDCOM search field to enrichment panel

**Acceptance:**
- [ ] Merge shows inline confirmation
- [ ] Panel order: merge → name → GEDCOM
- [ ] Person links go to admin view
- [ ] GEDCOM search available in enrichment
- [ ] 4+ tests

Commit, /clear.

---

## Phase 5: Codex Security Integration (20 min)

Receive security audit findings. Triage per `.claude/rules/ai-tool-audit.md`.

**Acceptance:**
- [ ] Findings: `docs/session_context/session-134-codex-audit.md`
- [ ] P0/P1 fixed with tests
- [ ] P2+ in BACKLOG with breadcrumbs
- [ ] Value assessment logged (STRONG/MODERATE/WEAK)

Commit, /clear.

---

## Phase 6: Performance — Codex Collaboration (40 min)

**Process:**
1. Review Codex performance findings
2. Cross-reference with already-done work (Sessions 111f-125)
3. Push back on duplicates — only NEW improvements
4. Agree on top 3-5 items
5. Implement with before/after measurements

**Known targets:**
- PERF-002: Tree cold load 6.4s → target <3s
- FB-105: Merge/confirm latency → target <1s

**Acceptance:**
- [ ] Before/after measurements for each change
- [ ] Tree load < 3s (or bottleneck + mitigation documented)
- [ ] Merge/confirm < 1s (measured)
- [ ] Performance findings logged in Codex audit doc

Commit, /clear.

---

## Phase 7: Production Verification Sprint (30 min, browser READ-ONLY)

**NL Query (/tools/search):**
- [ ] "Nace Capeluto" → person results
- [ ] "photos from 1940s" → temporal results
- [ ] "wedding photos" → collection results
- [ ] Empty query → suggestions

**Bug fixes (Fox Family photo page):**
- [ ] All 18 faces tagged in Dayton group photo (FB-016)
- [ ] Face overlays clickable (FB-003)
- [ ] People grid: 4-col, colored borders, clickable (FB-005/007/008/009)
- [ ] Speed-run checkmarks (FB-010)
- [ ] Cross-community badge (FB-100)
- [ ] "Identified" label (FB-113)
- [ ] Merge confirmation (FB-103)
- [ ] Enrichment panel order (FB-104)
- [ ] GEDCOM search in enrichment (FB-110)

**Regression:**
- [ ] Landing, people grid, person page, compare, estimate, 404
- [ ] Tree page load time

**Data integrity:**
- [ ] `PYTHONPATH=. python scripts/audit_merge_chains.py` → CLEAN
- [ ] `python scripts/face_coverage_audit.py` → 0 across all metrics

Commit screenshots, /clear.

---

## Phase 8: BACKLOG Sweep + Docs (20 min)
- Sweep ALL BACKLOG items — close silently-fixed items
- Update feedback files (Session 129, Fox triage) with resolution status
- Run data integrity audits — confirm zeros maintained

**Acceptance:**
- [ ] BACKLOG reflects current reality
- [ ] All fixed FBs marked with session/date
- [ ] Audit: all zeros

Commit, /clear.

---

## Phase 9: Deploy + Session Close (20 min)
- [ ] Assessment: `docs/assessments/session-134-assessment.md`
- [ ] CHANGELOG v0.99.44
- [ ] ROADMAP: Recently Completed
- [ ] SESSION_HISTORY: Session 134 entry
- [ ] `git push origin main`
- [ ] Deploy health 200
- [ ] `git log origin/main..HEAD` empty
- [ ] Run `/session-review`

---

## Key Files Reference
| File | Purpose | Phase |
|------|---------|-------|
| `docs/BACKLOG.md` | Housekeeping | 1, 8 |
| `app/page_routes.py` | Photo page, face overlays, people grid | 2, 3B |
| `app/main.py` | Identity lookup, caches | 2, 6 |
| `core/photo_registry.py` | SHA256 reverse index | 2 |
| `app/cluster_review_routes.py` | Speed-run, enrichment, suggestions | 3A, 4 |
| `app/identity_routes.py` | Quick Identify | 3C |
| `app/browse_routes.py` | People grid | 3B |
| `app/nl_query_executor.py` | NL query executor | 5 (Codex target) |
| `app/tools_routes.py` | /tools/search | 5 (Codex target) |
| `app/auth_routes.py` | Signup wiring | 5 (Codex target) |
| `app/perf_cache.py` | Performance cache | 6 |
| `docs/feedback/session-129-feedback.md` | Bug source | 3, 7, 8 |
| `docs/feedback/2026-03-14-fox-triage-feedback.md` | Bug source | 3, 4, 7, 8 |

## Codex Audit Scope
- **Security**: nl_query_executor.py, auth_routes.py, tools_routes.py
- **Performance**: main.py, page_routes.py, perf_cache.py
- **Strategy**: HD-028 — fresh audit, not resume. Log per `.claude/rules/ai-tool-audit.md`
