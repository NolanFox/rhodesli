# Session 151 Prompt — Deferred Work Completion + Harness Audit

**Mode:** implementation
**Predecessor:** Session 150 (v0.99.65)
**Baseline:** 4151 app tests

## Orientation
Read: `docs/assessments/session-150-assessment.md`, `docs/session_context/session-151-context.md`
Set: `echo "151" > .claude/current_session.txt`
Baseline: `make test-fast`

## Phase 1: Batch Event Context Script (~30 min)

### 1a: Build `scripts/batch_event_context.py`
- Query Fader photo_ids from `photo_communities` where community_id = `1a2c23d6-fc5e-4d0e-b020-1721579485bf`
- Use "identification" preset + `build_response_schema(preset="identification")`
- Upsert to Supabase `date_labels` table (source of truth — Lesson 162)
- Rate limiting, resume support (skip existing event_context), cost tracking
- Log every call to `gemini_api_calls` table
- Pattern: follow `scripts/batch_gemini_for_person.py` structure

### 1b: Tests
- Test script argument parsing
- Test community photo query (mocked)
- Test skip-existing logic
- Test Supabase upsert path (mocked)

### 1c: Dry-run on 5 photos
- `python scripts/batch_event_context.py --dry-run --limit 5`
- Then `python scripts/batch_event_context.py --limit 5`
- Verify results in Supabase date_labels table

Commit + /clear

## Phase 2: Browser Verify Deferred Session 150 Items (~15 min)
- Mobile responsive at 375px: landing, person, compare, photo pages
- Text hints textarea on /tools/estimate
- Identity suggestions panel on person page (PRD-059 Phase 4)
- Screenshots to `docs/screenshots/session-151/`

Commit + /clear

## Phase 3: Codex Audit (~10 min)
- Audit all changed files from this session
- Security, code quality, test quality
- P0/P1: fix immediately
- P2: fix if quick, else BACKLOG
- Save to `docs/session_context/session-151-codex-audit.md`

Commit + /clear

## Phase 4: Session Close
- Assessment: `docs/assessments/session-151-assessment.md`
- CHANGELOG: v0.99.66
- ROADMAP + SESSION_HISTORY: update
- BACKLOG: close done items
- Deploy: `git push origin main`
- Browser verify: health 200
- Memory backup: `./scripts/backup-memory.sh`
- Run /session-review
