# Session 161 — rhodesli `/admin/rhodes-inbox` Route + Image Handoff

**Predecessor**: [session-160-assessment.md](../assessments/session-160-assessment.md)
**Context**: [session-161-context.md](../session_context/session-161-context.md) ← **READ FIRST**
**Mode**: implementation
**Primary repo**: rhodesli (code changes here)
**Secondary repo**: rhodes-wiki (read-only; Session 160 carry-overs in Phase 7)
**Estimated time**: ~3 hours, single session, no /clear between phases

---

## Goal

Make the Session 160 inbox entry (Martha Girgenti / 1971 Menasche / Rhodesia) **fully ingestable into rhodesli** via a new admin route. End state:

- Admin opens `/admin/rhodes-inbox` locally → sees 1 pending entry
- Clicks Approve → fills upload form (prefilled community/source/collection/caption) → uploads the 1971 photo binary (admin-manual-download from FB)
- After upload, rhodesli runs face detection → 3 inbox identities created (Edward, Renee, Zeni) → ready for admin to link to dossiers / GEDCOM
- Inbox entry directory moves `inbox/pending/<slug>/` → `inbox/approved/<slug>/`
- `rhodes_inbox_entries` Supabase row records: status=approved, approved_by, approved_at, rhodesli_photo_id

**No production deploy this session**. The admin route is gated local-only (AD-S161-1).

---

## Pre-flight (FIRST action — DO BEFORE anything else)

```bash
echo "161" > .claude/current_session.txt
echo "implementation" > .claude/session_mode.txt
source venv/bin/activate

# Verify rhodes-wiki Session 160 entry is accessible
ls /Users/nolanfox/rhodes-wiki/inbox/pending/2026-04-28_2360240064471306/post.json
python3 -c "import json; d=json.load(open('/Users/nolanfox/rhodes-wiki/inbox/pending/2026-04-28_2360240064471306/post.json')); print('comments:', len(d['comments']), '| author:', d['post_author']['name'])"
# Expect: comments: 14 | author: Martha Girgenti

# Baseline rhodesli tests
make test-fast 2>&1 | tail -3
# Expect: 4271+ passed

# Baseline rhodes-wiki tests
cd /Users/nolanfox/rhodes-wiki && python3 -m pytest -q 2>&1 | tail -3 && cd /Users/nolanfox/rhodesli
# Expect: 209 passed
```

If any of these fail → STOP and diagnose. The pre-flight failures of Session 160 cost us hours.

---

## Phase 0 — Harness setup (10 min)

**Goal**: rhodesli Claude Code sessions can read rhodes-wiki inbox via the bridge.

1. Add to `/Users/nolanfox/rhodesli/.claude/settings.json` `additionalDirectories: ["/Users/nolanfox/rhodes-wiki"]` with **Read-only** allow rules:
   ```json
   "allow": [
     "Read(/Users/nolanfox/rhodes-wiki/**)",
     "Bash(ls /Users/nolanfox/rhodes-wiki/inbox/**:*)"
   ]
   ```
   AND a deny rule that blocks Write/Edit on the rhodes-wiki path (defense in depth — rhodesli MUST NOT write into rhodes-wiki except through `rhodes_inbox.mark_approved/mark_rejected` which uses Python shutil with explicit allow).

2. Commit: `chore(harness): add rhodes-wiki read bridge to rhodesli settings`

**Acceptance**: `Read("/Users/nolanfox/rhodes-wiki/inbox/pending/2026-04-28_2360240064471306/post.json")` succeeds in this session.

---

## Phase 1 — Supabase table (15 min)

**Goal**: `rhodes_inbox_entries` table exists in Supabase production.

1. Write `scripts/migrations/session-161-rhodes-inbox-entries.sql` per AD-S161-4 schema (see context file). NOTE: rhodesli migrations live under `scripts/migrations/` per existing convention (e.g., `session158b_current_v2_views.sql`, `gedcom_v2_schema.sql`).
2. Apply via Supabase pooler (`aws-0-us-west-2.pooler.supabase.com:5432`, session mode)
3. Smoke test:
   ```python
   from supabase import create_client
   sb = create_client(url, key)
   sb.table("rhodes_inbox_entries").insert({
       "slug": "test_smoke",
       "fb_post_id": "test",
       "fb_post_url": "test",
       "status": "pending"
   }).execute()
   sb.table("rhodes_inbox_entries").delete().eq("slug", "test_smoke").execute()
   ```
4. Commit: `feat(db): add rhodes_inbox_entries provenance table`

**Acceptance**: row inserts + deletes cleanly; no schema-cache errors.

---

## Phase 2 — Inbox reader module (25 min)

**Goal**: `app/rhodes_inbox.py` — pure functions for reading + status-mutating inbox entries.

API:
```python
def is_rhodes_wiki_available() -> bool:
    """True iff $RHODES_WIKI_ROOT (or default ~/rhodes-wiki/) has inbox/pending."""

@dataclass
class InboxSummary:
    slug: str
    fb_post_id: str
    fb_author_name: str
    captured_at: str
    comments_count: int
    status: Literal["pending", "approved", "rejected"]

def list_pending_entries() -> list[InboxSummary]: ...
def list_approved_entries() -> list[InboxSummary]: ...
def list_rejected_entries() -> list[InboxSummary]: ...
def load_entry(slug: str) -> dict:
    """Returns post.json content + extracted.json + meta.json merged."""

def mark_approved(slug: str, *, approved_by: str, rhodesli_photo_id: str | None = None) -> None:
    """Move inbox/pending/<slug>/ → inbox/approved/<slug>/ + upsert Supabase row.
    Atomic-or-rollback: if filesystem move succeeds but Supabase write fails,
    move back. If Supabase succeeds but filesystem fails, mark Supabase row
    with status=approved_pending_filesystem and log error."""

def mark_rejected(slug: str, *, rejected_by: str, reason: str) -> None: ...
```

**Tests** (`tests/test_rhodes_inbox.py`, ≥10 tests):
- list with no entries → empty
- list with the Session 160 entry → 1 entry, correct fields
- load_entry with valid slug → returns full dict
- load_entry with invalid slug → raises FileNotFoundError
- mark_approved moves directory + writes row
- mark_approved rollback when Supabase write fails (mock the failure)
- is_rhodes_wiki_available True when path exists, False when env says don't look
- Edge: malformed post.json in pending → list_pending logs warning + skips, doesn't crash

**Commit**: `feat(rhodes-inbox): inbox reader module + Supabase status sync`

**Acceptance**: tests pass; running `python -c "from app.rhodes_inbox import list_pending_entries; print(list_pending_entries())"` returns 1 entry (the Session 160 capture).

---

## Phase 3 — Admin routes (30 min)

**Goal**: 4 routes wired into `app/main.py` (or new `app/admin_rhodes_inbox_routes.py` imported into main).

```python
@app.get("/admin/rhodes-inbox")
def admin_rhodes_inbox_list(sess): ...   # list view

@app.get("/admin/rhodes-inbox/{slug}")
def admin_rhodes_inbox_detail(slug, sess): ...   # detail view

@app.post("/admin/rhodes-inbox/{slug}/approve")
def admin_rhodes_inbox_approve(slug, sess, request): ...   # approves + redirects to upload form prefill

@app.post("/admin/rhodes-inbox/{slug}/reject")
def admin_rhodes_inbox_reject(slug, sess, request): ...   # rejects with reason
```

All gated by `_check_admin(sess)` + `is_rhodes_wiki_available()` (returns 404 if not available).

**Wire into admin sidebar** — find the existing admin nav in main.py and add a "Rhodes Inbox" link with pending count badge (Lesson 138: features not in nav are invisible).

**Commit**: `feat(rhodes-inbox): admin routes for inbox approval workflow`

**Acceptance**: `curl http://localhost:5001/admin/rhodes-inbox` (with admin auth cookie) returns the list view HTML; `curl -X POST .../approve` (mocked / no real action) returns expected redirect; `_check_admin` rejection returns 401.

---

## Phase 4 — UI templates (25 min)

**Goal**: list view + detail view rendered with FastHTML inline-HTML (consistent with existing admin pages).

**List view** (`/admin/rhodes-inbox`):
- Header with counts: "Rhodes Inbox: N pending · M approved · K rejected"
- Tabs: Pending | Approved | Rejected (defaults to Pending)
- Table: slug, fb_author, comments_count, captured_at (relative), status badge, action button ("Review →")
- Empty state: "No pending entries. Capture posts via rhodes-wiki Chrome MCP workflow."

**Detail view** (`/admin/rhodes-inbox/<slug>`):
- Breadcrumb: Rhodes Inbox → `<slug>`
- Metadata: FB post URL (link to FB), author, date, comments_count, reactions
- Caption (verbatim, monospace, language tag)
- Image: NOT proxied — show FB photo URL with "Open in new tab" button + "Copy URL to clipboard" button (AD-S161-2: admin manually downloads)
- Comments thread (all 14): each comment shows author + text + reaction count + indented nested replies
- Kinship triples (computed live from `scripts.extract_kinship` via subprocess call OR imported as a library — prefer import; rhodes-wiki is on PYTHONPATH if needed)
- Person hints: list of 6 dossier subjects (Edward, Renee, Zeni, Simon, Lionel, Sarah Surmany) with confidence + cross-link to rhodes-wiki person.md path
- Approve form: textarea for notes, "Approve & Open Upload Form" button
- Reject form: textarea for reason, "Reject" button (red)

**Carry-over from rhodesli style**: use Tailwind, indigo accents, rounded-2xl, slate text. Match Session 92+ design tokens.

**Commit**: `feat(rhodes-inbox): list + detail UI with kinship triples and copy-to-clipboard`

**Acceptance**: browser-verify locally — `/admin/rhodes-inbox` shows 1 pending entry; `/admin/rhodes-inbox/2026-04-28_2360240064471306` shows all 14 comments + 6 hints + the goldmine April Merdjan comment. Copy-to-clipboard button works.

---

## Phase 5 — Upload form prefill (15 min)

**Goal**: existing rhodesli upload endpoint accepts `?prefill=<slug>` and prefills the form.

Find the existing upload route in `app/upload_routes.py` (the GET handler at `@rt("/upload")` line ~348, POST handler at ~526). Add `?prefill=<slug>` handling to the GET handler:
- Look up `rhodes_inbox_entries` row for slug
- Look up inbox entry post.json content
- Prefill form fields:
  - community → "rhodes"
  - source → "Facebook — Jews of Rhodes group"
  - collection → "FB Group Posts"
  - source_url → post.fb_post_url
  - description / caption → post.caption.text
  - admin_notes → `Inbox entry: <slug>\nFB post: <fb_post_id>\nCaptured: <captured_at>`

On upload success, server-side callback updates `rhodes_inbox_entries.rhodesli_photo_id = <new_photo_id>`. Wire via `_background_ingest` or wherever post-upload-success hooks live.

**Commit**: `feat(rhodes-inbox): upload form prefill + photo_id linkback`

**Acceptance**: clicking "Approve & Open Upload Form" in the detail page lands on the upload form with all 5 fields populated. Uploading a test photo binary sets `rhodes_inbox_entries.rhodesli_photo_id` correctly.

---

## Phase 6 — Tests (25 min)

**Goal**: ≥15 new tests for the new code paths.

Files:
- `tests/test_rhodes_inbox.py` — pure module tests (Phase 2 coverage)
- `tests/test_admin_rhodes_inbox_routes.py` — integration tests for the 4 routes

Coverage targets:
- All 4 admin routes: auth gating, 200 happy path, 404 on missing slug, 404 when rhodes-wiki path unavailable
- Approve flow end-to-end: filesystem move + Supabase write + photo_id linkback
- Reject flow: filesystem move + Supabase write + audit_log row
- Prefill flow: query param honored, form fields populated correctly
- Edge: malformed post.json → list silently skips with warn log
- Regression: production (no rhodes-wiki path) → all 4 routes 404 cleanly

**Commit**: `test(rhodes-inbox): unit + integration coverage for inbox workflow`

**Acceptance**: `make test-fast` baseline + new tests = 4286+ passing.

---

## Phase 7 — rhodes-wiki carry-overs (20 min)

These are Session 160 leftovers. Bundle here while context is fresh.

**FB-NESTED-001**: Fix `~/rhodes-wiki/scripts/build_inbox_from_js_extraction.py` (or `parse_fb_dom.py` if the issue is upstream) to capture nested replies. Current bug: depth>0 replies are missed because the `[role=article][aria-label^="Comment by"]` selector + parent-walk depth calc returns 0 for replies. Fix: detect `aria-label^="Reply by"` AND structurally walk into indented containers.
- Add 2 tests: a synthetic fixture with 1 top-level + 1 nested reply, assert both captured with correct depth values.
- Regenerate the Session 160 inbox entry post.json against the new parser — verify Martha's reply + Isaac's reply now show with `depth=1` and `parent_comment_id` set correctly.

**FB-PERMISSIONS-001**: New `~/rhodes-wiki/docs/reference/chrome-mcp-fb-permissions.md`:
- Document Claude in Chrome v1.0.70 per-action permission gate behavior
- Document the empirical workaround (one comprehensive JS call instead of many)
- Document the open question of site-level allowlist (we tested chrome://extensions options page — no site-level toggle was visible; the popup itself says "Site-level permissions are disabled" but no UI to enable was found)
- Cross-link from `.claude/rules/fb-tos-rule.md`

**Commits** (in rhodes-wiki):
- `fix(rhodes-wiki): FB-NESTED-001 capture nested replies in JS extraction`
- `docs(rhodes-wiki): FB-PERMISSIONS-001 Chrome MCP per-site permission behavior`

**Acceptance**: rhodes-wiki tests pass (target: 209 → ~212); regenerated post.json shows 12 + 2 = 14 comments with 2 having depth=1.

---

## Phase 8 — Codex audit + fixes (15 min)

```bash
cd /Users/nolanfox/rhodesli && codex exec "Audit the rhodesli + rhodes-wiki changes from this session.

rhodesli files:
- app/rhodes_inbox.py — new module reading rhodes-wiki inbox JSONs + Supabase status table
- app/admin_rhodes_inbox_routes.py (or main.py integration) — 4 admin routes
- migrations/session-161-rhodes-inbox-entries.sql
- tests/test_rhodes_inbox.py + tests/test_admin_rhodes_inbox_routes.py

rhodes-wiki files:
- scripts/build_inbox_from_js_extraction.py — FB-NESTED-001 fix
- docs/reference/chrome-mcp-fb-permissions.md — FB-PERMISSIONS-001

Focus on:
1. Security — admin route auth gating, path traversal in slug param, Supabase injection risk in upsert
2. Cross-repo boundary — rhodesli must NEVER write to rhodes-wiki except via the explicit mark_approved/mark_rejected paths
3. Atomicity — filesystem move + Supabase write rollback semantics
4. Production safety — admin route MUST return 404 when rhodes-wiki path unavailable
5. Test coverage gaps
6. Schema correctness — rhodes_inbox_entries indexes + foreign key safety

P0/P1/P2/P3 report. Be specific with file:line." </dev/null
```

Save audit to `docs/session_context/session-161-codex-audit.md`. Fix P0/P1 inline. P2/P3 → BACKLOG.

**Commit**: `fix(rhodes-inbox): Session 161 Phase 8 — Codex audit P1 fixes`

---

## Phase 9 — Closeout (15 min)

**rhodesli**:
1. CHANGELOG: new version entry (e.g., v0.99.81)
2. ROADMAP: mark RHODES-WIKI-003 as DONE; mark Session 161 in Recently Completed
3. SESSION_HISTORY: full Session 161 entry
4. docs/assessments/session-161-assessment.md
5. `git push origin main`
6. Verify production health 200 (no production code changed but verify nothing broken)

**rhodes-wiki**:
1. CHANGELOG: v0.3.0 entry (FB-NESTED-001 + FB-PERMISSIONS-001)
2. ROADMAP: status header bumped
3. wiki/log.md: 2026-MM-DD entry
4. `git push origin main` (private repo)

**Memory**: update `~/.claude/projects/-Users-nolanfox-rhodesli/memory/project_rhodes_wiki_repo.md` with Session 161 status + new commit count.

**Browser verification**: navigate to `http://localhost:5001/admin/rhodes-inbox`; click into the Session 160 entry; click Approve → upload form opens with prefilled fields → upload a placeholder image (or skip upload and just verify the prefill); verify the Session 160 inbox entry is now under `inbox/approved/`.

**Run `/session-review` skill at session end.**

---

## Anti-goals (out of scope this session)

- ❌ Programmatic FB image binary download (FB-DOWNLOAD-001 — future session with Chrome MCP site permissions)
- ❌ Auto-bind person hints to rhodesli identities (RHODESLI-INBOX-005 — future)
- ❌ Sync inbox JSON to Supabase / remote (only if a second admin needs remote approval — future)
- ❌ Production deploy of the admin route (gated 404 on prod is correct)
- ❌ rhodes-wiki narrative `wiki/` pages (Session 162)
- ❌ Notion publish workflow

---

## Success criteria (Feature Reality Contract)

| Check | Method |
|---|---|
| Inbox entry visible in rhodesli admin UI | Navigate to `/admin/rhodes-inbox`, see 1 row |
| Detail view shows all 14 comments | Navigate to detail, count comment cards |
| Kinship triples surface in detail view | See "Sarah Surmany → mother_of → Renee" etc. |
| Approve moves the entry on disk | Before: `inbox/pending/<slug>/`, after: `inbox/approved/<slug>/` |
| Approve writes Supabase row | `SELECT * FROM rhodes_inbox_entries WHERE slug='...'` returns status=approved |
| Upload form prefill works | Click Approve → upload form has community=rhodes + source URL + caption |
| 404 on production | Production rhodesli returns 404 (no rhodes-wiki path) |
| Tests pass | `make test-fast` ≥4286 passing |
| rhodes-wiki tests pass | 209 → ~212 passing |
| Codex audit done | `docs/session_context/session-161-codex-audit.md` exists |
| Both repos pushed | `git log origin/main..HEAD` empty for both |

If any FAIL → fix before declaring session done.
