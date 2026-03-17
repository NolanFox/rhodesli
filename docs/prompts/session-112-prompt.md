# Session 112 — Single Source of Truth: Eliminate JSON Split-Brain (PRD-051 Phase 1)

## Context
@docs/session_context/session-112-context.md
@docs/prds/051_single_source_of_truth.md

Session 111d exposed the 8th data corruption incident from three-source data divergence (Lessons 56→69→78→85→133→141→144→147→150). This session implements PRD-051 Phase 1: make Supabase the single read source for identities and photos. No more JSON reads in production.

## CRITICAL CONSTRAINTS — READ BEFORE STARTING

1. **ZERO REGRESSIONS.** Every change must be tested before AND after. If you're not sure a change is safe, plan it out first. Ask if unclear.
2. **Plan before coding.** Before modifying ANY read path, write out: what reads from this path, what would break if it returns different data, what test covers it.
3. **No fly-by-night decisions.** Every architectural choice gets documented in the session log with rationale.
4. **Browser verify EVERYTHING.** Every phase that touches data loading must be verified on production. READ-ONLY browser checks — NEVER click action buttons.
5. **Measure twice, cut once.** The last session shipped 3 regressions. That cannot happen again.

## Pre-Requisites
1. Read `tasks/lessons.md` — especially Lessons 56, 69, 78, 85, 133, 141, 144, 147, 149, 150
2. Read `docs/prds/051_single_source_of_truth.md` — the full PRD
3. Read `docs/session_context/session-112-context.md` — research findings and risks
4. Read `docs/CODING_RULES.md`
5. Set `.claude/current_session.txt` to `112`
6. Set `.claude/session_mode.txt` to `implementation`

---

## Phase 0: Audit + Plan (20 min)

**Do NOT write code in this phase.** This is planning only.

1. `git log --oneline -5` — confirm 111d on main
2. Map every split-brain vector — grep for ALL of these:
   - `json.load` in `app/` directory
   - `DATA_SOURCE` checks
   - `REGISTRY_PATH` reads
   - `photo_index_path` reads
   - `.load(` calls on data paths
3. For EACH vector, document:
   - File and line number
   - What Supabase function would replace it
   - What breaks if removed (downstream callers)
   - What test covers it
4. Write the plan to the session log BEFORE starting Phase 1
5. /clear after this phase

---

## Phase 1: Identity Read Path — Supabase Only (30 min)

### 1A: `load_registry()` — remove JSON fallback
- `app/main.py` ~line 1220: Remove the `if DATA_SOURCE == "postgres"` branch
- Always call `IdentityRegistry.load_from_postgres()`
- If Supabase fails: log error, return empty registry (never silently fall back to stale JSON)
- Keep JSON write in `save_registry()` as backup — but label it clearly as "backup only, never read"

### 1B: `save_registry()` — verify write-through
- Verify `save_registry()` writes to Supabase synchronously (not background thread)
- Verify `changed_ids` parameter works correctly with Supabase writes
- Verify `identity_overrides` table is updated consistently (Session 111d bug)

### Tests (write BEFORE implementing)
- `test_load_registry_reads_from_supabase` — mock Supabase, verify JSON is NOT read
- `test_save_registry_writes_to_supabase` — verify Supabase write is called
- `test_load_registry_returns_empty_on_supabase_failure` — no JSON fallback
- Run ALL existing registry tests to catch regressions

### Commit + /clear after this phase

---

## Phase 2: Photo Read Path — Supabase Only (30 min)

### 2A: `_build_caches()` — the critical fix
- `app/main.py` ~line 3931: Currently calls `json.load(photo_index_path)` directly
- Replace with data from `load_photo_registry()` (Supabase-backed)
- **CAUTION:** `_build_caches()` uses photo_index data to build filename-based fallback maps. The replacement must produce identical data structures.
- Plan the mapping BEFORE writing code: what fields does `_build_caches()` need from photo_index, and where do those fields exist in the PhotoRegistry?

### 2B: `load_photo_registry()` — remove JSON fallback
- Same pattern as 1A

### 2C: `_load_photo_dimensions_cache()` — use photo registry
- Currently reads `photo_index.json` directly
- Replace with data from `load_photo_registry()`

### Tests (write BEFORE implementing)
- `test_build_caches_does_not_read_json` — verify no `json.load()` call
- `test_photo_dimensions_from_supabase` — dimensions come from registry, not JSON
- Run ALL existing photo/face tests

### Commit + /clear after this phase

---

## Phase 3: Remove DATA_SOURCE config (15 min)

1. Remove `DATA_SOURCE` environment variable — postgres is the only mode
2. Remove all `if DATA_SOURCE == "json"` code paths (dead code after Phase 1-2)
3. Update `.env.example` — remove `DATA_SOURCE`
4. Update CLAUDE.md if it references `DATA_SOURCE`

### Commit + /clear after this phase

---

## Phase 4: Deploy + Exhaustive Verification (20 min)

1. Run full test suite: `make test-fast` + `make test-ml`
2. `git push origin main`
3. Wait for deploy SUCCESS (verify builder is DOCKERFILE)
4. **MANDATORY production checks (READ-ONLY — no clicking action buttons):**
   - [ ] Home page loads with photos and face counts
   - [ ] People page shows all confirmed identities (count matches pre-deploy)
   - [ ] New Matches page loads with identity cards
   - [ ] Focus mode shows identity with Similar panel
   - [ ] Photo page shows face overlays with bounding boxes
   - [ ] Search returns results
   - [ ] Person page loads for confirmed identity
   - [ ] Person page loads for INBOX identity
5. **Data persistence test (ask user to perform):**
   - Ask user to confirm one identity, then hard refresh — verify it persisted
   - Ask user to merge one identity, then hard refresh — verify it persisted
6. **Direct Supabase edit test:**
   - Read an identity name via Supabase query
   - Wait 120s (TTL)
   - Verify the app shows the current Supabase value (not a stale cache)

---

## Phase 5: Harness Outputs (10 min)

1. Assessment: `docs/assessments/session-112-assessment.md`
2. Session log: `docs/session_logs/session-112-log.md`
3. ROADMAP: Add session entry, update version
4. CHANGELOG: Session 112 entry
5. BACKLOG: Update DATA-024 status
6. Verify `git log origin/main..HEAD` is empty

---

## Verification Checklist (before declaring done)

- [ ] No `json.load()` calls on `identities.json` or `photo_index.json` in `app/` read paths
- [ ] No `DATA_SOURCE == "json"` branches in `app/` read paths
- [ ] `_build_caches()` uses `load_photo_registry()` not `json.load()`
- [ ] `_load_photo_dimensions_cache()` uses photo registry not `json.load()`
- [ ] `load_registry()` always loads from Supabase
- [ ] `save_registry()` writes Supabase synchronously + JSON as backup
- [ ] All admin actions persist across app restart (user-verified)
- [ ] All tests pass (app + ML)
- [ ] Deployed and browser verified (READ-ONLY)
- [ ] `git log origin/main..HEAD` is empty
- [ ] Assessment written with evidence
