# Session 147: PRD-059 Phase 4 Completion — Identity Inference UI + Signals

## Context
Session 146 deployed the Fader collection and built PRD-059 Phase 4 foundation: identity_suggestions Supabase table, batch computation script (2/6 signals active), and 16 tests. Dry-run scored 19 candidates but confidence was low (0.288) because 4/6 signals were placeholders. Evidence panel UI was deferred as stretch.
See `docs/session_context/session-147-context.md` for full context.
See `docs/assessments/session-146-assessment.md` for predecessor assessment.

## Approach
This session runs autonomously. Follow all harness rules in `.claude/rules/`. Codex audit after every phase. /clear between phases. Assessment + ROADMAP + BACKLOG + CHANGELOG at end.

**Three parallel tracks** — Tracks A, B, C can run simultaneously in worktrees. No file conflicts.

---

## Phase 0: Orient (SEQUENTIAL — 3 min)

```bash
echo "147" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate
make test-fast  # Baseline — expect 3996+ app tests pass
```

- Read this prompt: `cat docs/prompts/session-147-prompt.md`
- Read context: `cat docs/session_context/session-147-context.md`
- Read SDD: `cat docs/prds/059_phase4_sdd.md`
- Read batch script: `cat scripts/compute_identity_suggestions.py`
- Read ML review pattern: `cat app/admin_routes.py` (lines 391-535)
- Read ML suggestion card pattern: `cat app/person_routes.py` (lines 960-1063)
- Verify identity_suggestions table exists: quick Supabase query
- Create session log: `docs/session_logs/session-147-log.md`

**Commit + /clear before proceeding.**

---

## Phase 1: Wire Remaining Signals + Execute (Track A — PARALLEL worktree)

**File**: `scripts/compute_identity_suggestions.py`
**Tests**: `tests/test_identity_suggestions.py`

### 1a: Wire age_trajectory (lines 474-475)
The function `compute_age_feasibility()` already exists at line 137 and is tested. Currently the pipeline assigns a placeholder at line 474. Fix:
- For each GEDCOM candidate (Fox siblings), get their birth year from `current_gedcom_individuals`
- For the unidentified target, call `compute_age_feasibility(target_id, candidate_birth_year, date_labels, identity_photos)`
- This requires loading GEDCOM data at pipeline start (new function `load_gedcom_birth_years()`)
- **Birth year parsing**: GEDCOM `birth_date` is TEXT ("1889", "ABT 1890", "BEF 1895"). Extract 4-digit year via regex.
- **Key decision**: age_trajectory makes most sense when scoring against a SPECIFIC GEDCOM candidate (e.g., "is this person Rachel born 1889?"). For the general "is this person a Fox family member?" query, use the GEDCOM candidates' birth year range (1877-1910 for Fox siblings) and check if the target's photo ages are consistent with ANYONE in that range.

### 1b: Implement gedcom_match signal (lines 477-478)
New function: `compute_gedcom_match_score(target_id, family_config, gedcom_data, co_occurrence_data)`
- Load Fox siblings from GEDCOM: Bessie (1877), Sarah (1882), Harry (1884), Sadie (1884), Rachel (1889), Albert (1893), Irving (1899), Jacob (1903)
- For each unidentified person, check: (a) do they co-occur with known siblings? (b) does their estimated age range match any unlinked GEDCOM sibling? (c) generation consistency (are they same generation as Esther/Albert?)
- Score: 1.0 if exact match (right era + right co-occurrence pattern), 0.5 if partial, 0.0 if contradicts
- **Known linked GEDCOM IDs**: Albert, Esther, Harry, Bessie, Rachel are confirmed. Remaining unlinked: Sarah, Sadie, Irving, Jacob.

### 1c: Implement testimony signal (lines 480-481)
Hardcode known testimony from Session 145:
```python
KNOWN_TESTIMONY = {
    "273ac560-bf13-43f5-8f87-e0f7ec967b2c": {  # Person 3481
        "score": 0.0,
        "entries": [{"source": "Howard Newman", "relationship": "grandson of Rachel Fox",
                     "statement": "almost certain NOT my grandmother", "polarity": "NEGATIVE"}]
    },
}
```
Add `# TODO(PRD-059-P5): migrate to testimony_evidence Supabase table`

### 1d: Implement provenance signal (lines 483-484)
Hardcode known provenance:
```python
KNOWN_PROVENANCE = {
    # Person 82863536 — Fox cousin labeled "Ervin Fox's sister Sadie"
    # (wrong name but confirms Fox family membership)
}
```
Also: query photo source/collection for family name mentions as secondary signal.

### 1e: Run execute mode
```bash
source venv/bin/activate
python scripts/compute_identity_suggestions.py --family fox --dry-run  # Verify scores > 0.288
python scripts/compute_identity_suggestions.py --family fox --execute  # Write to Supabase
```
Verify in Supabase: `SELECT count(*), avg(confidence), max(confidence) FROM identity_suggestions`

### Tests (add to tests/test_identity_suggestions.py)
- `test_age_trajectory_wired_in_pipeline()` — age_trajectory no longer returns placeholder
- `test_gedcom_match_basic()` — matching era+generation scores > 0.5
- `test_gedcom_match_impossible_era()` — person from 1960s photo can't be 1877 sibling
- `test_testimony_known_negative()` — Person 3481 testimony score = 0.0
- `test_provenance_known_fox()` — known provenance identity scores > 0
- `test_aggregate_with_all_signals_active()` — confidence higher than 2-signal baseline

**Acceptance**: All 16 existing tests pass + 6 new tests pass. Dry-run confidence > 0.4 for top candidate.

---

## Phase 2: Evidence Panel UI (Track B — PARALLEL worktree)

**File**: `app/person_routes.py`
**New test file**: `tests/test_identity_suggestion_ui.py`

### 2a: Load suggestions from Supabase
In the person page handler (around line 964, after ML birth year check):
```python
identity_suggestions = []
if is_admin:
    sb = _main_mod._get_supabase_client()  # or however the app gets the client
    if sb:
        try:
            resp = sb.table("identity_suggestions").select("*") \
                .eq("target_identity_id", person_id) \
                .eq("status", "PENDING") \
                .order("confidence", desc=True).limit(3).execute()
            identity_suggestions = resp.data or []
        except Exception:
            identity_suggestions = []
```

### 2b: Build evidence panel
After `ml_suggestion_card` (around line 1063), build `identity_suggestion_panel`:

**For each suggestion, render:**
1. **Header**: Suggested name + overall confidence (color-coded badge)
2. **Signal bars**: 6 rows, each with:
   - Signal name (human-readable: "Family Resemblance", "Co-occurrence", "Age Consistency", "GEDCOM Match", "Testimony", "Photo Source")
   - Visual bar (Tailwind `w-[N%]` or fractional widths)
   - Numeric score (0.82)
   - For absent signals (score=0 or placeholder): show "(not available)" in muted text
   - For NEGATIVE testimony: show in red with statement text
3. **Action buttons**:
   - "Accept as [Name]" (emerald, `hx_post=/api/identity-suggestion/{id}/accept`)
   - "Reject" (red, `hx_post=/api/identity-suggestion/{id}/reject`, `hx_confirm="Reject this suggestion?"`)
   - "Need More Evidence" (indigo, `hx_post=/api/identity-suggestion/{id}/needs-more`)
4. **Container**: `id=f"identity-suggestion-{suggestion['id']}"`, `data_testid="identity-suggestion-card"`
5. All buttons: `hx_target=f"#identity-suggestion-{suggestion['id']}"`, `hx_swap="outerHTML"`

**Helper function**: `_build_signal_bar(signal_name, display_name, evidence_data)` — returns a Div row.

### 2c: Insert into page layout
Add after `ml_suggestion_card` in the page build:
```python
*([identity_suggestion_panel] if identity_suggestion_panel else []),
```

### Tests (new file: tests/test_identity_suggestion_ui.py)
- `test_panel_renders_for_admin_with_pending()` — mock Supabase, verify `data_testid="identity-suggestion-card"` in HTML
- `test_panel_hidden_for_nonadmin()` — no card for public users
- `test_panel_hidden_when_no_suggestions()` — no PENDING rows → no card
- `test_signal_bars_render_all_six()` — all 6 signal names in rendered HTML
- `test_accept_button_has_correct_endpoint()` — verify hx_post URL
- `test_multiple_suggestions_sorted()` — highest confidence first

**Acceptance**: Admin on person with PENDING suggestions sees evidence card. Non-admin does not. Tests pass.

---

## Phase 3: Accept/Reject/NeedMore Endpoints (Track C — PARALLEL worktree)

**File**: `app/admin_routes.py`
**New test file**: `tests/test_identity_suggestion_actions.py`

Follow the ML birth year review pattern at lines 391-535 exactly.

### 3a: POST `/api/identity-suggestion/{suggestion_id}/accept`
```python
@rt("/api/identity-suggestion/{suggestion_id}/accept")
async def post(suggestion_id: str, sess):
    # 1. Admin + CSRF check
    err = _main_mod._check_admin(sess)
    if err: return err
    _main_mod._check_origin(request)

    # 2. Load suggestion from Supabase
    sb = _main_mod._get_supabase_client()
    resp = sb.table("identity_suggestions").select("*").eq("id", suggestion_id).single().execute()
    suggestion = resp.data
    if not suggestion:
        return Div("Suggestion not found", cls="text-red-400 text-sm")

    # 3. Verify target identity exists and is not already confirmed
    target_id = suggestion["target_identity_id"]
    registry = _main_mod._load_full_registry()
    identity = registry.get_identity(target_id)
    if not identity:
        return Div("Identity no longer exists", cls="text-red-400 text-sm")
    if identity.get("state") == "CONFIRMED":
        # Already confirmed — just mark suggestion as accepted
        sb.table("identity_suggestions").update({"status": "ACCEPTED", ...}).eq("id", suggestion_id).execute()
        return Div("✓ Already confirmed", cls="text-emerald-400 text-sm", ...)

    # 4. Rename + confirm
    suggested_name = suggestion["suggested_name"]
    registry.rename_identity(target_id, suggested_name)
    registry.confirm_identity(target_id)

    # 5. Link GEDCOM if available
    if suggestion.get("suggested_gedcom_id"):
        registry.set_metadata(target_id, {"gedcom_id": suggestion["suggested_gedcom_id"]})

    # 6. Save + cache invalidation
    _main_mod.save_registry(registry, changed_ids={target_id})

    # 7. Update suggestion status
    sb.table("identity_suggestions").update({
        "status": "ACCEPTED",
        "reviewed_at": datetime.utcnow().isoformat(),
        "reviewed_by": sess.get("email", "admin"),
    }).eq("id", suggestion_id).execute()

    # 8. Audit log
    _main_mod._audit_log("identity_suggestion_accepted", target_id, ...)

    # 9. Return success (auto-dismiss after 4s like ML review)
    return Div(
        "✓ Accepted — confirmed as " + suggested_name,
        cls="text-emerald-400 text-sm p-3",
        id=f"identity-suggestion-{suggestion_id}",
        **{"_": "on load wait 4s then add .opacity-0 to me then wait 500ms then remove me"},
    )
```

### 3b: POST `/api/identity-suggestion/{suggestion_id}/reject`
- Admin + CSRF check
- Accept optional `reason` form parameter
- Update Supabase: status=REJECTED, rejection_reason, reviewed_at, reviewed_by
- Return: red "✗ Rejected" auto-dismiss Div

### 3c: POST `/api/identity-suggestion/{suggestion_id}/needs-more`
- Admin + CSRF check
- Update Supabase: status=NEEDS_MORE, reviewed_at, reviewed_by
- Return: amber "⚑ Flagged for follow-up" auto-dismiss Div

### Tests (new file: tests/test_identity_suggestion_actions.py)
- `test_accept_renames_and_confirms()` — mock registry + Supabase, verify rename + confirm called
- `test_accept_requires_admin()` — 401/403 for non-admin
- `test_accept_already_confirmed()` — graceful handling
- `test_accept_nonexistent_suggestion()` — returns error div
- `test_reject_stores_reason()` — verify Supabase update with reason
- `test_reject_without_reason()` — still works
- `test_needs_more_sets_status()` — verify status=NEEDS_MORE
- `test_all_endpoints_check_csrf()` — verify _check_origin called

**Acceptance**: All 8 tests pass. Endpoints admin-gated and CSRF-protected.

---

## Phase 4: Integration + Browser Verify (SEQUENTIAL — after merge)

### 4a: Merge parallel tracks
```bash
./scripts/merge.sh track-a-branch track-b-branch track-c-branch
make test-fast  # All tests pass post-merge
```

### 4b: Run batch execute on production data
```bash
python scripts/compute_identity_suggestions.py --family fox --dry-run
# Verify: confidence > 0.4 for top candidate, all 6 signals contribute
python scripts/compute_identity_suggestions.py --family fox --execute
```

### 4c: Deploy + browser verify
```bash
git push origin main
```
Wait for deploy. Browser verify (READ-ONLY):
- Navigate to person page for a candidate with PENDING suggestion (e.g., Person 82863536)
- Screenshot: evidence panel visible with signal bars
- Screenshot: Accept/Reject/NeedMore buttons visible
- Navigate to person with NO suggestion — verify no card
- Navigate as non-admin — verify no card
- Standard smoke: landing, people grid, compare, estimate, 404

### 4d: Codex audit (final)
```bash
codex exec --full-auto "Audit app/person_routes.py, app/admin_routes.py, scripts/compute_identity_suggestions.py for Session 147 changes. Security + data integrity. P0/P1/P2/P3."
```

---

## Phase 5: Self-Evaluation + Close (SEQUENTIAL — MANDATORY)

### 5a: Re-read prompt
```bash
cat docs/prompts/session-147-prompt.md
```
Check every phase PASS/FAIL.

### 5b: Assessment
Write `docs/assessments/session-147-assessment.md`:
- What shipped (with evidence: test counts, browser screenshots)
- What deferred (with BACKLOG entries)
- Red flags
- AI Tool Usage section
- Next session should verify

### 5c: Update docs
- CHANGELOG.md: increment to v0.99.60
- ROADMAP.md: mark PRD-059 Phase 4 complete, update "Recently Completed"
- BACKLOG.md: close PRD059-PHASE4-UI, add any new items
- SESSION_HISTORY.md: add Session 147 entry

### 5d: Final checks
```bash
git log origin/main..HEAD  # Must be empty
```

Run `/session-review`.

---

## Constraints
- Browser automation is READ-ONLY on production (Lesson 149)
- Supabase is source of truth (not JSON) — data-layer.md
- AD-110: web requests NEVER run heavy ML — batch only
- Frozen files: core/neighbors.py, core/pfe.py, data/*
- GEDCOM birth_date is TEXT — needs regex parsing
- Fox sibling list is DEFINITIVE: Bessie, Sarah, Harry, Sadie, Rachel, Albert, Irving, Jacob
- Rose Scheckzner is Harry's WIFE, not a sibling

## Key Files
- `docs/session_context/session-147-context.md` — full context
- `docs/prds/059_temporal_co_occurrence.md` — PRD
- `docs/prds/059_phase4_sdd.md` — SDD with wireframe + data model
- `docs/ml/ALGORITHMIC_DECISIONS.md` — AD-235 Family Cluster Score
- `scripts/compute_identity_suggestions.py` — batch pipeline (574 lines)
- `app/person_routes.py:960-1063` — ML suggestion card (UI pattern to follow)
- `app/admin_routes.py:391-535` — ML review endpoints (API pattern to follow)
- `tests/test_identity_suggestions.py` — existing 16 tests
- `scripts/sql/session_146_identity_suggestions.sql` — table schema

## Parallelization Plan
| Track | Phase | Files | Depends On |
|-------|-------|-------|------------|
| Sequential | Phase 0 | — | — |
| Track A (worktree) | Phase 1 | scripts/compute_identity_suggestions.py, tests/test_identity_suggestions.py | Phase 0 |
| Track B (worktree) | Phase 2 | app/person_routes.py, tests/test_identity_suggestion_ui.py | Phase 0 |
| Track C (worktree) | Phase 3 | app/admin_routes.py, tests/test_identity_suggestion_actions.py | Phase 0 |
| Sequential | Phase 4 | merge + verify | Tracks A+B+C |
| Sequential | Phase 5 | docs | Phase 4 |

## Mandatory Close
- Assessment: `docs/assessments/session-147-assessment.md`
- CHANGELOG: increment to v0.99.60
- ROADMAP + BACKLOG: update status
- Browser verify: evidence panel on person page, signal bars, action buttons
- `git log origin/main..HEAD` must be empty
- Run `/session-review`
