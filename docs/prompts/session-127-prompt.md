# Session 127 — Accessibility + Polish + Codex Audit

@docs/session_context/session-127-context.md
@tasks/lessons.md

## Goal

Fix remaining test flakiness, ship accessibility and touch target improvements, execute SQL indexes, run Codex security/accessibility audit, and merge Antigravity design polish. Parallelize aggressively via worktree subagents.

## CRITICAL CONSTRAINTS

1. **Browser automation is READ-ONLY on production** (Lesson 149).
2. **DO NOT touch**: `core/neighbors.py` (frozen), `core/pfe.py`, `data/*` files.
3. **Every change gets tests** — happy path + failure + regression.
4. **/clear between phases** — commit first, then /clear immediately.
5. **Parallelize**: Use worktree subagents for independent file changes. Use /prompt-parallelizer if phases touch 3+ files.
6. **Use skills**: /session-review at end, /ux-review after screenshots, /simplify after implementation.
7. **Antigravity file ownership**: Antigravity owns `app/browse_routes.py` and `app/estimate_routes.py` this session. You own everything else.

## Pre-Requisites

```bash
echo "127" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — must pass
```

---

## Phase 0: Orient + SQL Indexes + Last Flaky Test (15 min)

1. Create session log
2. Execute SQL indexes on production:
   ```bash
   curl -X POST https://rhodesli.nolanandrewfox.com/api/admin/run-migrations \
     -H "Cookie: <admin session cookie from browser>"
   ```
   Use Chrome browser tool to get the session cookie, then curl. Verify indexes created.
3. Fix `test_confirmed_anchors_in_face_to_photo` — same pattern as Session 126: stale cache not cleared between test files. Find the test, add `_raw_embeddings_cache = None` or equivalent teardown.
4. Run `make test-fast` — target: 0 failures.

**Commit + /clear**

---

## Phase 1: Accessibility + Touch Targets — Worktree Subagents (30 min)

Launch parallel worktree subagents:

### Subagent A: Touch Targets (app/cluster_review_routes.py, app/engagement_routes.py)
- Cluster review status badges: `py-0.5` → `py-1` (BACKLOG UX-AUDIT-001)
- Engagement pagination numbers: increase to `px-3 py-1.5`
- Any other interactive elements below 36px height

### Subagent B: SVG Aria Labels (app/tools_routes.py, app/main.py, app/discoveries_routes.py)
- Add `aria-label` to all icon-only SVG elements (BACKLOG UX-AUDIT-002)
- Add `role="img"` to decorative SVGs
- Add `aria-hidden="true"` to purely decorative icons that duplicate text

### Subagent C: UX Quick Wins (app/main.py)
- Top bar: clarify "TO REVIEW" vs "PROPOSALS" labels (rename to match sidebar)
- Focus/View All/Match buttons: reorder so primary action (Focus) is leftmost
- Confidence tier labels next to raw ML distance/gap numbers

Merge all worktrees, run tests.

**Commit + /clear**

---

## Phase 2: Person Page Polish — Worktree Subagents (20 min)

### Subagent D: Person Page CTA + Friction (app/person_routes.py)
- For CONFIRMED people with Unknown birth/death/place: add "Can you help?" CTA linking to annotation form
- Merge search box on CONFIRMED people: add confirmation dialog ("This person is confirmed — are you sure you want to merge?")

### Subagent E: Face Crop Fallback (app/main.py or app/browse_routes.py)
- When face crop fails to load (404/broken), show a placeholder silhouette instead of broken image
- Use `onerror` attribute on crop `<img>` tags to swap to a CSS placeholder

Merge, run tests.

**Commit + /clear**

---

## Phase 3: Codex Security + Accessibility Audit (30 min)

Write a Codex prompt to `docs/prompts/session-127-codex-audit-prompt.md`:

> "Audit the Rhodesli codebase for: (1) Security: auth guard gaps on POST routes, input sanitization, SQL injection via Supabase RPC, CSRF. (2) Accessibility: missing aria-labels, focus traps, keyboard-only navigation blockers, color contrast below WCAG AA. (3) Dead code: unused routes, orphaned imports, stale feature flags. Read all files in app/. Write findings to docs/session_context/session-127-codex-audit.md. Do NOT modify any code."

Review findings. For each:
- Security P0/P1 → fix immediately
- Accessibility quick win → implement via subagent
- Dead code → clean up if safe
- Needs design → BACKLOG

**Commit + /clear**

---

## Phase 4: Merge Antigravity + Deploy + Verify (20 min)

1. Check Antigravity branch `session-127/antigravity-polish`
2. Safety checklist:
   - No data/ changes, no core/ changes, no auth guard removals
   - No route path changes, no Supabase query changes
   - Only modifies browse_routes.py and estimate_routes.py
3. Cherry-pick safe changes, reject unsafe
4. Full test suite
5. Deploy via `git push origin main`
6. Browser verify: landing, people grid, person page, compare, estimate, 404
7. Run /ux-review on screenshots

**Commit + /clear**

---

## Phase 5: Harness Outputs (10 min)

1. Assessment: `docs/assessments/session-127-assessment.md`
2. CHANGELOG: v0.99.37
3. ROADMAP + SESSION_HISTORY
4. BACKLOG updates (close fixed items, add new)
5. Run /session-review

**Commit + Push**

---

## Verification Gate

| Check | Method | Expected |
|-------|--------|----------|
| SQL indexes created? | curl response | Both indexes OK |
| Flaky test fixed? | `make test-fast` 3x | 0 failures all runs |
| Touch targets ≥36px? | Browser inspect | All interactive ≥ py-1 |
| Aria labels added? | grep aria-label | 20+ new instances |
| UX quick wins? | Browser | Labels, button order, tiers |
| Person page CTA? | Browser | "Can you help?" visible |
| Codex audit done? | File exists | Audit doc with findings |
| Security fixes? | If any P0/P1 | Fixed and tested |
| Antigravity merged? | git log | Commit or BACKLOG note |
| All tests pass? | `make test-fast` | PASS |
| Assessment exists? | File check | Exists |
| `git log origin/main..HEAD` empty? | git log | Empty |
