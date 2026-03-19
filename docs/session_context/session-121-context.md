# Session 121 Context — Upload Verification + UX Fix Sprint + Planning

**Predecessor:** [Session 120 Context](session-120-context.md) (ML Comparison Script + UX Fix Sprint)
**Assessment:** [Session 120 Assessment](../assessments/session-120-assessment.md)
**Feedback:** [Session 119 Feedback](../feedback/session-119-feedback.md)

## Problem Statement

Session 120 shipped the ML comparison script, Sentry root cause fix, and 4 UX fixes (FB-009, FB-008, FB-001, FB-011). But AD-229 still needs 2 more criteria verified, 3 quick UX fixes remain from Session 119 feedback, and 2 larger features (TOOLS-003, WORKSPACE-001) need planning artifacts.

## Items

### 1. AD-229 Cosine Comparison Verification
- Script: `scripts/compare_ml_embeddings.py` (Session 120)
- Criteria: cosine similarity >= 0.999 between local and ML service embeddings
- Status: Script exists, needs to be run with real ML service
- Requires: ML_SERVICE_URL env var (Railway internal URL or admin endpoint)
- **Challenge**: ML service is on Railway internal network. Script can't reach it from local.
- **Options**: (a) Run via Railway CLI one-off, (b) Add admin proxy endpoint `/api/admin/ml-compare`, (c) Document as manual verification step
- **Decision**: Add lightweight admin endpoint that proxies to ML service, returns embeddings. Script calls that.
- Files: `app/admin_routes.py` (new endpoint), `scripts/compare_ml_embeddings.py` (add --url flag)
- AD-229 full criteria: 1) 24h uptime, 2) 3 uploads, 3) cosine >= 0.999, 4) billing <= $5/mo

### 2. UX-211: Face Overlay Buttons Too Small on Group Photos (P1)
- Face overlays in `app/page_routes.py:3780-3860`
- CSS in `app/main.py:1005-1034`
- Percentage-based sizing from bbox — no minimum size
- Fix: Add minimum click target size (44px per mobile guidelines)
- Add "click face to select, then act from panel" interaction for dense photos
- **This is a CSS + interaction fix, NOT a PRD** — the core behavior stays the same
- Files: `app/page_routes.py`, `app/main.py` (CSS)

### 3. UX-207: Approvals Not Community-Scoped (P1)
- Pending uploads loaded from `data/pending_uploads.json` via `_load_pending_uploads()`
- Each entry HAS a `community` field (set in upload_routes.py)
- Admin list shows ALL pending uploads regardless of community
- Fix: Filter by `request.state.community` in admin approval list
- Files: `app/admin_routes.py`, `app/main.py`

### 4. TOOLS-003: Face Compare Real-Time (Planning Only)
- PRD-034 documents the feature
- ML service is deployed (TOOLS-002 complete)
- Two paths: ONNX export vs ML service extension
- **This session**: Write PRD for TOOLS-003 implementation path
- Investigate: Does ML service `/api/v1/detect-and-embed` return embeddings suitable for compare?
- Files: `docs/prds/` (new PRD), `app/compare_routes.py` (read only)

### 5. WORKSPACE-001: Personal Archive Auto-Creation (Planning Only)
- PRD-036 exists at `docs/prds/036_workspace_onboarding.md`
- **This session**: Validate PRD against current codebase, add schema migration plan
- Schema: communities table needs `owner_id`, `is_personal`, `privacy` columns
- Files: `docs/prds/036_workspace_onboarding.md` (review), context file (plan)

### 6. UX-212: Source URL Not Saved During Upload (P2)
- Upload form HAS source_url field, JavaScript appends to FormData
- source_url IS saved to pending_uploads.json
- **Root cause hypothesis**: Not propagated when approval copies to photo record
- Trace: approval flow in admin_routes.py → photo_index.json write
- Files: `app/admin_routes.py` or `app/upload_routes.py`

### 7. UX-208: Always Show Community Badge on Suggestion Cards (P2)
- `_cross_community_badge()` in `app/main.py:549-590`
- Returns None for same-community (line 573) — this hides the badge
- Fix: Return a "same community" badge instead of None
- Also apply in `neighbor_card()` at main.py:9139
- Files: `app/main.py`

## Parallelization Plan

### File Dependency Analysis
| Track | Files Touched | Overlap? |
|-------|--------------|----------|
| AD-229 endpoint | admin_routes.py, compare_ml_embeddings.py | admin_routes.py |
| UX-211 | page_routes.py, main.py (CSS) | main.py |
| UX-207 | admin_routes.py, main.py | admin_routes.py, main.py |
| UX-212 | upload_routes.py or admin_routes.py | admin_routes.py |
| UX-208 | main.py | main.py |
| TOOLS-003 PRD | docs/prds/ (new) | None |
| WORKSPACE-001 plan | docs/prds/ (existing), context | None |

### Execution Strategy
**Phase 0**: Orient (sequential on main)
**Worktree A**: UX-211 (page_routes.py + main.py CSS only)
**Worktree B**: TOOLS-003 PRD + WORKSPACE-001 plan (docs only, no code)
**Sequential on main**: AD-229 endpoint → UX-207 → UX-212 → UX-208 (all touch admin_routes.py or main.py)
**Phase 8**: Harness outputs + browser verification + gap check

Note: UX-207, UX-212, and AD-229 all touch admin_routes.py — must be sequential.
UX-208 touches main.py which UX-211 also touches — but UX-211 only touches CSS section while UX-208 touches badge logic (~line 549). Can parallelize if careful, but safer sequential.

## Breadcrumbs
- AD-229: `docs/ml/ALGORITHMIC_DECISIONS.md` (lines 2672-2684)
- UX-206-215: `docs/BACKLOG.md` (Session 119 feedback items)
- TOOLS-003: `docs/prds/034_standalone_tool_suite.md`
- WORKSPACE-001: `docs/prds/036_workspace_onboarding.md`
- Session 120 assessment: `docs/assessments/session-120-assessment.md`
- Lesson 149: Browser READ-ONLY on production

---

## WORKSPACE-001: Personal Archive Auto-Creation — Implementation Plan

### Overview

PRD-036 defines the vision for self-service onboarding. WORKSPACE-001 is the first
deliverable: when a user signs up, automatically create a personal community archive
for them. This enables the funnel: standalone tools -> signup -> personal archive ->
community discovery.

### 1. Supabase Schema Changes

**communities table — 3 new columns:**
```sql
ALTER TABLE communities ADD COLUMN owner_id UUID REFERENCES auth.users(id);
ALTER TABLE communities ADD COLUMN is_personal BOOLEAN DEFAULT false;
ALTER TABLE communities ADD COLUMN privacy TEXT DEFAULT 'public'
    CHECK (privacy IN ('private', 'unlisted', 'public'));

-- Index for owner lookup
CREATE INDEX idx_communities_owner_id ON communities(owner_id);

-- Unique constraint: one personal archive per user
CREATE UNIQUE INDEX idx_communities_personal_owner
    ON communities(owner_id) WHERE is_personal = true;
```

**community_members table (new):**
```sql
CREATE TABLE IF NOT EXISTS community_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    community_id UUID NOT NULL REFERENCES communities(id),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    role TEXT NOT NULL DEFAULT 'viewer'
        CHECK (role IN ('viewer', 'member', 'admin')),
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    invited_by UUID REFERENCES auth.users(id),
    UNIQUE(community_id, user_id)
);
CREATE INDEX idx_community_members_user ON community_members(user_id);
CREATE INDEX idx_community_members_community ON community_members(community_id);
```

**Migration script:** `scripts/sql/session_NNN_workspace_schema.sql`
- Run via Supabase SQL editor (no automated migration runner yet)
- Backfill existing communities: `owner_id = NULL`, `is_personal = false`, `privacy = 'public'`

### 2. Auth Signup Hook Location

**File:** `app/auth_routes.py` line 253-260 (`POST /signup`)

Current flow:
```
validate_invite_code(code) -> signup_with_supabase(email, password) -> set session -> redirect
```

New flow after signup success:
```
validate_invite_code(code)
-> signup_with_supabase(email, password)
-> create_personal_archive(user_id, email)   # NEW
-> set session
-> redirect to personal archive
```

**Implementation:**

New function in `app/supabase_data.py`:
```python
async def create_personal_archive(user_id: str, email: str) -> dict | None:
    """Create a personal community archive for a new user.

    Returns the created community dict, or None if creation fails.
    Idempotent: if personal archive already exists, returns it.
    """
    # Extract name from email (e.g., "nolan" from "nolan@gmail.com")
    name_part = email.split("@")[0].replace(".", " ").title()
    slug = f"personal-{user_id[:8]}"

    # Check if already exists (idempotent)
    existing = supabase.table("communities").select("*") \
        .eq("owner_id", user_id).eq("is_personal", True).execute()
    if existing.data:
        return existing.data[0]

    # Create community
    community = supabase.table("communities").insert({
        "slug": slug,
        "name": f"{name_part}'s Archive",
        "description": "Personal photo archive",
        "admin_emails": [email],
        "r2_prefix": f"personal/{user_id[:8]}",
        "owner_id": user_id,
        "is_personal": True,
        "privacy": "private",
        "config": {"auto_created": True},
    }).execute()

    # Add owner as admin member
    if community.data:
        supabase.table("community_members").insert({
            "community_id": community.data[0]["id"],
            "user_id": user_id,
            "role": "admin",
        }).execute()

    return community.data[0] if community.data else None
```

**R2 prefix note:** Personal archives use `personal/{user_id_prefix}/` in R2.
This keeps them isolated from community archives (`rhodes/`, `fox-family/`).

### 3. UI Changes Needed

**A. Sidebar — community indicator (app/main.py ~line 564-630)**
- Currently shows community name from `request.state.community`
- Add: "Your Archive" label when viewing personal community
- Add: photo count, identity count for personal archive
- No ML features initially (no proposals, no discoveries for personal archives)

**B. Community switcher (app/page_routes.py)**
- Currently: admin dropdown shows Rhodes, Fox Family
- Add: personal archive as first option in the dropdown
- Personal archive marked with a distinct icon/label ("Personal")
- Sort: personal first, then communities alphabetically
- File: `app/page_routes.py` (community switcher function ~line 620-640)

**C. Post-signup redirect**
- Currently: redirects to `/` (landing page)
- Change: redirect to `/c/{personal_slug}/` (personal archive)
- Show welcome state: "Welcome! Upload your first photo to get started."
- File: `app/auth_routes.py` (signup POST handler, line 253+)

**D. Empty state for personal archive**
- New personal archives have 0 photos
- Show: upload CTA, link to Compare/Estimate tools, link to `/communities`
- Reuse existing empty state pattern from admin upload page
- File: `app/page_routes.py` (landing page handler)

**E. Navigation — "My Archive" link**
- Add to top nav when user is logged in
- Points to `/c/{personal_slug}/`
- File: `app/main.py` (`_public_nav_links()`)

### 4. Session Estimates Per Phase

| Phase | Effort | Description | Files |
|-------|--------|-------------|-------|
| Schema + migration | 0.5 session | SQL migration, backfill, tests | `scripts/sql/`, `app/supabase_data.py` |
| Signup hook | 0.5 session | Auto-create on signup, idempotency, tests | `app/auth_routes.py`, `app/supabase_data.py` |
| Community switcher | 0.5 session | Personal archive in dropdown, sort order | `app/page_routes.py`, `app/main.py` |
| Empty state + redirect | 0.5 session | Post-signup UX, upload CTA, welcome state | `app/page_routes.py`, `app/auth_routes.py` |
| **Total** | **2 sessions** | Conservative estimate; could compress to 1.5 |

### 5. Parallelization — Agent Team Decomposition

WORKSPACE-001 is tagged as an agent team candidate in ROADMAP.md. Here is the
file dependency analysis:

| Agent | Files | Dependencies |
|-------|-------|-------------|
| Agent A: Schema | `scripts/sql/`, `app/supabase_data.py` (new functions) | None |
| Agent B: Auth hook | `app/auth_routes.py`, `app/auth.py` | Needs Agent A schema |
| Agent C: UI/Sidebar | `app/main.py` (nav), `app/page_routes.py` (switcher, empty state) | Needs Agent A schema |

**Verdict: Partially parallelizable.**
- Agent A (schema) must go first
- Agents B and C can run in parallel after A completes
- B and C touch different files (auth_routes vs main.py/page_routes)
- Use worktrees for B and C

**Worktree strategy:**
```
main:           Agent A (schema migration + supabase_data functions)
worktree-auth:  Agent B (signup hook + redirect)
worktree-ui:    Agent C (sidebar + switcher + empty state)
merge:          ./scripts/merge.sh worktree-auth worktree-ui
```

### 6. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| R2 prefix collision | Data loss | Unique slug via user_id prefix; idempotent creation |
| Supabase schema migration breaks existing communities | P0 | ALTER TABLE ADD COLUMN with defaults; no existing data changes |
| Invite code removal needed for organic signup | Blocks adoption | Separate decision: keep invite codes for now, remove in WORKSPACE-004 |
| Community cache invalidation | Stale UI | Invalidate `load_communities()` TTL cache on community creation |
| Personal archives pollute admin views | UX confusion | Filter `is_personal=true` from admin community lists |

### 7. What This Does NOT Include

Per PRD-036 scope:
- WORKSPACE-002 (sharing mode UX) — depends on WORKSPACE-001
- WORKSPACE-003 (add photos to community) — depends on WORKSPACE-001
- WORKSPACE-004 (anonymous contributions) — independent
- WORKSPACE-005 (community discovery page) — independent
- WORKSPACE-006 (per-community permissions) — depends on community_members table from this phase

### Breadcrumbs

- PRD: `docs/prds/036_workspace_onboarding.md`
- Schema SQL: `scripts/sql/create_communities.sql` (existing table definition)
- Auth signup: `app/auth_routes.py:253` (POST /signup handler)
- Community middleware: `app/main.py:477` (CommunityMiddleware class)
- Community switcher: `app/page_routes.py:620` (load_communities usage)
- Supabase data layer: `app/supabase_data.py` (community CRUD functions)
- ROADMAP: WORKSPACE-001 tagged as agent team candidate
