# Rhodesli Web Application — System Design

**Version:** 1.1
**Date:** 2026-02-05
**Author:** System Design Session
**Updated:** 2026-02-05 — Finalized decisions, added invite-only auth, R2 backups, schema extension guide

## Executive Summary

This document describes the architecture for deploying Rhodesli as a public community website at `rhodesli.nolanandrewfox.com`. The design preserves the existing JSON-based data stores while adding a community layer for annotations, photo contributions, and user management.

**Key Decisions (Finalized):**
- **URL:** `rhodesli.nolanandrewfox.com` (subdomain via Cloudflare CNAME)
- **Hosting:** Railway (hobby tier ~$5-20/mo)
- **Auth:** Invite-only for V1 (admin sends invites, no open signup)
- **Browsing:** Fully public — no login required to browse/search
- **Email:** Supabase built-in
- **Backups:** Cloudflare R2 (daily automated uploads)

**Scale Target:**
- Dozens to low-hundreds of users
- 1-3 simultaneous users
- Low thousands of photos (currently 112, growing slowly)
- Emphasis on trust, attribution, and reversibility

---

## 1. Architecture Overview: "Layered Truth" Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                        PUBLIC WEB UI                                 │
│                 rhodesli.nolanandrewfox.com                          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │     FastHTML App      │
                    │   (Railway/Render)    │
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Layer 1:    │     │    Layer 2:     │     │    Layer 3:     │
│   Canonical   │     │   Community     │     │     Users       │
│     Data      │     │  Annotations    │     │  (Supabase)     │
├───────────────┤     ├─────────────────┤     ├─────────────────┤
│identities.json│     │   Postgres      │     │    Auth         │
│photo_index.json│    │  - annotations  │     │  - sessions     │
│embeddings.npy │     │  - photo_uploads│     │  - profiles     │
│raw_photos/    │     │  - activity_log │     │  - roles        │
└───────────────┘     └─────────────────┘     └─────────────────┘
     (admin)              (community)            (Supabase)
```

### Layer 1: Canonical Data (Curator-Controlled)
- **Files:** `identities.json`, `photo_index.json`, `embeddings.npy`
- **Access:** ONLY modified by admin actions
- **Purpose:** Represents accepted truth about identities
- **Integrity:** Backed up regularly, versioned in Git history

### Layer 2: Community Annotations (Postgres via Supabase)
- **Tables:** `annotations`, `photo_uploads`, `activity_log`
- **Access:** Contributors can create; admins approve/reject
- **Purpose:** Crowdsourced enrichments awaiting moderation
- **Workflow:** PENDING → ACCEPTED (promoted to canonical) or REJECTED

### Layer 3: User Management (Supabase Auth)
- **Services:** Authentication, sessions, roles
- **Features:** Email verification, password reset
- **Purpose:** Identity and access control

---

## 2. Current State Analysis

### 2.1 Existing Technology Stack
| Component | Technology | Notes |
|-----------|------------|-------|
| Framework | FastHTML (Python) | Inline HTML generation, no separate templates |
| Styling | Tailwind CSS (CDN) | JIT compilation via CDN |
| Interactivity | HTMX + Hyperscript | Declarative DOM updates |
| Server | Uvicorn | ASGI server |
| Data I/O | JSON + NumPy | Atomic writes with portalocker |

#### 2.1.1 FastHTML Architecture Note

FastHTML generates HTML inline in Python code. There are NO separate
template files (no Jinja2, no .html files). The entire UI lives in
`app/main.py` (currently ~3,980 lines) as Python functions that return
HTML elements.

When the implementation phases reference "creating components," this means:
- Creating Python modules (e.g., `app/components/auth_forms.py`)
- Each module exports functions that return FastHTML elements
- These functions are imported and called in route handlers
- They are NOT template files

Example:
```python
# app/components/auth_forms.py
from fasthtml.common import *

def login_form():
    return Form(
        Input(type="email", name="email", placeholder="Email"),
        Input(type="password", name="password", placeholder="Password"),
        Button("Sign In", type="submit"),
        method="POST", action="/auth/login"
    )
```

All implementation prompts must account for this pattern.

### 2.2 Data Stores
| File | Size | Purpose |
|------|------|---------|
| `identities.json` | 434 KB | Identity metadata, face assignments, states |
| `photo_index.json` | 51 KB | Photo metadata, source attribution |
| `embeddings.npy` | 2.3 MB | 547 face embeddings (512-dim PFE vectors) |
| `file_hashes.json` | 5 KB | Deduplication hashes |
| `raw_photos/` | 255 MB | 112 source photographs |

### 2.3 Endpoint Inventory (~30 routes)
- **Pages:** `/`, `/upload`, `/inbox/{id}/review`
- **Identity API:** `/api/identity/{id}/rename`, `/merge`, `/skip`, `/faces`, `/neighbors`
- **Photo API:** `/api/photo/{id}`, `/photos/{filename}`
- **Face API:** `/api/face/{id}/detach`
- **Admin:** `/confirm/{id}`, `/reject/{id}`

### 2.4 Memory Footprint
- **Embeddings:** ~2.3 MB (547 faces × 512 × 2 vectors × 4 bytes)
- **At 10,000 faces:** ~42 MB (well within limits)
- **Registry:** ~500 KB parsed JSON (identities + photo index)
- **Total startup:** < 10 MB, sub-second load time

### 2.5 What's Missing for Web Deployment
- [ ] No authentication (currently single-user)
- [ ] No role-based access control
- [ ] No community contribution workflow
- [ ] No environment-based configuration
- [ ] No Dockerfile / deployment configuration
- [ ] No HTTPS / production security hardening

---

## 3. Infrastructure Decisions

### 3.1 Compute Platform: Railway

| Platform | Pros | Cons | Cost |
|----------|------|------|------|
| **Railway** | Persistent disk, simple deploys, good Python support | Less flexible than Fly | $5/mo hobby, scales to $20/mo |
| Render | Similar to Railway, free tier | Cold starts on free tier | Free-$7/mo |
| Fly.io | Edge deployment, volumes | More complex config | $5/mo+ |

**Decision:** Railway
- Persistent disk for `data/` directory (photos, JSON, embeddings)
- Simple Docker or Nixpacks deployment
- No cold starts on hobby plan
- GitHub integration for auto-deploy

**⚠️ Storage Consideration:**
Railway persistent volumes may require the Pro plan ($20/mo).
Verify current pricing at railway.app/pricing before deployment.

**If persistent volumes require Pro plan:**
- **Option A: Use Pro plan ($20/mo)** — simplest, persistent storage included
- **Option B: Use Hobby plan + Cloudflare R2 for all file storage**
  - Photos served from R2 via signed URLs
  - JSON/embeddings loaded from R2 on startup, cached in memory
  - Writes go to R2 (higher latency but works)
  - More complex but cheaper
- **Option C: Bundle data into Docker image**
  - Only works for read-only data (photos, initial embeddings)
  - Dynamic data (identities.json) still needs persistent storage
  - Not viable for an app that writes data

**Recommendation:** Verify pricing. If persistent volumes are on Pro,
the $20/mo is worth it for simplicity. The alternative (R2 for everything)
adds significant complexity for minimal savings.

**Fallback:** If Railway doesn't work, Render offers persistent disk
on their $7/mo plan. Fly.io offers volumes on all plans.

### 3.2 Database & Auth: Supabase (Free Tier)

**Why Supabase over alternatives:**
- Managed Postgres + Auth in one service
- Free tier: 500 MB database, 50,000 monthly active users
- Built-in email verification, password reset
- Row Level Security for fine-grained access control
- Python client library (`supabase-py`)

**Usage vs Free Tier:**
| Resource | Free Limit | Expected Usage |
|----------|------------|----------------|
| Database | 500 MB | < 10 MB (annotations + logs) |
| Auth users | 50,000 MAU | < 100 total |
| API requests | Unlimited | Low thousands/month |
| Bandwidth | 2 GB | Minimal (photos served from Railway) |

**Integration Pattern:** Server-side only.
All Supabase calls are made from the Python backend using `supabase-py`.
The Supabase JavaScript client is NOT used in the browser.
This means:
- No CORS configuration needed
- Service role key stays on the server (never exposed to client)
- All auth flows go through FastHTML routes, not client-side redirects

### 3.3 Photo Storage Strategy

**V1 (Initial):** Local filesystem on Railway
- Photos stored on Railway persistent volume
- Simple FileResponse serving
- ~255 MB current, room for 2-3 GB

**V2 (If needed):** Cloud storage migration
- Trigger: When approaching 5 GB or needing CDN
- Target: Cloudflare R2 (S3-compatible, no egress fees)
- Migration path: Background job moves files, updates `photo_index.json`

### 3.4 DNS & Routing

**Decision:** Subdomain via Cloudflare CNAME
```
rhodesli.nolanandrewfox.com → Railway app
```

**Setup Steps:**

1. **In Cloudflare DNS:**
   - Add CNAME record: `rhodesli` → `<railway-app>.up.railway.app`
   - Proxy status: **Proxied** (orange cloud) for free SSL + caching

2. **In Railway:**
   - Add custom domain: `rhodesli.nolanandrewfox.com`
   - Railway automatically provisions SSL via Let's Encrypt

**Benefits:**
- Cloudflare provides DDoS protection and caching
- SSL handled automatically at both Cloudflare and Railway edge
- No reverse proxy configuration needed
- Simple DNS change if Railway ever needs to be replaced

---

## 4. Data Model: New Postgres Tables

These tables support the community layer. **Canonical data remains in JSON files.**

### 4.1 profiles
Links Supabase auth users to application-specific data.

```sql
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id),
  email TEXT NOT NULL,
  display_name TEXT,
  role TEXT NOT NULL DEFAULT 'contributor'
    CHECK (role IN ('admin', 'contributor', 'viewer')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RLS: Users can read their own profile, admins can read all
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile"
  ON profiles FOR SELECT
  USING (auth.uid() = id);

CREATE POLICY "Admins can view all profiles"
  ON profiles FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role = 'admin'
    )
  );
```

### 4.2 invites
Invite tokens for invite-only signup. Admins create invites, contributors consume them.

```sql
CREATE TABLE invites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT NOT NULL,
  invited_by UUID NOT NULL REFERENCES profiles(id),
  token TEXT NOT NULL UNIQUE DEFAULT encode(gen_random_bytes(32), 'hex'),
  used_at TIMESTAMPTZ,  -- NULL until consumed
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Invites expire after 30 days
  expires_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '30 days'
);

CREATE INDEX idx_invites_token ON invites(token);
CREATE INDEX idx_invites_email ON invites(email);

-- RLS: Only admins can create/view invites
ALTER TABLE invites ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage invites"
  ON invites FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role = 'admin'
    )
  );
```

### 4.3 annotations
Community-submitted enrichments awaiting moderation.

```sql
CREATE TABLE annotations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id UUID NOT NULL REFERENCES profiles(id),

  -- What is being annotated
  target_type TEXT NOT NULL
    CHECK (target_type IN ('identity', 'photo', 'face')),
  target_id TEXT NOT NULL,  -- UUID from identities.json or photo_id

  -- Type of annotation
  annotation_type TEXT NOT NULL
    CHECK (annotation_type IN (
      'name_suggestion',
      'date_suggestion',
      'location_suggestion',
      'relationship_note',
      'general_note'
    )),

  -- Flexible payload for different annotation types
  payload JSONB NOT NULL,
  /*
    Examples:
    {"suggested_name": "Victoria Capeluto", "confidence": "certain", "notes": "My grandmother"}
    {"suggested_date": "circa 1965", "notes": "Based on venue decoration"}
    {"related_identity": "uuid-xxx", "relationship": "spouse"}
    {"note": "This person also appears in photo xyz"}
  */

  -- Moderation workflow
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'accepted', 'rejected')),
  reviewed_by UUID REFERENCES profiles(id),
  reviewed_at TIMESTAMPTZ,
  review_notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_annotations_target ON annotations(target_type, target_id);
CREATE INDEX idx_annotations_status ON annotations(status);
CREATE INDEX idx_annotations_author ON annotations(author_id);
```

### 4.4 photo_uploads
Staging area for community photo contributions.

```sql
CREATE TABLE photo_uploads (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  author_id UUID NOT NULL REFERENCES profiles(id),

  -- File information
  filename TEXT NOT NULL,
  file_path TEXT NOT NULL,  -- Path in staging directory
  file_size_bytes INTEGER,
  file_hash TEXT,  -- SHA-256 hash for deduplication

  -- Metadata from contributor
  source_collection TEXT,  -- "Franco Family Album", "Estate of J. Smith"
  source_notes TEXT,
  estimated_date TEXT,

  -- Moderation workflow
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'accepted', 'rejected', 'processing')),
  reviewed_by UUID REFERENCES profiles(id),
  reviewed_at TIMESTAMPTZ,
  review_notes TEXT,

  -- After acceptance, links to canonical data
  canonical_photo_id TEXT,  -- Set after ingestion

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_photo_uploads_status ON photo_uploads(status);
CREATE INDEX idx_photo_uploads_author ON photo_uploads(author_id);
```

**Duplicate Detection on Upload:**
Before creating a photo_upload record:
1. Compute SHA-256 hash of uploaded file
2. Check against `file_hashes.json`
3. If duplicate: reject immediately with "This photo already exists"
4. If new: proceed with staging

### 4.5 activity_log
Append-only audit trail for community and admin actions.

```sql
CREATE TABLE activity_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id UUID REFERENCES profiles(id),  -- NULL for system actions

  action TEXT NOT NULL,
  /*
    Actions:
    - annotation_submitted, annotation_accepted, annotation_rejected
    - photo_uploaded, photo_accepted, photo_rejected
    - identity_merged, identity_confirmed, identity_rejected
    - user_registered, user_role_changed
  */

  target_type TEXT,  -- 'identity', 'photo', 'annotation', 'user'
  target_id TEXT,

  details JSONB,  -- Action-specific context

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_activity_log_actor ON activity_log(actor_id);
CREATE INDEX idx_activity_log_target ON activity_log(target_type, target_id);
CREATE INDEX idx_activity_log_created ON activity_log(created_at DESC);
```

---

## 5. Authentication Flow

**Model:** Invite-only for V1. Admins send invites, no public signup.

### 5.1 Invite Flow (Admin Creates Invite)
```
Admin                   FastHTML                 Supabase
  │                         │                        │
  │── POST /admin/invite ──►│                        │
  │   {email}               │                        │
  │                         │── INSERT invites ─────►│
  │                         │   token=random_hex(32) │
  │                         │                        │
  │                         │── Send email via ─────►│
  │                         │   Supabase SMTP        │
  │                         │   Link: /signup?token= │
  │                         │                        │
  │◄── "Invite sent!" ──────│                        │
```

**Admin UI (User Management page):**
1. Admin goes to User Management
2. Enters email address of person to invite
3. System creates invite record with unique token
4. Supabase sends email with signup link:
   `rhodesli.nolanandrewfox.com/signup?token=abc123...`
5. Admin sees invite status (pending, accepted, expired)

### 5.2 Signup Flow (Contributor Accepts Invite)
```
Contributor             FastHTML                 Supabase
  │                         │                        │
  │── GET /signup?token=───►│                        │
  │                         │── SELECT invite ──────►│
  │                         │   WHERE token=X        │
  │                         │                        │
  │                         │   Validate:            │
  │                         │   - Token exists       │
  │                         │   - Not expired        │
  │                         │   - Not already used   │
  │                         │                        │
  │◄── Signup form ─────────│                        │
  │    (email pre-filled)   │                        │
  │                         │                        │
  │── POST /signup ────────►│                        │
  │   {first, last, pass}   │                        │
  │                         │── signUp() ───────────►│
  │                         │                        │
  │                         │◄── user + session ─────│
  │                         │                        │
  │                         │── INSERT profile ─────►│
  │                         │   (role='contributor') │
  │                         │                        │
  │                         │── UPDATE invite ──────►│
  │                         │   used_at=NOW()        │
  │                         │                        │
  │◄── Set cookie ──────────│                        │
  │    Redirect to /        │                        │
  │                         │                        │
  │◄────────────── Verification email ──────────────│
```

**Contributor experience:**
1. Receives email with invite link
2. Clicks link → signup page (pre-filled email, token validated)
3. Enters first name, last name, password
4. Account created, token marked as used
5. Email verification still required before contributing
6. If token is invalid/expired → friendly error with:
   "Contact the administrator for a new invite"

### 5.3 Invalid Invite Handling
- **Token not found:** "This invite link is invalid."
- **Token expired:** "This invite has expired. Contact the administrator for a new invite."
- **Token already used:** "This invite has already been used. If you need access, contact the administrator."

### 5.4 Login
```
User                    FastHTML                 Supabase
  │                         │                        │
  │──── POST /login ───────►│                        │
  │     {email, password}   │                        │
  │                         │──── signInWithPassword()──►│
  │                         │                        │
  │                         │◄─── session + JWT ─────│
  │                         │                        │
  │◄─── Set httpOnly cookie─│                        │
  │     Redirect to /       │                        │
```

### 5.5 Session Validation (Middleware)
```python
async def auth_middleware(request: Request, call_next):
    """Validate JWT on every request, populate request.state.user."""

    token = request.cookies.get("sb_access_token")

    if token:
        try:
            user = supabase.auth.get_user(token)
            profile = supabase.table("profiles").select("*") \
                .eq("id", user.id).single().execute()

            request.state.user = {
                "id": user.id,
                "email": user.email,
                "role": profile.data["role"],
                "display_name": profile.data["display_name"]
            }
        except:
            request.state.user = None
    else:
        request.state.user = None

    return await call_next(request)
```

### 5.6 Password Reset
1. User clicks "Forgot password" → `/auth/forgot-password`
2. Enters email → Supabase sends reset link
3. User clicks link → `/auth/reset-password?token=xxx`
4. User sets new password → Supabase updates auth

### 5.7 Security Considerations
- **JWTs in httpOnly cookies** (not localStorage) — XSS protection
- **CSRF tokens** on state-changing forms
- **Rate limiting** on auth endpoints
- **Email verification required** before contributing

---

## 6. Permission Matrix

### 6.1 Role Definitions

| Role | Description | Default For |
|------|-------------|-------------|
| `viewer` | Read-only access, browse and search | Not logged in |
| `contributor` | Can submit annotations and photos | New signups |
| `admin` | Full access, moderation, canonical writes | NolanFox@gmail.com |

### 6.2 Action Permissions

| Action | Viewer | Contributor | Admin |
|--------|--------|-------------|-------|
| Browse photos | ✅ | ✅ | ✅ |
| View identities | ✅ | ✅ | ✅ |
| Search | ✅ | ✅ | ✅ |
| View accepted annotations | ✅ | ✅ | ✅ |
| Submit name suggestion | ❌ | ✅ | ✅ |
| Submit date/location/note | ❌ | ✅ | ✅ |
| Upload photos | ❌ | ✅ | ✅ |
| View own pending submissions | ❌ | ✅ | ✅ |
| View all pending submissions | ❌ | ❌ | ✅ |
| Accept/reject annotations | ❌ | ❌ | ✅ |
| Accept/reject photo uploads | ❌ | ❌ | ✅ |
| Confirm identity | ❌ | ❌ | ✅ |
| Reject identity | ❌ | ❌ | ✅ |
| Merge identities | ❌ | ❌ | ✅ |
| Detach faces | ❌ | ❌ | ✅ |
| Rename identity (direct) | ❌ | ❌ | ✅ |
| Manage user roles | ❌ | ❌ | ✅ |

### 6.3 Implementation Pattern

```python
def require_role(min_role: str):
    """Decorator to enforce minimum role."""
    role_hierarchy = {"viewer": 0, "contributor": 1, "admin": 2}

    def decorator(func):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            user = getattr(request.state, "user", None)
            user_role = user["role"] if user else "viewer"

            if role_hierarchy.get(user_role, 0) < role_hierarchy[min_role]:
                return Response("Forbidden", status_code=403)

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator

# Usage
@rt("/api/identity/{id}/merge/{source_id}")
@require_role("admin")
async def merge_identity(request: Request, id: str, source_id: str):
    ...
```

---

## 7. UI Modifications

### 7.1 Sidebar Changes

```
┌─────────────────────────────────┐
│  RHODESLI                       │
│  Command Center                 │
├─────────────────────────────────┤
│                                 │
│  📋 Triage Queue                │ ← All users see
│  📸 Photo Viewer                │ ← All users see
│  🔍 Browse                      │ ← All users see
│                                 │
│  ─────────────────────────────  │
│                                 │
│  📤 Upload Photos     [●]       │ ← Contributors+ (badge if pending)
│  📝 My Contributions  [3]       │ ← Contributors only (count badge)
│                                 │
│  ─────────────────────────────  │ ← Admins only below
│                                 │
│  👥 Community                   │
│    ├─ Pending Approvals [5]     │
│    ├─ Activity Log              │
│    └─ User Management           │
│                                 │
├─────────────────────────────────┤
│  👤 Nolan Fox (admin)           │ ← If logged in
│     Sign Out                    │
│  ─────────────────────────────  │
│  Sign In                        │ ← If not logged in
│  Invite-only community          │    (no "Create Account" link)
└─────────────────────────────────┘
```

**Note for anonymous visitors:**
The sidebar should NOT show "Create Account" for anonymous users.
Instead display: "This is an invite-only community archive."
with a link to sign in if they already have an account.

### 7.2 Identity Card Modifications

**For Viewers (anonymous):**
```html
<!-- Hide all action buttons -->
<div class="identity-card">
  <h3>Leon Capeluto</h3>
  <div class="faces-grid">...</div>
  <!-- Actions hidden -->
  <p class="text-gray-500 text-sm">Sign in to suggest names or notes</p>
</div>
```

**For Contributors:**
```html
<div class="identity-card">
  <h3>
    Unidentified Person 033
    <span class="badge">1 pending suggestion</span>  <!-- If they have one -->
  </h3>
  <div class="faces-grid">...</div>
  <div class="actions">
    <button hx-get="/annotate/name/{id}">Suggest Name</button>
    <button hx-get="/annotate/note/{id}">Add Note</button>
    <!-- NO confirm/reject/merge buttons -->
  </div>
</div>
```

**For Admins:**
```html
<!-- Full existing UI, plus annotation indicators -->
<div class="identity-card">
  <h3>
    Unidentified Person 033
    <span class="badge badge-info">2 suggestions</span>
  </h3>
  <!-- Full action buttons as now -->
  <button hx-get="/api/identity/{id}/suggestions">Review Suggestions</button>
</div>
```

### 7.3 Annotation Modal

```html
<dialog id="annotate-name-modal">
  <form hx-post="/api/annotations" hx-swap="outerHTML">
    <input type="hidden" name="target_type" value="identity">
    <input type="hidden" name="target_id" value="{identity_id}">
    <input type="hidden" name="annotation_type" value="name_suggestion">

    <h2>Who do you think this is?</h2>

    <label>
      Suggested Name *
      <input type="text" name="suggested_name" required>
    </label>

    <label>
      How do you know? (optional)
      <textarea name="notes" placeholder="e.g., This is my grandmother..."></textarea>
    </label>

    <label>
      Confidence
      <select name="confidence">
        <option value="certain">Certain</option>
        <option value="likely" selected>Likely</option>
        <option value="guess">Just a guess</option>
      </select>
    </label>

    <div class="actions">
      <button type="button" onclick="this.closest('dialog').close()">Cancel</button>
      <button type="submit">Submit Suggestion</button>
    </div>
  </form>
</dialog>
```

### 7.4 My Contributions Page

```
┌─────────────────────────────────────────────────────┐
│  MY CONTRIBUTIONS                                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ⏳ Pending (3)                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │ Name suggestion for Unidentified Person 033  │   │
│  │ "Victoria Capeluto" - Submitted 2 hours ago  │   │
│  │ Status: Awaiting review                      │   │
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │ Photo upload: 3 photos from Franco Album     │   │
│  │ Submitted yesterday                          │   │
│  │ Status: Processing                           │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  ✅ Accepted (12)                                   │
│  ┌─────────────────────────────────────────────┐   │
│  │ Name "Leon Capeluto" accepted for Identity   │   │
│  │ Accepted by Admin on Jan 15, 2026            │   │
│  └─────────────────────────────────────────────┘   │
│  ...                                               │
│                                                     │
│  ❌ Not accepted (2)                                │
│  ...                                               │
└─────────────────────────────────────────────────────┘
```

---

## 8. Contributor Annotation Flow

### 8.1 Name Suggestion Flow

```
Contributor                  FastHTML                  Supabase
    │                            │                         │
    │── Click "Suggest Name" ───►│                         │
    │                            │                         │
    │◄── Return modal form ──────│                         │
    │                            │                         │
    │── Submit form ────────────►│                         │
    │   {name, notes, confidence}│                         │
    │                            │── INSERT annotation ───►│
    │                            │   status='pending'      │
    │                            │                         │
    │                            │── INSERT activity_log ─►│
    │                            │   'annotation_submitted'│
    │                            │                         │
    │◄── "Submitted!" toast ─────│                         │
    │    Badge added to card     │                         │
```

### 8.2 Admin Approval Flow

```
Admin                       FastHTML                  Supabase
    │                            │                         │
    │── View pending queue ─────►│                         │
    │                            │◄── SELECT annotations ──│
    │                            │    WHERE status=pending │
    │◄── List of suggestions ────│                         │
    │                            │                         │
    │── Click suggestion ───────►│                         │
    │                            │                         │
    │◄── Details + context ──────│                         │
    │    [Accept] [Reject]       │                         │
    │                            │                         │
    │── Click [Accept] ─────────►│                         │
    │                            │── UPDATE annotation ───►│
    │                            │   status='accepted'     │
    │                            │                         │
    │                            │── UPDATE identities.json│
    │                            │   (apply the name)      │
    │                            │                         │
    │                            │── INSERT activity_log ─►│
    │                            │   'annotation_accepted' │
    │                            │                         │
    │◄── Success, next item ─────│                         │
```

### 8.3 Photo Upload Flow

```
Contributor                  FastHTML                  Supabase
    │                            │                         │
    │── Select files ───────────►│                         │
    │   + source collection      │                         │
    │                            │                         │
    │                            │── Save to staging/ ─────│
    │                            │   (not raw_photos/)     │
    │                            │                         │
    │                            │── INSERT photo_uploads ►│
    │                            │   status='pending'      │
    │                            │                         │
    │◄── "Uploaded! Pending..." ─│                         │
```

**Admin approval:**
1. Admin reviews in moderation queue
2. Accept → triggers ingestion pipeline:
   - Move files from staging/ to raw_photos/ or data/uploads/
   - Run face detection
   - Update embeddings.npy
   - Update photo_index.json
   - Create inbox identities
3. Reject → files cleaned up, contributor notified

### 8.4 Annotation Promotion: What Happens When Admin Accepts

#### Name Suggestion Accepted:
1. Read identities.json (with file lock)
2. Find identity by target_id
3. Update name field with suggested name
4. Write identities.json (atomic write: temp file + rename)
5. Update annotation status to 'accepted'
6. Log to activity_log with full context
7. If contributor is watching: badge updates to "Accepted ✓"

#### Date/Location/Note Accepted:
1. Read identities.json or photo_index.json (depending on target_type)
2. Add metadata to appropriate record
3. Write file (atomic)
4. Update annotation status
5. Log to activity_log

#### Photo Upload Accepted:
This is the most complex promotion because it triggers the ingestion pipeline:
1. Move file(s) from data/staging/ to raw_photos/ (or data/uploads/)
2. Run face detection on new photo(s)
3. Generate embeddings for detected faces
4. Append new embeddings to embeddings.npy
5. Update photo_index.json with new photo metadata + source
6. Create new identity entries in identities.json (state: INBOX)
7. Update file_hashes.json with new hash
8. Update photo_uploads record: status='accepted', canonical_photo_id set
9. Log to activity_log

⚠️ Steps 2-7 may take 30-60 seconds per photo. This should run as a
background task, not block the admin's request. The status goes through:
pending → processing → accepted (or failed).

---

## 9. Implementation Phases

### Phase A: Deploy Existing App (1-2 sessions)
**Goal:** Current app running publicly, read-only access

**Pre-work:**
- [ ] Verify Railway persistent volume pricing (may require Pro plan)
- [ ] Set up Cloudflare R2 bucket for backups
- [ ] Configure Cloudflare DNS CNAME record: `rhodesli` → Railway

**Files to create:**
- `Dockerfile`
- `railway.toml` (or `render.yaml`)
- `.env.example`

**Files to modify:**
- `core/config.py` — add environment variable support
- `app/main.py` — make host/port/debug configurable
- `.gitignore` — ensure data/ and .env excluded

**Milestone:** App accessible at `rhodesli.nolanandrewfox.com`

---

### Phase B: Authentication (2-3 sessions)
**Goal:** Login + invite-only signup working, role-based UI hiding

**Files to create:**
- `core/auth.py` — Supabase integration
- `core/middleware.py` — JWT validation, user injection (investigate FastHTML middleware patterns)
- `app/components/auth_forms.py` — login/invite signup forms
- `app/components/user_badge.py` — sidebar user info

**Files to modify:**
- `requirements.txt` — add `supabase`, `python-jose`
- `app/main.py` — add auth middleware, conditional rendering
- All action buttons — wrap in role checks

**Database setup:**
- Create Supabase project
- Run schema migrations (profiles table + invites table)
- Configure email templates (invite email, verification)

**Admin UI:**
- Add basic invite form to User Management (even if minimal V1)
- Admin can enter email → system sends invite link

**Milestone:** Admin can invite users, invited users can sign up, login works

---

### Phase C: Annotation Engine (2-3 sessions)
**Goal:** Contributors can suggest names and metadata

**Files to create:**
- `core/annotations.py` — CRUD for annotations table
- `app/components/annotation_modal.py` — suggestion forms
- `app/routes/annotations.py` — submission endpoints
- `app/routes/my_contributions.py` — contributor's view

**Database setup:**
- Create annotations table
- Create activity_log table

**Milestone:** Contributors can submit, see pending status

---

### Phase D: Photo Upload Queue (1-2 sessions)
**Goal:** Contributors can upload photos for review

**Files to create:**
- `core/upload_queue.py` — staged upload handling
- `data/staging/` — temporary storage for pending uploads

**Files to modify:**
- `app/main.py` — modify upload endpoint for role-based behavior
- Current upload flow — branch on contributor vs admin

**Milestone:** Uploads go to staging, admin can approve

---

### Phase E: Admin Moderation Dashboard (2-3 sessions)
**Goal:** Admin can review and act on all submissions

**Files to create:**
- `app/routes/admin.py` — moderation endpoints
- `app/components/approval_queue.py` — pending items list
- `app/components/activity_feed.py` — recent actions
- `app/routes/users.py` — user management
- `scripts/migrate_activity_log.py` — parse existing user_actions.log → Postgres

**Files to modify:**
- Sidebar — add Community section for admins

**Activity Log Migration:**
- Parse existing `logs/user_actions.log` into Postgres activity_log table
- Preserves historical attribution of admin actions
- One-time migration script with --dry-run

**Milestone:** Full moderation workflow functional

---

### Phase F: Polish & Security (1-2 sessions)
**Goal:** Production-ready hardening

**Security Tasks:**
- Rate limiting on auth and submission endpoints
- CSRF protection on all forms
- Input sanitization review
- Error pages (404, 500)
- Logging to external service (optional)

**Backup Tasks:**
- Set up Cloudflare R2 backup cron job (see Section 10.4)
- Create `scripts/backup_to_r2.py`
- Test backup/restore procedure end-to-end
- Document recovery procedure

**Validation:**
- Load testing at expected scale
- Verify backup/restore works

**Milestone:** Confidently shareable with community, backups verified

---

## 10. Migration Plan

### 10.1 Data Migration Summary

| Data Type | Current | After Migration | Notes |
|-----------|---------|-----------------|-------|
| Identities | `identities.json` | `identities.json` | Unchanged |
| Photos | `photo_index.json` | `photo_index.json` | Unchanged |
| Embeddings | `embeddings.npy` | `embeddings.npy` | Unchanged |
| Users | N/A | Supabase auth + profiles | New |
| Annotations | N/A | Postgres annotations | New |
| Upload queue | N/A | Postgres photo_uploads | New |
| Activity log | `logs/user_actions.log` | Postgres activity_log | Migration optional |

### 10.2 Initial Admin Setup

1. Deploy app with auth enabled
2. Create admin user: `NolanFox@gmail.com`
3. Manually set role to 'admin' in Supabase dashboard (one-time)
4. Future admins promoted via user management UI

### 10.3 Photo Storage Path

**V1 (Launch):**
```
Railway persistent volume:
/app/
├── data/
│   ├── identities.json
│   ├── photo_index.json
│   ├── embeddings.npy
│   ├── uploads/
│   └── staging/        ← NEW: pending uploads
└── raw_photos/
    └── *.jpg
```

**V2 (If storage exceeds 5 GB):**
- Migrate to Cloudflare R2
- Update photo serving to proxy/redirect
- Keep embeddings and JSON local

### 10.4 Backup Strategy

#### The Problem
When running on Railway, admin actions modify canonical JSON files
(identities.json, photo_index.json) on Railway's persistent volume.
These changes do NOT automatically sync to Git or any other backup.
Railway snapshots exist but are not a reliable long-term backup.

#### Solution: Daily Backup to Cloudflare R2

Since we already use Cloudflare for DNS, Cloudflare R2 is the natural backup target.
R2 is S3-compatible with no egress fees.

**Backup Script:** `scripts/backup_to_r2.py`
- Runs daily via Railway cron job
- Uploads: identities.json, photo_index.json, embeddings.npy, file_hashes.json
- Versioned with date prefix: `backups/2026-02-05/identities.json`
- Retains last 30 days
- Logs success/failure to activity_log

**Backup Schedule:**

| Data | Method | Frequency | Retention |
|------|--------|-----------|-----------|
| `identities.json` | R2 upload | Daily + on admin write | 30 days |
| `photo_index.json` | R2 upload | Daily + on admin write | 30 days |
| `embeddings.npy` | R2 upload | Daily | 30 days |
| `file_hashes.json` | R2 upload | Daily | 30 days |
| `raw_photos/` | R2 upload | On new photo accepted | Permanent |
| Supabase Postgres | Supabase auto-backup | Continuous | 7 days (free) |

**Recovery:**
1. Download latest backup from R2 (via web console or `scripts/restore_from_r2.py`)
2. Replace files on Railway volume
3. Restart app

**Cost:** R2 free tier includes 10 GB storage, 10 million reads/month.
At our scale (~300 MB total), this is free.

#### Git as Secondary Archive
The local development copy of data/ serves as an additional snapshot.
Before each deployment, the developer should pull the latest backup from R2
and commit to Git as a checkpoint. This is manual but provides Git history.

---

## 11. Risks & Mitigations

### Risk 1: Memory Pressure
**Concern:** Embeddings loaded into RAM
**Current:** ~2.3 MB for 547 faces
**At 5,000 faces:** ~21 MB (still fine)
**Mitigation:** Railway hobby plan includes 512 MB RAM; embeddings fit easily

### Risk 2: Data Loss
**Concern:** JSON files are single points of failure
**Mitigation:**
- Atomic writes with temp file + rename
- **Daily automated backups to Cloudflare R2** (see Section 10.4)
- Backup on every admin write for critical files
- Git history as secondary archive (manual sync from R2)
- Supabase handles its own backups

### Risk 3: Spam/Abuse
**Concern:** ~~Open signup could attract spam~~ (MITIGATED)
**Decision:** Invite-only for V1
**Mitigation:**
- **Invite-only signup** — only invited users can create accounts
- Email verification required before contributing
- Rate limiting on submissions (5 per hour per user)
- Admin can deactivate accounts
- Initial user pool: 5-10 known contributors

### Risk 4: Scope Creep
**Concern:** Full build is 6-8 weeks
**Mitigation:**
- Phase A delivers public value immediately
- Each phase is independently valuable
- Can pause after any phase

### Risk 5: Contributor Confusion
**Concern:** Users may not understand suggestion vs edit
**Mitigation:**
- Clear UI language ("Suggest a name" not "Edit name")
- Confirmation dialogs explaining review process
- Status badges showing pending/accepted

---

## 12. Decisions Log

All major decisions have been finalized. This section documents the choices made.

### Deployment Decisions (Finalized 2026-02-05)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Auth model | **Invite-only for V1** | More controlled, less spam risk, appropriate for small community |
| Hosting platform | **Railway** | Simple Python deployment, persistent disk, GitHub integration |
| URL | **rhodesli.nolanandrewfox.com** (subdomain) | Simpler DNS setup than subdirectory; CNAME via Cloudflare |
| DNS provider | **Cloudflare** | User has access, free SSL, DDoS protection, R2 for backups |
| Budget | **Railway hobby (~$5-20/mo) + Supabase free** | Sufficient for expected scale |

### Authentication Decisions (Finalized 2026-02-05)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Email service | **Supabase built-in** | Free, quick setup; can upgrade to custom SMTP later |
| Browsing access | **Fully public** | No login required to browse/search; auth only for contributions |
| Initial users | **5-10 invited contributors** | Known community members in first wave |
| Invite UX | **One-at-a-time** | No bulk import needed; admin enters email manually |

### Feature Decisions (Finalized 2026-02-05)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Activity log migration | **Yes, migrate existing logs** | Preserves historical attribution; script in Phase E |
| Backup strategy | **Cloudflare R2** | Already using Cloudflare; S3-compatible, no egress fees |

### Remaining Open Items

- **Railway persistent volume pricing:** Verify if hobby plan includes volumes or if Pro ($20/mo) is required
- **Exact initial invite list:** Names of 5-10 community members for first wave (user to provide)

---

## Appendix A: File Structure After Implementation

```
rhodesli/
├── app/
│   ├── main.py                    # Modified: auth middleware, role checks
│   ├── static/
│   ├── components/
│   │   ├── auth_forms.py          # NEW: login/signup
│   │   ├── annotation_modal.py    # NEW: suggestion forms
│   │   ├── approval_queue.py      # NEW: admin moderation
│   │   └── user_badge.py          # NEW: sidebar user info
│   └── routes/
│       ├── annotations.py         # NEW: annotation CRUD
│       ├── admin.py               # NEW: moderation endpoints
│       └── users.py               # NEW: user management
├── core/
│   ├── auth.py                    # NEW: Supabase integration
│   ├── middleware.py              # NEW: JWT validation
│   ├── annotations.py             # NEW: annotation business logic
│   ├── upload_queue.py            # NEW: staged uploads
│   └── ...existing...
├── data/
│   ├── identities.json            # Unchanged
│   ├── photo_index.json           # Unchanged
│   ├── embeddings.npy             # Unchanged
│   ├── uploads/                   # Existing: accepted uploads
│   └── staging/                   # NEW: pending uploads
├── scripts/
│   ├── backup_to_r2.py            # NEW: daily R2 backup
│   ├── restore_from_r2.py         # NEW: restore from backup
│   └── migrate_activity_log.py    # NEW: parse user_actions.log → Postgres
├── raw_photos/                    # Unchanged
├── Dockerfile                     # NEW
├── railway.toml                   # NEW
├── .env.example                   # NEW
└── requirements.txt               # Modified: add supabase, python-jose, boto3
```

---

## Appendix B: Environment Variables

```bash
# .env.example

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # For admin operations

# Session
JWT_SECRET=your-secret-key  # For cookie signing

# Admin
ADMIN_EMAIL=NolanFox@gmail.com

# Cloudflare R2 (for backups)
R2_ACCOUNT_ID=your-cloudflare-account-id
R2_ACCESS_KEY_ID=your-r2-access-key
R2_SECRET_ACCESS_KEY=your-r2-secret-key
R2_BUCKET_NAME=rhodesli-backups
```

---

## Appendix C: Deployment Commands

### Railway
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link
railway login
railway link

# Deploy
railway up

# Set environment variables
railway variables set SUPABASE_URL=...
railway variables set SUPABASE_ANON_KEY=...
```

### Docker (local testing)
```bash
# Build
docker build -t rhodesli .

# Run
docker run -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/raw_photos:/app/raw_photos \
  -e SUPABASE_URL=... \
  rhodesli
```

---

## Appendix D: Schema Extension Guide

This section documents how to extend the data model for future needs.

### Adding a New Annotation Type

No schema migration needed. Just:
1. Add the new type to the CHECK constraint on `annotations.annotation_type`
2. Document the expected payload structure
3. Add UI components for submitting and reviewing the new type
4. Add promotion logic for accepting the new type (see Section 8.4)

Example — adding geotags:
```sql
-- Update CHECK constraint
ALTER TABLE annotations DROP CONSTRAINT annotations_annotation_type_check;
ALTER TABLE annotations ADD CONSTRAINT annotations_annotation_type_check
  CHECK (annotation_type IN (
    'name_suggestion', 'date_suggestion', 'location_suggestion',
    'relationship_note', 'general_note',
    'geotag'  -- NEW
  ));
```

Payload structure:
```json
{
  "latitude": 25.7617,
  "longitude": -80.1918,
  "location_name": "Miami Beach, FL",
  "notes": "Identifiable from the Brass Rail restaurant sign"
}
```

### Adding New Fields to Canonical Data

Canonical data lives in JSON files, which are schema-free.
To add new fields (e.g., splitting name into first_name/last_name):

1. Create a migration script: `scripts/migrate_split_names.py`
2. MUST support `--dry-run` (per CLAUDE.md)
3. Run dry-run, review output
4. Run `--execute` after approval
5. Update app code to read/write new fields
6. Maintain backward compatibility (old field can coexist during transition)

Example:
```python
# Before:
{"name": "Victoria Capeluto"}

# After (backward compatible):
{"name": "Victoria Capeluto", "first_name": "Victoria", "last_name": "Capeluto"}
```

### Adding New Postgres Tables

For entirely new features (e.g., family trees, event timelines):

1. Design table in this document first
2. Create SQL migration script
3. Run in Supabase SQL editor
4. Add RLS policies
5. Add Python CRUD module in `core/`
6. Add UI components in `app/components/`
7. Update this document

### Versioning Strategy

This document uses semantic sections. When extending:
- Add new subsections rather than modifying existing ones
- Note the date of changes in section headers if significant
- Keep the Decisions Log updated with any new decisions
