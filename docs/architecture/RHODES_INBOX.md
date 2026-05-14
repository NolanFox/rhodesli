# Rhodes Inbox — Cross-Repo Provenance Pipeline

**Last updated:** 2026-05-13 (Session 161)
**Status:** Shipped (local-dev only; production returns 404)

The Rhodes Inbox connects the [rhodes-wiki](../../../rhodes-wiki/) sibling
repo to rhodesli via an inbox JSON contract. Admin reviews each
captured FB post, then approves it into the existing rhodesli upload
pipeline. Supabase row tracks provenance.

---

## Architecture decisions (AD-RID-1 through AD-RID-6)

These were assigned `AD-S161-N` in `docs/session_context/session-161-context.md`
during Session 161; renumbered to `AD-RID-N` here for cross-doc clarity.
The session context file remains the historical record of *why* each
decision was made; this doc is the durable reference.

### AD-RID-1: `/admin/rhodes-inbox` is LOCAL-DEV-ONLY — defense in depth

The admin route is gated by `is_rhodes_wiki_available()` which requires
**BOTH** of these to be true:

1. Path existence: `Path(RHODES_WIKI_ROOT or ~/rhodes-wiki) / "inbox" / "pending"` is a directory
2. Production marker absence: `not os.environ.get("RAILWAY_ENVIRONMENT")`

A misconfigured `RHODES_WIKI_ROOT` on Railway is harmless because the
environment marker takes precedence. Local dev with the path present
→ gate is True. Anything else → gate is False, route returns 404.

This avoids any need to sync inbox JSON to Supabase / R2. The admin
user is Nolan, who develops rhodesli locally and has rhodes-wiki on
the same machine. Approval is a discretionary admin action.

If a second admin needs remote approval in the future, see the open
BACKLOG item `RHODESLI-INBOX-007` for the sync-to-Supabase migration.

### AD-RID-2: Image binary download via admin-manual-download (MVP)

FB CDN URLs have ~30-day expiring signatures and Chrome MCP popup
gates make programmatic fetch unreliable. **MVP**: admin manually
downloads from FB (right-click save, or open the FB photo URL and
Cmd+S), then uploads via the existing rhodesli upload UI.

The `/admin/rhodes-inbox/<slug>` detail page assists with:
- "Copy FB photo URL" button (one-click clipboard)
- Pre-filled upload form fields after approve (community=rhodes,
  source URL, source, collection, description)

After upload, the new `photo_id` is written to
`rhodes_inbox_entries.rhodesli_photo_id`.

**Future**: `FB-DOWNLOAD-001` programmatic path is a separate session.

### AD-RID-3: Person-hint surfacing is informational, not auto-applied

The detail page shows the 6 rhodes-wiki dossier subjects (Edward,
Renee, Zeni, Simon, Lionel Menasche + Sarah Surmany) + kinship triples
+ comment author surnames as **reference information**. Hints are NOT
auto-bound to rhodesli identities.

Rationale: rhodesli has no Rhodes-community identities yet — they will
be created by face detection on the approved upload. Hint auto-binding
(`RHODESLI-INBOX-005`) is a future session.

### AD-RID-4: Supabase `rhodes_inbox_entries` schema

```sql
CREATE TABLE rhodes_inbox_entries (
  slug TEXT PRIMARY KEY,                    -- "2026-04-28_2360240064471306"
  fb_post_id TEXT NOT NULL,
  fb_group_id TEXT,
  fb_post_url TEXT NOT NULL,
  fb_author_name TEXT,
  fb_author_id TEXT,
  captured_at TIMESTAMPTZ,
  captured_by TEXT,
  contract_version TEXT DEFAULT '0.1.0',
  parser_version TEXT,
  comments_count INT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'approved', 'rejected')),
  approved_by TEXT,
  approved_at TIMESTAMPTZ,
  rejection_reason TEXT CHECK (length(rejection_reason) <= 4096),
  rhodesli_photo_id TEXT REFERENCES photos(photo_id) ON DELETE SET NULL,
  kinship_triples_json JSONB,               -- cached: computed once at first detail-view load
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_rhodes_inbox_status ON rhodes_inbox_entries(status);
CREATE INDEX idx_rhodes_inbox_fb_post ON rhodes_inbox_entries(fb_post_id);
```

Verified against `scripts/sql/001_photos_table.sql:6`
(`photos.photo_id TEXT PRIMARY KEY`). rhodes-wiki ARCHITECTURE.md §3.3
mirrors this schema (Session 161 Phase 7 sync).

### AD-RID-5: Cross-repo bridge for rhodesli → rhodes-wiki

rhodesli's `.claude/settings.json` adds `/Users/nolanfox/rhodes-wiki`
to `additionalDirectories` with **Read-only allow** rules. The
production app's runtime path reads (via `app/rhodes_inbox.py`) are
independent of harness settings — production never reaches them because
`is_rhodes_wiki_available()` returns False.

This is also tracked as `HD-035` in `docs/HARNESS_DECISIONS.md`.

### AD-RID-6: Supabase is authoritative for status; filesystem mirrors it

**Approve flow** (atomic CAS via Supabase + POSIX rename):

1. `_validate_slug(slug)` — path-traversal guard
2. Supabase: `UPDATE rhodes_inbox_entries SET status='approved', approved_by=...,
   approved_at=now() WHERE slug=$1 AND status='pending' RETURNING *`
3. Empty RETURNING → `AlreadyApprovedError` (someone else won the race)
4. `os.replace(pending/<slug>, approved/<slug>)` — POSIX atomic rename
5. If step 4 fails → log error + leave Supabase row at approved +
   re-raise; `scripts/rhodes_inbox_reconcile.py` detects drift

**Why Supabase first**: the upsert is idempotent (retry = no-op). A
crash between step 2 and step 4 leaves the row at approved with the
entry still in `pending/` — recoverable via reconcile script. The
reverse ordering would leave entry in `approved/` with no Supabase
row — invisible to admin UI until a manual SQL query.

---

## File map

| Path | Purpose |
|---|---|
| `app/rhodes_inbox.py` | Pure module: inbox reader, slug validation, atomic CAS, kinship cache |
| `app/admin_rhodes_inbox_routes.py` | 4 admin routes (list, detail, approve, reject) + UI templates + sidebar wiring |
| `app/extract_kinship.py` | Copied from rhodes-wiki Session 160 (decouples cross-repo Python) |
| `app/upload_routes.py` | Phase 5 prefill handler for `?prefill=<slug>` |
| `scripts/migrations/session-161-rhodes-inbox-entries.sql` | Phase 1 schema migration |
| `scripts/rhodes_inbox_reconcile.py` | Drift detection between Supabase and filesystem |
| `tests/test_rhodes_inbox.py` | 21 unit tests for the module |
| `tests/test_admin_rhodes_inbox_routes.py` | 13 integration tests for the 4 routes |

## Operational notes

- **Reconcile dry-run**:
  `python scripts/rhodes_inbox_reconcile.py --dry-run`
  Reports drift between Supabase rows and `~/rhodes-wiki/inbox/{pending,approved,rejected}/`
- **Apply reconciliation** (trust Supabase):
  `python scripts/rhodes_inbox_reconcile.py --apply`
- **Production safety**: any call to a route handler in this module
  returns 404 if `RAILWAY_ENVIRONMENT` is set OR the rhodes-wiki path
  is absent. Verified by `test_*_route_404_on_railway` and
  `test_routes_404_when_path_absent`.

## Anti-goals (out of scope, see future sessions)

- ❌ Programmatic FB image binary download (FB-DOWNLOAD-001)
- ❌ FB image proxying via rhodesli backend
- ❌ Auto-bind person hints to rhodesli identities (RHODESLI-INBOX-005)
- ❌ Sync inbox JSON to Supabase / remote (RHODESLI-INBOX-007)
- ❌ Soft-delete path for rhodes_inbox_entries (RHODESLI-INBOX-006)
- ❌ Production deploy of the admin route (404 gate is the correct end state)

## Cross-references

- `docs/session_context/session-161-context.md` — full design discussion
- `docs/session_context/session-161-codex-audit.md` — pre-execution audit
- `docs/HARNESS_DECISIONS.md` HD-035 — cross-repo bridge harness rationale
- `/Users/nolanfox/rhodes-wiki/docs/ARCHITECTURE.md` §3.3 — sister schema reference
