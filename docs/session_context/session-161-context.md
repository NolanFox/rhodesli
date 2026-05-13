# Session 161 Context — rhodesli `/admin/rhodes-inbox` Route + Image Handoff

**Predecessor**: [session-160-assessment.md](../assessments/session-160-assessment.md)
**Predecessor (rhodes-wiki)**: `/Users/nolanfox/rhodes-wiki/` at v0.2.0
**Repos in play**: rhodesli (primary, code changes) + rhodes-wiki (read-only, inbox source) + fox-genealogy (read-only, pattern reference)
**Mode**: implementation
**Pre-flight gate**: Session 160 closeout pushed; rhodes-wiki v0.2.0 on PRIVATE GitHub remote

---

## Why this session

Session 160 produced the first real FB inbox entry (`~/rhodes-wiki/inbox/pending/2026-04-28_2360240064471306/`) — Martha Girgenti's 1971 Menasche family Rhodesia photo with 14 captured comments, 6 person dossiers, and contract-valid `post.json`. That entry currently sits on the user's disk with **no rhodesli-side ingestion path**. The whole point of the rhodes-wiki ↔ rhodesli architecture (locked Session 159) was that rhodesli would consume inbox JSONs via an admin route. Session 161 builds that route.

**End-state goal for Session 161**: User opens `/admin/rhodes-inbox` locally, sees the Session 160 entry plus any future ones, clicks Approve, and the 1971 Menasche photo lands in rhodesli's R2 with face detection run, attributed to community=rhodes, source="Facebook — Jews of Rhodes group". From that point on, the existing rhodesli identity-merge / GEDCOM-link workflow takes over.

---

## Architecture decisions (lock these before coding)

### AD-S161-1: `/admin/rhodes-inbox` is a LOCAL-DEV-ONLY route

**Question**: How does rhodesli (which runs on Railway in prod) read `~/rhodes-wiki/inbox/pending/`? Railway has no filesystem access to the user's laptop.

**Decision**: The admin route is gated on local filesystem availability — `os.path.exists("/Users/nolanfox/rhodes-wiki/inbox/pending")` OR the `RHODES_WIKI_ROOT` env var. Production Railway has neither → route returns 404 cleanly. Local dev → fully functional. This avoids any need to sync inbox JSON to Supabase / R2.

**Why this works**: the admin user is Nolan, who develops rhodesli locally and has rhodes-wiki on the same machine. Approval is a discretionary admin action, not something users do. Local-only is fine.

**Future**: if a second admin needs remote approval, OD-013 (TBD) will document the sync-to-Supabase migration.

### AD-S161-2: Image binary download via admin-manual-download, not programmatic

**Question**: How does the 1971 Menasche photo binary land in rhodesli? FB CDN URLs have ~30-day expiring signatures; programmatic fetch via Chrome MCP requires site-permission grants we haven't pinned down.

**Decision (Session 161 MVP)**: Admin manually downloads from FB (right-click save, or open the FB photo URL in browser and Cmd+S), then uploads via rhodesli's existing upload UI. The `/admin/rhodes-inbox/<slug>` detail page provides a one-click "Copy FB photo URL" button and prefilled upload form (community=rhodes, source URL = FB post URL, source = "Facebook — Jews of Rhodes group", collection = "FB Group Posts"). After upload, the new `photo_id` is linked back to `rhodes_inbox_entries`.

**Why**: lowest friction; no new failure modes (Chrome MCP popups, FB rate limits, CSRF tokens). 30 seconds of admin manual work.

**Future**: `FB-DOWNLOAD-001` programmatic path is a separate session.

### AD-S161-3: Person-hint surfacing is informational, not auto-applied

**Question**: When admin approves, should the 6 dossier subjects from Session 160 (Edward, Renee, Zeni, Simon, Lionel Menasche + Sarah Surmany) be pre-loaded as identity hints in rhodesli's face-detection UI?

**Decision (Session 161 MVP)**: Display the dossier names + kinship triples + comment author surnames in the detail page as REFERENCE INFORMATION. Don't pre-bind to rhodesli identities. The admin uses the existing rhodesli inbox-identity workflow after face detection runs.

**Why**: rhodesli has no Rhodes community identities yet — they'll be created by this upload's face detection. There's nothing to bind hints TO until faces are detected. Hint-auto-application is `RHODESLI-INBOX-005` (future session).

### AD-S161-4: Supabase `rhodes_inbox_entries` schema

**Decision** — minimal provenance table:

```sql
CREATE TABLE rhodes_inbox_entries (
  slug text PRIMARY KEY,                    -- "2026-04-28_2360240064471306"
  fb_post_id text NOT NULL,
  fb_group_id text,
  fb_post_url text NOT NULL,
  fb_author_name text,
  fb_author_id text,
  captured_at timestamptz,
  captured_by text,
  contract_version text DEFAULT '0.1.0',
  parser_version text,
  comments_count int,
  status text NOT NULL DEFAULT 'pending'    -- pending | approved | rejected
    CHECK (status IN ('pending', 'approved', 'rejected')),
  approved_by text,
  approved_at timestamptz,
  rejection_reason text,
  rhodesli_photo_id text REFERENCES photos(photo_id),
  notes text,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX idx_rhodes_inbox_status ON rhodes_inbox_entries(status);
CREATE INDEX idx_rhodes_inbox_fb_post ON rhodes_inbox_entries(fb_post_id);
```

This table tracks: which inbox entries have been processed, by whom, and the resulting rhodesli photo (if approved). The local filesystem (`inbox/pending/` vs `inbox/approved/`) is the source of truth for entry CONTENT; this table is the **rhodesli-side status mirror**.

### AD-S161-5: Cross-repo bridge for rhodesli → rhodes-wiki

**Currently**: rhodesli's `.claude/settings.json` has no `additionalDirectories`. rhodes-wiki ↔ rhodesli bridge is one-way (rhodes-wiki can read rhodesli; not vice versa).

**Decision**: Add `/Users/nolanfox/rhodes-wiki` to rhodesli's `additionalDirectories` with **Read-only allow** rules. This is a HARNESS change (HD-NNN), not application code — Claude Code sessions in the rhodesli repo will be able to read the inbox JSON. The PRODUCTION app reads via Python `Path("/Users/nolanfox/rhodes-wiki/inbox/...")` which works at runtime regardless of Claude harness settings.

### AD-S161-6: Status transitions are file-system-mirrored

**Decision**: When approved, the inbox entry directory moves from `inbox/pending/<slug>/` to `inbox/approved/<slug>/` on the rhodes-wiki filesystem. When rejected, → `inbox/rejected/<slug>/`. This is a filesystem move; the Supabase row records the same status. Two sources of truth, kept in sync by the admin route.

**Why filesystem-mirrored**: rhodes-wiki's local vault is authoritative for content. The status field needs to be visible to a future researcher browsing the vault offline (without Supabase access).

---

## Phase plan

### Phase 0 — Pre-flight (10 min)

- Verify rhodes-wiki v0.2.0 inbox entry is readable from rhodesli cwd
- Add rhodesli `/.claude/settings.json` `additionalDirectories: ["/Users/nolanfox/rhodes-wiki"]` with Read-only allow rules (AD-S161-5)
- Confirm rhodes-wiki `inbox/pending/2026-04-28_2360240064471306/post.json` validates clean
- Baseline `make test-fast` returns 4271 app tests passing
- Set `.claude/current_session.txt` to "161", `.claude/session_mode.txt` to "implementation"

### Phase 1 — Supabase table (15 min)

- Create migration SQL: `migrations/session-161-rhodes-inbox-entries.sql` (AD-S161-4 schema)
- Apply via Supabase pooler (us-west-2, port 5432, session mode)
- Smoke test: insert a row for the Session 160 entry, query back, delete
- Add row count to `/api/health/data` endpoint (optional)

### Phase 2 — Inbox reader module (25 min)

- New file: `app/rhodes_inbox.py` — pure functions, no FastHTML
  - `list_pending_entries() -> list[InboxSummary]` reads `~/rhodes-wiki/inbox/pending/*/post.json`
  - `load_entry(slug) -> InboxEntry` returns full post.json + extracted.json + meta.json
  - `mark_approved(slug, approved_by, photo_id) -> None` moves dir + writes Supabase
  - `mark_rejected(slug, rejected_by, reason) -> None` moves dir + writes Supabase
  - All file I/O guarded by `_check_rhodes_wiki_available()` that returns False on production
- 8+ unit tests with fixture inbox entry

### Phase 3 — Admin routes (30 min)

- New file: `app/admin_rhodes_inbox_routes.py`
  - `GET /admin/rhodes-inbox` — list view (pending count, approved count, rejected count + table)
  - `GET /admin/rhodes-inbox/<slug>` — detail view
  - `POST /admin/rhodes-inbox/<slug>/approve` — moves to approved, prefills upload form, returns redirect to `/admin/upload?prefill=...`
  - `POST /admin/rhodes-inbox/<slug>/reject` — moves to rejected, writes reason
  - All gated by `_check_admin(sess)` + `_check_rhodes_wiki_available()`
- Wired in `app/main.py` route registration

### Phase 4 — UI templates (25 min)

- List view: table with slug, fb_author, comments_count, age, status badge, action button
- Detail view:
  - Caption (verbatim, language tag)
  - Image preview (proxy via FB photo URL — or just show the URL with "Open in new tab")
  - All 14 comments rendered with author + text + reaction count + nested-reply indentation
  - Kinship triples section (computed live from `scripts.extract_kinship` against post.json)
  - Person-hints section (lists the 6 Menasche dossier subjects + commenter surnames)
  - Approve / Reject forms with reason field (textarea)
  - "Copy FB photo URL" button (clipboard API)
- Tailwind, FastHTML inline-HTML style consistent with existing admin pages

### Phase 5 — Upload-form prefill integration (15 min)

- Existing rhodesli upload page (`/admin/upload` or wherever) accepts `?prefill=<slug>` query param
- When set, looks up rhodes_inbox_entries row, prefills:
  - Community: rhodes
  - Source: "Facebook — Jews of Rhodes group"
  - Collection: "FB Group Posts"
  - Source URL: fb_post_url
  - Caption / description: post caption verbatim
  - Provenance note: "Inbox entry <slug>; FB post <fb_post_id>"
- On upload success, server-side updates `rhodes_inbox_entries.rhodesli_photo_id`

### Phase 6 — Tests (25 min)

- Unit: `test_rhodes_inbox.py` — list/load/mark_approved/mark_rejected with fixture entry
- Integration: `test_admin_rhodes_inbox_routes.py` — all 4 routes with mocked auth + Supabase
- Regression: an entry that fails the contract should NOT appear in list view (silent skip + log warn)
- Edge: rhodes-wiki path not available → routes 404 cleanly
- Target: ≥15 new tests

### Phase 7 — rhodes-wiki carry-overs (20 min)

These were deferred from Session 160; small enough to bundle here:

- **FB-NESTED-001**: Fix `scripts/build_inbox_from_js_extraction.py` to capture nested replies (extend JS extractor's article selector OR add a `nested_replies` extraction pass)
- **FB-PERMISSIONS-001**: New `docs/reference/chrome-mcp-fb-permissions.md` documenting Claude in Chrome v1.0.70 per-action permission gate behavior + the empirical workaround (one comprehensive JS call) + the open question of site-level allowlist

### Phase 8 — Codex audit + fixes (15 min)

- Run `codex exec` on the rhodesli commits + rhodes-wiki commits this session
- Save to `docs/session_context/session-161-codex-audit.md`
- Fix P0/P1 inline; backlog P2+ if quick fix not viable

### Phase 9 — Closeout (15 min)

- rhodesli: CHANGELOG, ROADMAP, SESSION_HISTORY, assessment, push
- rhodes-wiki: CHANGELOG (v0.3.0), ROADMAP, wiki/log.md, push
- Memory: update `project_rhodes_wiki_repo.md` with Session 161 status + new commit count
- Browser verify: navigate to `/admin/rhodes-inbox` locally; approve the Session 160 entry; verify upload flow prefills correctly; verify approved entry moves to `inbox/approved/`

---

## Open questions to confirm with user before Phase 2

None blocking — Architecture Decisions 1-6 are the answers. But two clarifications would tighten Phase 4/5:

1. **Image preview in detail view**: do we embed the FB photo via `<img src="<fb_photo_url>">` (works in browser when admin is FB-logged-in; broken otherwise), OR just show a link? Default to **link-only** since the proxy approach fails when admin is in incognito.

2. **Rejection workflow**: should rejected entries be deletable from disk after a grace period (e.g., 30 days), or persist forever? Default to **persist forever** — disk is cheap, audit trail is valuable.

---

## Cross-references

- Session 160 inbox entry (the test target): `/Users/nolanfox/rhodes-wiki/inbox/pending/2026-04-28_2360240064471306/`
- Session 160 ARCHITECTURE.md §4.1: two-path capture flow (this session reads JS-structured path output)
- Session 160 Codex audit: `docs/session_context/session-160-codex-audit.md` (informs JS-BUILDER-001/002/003/004 carryover decisions)
- Session 159 ARCHITECTURE.md §3.1: inbox JSON contract (the contract this session consumes)
- rhodesli existing admin routes: `app/main.py` (look for `/admin/*` patterns)
- rhodesli upload pipeline: `app/main.py` (look for `POST /upload` and `_background_ingest`)

## Lessons explicitly relevant to this session

- **Lesson 109**: CommunityMiddleware /api/ skip — admin routes need `/c/<community>/` prefix awareness; gate on auth not on prefix
- **Lesson 130**: never full-scan a versioned rich mirror in the request path — the rhodes_inbox_entries table is small, but always query by primary key (slug) not by full-table scan
- **Lesson 136**: fire-and-forget Supabase syncs hide errors — every write must surface failures
- **Lesson 138**: features built but never linked from navigation are invisible — wire `/admin/rhodes-inbox` into the admin sidebar in Phase 3
- **Lesson 154**: post-write integrity verification — when approving, verify the filesystem move AND the Supabase write both succeeded; rollback either if the other fails
- **Lesson 168**: automated side effects of admin actions must be audited — approve action writes audit_log row
- **Lesson 178**: subagent token budget — if Phase 6 tests get heavy, dispatch test-writing as a separate worktree subagent

## Estimated total time

| Phase | Time |
|---|---|
| 0 — Pre-flight | 10 min |
| 1 — Supabase table | 15 min |
| 2 — Inbox reader | 25 min |
| 3 — Admin routes | 30 min |
| 4 — UI templates | 25 min |
| 5 — Prefill integration | 15 min |
| 6 — Tests | 25 min |
| 7 — rhodes-wiki carry | 20 min |
| 8 — Codex audit + fixes | 15 min |
| 9 — Closeout | 15 min |
| **TOTAL** | **~3 hours** |

Fits in a single focused session. No /clear needed between phases if context budget holds (~150k expected for this scope).
