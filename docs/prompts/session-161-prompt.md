# Session 161 — rhodesli `/admin/rhodes-inbox` Route + Image Handoff

**Predecessor**: [session-160-assessment.md](../assessments/session-160-assessment.md)
**Context**: [session-161-context.md](../session_context/session-161-context.md) ← **READ FIRST**
**Mode**: implementation
**Primary repo**: rhodesli (code changes here)
**Secondary repo**: rhodes-wiki (read-only; Session 160 carry-overs in Phase 7)
**Estimated time**: ~4h 15min (revised post-Codex-audit). /clear after Phase 4 if context > 120k.
**Pre-execution audit**: see `docs/session_context/session-161-codex-audit.md` — Verdict PROCEED-WITH-FIXES; 2 P0 + 7 P1 + 9 P2 + 5 P3; all P0/P1 fixes applied to this prompt + context BEFORE you start.

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

## Phase 0 — Harness setup + extract_kinship copy + P0 helpers (15 min)

**Goal**: rhodesli ready to consume rhodes-wiki inbox; audit P0-2 helpers in place; kinship NER decoupled.

1. Add to `/Users/nolanfox/rhodesli/.claude/settings.json` `additionalDirectories: ["/Users/nolanfox/rhodes-wiki"]`:
   ```json
   "additionalDirectories": ["/Users/nolanfox/rhodes-wiki"],
   "allow": [
     "Read(/Users/nolanfox/rhodes-wiki/**)",
     "Bash(ls /Users/nolanfox/rhodes-wiki/inbox/**:*)"
   ],
   "deny": [
     "Edit(/Users/nolanfox/rhodes-wiki/**)",
     "Write(/Users/nolanfox/rhodes-wiki/**)",
     "Bash(python:* /Users/nolanfox/rhodes-wiki/*)",
     "Bash(python3:* /Users/nolanfox/rhodes-wiki/*)",
     "Bash(rm:* /Users/nolanfox/rhodes-wiki/*)",
     "Bash(mv:* /Users/nolanfox/rhodes-wiki/*)"
   ]
   ```
   (Codex audit P2-H: deny rules cover runtime Python invocations from Claude Code sessions; the actual web app at runtime is exempt by design — admin routes call `rhodes_inbox.mark_approved/mark_rejected` which use `os.replace()` with explicit slug validation).

2. **Audit P0-2: Copy `extract_kinship.py` from rhodes-wiki to rhodesli** (decouples cross-repo Python import per Audit P1-7):
   ```bash
   cp /Users/nolanfox/rhodes-wiki/scripts/extract_kinship.py /Users/nolanfox/rhodesli/app/extract_kinship.py
   # Update import paths in the copy — search for "from scripts." and update to "from app."
   ```
   Update top-of-file comment to note "Copied from rhodes-wiki Session 160 to decouple cross-repo Python (Audit P1-7)."

3. Run baseline `make test-fast` and verify 4271+ tests pass after the copy.

4. Commit: `chore(harness): add rhodes-wiki read bridge + copy extract_kinship for decoupling`

**Acceptance**:
- `Read("/Users/nolanfox/rhodes-wiki/inbox/pending/2026-04-28_2360240064471306/post.json")` succeeds.
- `from app.extract_kinship import extract_kinship_from_post` works in rhodesli.
- `make test-fast` still passes.

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

## Phase 2 — Inbox reader module + reconcile script (35 min)

**Goal**: `app/rhodes_inbox.py` (pure functions) + `scripts/rhodes_inbox_reconcile.py` (drift detection).

**API** (revised per Audit P0-1, P0-2, P1-7, P2-A, P2-B, P2-G):

```python
# Audit P0-2: slug validation BEFORE any filesystem op
import re
_SLUG_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-zA-Z0-9_-]+$")

def _validate_slug(slug: str) -> None:
    if not _SLUG_PATTERN.fullmatch(slug):
        raise ValueError(f"invalid slug: {slug!r}")
    # Defense in depth: resolve and verify it stays within inbox root
    inbox_root = _rhodes_wiki_inbox_root().resolve()
    for state in ("pending", "approved", "rejected"):
        candidate = (inbox_root / state / slug).resolve()
        if os.path.commonpath([str(candidate), str(inbox_root)]) != str(inbox_root):
            raise ValueError(f"slug resolves outside inbox root: {slug!r}")

# Audit P1-2: BOTH path AND not-production gate
def is_rhodes_wiki_available() -> bool:
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        return False
    root = os.environ.get("RHODES_WIKI_ROOT", str(Path.home() / "rhodes-wiki"))
    return (Path(root) / "inbox" / "pending").is_dir()

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

# Audit P1-6: state param so prefill can load from approved/
def load_entry(slug: str, *, state: Literal["pending", "approved", "rejected"] = "pending") -> dict:
    """Returns post.json content + extracted.json + meta.json merged.
    state determines which subdirectory to read from."""

# Audit P0-1 + P2-A: Supabase-first, atomic CAS, idempotent retries
class AlreadyApprovedError(RuntimeError): ...

def mark_approved(slug: str, *, approved_by: str, rhodesli_photo_id: str | None = None) -> None:
    """Atomic CAS via Supabase + os.replace() for filesystem.

    Order:
    1. _validate_slug(slug)  — path-traversal guard
    2. Supabase: UPDATE rhodes_inbox_entries SET status='approved', approved_by=...,
       approved_at=now() WHERE slug=$1 AND status='pending' RETURNING *
    3. If RETURNING empty → raise AlreadyApprovedError (someone else won the race)
    4. os.replace(inbox/pending/<slug>, inbox/approved/<slug>)  — POSIX atomic
    5. If step 4 fails → log error + leave Supabase row at approved (reconciliation
       script detects + reports). Re-raise the OSError.

    Retries are idempotent: a re-run hits AlreadyApprovedError at step 3 (no harm)
    or finds the filesystem already moved at step 4 (no-op via if-exists check).
    """

def mark_rejected(slug: str, *, rejected_by: str, reason: str) -> None: ...

def kinship_triples_for(slug: str) -> list[dict]:
    """Audit P1-7: returns cached kinship triples from rhodes_inbox_entries.kinship_triples_json.
    If null, computes via app.extract_kinship.extract_kinship_from_post, caches, returns."""
```

**Reconcile script** (`scripts/rhodes_inbox_reconcile.py` — Audit P2-G):
- `--dry-run` walks both Supabase rhodes_inbox_entries and the filesystem
- Reports drift cases: (a) FS in approved/ but Supabase status=pending, (b) Supabase status=approved but FS in pending/, (c) FS in pending/ but no Supabase row at all
- `--apply` reconciles by trusting Supabase (the authoritative source per AD-S161-6)

**Tests** (`tests/test_rhodes_inbox.py`, ≥15 tests — Audit P0-2, P1-2, P2-A):
- list with no entries → empty
- list with the Session 160 entry → 1 entry, correct fields
- load_entry with valid slug → returns full dict
- load_entry with invalid slug → raises FileNotFoundError
- **`test_mark_approved_rejects_path_traversal_slug`** — `slug="../../../etc"` raises ValueError before any filesystem op (Audit P0-2)
- **`test_mark_approved_atomic_cas_race`** — two threading.Thread approvals dispatched simultaneously; exactly one succeeds, the other raises AlreadyApprovedError (Audit P2-A)
- **`test_is_rhodes_wiki_available_blocked_by_RAILWAY_ENVIRONMENT`** — even with valid path, RAILWAY_ENVIRONMENT=production → False (Audit P1-2)
- mark_approved happy path: Supabase row updated + filesystem moved
- mark_approved Supabase failure → no filesystem move attempted; clear error surfaced
- mark_approved filesystem failure → Supabase row already at approved; OSError raised; drift detectable by reconcile
- Edge: malformed post.json in pending → list_pending logs warning + skips, doesn't crash
- Reconcile dry-run detects forged drift correctly (set up FS in approved/ + Supabase pending; assert detection)
- Audit P2-D: `_log_audit(action='rhodes_inbox.approve', actor=..., entity_id=slug)` called on success

**Commit**: `feat(rhodes-inbox): inbox reader + Supabase atomic-CAS + reconcile script`

**Acceptance**: tests pass; `python -c "from app.rhodes_inbox import list_pending_entries; print(list_pending_entries())"` returns 1 entry; `python scripts/rhodes_inbox_reconcile.py --dry-run` reports "no drift" when state is consistent.

---

## Phase 3 — Admin routes (40 min, +10 per Audit P1-5)

**Goal**: 4 routes in new `app/admin_rhodes_inbox_routes.py` imported by main.py; sidebar wired.

```python
# All POST handlers MUST follow this exact gate order (Audit P1-1: CSRF first):

@rt("/admin/rhodes-inbox")
def get(sess=None, request=None):
    if not is_rhodes_wiki_available(): return Response("", status_code=404)
    guard = _check_admin(sess)
    if guard: return guard
    # render list view
    ...

@rt("/admin/rhodes-inbox/{slug}")
def get(slug: str, sess=None, request=None):
    if not is_rhodes_wiki_available(): return Response("", status_code=404)
    guard = _check_admin(sess)
    if guard: return guard
    _validate_slug(slug)  # Audit P0-2: raises ValueError → 400
    # render detail view (use kinship_triples_for(slug) for cached triples)
    ...

@rt("/admin/rhodes-inbox/{slug}/approve")  # POST
def post(slug: str, sess=None, request=None, notes: str = ""):
    if not is_rhodes_wiki_available(): return Response("", status_code=404)
    origin_err = _check_origin(request)  # Audit P1-1: CSRF check FIRST
    if origin_err: return origin_err
    guard = _check_admin(sess)
    if guard: return guard
    _validate_slug(slug)  # Audit P0-2
    user = User.from_session(sess)
    try:
        mark_approved(slug, approved_by=user.email)
    except AlreadyApprovedError:
        return RedirectResponse(f"/admin/rhodes-inbox/{slug}?msg=already_approved", status_code=303)
    _log_audit(action='rhodes_inbox.approve', actor=user.email, entity_type='rhodes_inbox', entity_id=slug)  # Audit P2-D
    return RedirectResponse(f"/upload?prefill={slug}", status_code=303)

@rt("/admin/rhodes-inbox/{slug}/reject")  # POST
def post(slug: str, sess=None, request=None, reason: str = ""):
    if not is_rhodes_wiki_available(): return Response("", status_code=404)
    origin_err = _check_origin(request)
    if origin_err: return origin_err
    guard = _check_admin(sess)
    if guard: return guard
    _validate_slug(slug)
    user = User.from_session(sess)
    mark_rejected(slug, rejected_by=user.email, reason=reason[:4096])  # Audit P3-B: length cap
    _log_audit(action='rhodes_inbox.reject', actor=user.email, entity_type='rhodes_inbox', entity_id=slug, details={'reason': reason[:200]})
    return RedirectResponse(f"/admin/rhodes-inbox", status_code=303)
```

**Wire into admin sidebar** (Audit P1-5 pre-research): nav is in `app/components/nav.py` (extracted in REFACTOR-001 Phase 2). Existing pattern at `app/main.py:4640-4700` (`nav_item(f"{prefix}/admin/X", icon, label, count, key, color)`). Add a new entry between `/admin/pending` and `/admin/approvals` for visibility — title "Rhodes Inbox", icon "📥", count = `count_pending_rhodes_inbox()`, color "indigo".

The count function: gate on `is_rhodes_wiki_available()`; return 0 in production.

**Commit**: `feat(rhodes-inbox): 4 admin routes + sidebar wiring + CSRF + slug validation`

**Acceptance**: `curl -H "Cookie: <admin_cookie>" http://localhost:5001/admin/rhodes-inbox` returns the list view; `curl -X POST` without Origin header returns 403; `curl -X POST` with malformed slug returns 400; unauthenticated → 401; production (RAILWAY_ENVIRONMENT set) → 404.

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

## Phase 5 — Upload form prefill (20 min, +5 per Audit P1-6)

**Goal**: existing rhodesli upload endpoint accepts `?prefill=<slug>` and prefills the form.

Find the existing upload route in `app/upload_routes.py` (GET handler at `@rt("/upload")` line ~348, POST handler at ~526). Add `?prefill=<slug>` handling to the GET handler:

```python
# Audit P1-6: prefill GET reads from APPROVED state (post-approval is the right
# time to prefill — the approve route already moved the entry to inbox/approved/)
prefill_slug = request.query_params.get("prefill")
if prefill_slug:
    from app.rhodes_inbox import _validate_slug, load_entry, is_rhodes_wiki_available
    if not is_rhodes_wiki_available():
        return Response("", status_code=404)
    try:
        _validate_slug(prefill_slug)  # Audit P0-2: re-validate on prefill GET too
        entry = load_entry(prefill_slug, state="approved")  # Audit P1-6: approved/
        prefill = {
            "community": "rhodes",
            "source": "Facebook — Jews of Rhodes group",
            "collection": "FB Group Posts",
            "source_url": entry["fb_post_url"],
            "description": entry["caption"]["text"],
            "admin_notes": f"Inbox entry: {prefill_slug}\nFB post: {entry['fb_post_id']}\nCaptured: {entry['captured_at']}",
        }
    except (ValueError, FileNotFoundError) as exc:
        logger.warning("Prefill failed for slug %r: %s", prefill_slug, exc)
        prefill = {}
```

On upload success, server-side callback updates `rhodes_inbox_entries.rhodesli_photo_id = <new_photo_id>`. Wire via `_background_ingest` or wherever post-upload-success hooks live — pass `prefill_slug` through the upload form as a hidden field so the POST handler can perform the linkback.

**Commit**: `feat(rhodes-inbox): upload form prefill + photo_id linkback`

**Acceptance**: clicking "Approve & Open Upload Form" in the detail page → /upload?prefill=<slug> → form has community=rhodes + source + collection + source_url + description prefilled. Uploading a test photo binary sets `rhodes_inbox_entries.rhodesli_photo_id` correctly. Reload of the same prefill URL works (idempotent reads from approved/). Malformed slug → form renders blank, no crash.

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

## Phase 7 — rhodes-wiki carry-overs + ARCH §3.3 sync (25 min, +5 per Audit P1-3)

These are Session 160 leftovers + the schema-drift sync from Audit P1-3. Bundle here while context is fresh.

**Audit P1-3: rhodes-wiki ARCHITECTURE.md §3.3 schema sync**: Update `~/rhodes-wiki/docs/ARCHITECTURE.md §3.3` (the inbox JSON contract section) to reflect the canonical `rhodes_inbox_entries` schema this session shipped. Specifically: drop the `id uuid` PK + `inbox_entry_slug` indirection (rhodesli uses `slug text PRIMARY KEY` directly); change `photo_ids uuid[]` → `rhodesli_photo_id text REFERENCES photos(photo_id)`; add `kinship_triples_json jsonb`; align field naming (`rejection_reason` not `rejected_reason`). Add a note: "Schema canonicalized in rhodesli Session 161 — rhodes-wiki implements per this canonical form."

**FB-NESTED-001** (Audit P2-F: downgraded to synthetic-only): Fix `~/rhodes-wiki/scripts/build_inbox_from_js_extraction.py` (or `parse_fb_dom.py` if the issue is upstream) to capture nested replies. Current bug: depth>0 replies are missed because the `[role=article][aria-label^="Comment by"]` selector + parent-walk depth calc returns 0 for replies. Fix: detect `aria-label^="Reply by"` AND structurally walk into indented containers.
- Add 2 tests: a synthetic fixture with 1 top-level + 1 nested reply, assert both captured with correct depth values.
- **Do NOT regenerate the Session 160 inbox entry** — its 2 nested replies were manually filled in from screenshots; regenerating would lose that audit trail. Real-world validation deferred to a future capture session.

**FB-PERMISSIONS-001**: New `~/rhodes-wiki/docs/reference/chrome-mcp-fb-permissions.md`:
- Document Claude in Chrome v1.0.70 per-action permission gate behavior
- Document the empirical workaround (one comprehensive JS call instead of many)
- Document the open question of site-level allowlist (we tested chrome://extensions options page — no site-level toggle was visible; the popup itself says "Site-level permissions are disabled" but no UI to enable was found)
- Cross-link from `.claude/rules/fb-tos-rule.md`

**Commits** (in rhodes-wiki):
- `docs(rhodes-wiki): Audit P1-3 sync ARCHITECTURE.md §3.3 with rhodesli canonical schema`
- `fix(rhodes-wiki): FB-NESTED-001 capture nested replies (synthetic fixture only)`
- `docs(rhodes-wiki): FB-PERMISSIONS-001 Chrome MCP per-site permission behavior`

**Acceptance**: rhodes-wiki tests pass (target: 209 → ~211, +2 nested-reply tests). ARCHITECTURE.md §3.3 schema matches rhodesli's `rhodes_inbox_entries` exactly.

---

## Phase 8 — Codex audit + fixes (45 min, +30 per Audit P2-E)

**Note**: Pre-execution audit already caught 2 P0 + 7 P1 + 9 P2 + 5 P3 (see `docs/session_context/session-161-codex-audit.md`). This phase audits the **executed code** against the corrected plan. Use the documented fallback path: try Codex first; if it hangs >5 min with no output, kill it and dispatch a Claude general-purpose subagent.

```bash
cd /Users/nolanfox/rhodesli && codex exec "Audit the rhodesli + rhodes-wiki changes from this session.

rhodesli files:
- app/rhodes_inbox.py — new module reading rhodes-wiki inbox JSONs + Supabase status table
- app/admin_rhodes_inbox_routes.py — 4 admin routes + sidebar wiring
- app/extract_kinship.py — COPIED from rhodes-wiki Session 160 (Audit P1-7 decoupling)
- scripts/migrations/session-161-rhodes-inbox-entries.sql
- scripts/rhodes_inbox_reconcile.py — drift detection
- tests/test_rhodes_inbox.py + tests/test_admin_rhodes_inbox_routes.py

rhodes-wiki files:
- docs/ARCHITECTURE.md §3.3 schema sync
- scripts/build_inbox_from_js_extraction.py — FB-NESTED-001 synthetic fixture fix
- docs/reference/chrome-mcp-fb-permissions.md — FB-PERMISSIONS-001

Focus on:
1. Security — admin route auth gating, path traversal in slug param (P0-2 from pre-audit), CSRF (P1-1), prefill query param sanitization (P1-6)
2. Cross-repo boundary — rhodesli must NEVER write to rhodes-wiki except via the explicit mark_approved/mark_rejected paths; settings.json deny rules cover Bash(python) invocations (P2-H)
3. Atomicity — Supabase-first, filesystem-second ordering (P0-1 from pre-audit); os.replace not shutil.move; atomic CAS via WHERE status='pending' RETURNING *; reconcile script catches drift
4. Production safety — admin route 404 when RAILWAY_ENVIRONMENT set OR path absent (P1-2)
5. Test coverage — path-traversal test, concurrent-CAS race test, production-gate test, drift detection test
6. Schema correctness — rhodes_inbox_entries.rhodesli_photo_id text REFERENCES photos(photo_id) verified against scripts/sql/001_photos_table.sql; kinship_triples_json jsonb; rejection_reason length cap

P0/P1/P2/P3 report. Be specific with file:line." </dev/null
```

If Codex hangs >5 min with 0-byte output: kill it, dispatch Claude subagent with same prompt + access to all referenced files.

Save audit to `docs/session_context/session-161-post-execution-audit.md`. Fix P0/P1 inline. P2/P3 → BACKLOG.

**Commit**: `fix(rhodes-inbox): Session 161 Phase 8 — post-execution audit fixes`

---

## Phase 9 — Closeout (25 min, +10 per Audit P2-I)

**rhodesli**:
1. CHANGELOG: new version entry (e.g., v0.99.81)
2. ROADMAP: mark RHODES-WIKI-003 as DONE; mark Session 161 in Recently Completed
3. SESSION_HISTORY: full Session 161 entry
4. `docs/assessments/session-161-assessment.md`
5. **NEW** `docs/architecture/RHODES_INBOX.md` (Audit P2-I): full AD log for all Session 161 architecture decisions — AD-RID-1 through AD-RID-6 (renumbered from AD-S161-N). Cross-link from CLAUDE.md key docs.
6. `docs/HARNESS_DECISIONS.md`: add HD-035 entry for cross-repo bridge (was AD-S161-5).
7. `git push origin main`
8. Verify production health 200 (no production code changed but verify nothing broken)

**rhodes-wiki**:
1. CHANGELOG: v0.3.0 entry (FB-NESTED-001 + FB-PERMISSIONS-001 + ARCH §3.3 sync)
2. ROADMAP: status header bumped to v0.3.0
3. wiki/log.md: 2026-MM-DD entry
4. `git push origin main` (private repo)

**Memory**: update `~/.claude/projects/-Users-nolanfox-rhodesli/memory/project_rhodes_wiki_repo.md` with Session 161 status + new commit count + new docs reference.

**Browser verification (MANDATORY per Audit P3-D)**: navigate to `http://localhost:5001/admin/rhodes-inbox`; click into the Session 160 entry; click Approve → upload form opens with prefilled fields → **upload a real placeholder image** (verify the Session 160 inbox entry photo or any test image works end-to-end) → verify `rhodes_inbox_entries.rhodesli_photo_id` is set → verify the Session 160 inbox entry is now under `inbox/approved/` on the filesystem. The full chain must work, not just prefill.

**Run `/session-review` skill at session end.**

---

## Anti-goals (out of scope this session)

- ❌ Programmatic FB image binary download (FB-DOWNLOAD-001 — future session with Chrome MCP site permissions)
- ❌ FB image proxying via rhodesli backend (would require FB cookies/login in production — out of scope)
- ❌ Auto-bind person hints to rhodesli identities (RHODESLI-INBOX-005 — future)
- ❌ Identity-hint persistence into rhodesli's identity-merge workflow (post-approval hints stay informational)
- ❌ Sync inbox JSON to Supabase / remote (only if a second admin needs remote approval — future)
- ❌ Duplicate-detection beyond rhodesli's existing photo SHA256 dedup
- ❌ Production deploy of the admin route (gated 404 on prod is correct)
- ❌ rhodes-wiki narrative `wiki/` pages (Session 162)
- ❌ Notion publish workflow
- ❌ Soft-delete path for rhodes_inbox_entries (admin can DELETE via Supabase SQL editor; future route in RHODESLI-INBOX-006)

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
