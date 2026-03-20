# Session 124 — Performance Blitz + UX Design Audit

@docs/session_context/session-124-context.md
@docs/session_context/session-123-codex-perf-audit.txt
@tasks/lessons.md

## Goal

Fix the 3 remaining high-impact performance bottlenecks from Codex audit and implement top UX improvements from Antigravity design audit. Two parallel tracks.

## CRITICAL CONSTRAINTS

1. **Browser automation is READ-ONLY on production** (Lesson 149).
2. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`.
3. **Every change gets tests** — happy path + failure + regression.
4. **/clear between phases** — commit first, then /clear immediately.
5. **Parallelization**: See context for track breakdown.
6. **Security audit**: After all code phases.
7. **Gap check**: Re-read this prompt at end. Auto-fix any gaps.
8. **REMINDER**: Ask user about AD-229 upload testing status.

## Pre-Requisites

```bash
echo "124" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline
```

Read:
- `docs/session_context/session-124-context.md`
- `docs/session_context/session-123-codex-perf-audit.txt` (Codex findings #2, #3, #5)

---

## Phase 0: Orient + Generate Antigravity Prompt (5 min)

Create session log. Verify baseline tests pass.
Output the Antigravity prompt from `docs/prompts/session-124-antigravity-prompt.md` for user to paste.

**Commit:** `docs: session 124 phase 0 — orient`
**/clear**

---

## Phase 1: PERF — Recursive Speed-Run Prefetch Fix (25 min)

### The Problem (Codex Finding #2)
Each speed-run card contains a hidden `hx_trigger="load"` div that prefetches the next card. The prefetched card ALSO contains a prefetch div. This cascades to prefetch ALL remaining cards (up to 179 requests) on page load.

### The Fix
Find the prefetch div in `app/cluster_review_routes.py` (around line 1917 or 2251).

Option A (preferred): Remove nested prefetch from prefetched cards. The prefetch endpoint should return a card WITHOUT another prefetch node.
Option B: Prefetch only JSON metadata, hydrate on advance.

### Implementation
1. Find where prefetch divs are rendered (search for `hx_trigger="load"` in cluster_review_routes.py)
2. Add a `prefetched=True` parameter to the card renderer
3. When `prefetched=True`, skip the nested prefetch div
4. The initial (non-prefetched) card still has its prefetch div

### Tests
- Test that prefetched cards do NOT contain nested `hx_trigger="load"` prefetch divs
- Test that initial cards DO contain prefetch div
- Test speed-run renders correctly with fix

**Commit:** `perf: session 124 phase 1 — fix recursive speed-run prefetch (Codex #2)`
**/clear**

---

## Phase 2: PERF — Community Indexes SQL (5 min)

### The Problem (Codex Finding #5)
`photo_communities` and `identity_communities` tables filter by `community_id` but lack dedicated indexes.

### The Fix
Create `scripts/sql/session_124_community_indexes.sql`:
```sql
CREATE INDEX IF NOT EXISTS idx_photo_communities_community_id
ON photo_communities (community_id);

CREATE INDEX IF NOT EXISTS idx_identity_communities_community_id
ON identity_communities (community_id);
```

### Tests
- Test SQL file exists with correct index statements

**Commit:** `perf: session 124 phase 2 — community indexes SQL (Codex #5)`
**/clear**

---

## Phase 3: PERF — Unresolved Review Groups Cache (20 min)

### The Problem (Codex Finding #3)
`_build_unresolved_review_groups()` at cluster_review_routes.py:514 builds a full distance matrix for ~1571 identities (815ms). Called on every dashboard page load.

### The Fix
Add a TTL cache (same pattern as speed-run clusters):
1. Module-level cache dict: `_review_groups_cache = {}`
2. Cache key: community_slug
3. TTL: 120s (same as speed-run)
4. Invalidate on confirm/merge/skip/reject (add to `invalidate_cluster_review_caches`)

### Tests
- Test cache is populated after first call
- Test cache is returned within TTL
- Test cache is invalidated on identity mutation
- Test TTL constant is 120s

**Commit:** `perf: session 124 phase 3 — unresolved review groups cache (Codex #3)`
**/clear**

---

## Phase 4: UX Implementation from Antigravity/Screenshot Audit (25 min)

### If Antigravity output available:
Read the output file. Curate top 5 actionable improvements. Implement.

### If not available (fallback):
Take production screenshots of:
1. Landing page (mobile viewport)
2. Person page
3. Speed-run page
4. Compare tool

Analyze each for: visual hierarchy, touch targets, emotional design, information density.
Implement top 3 quick wins.

### Likely improvements:
- Mobile viewport meta tag optimization
- Touch target sizes on key actions
- Visual hierarchy on speed-run (larger face, smaller metadata)
- Warm accent colors for heritage context

### Tests
- Test any CSS/HTML changes don't break existing tests
- Test mobile viewport meta exists

**Commit:** `feat(ux): session 124 phase 4 — UX improvements from design audit`
**/clear**

---

## Phase 5: Security Audit + Harness Outputs (10 min)

### 5A: Security audit
Review all changed files for auth guards, injection, XSS.

### 5B: Harness outputs
1. Assessment: `docs/assessments/session-124-assessment.md`
2. CHANGELOG: v0.99.34
3. ROADMAP + SESSION_HISTORY
4. BACKLOG updates (PERF items)

### 5C: Gap check
Re-read this prompt. Verify every phase. Auto-fix gaps.

### 5D: Browser verify + remind user
Screenshots of speed-run (no recursive prefetch).
Ask about AD-229 upload testing.

**Commit:** `docs: session 124 harness outputs`
**Push to origin main**

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| Recursive prefetch fixed? | Test | Prefetched cards have no nested prefetch |
| Community indexes SQL? | File exists | 2 CREATE INDEX statements |
| Review groups cached? | Test | TTL cache, 120s, invalidated |
| UX improvements? | Test + browser | At least 3 improvements |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | File check | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |

## Parallelization

- **Phase 1 + Phase 2**: Can run in parallel (different files)
- **Phase 3**: Sequential after Phase 1 (same file: cluster_review_routes.py)
- **Phase 4**: Can run in parallel with Phase 1-3 if Antigravity output available
- **Phase 5**: Sequential last
