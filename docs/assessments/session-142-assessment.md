# Session 142 Assessment — FINAL

## Summary
Interactive feedback session + batch Gemini estimation for Esther/Albert Fox temporal analysis.
**Version**: v0.99.53 → v0.99.54 | **Tests**: 3846 passing | **Site**: healthy

---

## Shipped — Feedback Fixes (12 items)

| FB | P | Fix | Commit |
|---|---|---|---|
| FB-001 | P1 | Similar Identities links → /person/{uuid} not review grid | e953ba6 |
| FB-002 | P1 | Compare "View Photo" missing community prefix | e953ba6 |
| FB-003 | P1 | Multi-merge Focus mode toast instead of redirect | e953ba6 |
| FB-004 | P0 | "Confirm as [Name]" now merges with target | efa43f5 |
| FB-006 | P1 | Bulk merge "already merged" shown as info not warning | efa43f5 |
| FB-007 | P1 | Similar panel filters merged identities | efa43f5 |
| FB-008 | P1 | Neighbor fetch limit 20→100 | 7a32cf7 |
| FB-010 | P1 | Face overlay click → person page | 06b70e3 |
| FB-011 | P2 | "Confirm Only" button alongside "Confirm as [Name]" | 2b13269 |
| FB-012 | P2 | Expansion panel cleared after confirm | 4f5f1d4 |
| FB-005 | P2 | Merge toast improved (via FB-003/006) | efa43f5 |
| FB-009 | P2 | Speed Loop auto-suggestion — DEFERRED (feature gap) | — |

## Shipped — Security (Codex Audit #1)

- P1 CSRF: `/inbox/{id}/confirm` missing `_check_origin()` — FIXED
- P1 Merge side effects: confirm+merge now runs `_merge_annotations()` + recalibration — FIXED
- P2 Rematch target: post-confirm uses surviving target ID — FIXED
- P0 Face sort: coordinates sorted left-to-right for Gemini — FIXED

## Shipped — Infrastructure

- **Startup retry**: 3-attempt retry with 10/20/30s backoff for Supabase identity load on Railway
- **Quota early-stop**: Batch script stops immediately on 429 RESOURCE_EXHAUSTED
- **First-result quality check**: Verifies GEDCOM, face coords, all enrichments on photo #1
- **GEDCOM preload optimization**: Loads tree once (not per-photo). 6h → 30min batch time.
- **Supabase audit backfill**: 82 gemini_api_calls rows inserted from local data

## Shipped — Temporal Co-Occurrence (PRD-059)

- **PRD-059 drafted**: 4-phase plan for family identification via temporal analysis
- **Phase 2 event grouping**: scripts/event_grouping.py — 8 event groups from 84 dated photos
- **Admin UI**: /admin/event-groups timeline page with event groups + frequent companions
- **Co-occurrence analysis**: 3 frequent companions identified, GEDCOM cross-referenced
  - Person 3051 likely Sarah "Sura" Burd (Esther's sister, b.1892)
  - 31 unidentified faces in 1920-1924 era = highest priority targets
- **Research**: Temporal co-occurrence best practices documented (Dai et al. WACV 2015, Apple/Google approaches)

## Shipped — Prompt Improvements

- **AD-231**: Merge legacy prompt fields into full extraction preset
- scene_description, capture_vs_print, reasoning_summary added to "full" preset
- Prompt comparison documented (old 80% high conf vs new 45% high conf)
- 10 new extraction tests

## Gemini Batch Status — INCOMPLETE

### What ran:
- **84 photos** processed with "full" preset (face analysis, subject ages, group composition)
- **83 of 84 have NO GEDCOM context** — the overnight batch timed out on Supabase GEDCOM loading for every photo. GEDCOM preload fix was implemented AFTER those runs.
- **1 photo with proper GEDCOM context**: `inbox_fox-charlie-001_12_01635_p_13akf5twbc0904` (1917, male age 21, high confidence)
  - URL: https://rhodesli.nolanandrewfox.com/c/fox-family/photo/inbox_fox-charlie-001_12_01635_p_13akf5twbc0904
- **195 photos never processed** — blocked by Gemini free tier quota (250/day)

### Why it failed:
1. Free tier limit is 250 requests/day for gemini-3.1-pro
2. Overnight batch used ~80 calls, test calls used ~5, second batch attempt used rest
3. GEDCOM context loading timed out per-photo (before preload fix was implemented)
4. Did not verify GEDCOM was included after first batch photo (Lesson 161)

### What needs to happen:
1. **Enable billing** at https://aistudio.google.com/apikey → upgrades to Tier 1 (1,500/day)
2. **Re-run ALL 279 photos** (not just remaining 195) — the 83 without GEDCOM need redo
3. **Cost**: ~$15.35 total for 279 photos
4. **Time**: ~30 minutes with GEDCOM preload
5. **Clear existing labels first** (`--no-skip-existing` flag)

## Codex Audits (4 total)

### Audit #1: Security + Code Quality
- 3 P1 + 2 P2 findings. All P1s fixed. STRONG value — caught CSRF.

### Audit #2: Gemini Prompt Quality
- 3 P0 + 4 P1 findings. Face sort P0 fixed. Prompt improvements adopted. STRONG value — identified contract drift.

### Audit #3: Batch API Speed
- P0: GEDCOM preload (implemented). P1: precompute maps. P2: client reuse. MODERATE value.

### Audit #4: GEDCOM Preload + Backfill
- No P0s. P1: SERVICE_ROLE_KEY documentation. P2: cost_usd missing in backfill. Safe.

## Lessons Learned

| # | Lesson |
|---|---|
| 159 | ALWAYS verify deploy health before ending session — site was down overnight |
| 160 | Batch scripts must verify logging on first call — 82 calls unlogged |
| 161 | Verify FULL output quality on first batch call — 83 photos ran without GEDCOM |

## Red Flags

- **HIGH**: 83/84 Gemini labels lack GEDCOM context. Need full re-run after billing enabled.
- **MEDIUM**: Free tier 250/day limit makes batch work impractical. Enable billing ($0/month, pay-per-use).
- **LOW**: Supabase free tier instability caused 3+ failed Railway deploys during session.

## Deferred to Next Session

| Item | Reason |
|---|---|
| Re-run all 279 photos with GEDCOM | Need billing enabled (Tier 1: 1,500/day) |
| FB-009 Speed Loop auto-suggestion | Feature gap, needs proposal pipeline |
| BATCH-001 atomic JSON writes | P2, Codex finding |
| BATCH-002 Supabase date labels sync | P2, Codex finding |
| PRD-059 Phase 3 co-occurrence matrix | Depends on complete Gemini data |
| PRD-059 Phase 4 identity inference | Depends on Phase 3 |

## Next Session Should Do FIRST

1. Enable Gemini billing (Tier 1) at https://aistudio.google.com/apikey
2. Re-run ALL 279 photos: `python scripts/batch_gemini_for_person.py --identity 65207728-... --identity 85546ebf-... --no-skip-existing --max-cost 20`
3. Verify first result has GEDCOM context (quality check will warn if not)
4. After batch: re-run event_grouping.py, update event_groups.json
5. Browser verify the event groups admin page with full data

## Session Stats
- **Commits**: 28
- **Tests**: 3846 (31 new)
- **Files changed**: ~30
- **Codex audits**: 4
- **Subagents launched**: 12+
- **Gemini API calls**: ~170 (84 successful, rest quota-blocked)
- **Duration**: ~17 hours (overnight + morning)
