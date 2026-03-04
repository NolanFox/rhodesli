# Session 88: Fix Session 87 Scoring & Card Failures

## Context
Session 87 claimed to unify confidence scoring and improve Compare/Discoveries UX but failed:
- Scoring STILL divergent (62% vs 43% for same distance 1.13)
- Discovery cards inconsistent with review cards (missing distance, gap, actions)
- Compare link from Discoveries broken (wrong URL params)
- Per-face accordion headers useless when collapsed
- Admin badge noise on every card

**Predecessor**: Session 87 (v0.91.0)

## User Decisions (from planning conversation)
1. **Scoring**: Calibrator everywhere -> one consistent score. No dual display. No admin badges.
2. **Card design**: Unified `match_card()` component. ADDITIVE from neighbor_card base. No risky rewrites.
3. **Accordion headers**: Show "Face N -- X matches (best: [Name] [Confidence]%)"
4. **Admin badges**: Remove per-card "Admin" labels. Sidebar shows admin status globally.
5. **Scope**: All 5 fixes.

## Root Causes

### Scoring: batch override in neighbors.py
- `core/confidence.py::_compute_pct()` tries isotonic calibrator -> falls to linear `(2-d)/2*100 = 43%`
- `core/neighbors.py::find_similar_faces()` lines 359-363 OVERRIDES with batch ONNX -> 62%
- Fix: Debug isotonic loading, remove batch override

### Cards: 3 separate implementations
- `neighbor_card()` (main.py:6668): richest -- distance, gap, co-occurrence, Compare/Merge/Not Same
- `_build_discovery_card()` (main.py:23417): MISSING distance, gap, Profile, Similar
- Fix: Unified match_card() based on neighbor_card

### Compare link: wrong URL params
- Discovery generates `/compare?source={id}&target={id}`, route expects `face_id=`, `person_id=`
- Fix: `/compare?face_id={source_face}&person_id={target_id}`

### Accordion: no match preview
- Shows "Face N" only. Fix: "Face N -- X matches (best: [Name] [Pct]%)"

### Admin badge: noise
- "Admin" on every card. Fix: subtle gear icon

---

## Act 1: Orient & Setup (5 min)
- Set current_session.txt to "88"
- Create prompt, context, and log files
- Log Lesson 101: "Subagent work MUST be browser-verified before declaring PASS"
- Commit + /clear

## Act 2: Fix Scoring (core/confidence.py + core/neighbors.py)
- Debug isotonic calibrator loading in `_get_calibrator()`
- Remove batch override in neighbors.py lines 339-363
- Add scoring consistency tests
- Commit + /clear

## Act 3: Quick Fixes (Fix 3+4+5) -- CAN PARALLELIZE
**Track A** (compare_routes.py): Accordion headers -- "Face N -- X matches (best: Name Pct%)"
**Track B** (main.py): Compare link fix + Admin badge -> gear icon
- Commit + /clear

## Act 4: Unified match_card (main.py only)
- Phase 1: Create match_card() near neighbor_card with config flags
- Phase 2: neighbor_card delegates to match_card (run tests)
- Phase 3: _build_discovery_card uses match_card (run tests + browser verify)
- ADDITIVE only. No rewrites. Functionality loss = session failure.
- Commit + /clear

## Act 5: Verify & Close
- Deploy, browser verify all pages, screenshots, assessment, docs
- /session-review

## Key Files
| File | Acts | Changes |
|------|------|---------|
| core/confidence.py | 2 | Fix calibrator loading |
| core/neighbors.py | 2 | Remove batch override lines 339-363 |
| app/main.py | 3,4 | Compare link, admin badge, match_card |
| app/compare_routes.py | 3 | Accordion headers |
| tests/test_confidence.py | 2 | Consistency tests |
