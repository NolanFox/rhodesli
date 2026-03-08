# Session 92: Ship Everything — Close All Gaps, Deploy, Verify, Harden

**Context**: `docs/session_context/session-92-context.md`
**Predecessor**: Session 91b (`docs/assessments/session-91b-assessment.md`)

## Problem Statement

Sessions 90-91b built significant features (main.py refactor, discoveries, notifications, Supabase tables, GEDCOM prompt improvements) but left critical gaps: env vars not set, tables not executed against production Supabase, API call logging incomplete, Leon's Restaurant still wrong, P1 UX bugs open, tests flaky, email notifications unwired, share flow unverified. This session closes EVERYTHING.

Nolan's directive: "Address all outstanding gaps and deferrals and solve and fully cover everything in Option 1 through Option 6 (and everything in between)."

## Session Protocol
- Set `.claude/current_session.txt` to `92`
- Read `tasks/lessons.md` at start
- Commit after every act, `/clear` between acts (NON-NEGOTIABLE — Lesson 89, failed 5+ times)
- Use Claude Chrome for ALL frontend verification (Lesson 97)
- Use subagents in worktrees for parallel tracks (Lesson 88)
- Run `make test-fast` before every commit (Lesson 80)
- Run `/session-review` at session end (mandatory)
- Screenshots to `docs/screenshots/session-92/`

---

## Parallelization Plan

### Round 1: Orient (Act 0) — sequential on main
### Round 2: 6 parallel worktree tracks (Acts 1-6) — independent
### Round 3: Merge Round 2 + sequential tracks (Acts 7-8) — on main
### Round 4: Verify + Assess (Act 9) — on main

| Track | Branch | Scope | Files Touched | Independent? |
|-------|--------|-------|---------------|-------------|
| C: Tests | `session-92/tests` | Test hardening + CI/CD | tests/, conftest.py, .github/ | Yes |
| D: UX Fixes | `session-92/ux-fixes` | 10 P1/P2 UX bugs | app/*_routes.py, app/main.py | Yes |
| E: Growth Loop | `session-92/growth` | Email, share, help-identify, timeline | app/notification_routes.py, app/event_routes.py | Yes |
| F: Gemini+ML | `session-92/gemini-ml` | Leon's fix, API logging, multi-pass | rhodesli_ml/, app/estimate_routes.py, app/supabase_data.py | Yes |
| G: Products | `session-92/products` | Compare Tier 2, NL Query, Date Estimator | New files mostly | Yes |
| H: Architecture | `session-92/arch` | pgvector eval, CI/CD, debt docs | docs/, scripts/ | Yes |

**Sequential on main (before parallel)**: Acts 1-2 (Deploy verify + Supabase tables)
**Parallel Group**: C + D + E + F + G + H (all independent files)
**Merge Order**: H (docs) → C (tests) → D (UX) → E (growth) → F (ML) → G (products)

### Subagent Context Briefs

Each subagent gets:
1. This prompt (their track section only)
2. `docs/session_context/session-92-context.md`
3. `tasks/lessons.md`
4. Key source files listed in their track section

Each subagent MUST:
- Run `make test-fast` before every commit (Lesson 80)
- Run `make test-ml` if touching rhodesli_ml/ (dual test suite rule)
- Commit ALL files before completing (Lesson 87)
- Use conventional commits: `feat/fix(scope): description`
- NOT touch files outside their listed scope

---

## Act 0: Orient + Verify State (5 min)

1. Read this prompt, `docs/session_context/session-92-context.md`, `tasks/lessons.md`
2. `git status`, `git log --oneline -10`, verify `make test-fast` passes
3. Set `.claude/current_session.txt` to `92`
4. Create `docs/session_logs/session-92-log.md` with phase checklist
5. Record baseline: `time make test-fast`, count tests, note any failures
6. Verify v0.94.1 is deployed: `curl -s https://rhodesli.nolanandrewfox.com/health | jq .version`

Commit: `chore: session 92 orient`

**IMMEDIATELY /clear after this commit.**

---

## Act 1: Deploy Verification + Railway Env Vars (15 min) — sequential on main

**NO CODE CHANGES — browser + Railway CLI only.**

### 1a. Set Railway Environment Variables

Use Railway MCP or CLI to set:
```
SENTRY_DSN=<value from Nolan or create Sentry project>
POSTHOG_API_KEY=<value from Nolan or create PostHog project>
RESEND_API_KEY=<value from Nolan>
```

If values are unknown, document what's needed and move on. Do NOT block on this.

### 1b. Browser Verify Production (Claude Chrome)

Navigate to https://rhodesli.nolanandrewfox.com and verify each page:

1. **Landing page** — loads, photos visible, stats counter works
2. **Browse /photos** — grid renders, collection filter works
3. **Person page** — `/person/{any_confirmed_id}` — name, faces, photos visible
4. **Photo detail** — `/photo/{any_id}` — image loads, face overlays work
5. **Discoveries /discoveries** — three sections visible, cards have confidence labels (not percentages)
6. **Notifications** — bell icon visible when logged in, `/notifications` page loads
7. **Events /events** — page loads, seeded events visible (check for double admin bar bug)
8. **Compare /compare** — page loads, upload form visible
9. **Estimate /estimate** — page loads, upload form visible
10. **About /about** — page loads, navbar present

Save screenshots to `docs/screenshots/session-92/`

### 1c. Verify Confirm → Notification E2E

1. Navigate to any PROPOSED identity
2. Click "Confirm"
3. Check `/notifications` — new notification should appear
4. Check bell icon — badge count should increment
5. Click "Mark as Read" — badge should decrement

If notification trigger doesn't fire, document the gap for Act 7 (E track).

### 1d. Verify Leon's Restaurant Current State

1. Navigate to photo `inbox_staged-20260210-182610_5_757557421.130308`
2. Note current location estimate (expected: still showing wrong location)
3. Screenshot as "before" evidence for Track F fix

Commit: `docs: session 92 deploy verification + screenshots`

**IMMEDIATELY /clear after this commit.**

---

## Act 2: Supabase Tables + Data Verification (15 min) — sequential on main

### 2a. Verify Existing Tables

Connect to Supabase (use DATABASE_URL from .env or Supabase MCP):
```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' ORDER BY table_name;
```

Check which of these exist:
- `communities` — should exist from Session 91b
- `life_events` — should exist
- `notifications` — should exist
- `global_person_links` — should exist
- `gemini_api_calls` — should exist from Session 64

### 2b. Execute Missing Tables

For any missing table, run the corresponding SQL script:
- `scripts/sql/create_communities.sql` + `scripts/sql/seed_rhodes_community.sql`
- `scripts/sql/create_life_events.sql`
- `scripts/sql/007_notifications.sql`
- `scripts/sql/create_global_person_links.sql`

### 2c. Verify Seed Data

```sql
SELECT count(*) FROM communities;        -- expect >= 1
SELECT count(*) FROM life_events;         -- expect >= 5
SELECT count(*) FROM notifications;       -- expect >= 0
SELECT count(*) FROM global_person_links; -- expect 0
SELECT count(*) FROM gemini_api_calls;    -- expect > 0
```

If life_events is empty, run: `python scripts/seed_life_events.py`

### 2d. Test DATA_SOURCE=postgres (Quick Flip)

1. Set `DATA_SOURCE=postgres` on Railway
2. Verify app loads (health check, landing page, one person page)
3. If working: leave on postgres. If broken: flip back to `json` and document issue.

Commit: `chore: session 92 Supabase verification + data seeding`

**IMMEDIATELY /clear after this commit.**

---

## Act 3 (Track C): Test Hardening + CI/CD — worktree `session-92/tests`

**Key files**: `tests/`, `tests/conftest.py`, `Makefile`, `.github/workflows/`
**Goal**: All tests pass reliably, no flaky xfails, speed <30s, CI/CD foundation.

### 3a. Fix Flaky xfail Tests (BACKLOG-FLAKY-001)

1. Find all xfail markers: `grep -rn "xfail" tests/`
2. For each xfail test:
   - Run it in isolation: `pytest tests/path/test_file.py::test_name -v`
   - If it passes: remove xfail marker, verify it passes in full suite
   - If it fails: diagnose root cause (likely route module loading order)
   - Fix: ensure route registration is deterministic (sorted import order in conftest)

### 3b. Fix e2e test_admin_review_queue_sorted

1. Read the test to understand what it expects
2. After route extraction (Session 91b), the admin review queue may render differently
3. Update selectors to match current HTML structure
4. Verify: `pytest tests/e2e/test_admin_review.py -v`

### 3c. Investigate xpassed Test

1. Find the test that's marked xfail but now passes
2. Remove the xfail marker
3. Add a comment explaining why it now works (likely fixed by route extraction)

### 3d. Test Speed Optimization (PERF-001)

Current: ~43s. Target: <30s.

Strategy (try in order, stop when target met):
1. **Profile**: `pytest tests/ --durations=30 -q` — find slowest 30 tests
2. **Session-scoped fixtures**: Change app/client fixture from function to session scope
   - If this causes test isolation issues, use module scope instead
   - Tests that modify global state need their own fresh client
3. **Lazy ML imports**: Mock InsightFace/torch at conftest level if not already done
4. **Parallel execution**: Verify `pytest-xdist` is configured in `make test-fast`
5. **Skip slow tests in fast mode**: Mark integration tests with `@pytest.mark.slow`

Report before/after timing.

### 3e. CI/CD Foundation (OPS-002)

Create `.github/workflows/test.yml`:
```yaml
name: Tests
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: make test-fast
```

### 3f. Tests for This Track

- All previously-xfail tests now pass without xfail marker
- `make test-fast` < 30 seconds
- CI workflow file is valid YAML
- Zero test regressions

Commit: `fix(tests): resolve flaky xfails + speed optimization + CI/CD foundation`

### Subagent MUST:
- Run `make test-fast` AND `make test-ml` before commit
- Report exact timing before/after
- NOT touch any app/ code

---

## Act 4 (Track D): UX Bug Fixes — worktree `session-92/ux-fixes`

**Key files**: `app/main.py`, `app/page_routes.py`, `app/browse_routes.py`, `app/estimate_routes.py`, `app/identity_routes.py`, `app/event_routes.py`, `app/person_routes.py`
**Goal**: Fix all P1 UX bugs and most P2 UX bugs.

### D1. UX-042: /identify/{id} — Add Link to Source Photo (P1)

Read the `/identify/{identity_id}` route. Add a "View Source Photo" link that navigates to the photo page showing this face in context. The identity's anchor_ids or candidate_ids map to face_ids, which map to photo_ids via face_to_photo.

### D2. UX-045/046: Compare Upload — Loading Indicator + Auto-Scroll (P1)

In the compare upload flow:
1. Add HTMX loading indicator: `hx-indicator="#compare-loading"` with a spinner div
2. Add auto-scroll after results load: `hx-on::after-settle="this.scrollIntoView({behavior:'smooth'})"`

### D3. UX-054/055: Estimate Upload — Loading Indicator + Auto-Scroll (P1)

Same pattern as D2 but for the estimate upload flow in `estimate_routes.py`.

### D4. UX-080: 404 Page — Add Tailwind + Navbar (P1)

Find the 404/exception handler. Ensure it returns a full HTML page with:
- Tailwind CDN link in `<head>`
- Standard navbar
- "Page not found" message with link back to home

### D5. UX-081: About Page — Add Navbar (P1)

Find the `/about` route. Ensure it uses the standard page layout with navbar.

### D6. UX-092: Birth Year Save/Edit Race Condition (P1)

Find the birth year edit form. The race condition is likely:
- User clicks "Edit" → form appears
- User clicks "Save" → POST fires
- But the "Edit" click handler also fires → cancels the save

Fix: Use `hx-on::click="event.stopPropagation()"` on the Save button, or restructure the form so Edit and Save are mutually exclusive states.

### D7. UX-106: Inconsistent Contribution CTA Phrasing (P2)

Search for "Do you know" and "Can you help" across all route files. Standardize to one phrase: "Can you help identify this person?" everywhere.

### D8. UX-107: "Identified" Badge — Add Tooltip (P2)

Find the "Identified" badge on person pages. Add `title="This person has been identified by an admin"` attribute.

### D9. UX-114: Collection Dropdown Focus Handling (P2)

Replace `onfocus="this.select()"` with a proper placeholder: `placeholder="Filter by collection..."` and remove the onfocus handler.

### D10. Double Admin Bar on /events Page (Cosmetic)

Read `app/event_routes.py` — it likely renders its own admin bar AND inherits one from the page layout. Remove the duplicate.

### Tests for This Track

For each fix, add a test:
- D1: `/identify/{id}` response contains link to source photo
- D2: Compare upload form has `hx-indicator` attribute
- D3: Estimate upload form has `hx-indicator` attribute
- D4: 404 page contains Tailwind CDN and navbar
- D5: About page contains navbar
- D6: Birth year form has event propagation handling
- D7: No instances of "Do you know" remain (standardized to "Can you help")
- D10: Events page has exactly 1 admin bar

Commit: `fix(ux): 10 P1/P2 UX bugs — loading indicators, 404 styling, nav fixes, race conditions`

### Subagent MUST:
- Run `make test-fast` before commit
- Commit ALL files
- NOT touch rhodesli_ml/ or tests/conftest.py

---

## Act 5 (Track E): Growth Loop — Email + Share + Timeline — worktree `session-92/growth`

**Key files**: `app/notification_routes.py`, `app/event_routes.py`, `app/page_routes.py`
**Goal**: Complete the growth loop: Email notifications, share flow E2E, help-identify production, timeline integration.

### E1. Email Notifications (PRD-028 P1)

Read `app/notification_routes.py`. The in-app notification system exists. Add email sending:

1. Add Resend integration:
```python
import os
import httpx

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

async def send_notification_email(to_email: str, subject: str, html_body: str):
    if not RESEND_API_KEY:
        return  # Silently skip if not configured
    async with httpx.AsyncClient() as client:
        await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": "Rhodesli <noreply@rhodesli.nolanandrewfox.com>",
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            },
        )
```

2. Wire into notification creation: when a notification is created, also send email if:
   - `RESEND_API_KEY` is set
   - User has `email_enabled=True` in notification_preferences (default True)
   - The notification type is one that should send email (identity_confirmed, new_match)

3. Email template: inline CSS (Lesson 12), simple layout with:
   - Rhodesli logo/header
   - Notification text
   - "View in Archive" button linking to the relevant page
   - Unsubscribe link

### E2. Verify Share Flow E2E

This is a verification task, not implementation. Test the existing share flow:
1. Find a confirmed identity with a share button
2. Get the share URL
3. Verify the URL returns a page with OG meta tags (og:title, og:image, og:description)
4. Verify the page has a CTA ("Can you help identify this person?")
5. If any step fails, fix it

### E3. Help Identify Mode Verification

1. Navigate to `/help` — verify page loads with top unidentified faces
2. Toggle "Identify Mode" — verify pulse animation and "?" badges appear
3. Click an unidentified face in identify mode — verify identification form appears
4. Submit a suggestion — verify it creates an annotation (mock or real)

If broken, fix. If working, screenshot as evidence.

### E4. Timeline Integration for Life Events

Read the `/timeline` route. Add life_events to the timeline:

1. Query life_events from Supabase
2. Create timeline markers for each event (different styling from photo cards)
3. Events without photos still appear as text cards with event type icon
4. Merge with existing `rhodes_context_events.json` historical events
5. Sort all timeline items chronologically

### Tests for This Track

- Email sending function called when RESEND_API_KEY set (mock httpx)
- Email NOT sent when RESEND_API_KEY absent
- Share URL returns page with og:title and og:image meta tags
- Timeline includes life_events alongside photo cards
- Help identify page renders top 50 unidentified faces

Commit: `feat(growth): email notifications + share verification + timeline life events`

### Subagent MUST:
- Run `make test-fast` before commit
- NOT touch rhodesli_ml/ or tests/conftest.py

---

## Act 6 (Track F): Gemini + ML Fixes — worktree `session-92/gemini-ml`

**Key files**: `rhodesli_ml/gedcom_context.py`, `rhodesli_ml/gemini_extraction.py`, `app/estimate_routes.py`, `app/supabase_data.py`, `scripts/sql/`
**Goal**: Leon's Restaurant → Asheville. Full API call logging. Multi-pass foundation.

### F1. Leon's Restaurant Fix — GEDCOM Context Builder Enhancement

**Root cause**: `build_photo_context()` only includes GEDCOM data for people pictured in the photo. Leon Capeluto owns the restaurant but isn't pictured.

**Fix** in `rhodesli_ml/gedcom_context.py`:

1. Add a new function `find_business_owner_context()`:
```python
def find_business_owner_context(
    visible_text: str,
    parsed_gedcom,
    gedcom_face_links: dict,
    identities: dict,
    variant: str = "curated",
    photo_date_estimate: Optional[int] = None,
) -> str:
    """Find GEDCOM records for family members whose names match visible business text.

    If a sign says "LEON'S RESTAURANT" and there's a family member named Leon,
    include Leon's residential history in the context even if he's not pictured.
    """
    if not visible_text:
        return ""

    # Normalize text for matching
    text_upper = visible_text.upper()

    # Check all GEDCOM individuals for name matches
    matched_sections = []
    for xref, indi in parsed_gedcom.individuals.items():
        first_name = (indi.first_name or "").upper()
        last_name = (indi.last_name or "").upper()
        full_name = (indi.full_name or "").upper()

        if not first_name:
            continue

        # Check if first name appears in visible text (e.g., "LEON" in "LEON'S RESTAURANT")
        if first_name in text_upper or full_name in text_upper:
            section = _build_person_context(indi, parsed_gedcom, variant, photo_date_estimate)
            if section:
                matched_sections.append(f"[Business name match: \"{visible_text}\" → {indi.full_name}]\n{section}")

    if not matched_sections:
        return ""

    return "\n\n".join(matched_sections)
```

2. Update `build_photo_context()` to accept `visible_text` parameter and call the new function:
```python
def build_photo_context(
    photo_id, identified_faces, parsed_gedcom, gedcom_face_links, identities,
    photo_index=None, variant="curated", photo_date_estimate=None,
    visible_text=None,  # NEW parameter
) -> str:
    # ... existing code ...

    # After existing sections, add business owner context
    if visible_text:
        business_context = find_business_owner_context(
            visible_text, parsed_gedcom, gedcom_face_links, identities,
            variant, photo_date_estimate,
        )
        if business_context:
            sections.append(business_context)

    # ... rest of function ...
```

3. Update the caller in `app/estimate_routes.py` to pass `visible_text` from photo metadata.

### F2-F4. Full API Call Logging

**Schema change** — add 3 columns to gemini_api_calls:
```sql
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS prompt_text TEXT;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS full_response JSONB;
ALTER TABLE gemini_api_calls ADD COLUMN IF NOT EXISTS gedcom_context TEXT;
```

**Update `log_gemini_call()`** in `app/supabase_data.py`:
```python
def log_gemini_call(photo_id, model_used, call_type, **kwargs):
    # Add new fields to the insert dict:
    # prompt_text=kwargs.get("prompt_text"),
    # full_response=kwargs.get("full_response"),
    # gedcom_context=kwargs.get("gedcom_context"),
```

**Update all call sites** to pass the new fields:
- `app/estimate_routes.py` `_call_gemini_date_estimate()` — pass `prompt_text=prompt_text`, `full_response=parsed`, `gedcom_context=gedcom_context`
- `app/face_alignment.py` `log_call_to_supabase()` — pass `prompt_text` and `full_response`
- `scripts/process_batch_results.py` — pass available data

### F5. Multi-Pass Gemini Foundation (ML-053)

Create `rhodesli_ml/multi_pass.py`:

```python
"""Multi-pass Gemini re-labeling for low-confidence photos.

Strategy: Photos with confidence < THRESHOLD get re-analyzed with:
1. Enriched GEDCOM context (first_order variant instead of curated)
2. Results from first pass as "previous analysis" context
3. Specific questions about ambiguous evidence
"""

LOW_CONFIDENCE_THRESHOLD = 0.6  # Below this, re-analyze

def identify_low_confidence_photos(date_labels: dict) -> list[str]:
    """Find photos that would benefit from re-analysis."""
    candidates = []
    for photo_id, label in date_labels.items():
        confidence = label.get("confidence", "low")
        if confidence == "low" or _max_decade_probability(label) < LOW_CONFIDENCE_THRESHOLD:
            candidates.append(photo_id)
    return candidates

def build_reanalysis_prompt(photo_id: str, previous_result: dict, enriched_context: str) -> str:
    """Build a targeted prompt for re-analysis."""
    # Include previous result as context
    # Ask specifically about ambiguous evidence
    # Use enriched GEDCOM context
    pass
```

This is foundation only — the actual batch execution is a separate script run.

### F6. Active Learning Pipeline Foundation

Create `rhodesli_ml/active_learning.py`:

```python
"""Active learning pipeline — surface uncertain pairs for admin labeling.

Feedback loop:
1. Find face pairs near decision boundary (P(match) 0.4-0.6)
2. Surface to admin for labeling (match/not-match)
3. Add labeled pairs to calibration training set
4. Re-train isotonic calibrator
5. Update thresholds
"""

UNCERTAINTY_BAND = (0.4, 0.6)

def find_uncertain_pairs(calibrated_scores: dict) -> list[tuple[str, str, float]]:
    """Find face pairs near the decision boundary."""
    pass

def add_labeled_pair(face_id_a: str, face_id_b: str, is_match: bool):
    """Record an admin-labeled pair for calibration training."""
    pass
```

Foundation only — wiring to admin UI is future work.

### Tests for This Track

- `find_business_owner_context()` returns Leon's data when visible_text contains "LEON'S RESTAURANT"
- `find_business_owner_context()` returns empty when no name matches
- `build_photo_context()` with visible_text includes business owner section
- `log_gemini_call()` accepts and stores prompt_text, full_response, gedcom_context
- `identify_low_confidence_photos()` returns correct photo list
- AD-210 entry written for business-name-owner lookup

Commit: `feat(ml): Leon's fix + full API logging + multi-pass foundation + active learning foundation`

### Subagent MUST:
- Run `make test-fast` AND `make test-ml` before commit
- Write AD-210 (business name → owner GEDCOM lookup)
- NOT touch app/main.py or tests/conftest.py

---

## Act 7 (Track G): Product Features — worktree `session-92/products`

**Key files**: New files mostly
**Goal**: Lay architectural foundation for Face Compare Tier 2, NL Query, Date Estimator standalone, and second collection.

### G1. Face Compare Tier 2 — Architecture Document + Stub

Create `docs/prds/031_face_compare_tier2.md`:
- Problem: Current compare only works with pre-computed archive embeddings
- Solution: Shared comparison engine — archive path adds identity matching + persistence, public path compares and discards
- Architecture: Separate `/api/compare/v2` endpoint abstracting embedding source
- Blocker: Railway GPU or ONNX export needed for real-time inference
- This session: PRD + API stub only

Create `app/compare_v2_routes.py` with stub endpoints:
```python
def register_compare_v2_routes(rt):
    @rt("/api/compare/v2/upload", methods=["POST"])
    def compare_v2_upload(sess):
        """Tier 2 compare — accepts uploaded photo, returns face embeddings + matches."""
        return {"status": "not_implemented", "message": "Requires ONNX export or GPU"}
```

### G2. NL Archive Query — Design + Stub

Create `docs/prds/032_nl_archive_query.md`:
- Problem: Users can't ask natural language questions about the archive
- Solution: LangChain chain — query parsing → Supabase search → Gemini response
- Prerequisites: Stable identity data in Postgres, GEDCOM data accessible
- This session: PRD + query parsing prototype only

Create `rhodesli_ml/nl_query.py` with foundation:
```python
"""Natural language archive query (PRODUCT-003).

Chain: User question → parse intent → query Supabase → format response.
"""

def parse_query_intent(question: str) -> dict:
    """Parse a natural language question into structured query intent."""
    # Simple keyword-based parsing for MVP
    # "Show me photos from the 1930s" → {"type": "date_search", "decade": 1930}
    # "Who is in photo X?" → {"type": "identity_lookup", "photo_id": "X"}
    pass
```

### G3. Date Estimator Standalone — Architecture

Create `docs/prds/033_date_estimator_standalone.md`:
- Problem: No standalone tool exists for historical photo dating
- Solution: Rhodesli's Gemini pipeline as a separate product
- Architecture: Same extraction prompt, no GEDCOM context, public-facing
- Revenue model: Freemium (3 free/day, API access for subscribers)
- This session: PRD only (implementation is multi-session)

### G4. Second Collection Prep — Fox Family

Create `docs/collections/fox_family_prep.md`:
- Inventory: What photos exist, format, metadata
- GEDCOM: Does a Fox family GEDCOM exist?
- Integration plan: New community in communities table, R2 prefix, collection slug
- Estimate: Number of photos, faces, processing cost

### G5. ML Service Extraction — Architecture

Create `docs/architecture/ML_SERVICE.md`:
- Problem: ML dependencies (InsightFace, torch) bloat Docker image and can't run on Railway
- Solution: Separate FastAPI service for ML inference
- Architecture: Web app → HTTP → ML service (GPU instance)
- Endpoints: `/embed` (face → embedding), `/compare` (two embeddings → score), `/detect` (photo → faces)
- Deployment: Separate Railway service or Modal/Replicate
- This session: Architecture doc only

### Tests for This Track

- Compare v2 stub returns correct "not_implemented" response
- NL query parse function exists and is importable
- PRD files exist and are <300 lines each

Commit: `feat(products): PRDs + architecture for Compare Tier 2, NL Query, Date Estimator, ML service`

### Subagent MUST:
- Run `make test-fast` before commit
- Keep all docs <300 lines
- NOT touch existing app routes or ML code

---

## Act 8 (Track H): Architecture + Debt — worktree `session-92/arch`

**Key files**: `docs/`, `scripts/`
**Goal**: Evaluate pgvector, clean up tech debt docs, frontend migration assessment.

### H1. pgvector Migration Evaluation

Create `docs/architecture/PGVECTOR_EVALUATION.md`:
- Current state: 550 embeddings in embeddings.npy (~2.3 MB)
- pgvector capability: Supabase supports pgvector, HNSW index
- Migration path: Load embeddings → Supabase `face_embeddings` table with vector(512) column
- Pros: Unified data layer, similarity search in SQL, no .npy file management
- Cons: Query latency (network vs local NumPy), migration complexity
- Recommendation: Migrate when embedding count exceeds 5,000 or when ML service extraction happens
- Decision: DEFERRED (current scale doesn't warrant migration)

### H2. Tech Debt Audit

Review and document:
1. `app/main.py` — current line count, remaining utility functions that could be extracted
2. `rhodesli_ml/` — any dead code or unused modules
3. `scripts/` — scripts that are obsolete after Supabase migration
4. `data/` — JSON files that are deprecated now that Supabase is source of truth

Create `docs/architecture/TECH_DEBT.md` with findings and prioritized cleanup plan.

### H3. Frontend Framework Migration Assessment

Update `docs/architecture/OVERVIEW.md` with current assessment:
- HD-022 trigger: 3+ JS embeds needing shared state
- Current JS embed count: D3 tree, Leaflet map, PostHog snippet, face overlay — count them
- Assessment: Is the trigger met? If not, document why FastHTML+HTMX is still appropriate.

### Tests for This Track

- No tests needed (docs only)
- Verify all docs are <300 lines

Commit: `docs: pgvector evaluation + tech debt audit + frontend framework assessment`

### Subagent MUST:
- NOT touch any code files
- Keep all docs <300 lines

---

## Act 9: Merge + Final Verify + Assessment (30 min) — sequential on main

### 9a. Merge All Tracks

Use `./scripts/merge.sh` or manual merge:

**Merge order**: H (docs) → C (tests) → D (UX) → E (growth) → F (ML) → G (products)

Run `make test-fast` after EACH merge. If merge conflict:
- For AD entries: keep both, renumber if needed
- For test files: keep both
- For app routes: review carefully, prefer the newer change

### 9b. Re-analyze Leon's Restaurant (Post-F Merge)

After Track F merges:
1. Ensure Leon's photo has `visible_text` in photo metadata
2. Navigate to the photo in Chrome
3. Click "Re-analyze"
4. Verify location now says "Asheville, NC" (not Tampa, not "United States")
5. Screenshot as "after" evidence

If still wrong, check:
- Is `visible_text` being passed to `build_photo_context()`?
- Is Leon's GEDCOM record in the parsed GEDCOM data?
- What does the full prompt text show? (Now logged via F2-F4)

### 9c. Full Browser Verification (Claude Chrome)

Re-run all checks from Act 1, plus:
1. **Loading indicators**: Upload a test photo on compare + estimate, verify spinner appears
2. **404 page**: Navigate to `/nonexistent` — verify styled page with navbar
3. **About page**: Verify navbar present
4. **Share flow**: Get a share URL, open in incognito, verify OG card
5. **Email**: If RESEND_API_KEY is set, verify email sent on identity confirmation

### 9d. Verify API Call Logging

After Track F merges:
1. Re-analyze any photo
2. Check Supabase `gemini_api_calls` table:
   ```sql
   SELECT id, photo_id, prompt_text IS NOT NULL as has_prompt,
          full_response IS NOT NULL as has_response,
          gedcom_context IS NOT NULL as has_gedcom,
          created_at
   FROM gemini_api_calls
   ORDER BY created_at DESC LIMIT 5;
   ```
3. Verify prompt_text, full_response, and gedcom_context are populated

### 9e. Final Test Run

```bash
make test-fast   # target: <30s, 0 failures, 0 xfails
make test-ml     # 0 failures
```

### 9f. Update All Harness Docs

1. **CHANGELOG.md** — v0.95.0 entry
2. **ROADMAP.md** — mark completed items, move to Recently Completed
3. **BACKLOG.md** — update status on all addressed items
4. **tasks/todo.md** — rewrite to current state
5. **docs/roadmap/SESSION_HISTORY.md** — Session 92 entry
6. **docs/roadmap/FEATURE_STATUS.md** — update checkboxes

### 9g. Write Assessment

Create `docs/assessments/session-92-assessment.md`:

```markdown
# Session 92 Assessment

## Shipped
- [ ] Track A: Deploy verification — Evidence: screenshots
- [ ] Track B: Supabase tables verified — Evidence: SQL counts
- [ ] Track C: Test hardening — Evidence: timing, xfail count
- [ ] Track D: UX fixes — Evidence: screenshots before/after
- [ ] Track E: Growth loop — Evidence: email sent, share flow, timeline
- [ ] Track F: Leon's fix + API logging — Evidence: Asheville, SQL query
- [ ] Track G: Product foundations — Evidence: PRD files, stubs
- [ ] Track H: Architecture docs — Evidence: file list

## Deferred
[List anything not completed with reason and BACKLOG entry]

## Red Flags
[List any concerns with severity]

## Next Session Should Verify
1. [Highest priority check]
```

### 9h. Run /session-review

Mandatory end-of-session skill.

Commit: `docs: session 92 completion — merge + verify + assessment`

---

## Acceptance Criteria

### MUST Ship (session is not complete without ALL of these)

- [ ] v0.94.1+ deployed and browser-verified on all pages (screenshots)
- [ ] Leon's Restaurant photo shows Asheville, NC (not Tampa/SF/US)
- [ ] Full Gemini API call logging: prompt_text + full_response + gedcom_context columns populated
- [ ] All P1 UX bugs fixed: UX-042, 045/046, 054/055, 080, 081, 092
- [ ] `make test-fast` < 30 seconds with 0 failures and 0 xfail markers
- [ ] `make test-ml` passes with 0 failures
- [ ] Supabase tables verified: communities, life_events, notifications, global_person_links, gemini_api_calls
- [ ] Notification E2E: confirm identity → notification appears → bell badge updates
- [ ] Email notification code wired (sends when RESEND_API_KEY configured)
- [ ] Share flow E2E verified (share URL → OG card → CTA)
- [ ] CI/CD: `.github/workflows/test.yml` exists
- [ ] AD-210 written (business name → owner GEDCOM lookup)
- [ ] Assessment + session log + CHANGELOG + ROADMAP updated
- [ ] Browser verified with screenshots (end-to-end, not superficial)

### Should Ship

- [ ] SENTRY_DSN + POSTHOG_API_KEY + RESEND_API_KEY set on Railway
- [ ] DATA_SOURCE=postgres tested and working on Railway
- [ ] Timeline shows life events alongside photos
- [ ] Help Identify mode verified in production
- [ ] Multi-pass Gemini foundation (ML-053 — `rhodesli_ml/multi_pass.py`)
- [ ] Active learning foundation (`rhodesli_ml/active_learning.py`)
- [ ] PRDs written: Compare Tier 2, NL Query, Date Estimator
- [ ] ML Service architecture doc
- [ ] pgvector evaluation doc
- [ ] Tech debt audit doc
- [ ] Double admin bar on /events fixed
- [ ] P2 UX bugs fixed: UX-106, 107, 114

### Deferred (Session 93+)

- [ ] Face Compare Tier 2 implementation (blocked by GPU/ONNX)
- [ ] NL Archive Query implementation
- [ ] Date Estimator standalone implementation
- [ ] Second collection actual onboarding (Fox family photos — data collection)
- [ ] ML service extraction implementation
- [ ] pgvector actual migration
- [ ] Frontend framework migration (NOT YET TRIGGERED)
- [ ] Batch GEDCOM re-analysis of all 271 photos
- [ ] Per-identity adaptive clustering thresholds (ML-098)
- [ ] Remaining P3 UX backlog items (~50+)

## Key Skills to Use

- `/session-review` — at session end (mandatory)
- Claude Chrome — for ALL frontend verification
- Worktree subagents — for 6 parallel tracks
- `/simplify` — after implementation acts
- `/verify` — for test-fix loops

## Non-Goals

- Removing JSON files (keep as fallback)
- Running batch ML on all photos
- Full multi-tenant runtime
- Frontend framework migration
- Any feature not listed in the tracks above

## Risk Mitigation

**Risk 1**: 6 parallel tracks is ambitious.
**Mitigation**: Each track has independent file scope. Clear merge order. If a track is incomplete, merge what's done and BACKLOG the rest. Tracks G and H are mostly docs — lowest risk.

**Risk 2**: Leon's fix depends on GEDCOM data quality.
**Mitigation**: If Leon's GEDCOM record doesn't exist or lacks Asheville residence, the fix can't work. Verify GEDCOM data FIRST before implementing the code change.

**Risk 3**: Test speed target may not be achievable.
**Mitigation**: If <30s is impossible without architectural changes, document the bottleneck and set a realistic target. Don't sacrifice test reliability for speed.

**Risk 4**: Email sending may fail without RESEND_API_KEY.
**Mitigation**: Email code is gated on env var. If key not available, code ships but email is disabled. Document what Nolan needs to set.

**Risk 5**: Context overflow from 6 subagents.
**Mitigation**: Each subagent works in isolation. Orchestrator only sees merge results. Use `/clear` aggressively between acts. Subagents write their own commit messages with context.
