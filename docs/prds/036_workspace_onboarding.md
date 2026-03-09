# PRD-036: Workspace UX Vision — Self-Service Onboarding & Contributions

**Status:** Vision Document (not implementing now)
**Author:** Session 95b Track D
**Date:** 2026-03-09
**Related:** PRD-035 (multi-community platform), PRD-030 (multi-tenant), COMMUNITY-001/002

---

## Problem Statement

Rhodesli supports multiple communities (Session 95, PRD-035), but the UX is admin-only. There is no self-service way for users to create archives, upload photos to communities, or contribute without admin access. The current flow requires the admin to create communities, upload photos, and manage all identities. This bottleneck prevents organic growth and limits the platform to communities where Nolan is personally involved.

**Current gaps:**
- No personal workspace for users
- No way for non-admins to upload photos
- No community discovery mechanism
- No tiered permissions (admin or nothing)
- Anonymous visitors cannot contribute at all
- Signup requires an invite code and has no organic hook

---

## Personal Archive Model

Every user gets a personal workspace on signup.

### Auto-Creation
- Triggered on first successful signup
- Name: `"{first_name}'s Archive"` (e.g., "Nolan's Archive")
- Supabase row in `communities` table with `owner_id = user.id`
- `is_personal = true` flag distinguishes from shared communities

### Defaults
- Default collection: "Personal Archive"
- Default source: "Personal"
- Privacy: photos private by default (only visible to owner)

### What Users Can Do
- Upload photos (face detection runs automatically via ML service, TOOLS-002)
- Run Compare and Estimate on their own photos
- Organize into collections
- Share individual photos or results via public links

### Data Model Addition
```
communities table (existing):
  + owner_id UUID REFERENCES auth.users(id)
  + is_personal BOOLEAN DEFAULT false
  + privacy TEXT DEFAULT 'private'  -- 'private', 'unlisted', 'public'
```

---

## Sharing Mode vs Admin Mode

Two distinct interaction levels per community.

### Admin Mode (current)
Full control over a community archive:
- Upload and manage photos
- Confirm/reject ML identity matches
- Merge and split identities
- Upload and link GEDCOM files
- Review ML proposals (Discoveries, auto-clustering)
- Configure community settings

### Sharing Mode (new, lighter)
Read-heavy with lightweight contributions:
- Browse photos and identities
- Use "Help Identify" to suggest names for unidentified faces
- View family tree, map, timeline
- Share photos and identities via social links
- Receive notifications when suggestions are reviewed

### Mode Assignment
- New users start in sharing mode for all communities
- Community admin can promote members to admin per-community
- Personal archive: owner always has admin mode

---

## Low-Friction Contributions

### Anonymous Visitors
- Can browse public communities and use standalone tools
- Can suggest identifications on "Help Identify" faces
- Optional email capture: "Want to be notified when someone responds?"
- Suggestions tracked by session ID (browser cookie)

### Gentle Signup Push
- After 3 anonymous contributions: "Sign up to track your contributions"
- After using a tool: "Sign up to save your results"
- Never block the contribution flow — signup is always optional

### Account Linking
- If an anonymous visitor signs up later, link their session contributions
- Match by session cookie → user ID mapping
- Contributions retroactively attributed to the new account

---

## Add Photos to Community

Users can share personal photos into a community archive.

### Flow
1. User uploads photos to their personal archive
2. Selects photos to share
3. Chooses target community from their memberships
4. Photos appear in community with `"{User}'s Archive"` as collection
5. Original stays in personal archive (reference, not copy)
6. Community admin reviews shared photos (Gatekeeper pattern)

### Data Model
```
community_photo_shares:
  id UUID PRIMARY KEY
  photo_id UUID REFERENCES photos(id)
  source_community_id UUID  -- personal archive
  target_community_id UUID  -- shared community
  shared_by UUID REFERENCES auth.users(id)
  status TEXT DEFAULT 'pending'  -- 'pending', 'approved', 'rejected'
  created_at TIMESTAMPTZ DEFAULT now()
  reviewed_at TIMESTAMPTZ
  reviewed_by UUID
```

### Rules
- Admin approval required before photos appear in community
- Rejection sends notification to contributor with optional reason
- Approved photos inherit community's ML pipeline (face detection, etc.)

---

## Community Discovery

### Public Community Directory
- Route: `/communities`
- Lists all communities with `privacy = 'public'`
- Shows: name, subtitle, photo count, identity count, era/location tags
- Search by name, location, era

### Joining a Community
- "Browse" button: view immediately (no approval needed)
- "Join" button: adds user as member (viewer role)
- Contributing requires member status
- Admin approval not required for joining, only for contributing photos

### Data Model
```
community_members:
  id UUID PRIMARY KEY
  community_id UUID REFERENCES communities(id)
  user_id UUID REFERENCES auth.users(id)
  role TEXT DEFAULT 'viewer'  -- 'viewer', 'member', 'admin'
  joined_at TIMESTAMPTZ DEFAULT now()
  invited_by UUID
  UNIQUE(community_id, user_id)
```

---

## Per-Community Permissions

| Action | Viewer | Member | Admin |
|--------|--------|--------|-------|
| Browse photos | Yes | Yes | Yes |
| View identities | Yes | Yes | Yes |
| Suggest identifications | No | Yes | Yes |
| Share photos from personal | No | Yes | Yes |
| Upload directly | No | No | Yes |
| Confirm/reject matches | No | No | Yes |
| Manage GEDCOM | No | No | Yes |
| Community settings | No | No | Yes |
| Invite members | No | No | Yes |

### Enforcement
- Middleware checks `community_members.role` for the active community
- Falls back to viewer for non-members of public communities
- Private communities return 404 for non-members

---

## Signup-Without-Community Flow

For users who discover Rhodesli through standalone tools.

### Journey
1. User finds Compare or Estimate via search/social
2. Uses tool without signup (anonymous, free tier)
3. CTA after use: "Sign up to save your results"
4. On signup: personal archive auto-created
5. Previous tool results saved to personal archive
6. User discovers communities later via `/communities`

### Key Principle
Tools are the top of funnel. Communities are the retention mechanism. Personal archives bridge the two.

---

## Out of Scope

- Billing/monetization (free tier only for now)
- Community creation wizard (admin-only via Supabase/admin panel)
- White-label/custom domain per community
- Mobile app
- Real-time collaboration (comments, chat)
- Community-to-community photo sharing

---

## Priority Order

| Priority | Feature | Effort | Dependencies |
|----------|---------|--------|--------------|
| P1 | Personal archive auto-creation on signup | 1 session | TOOLS-002 for ML |
| P2 | Sharing mode UX (Help Identify for members) | 1-2 sessions | P1 |
| P3 | Add photos to community flow | 1-2 sessions | P1 |
| P4 | Anonymous contributions with session tracking | 1 session | None |
| P5 | Community discovery page (`/communities`) | 1 session | None |
| P6 | Per-community permissions enforcement | 2 sessions | P5 |

### Sequencing Notes
- P1 and P4 are independent and can be parallelized
- P2 and P3 depend on P1 (personal archive must exist)
- P5 and P6 are independent of P1-P3
- Total estimated effort: 5-8 sessions

---

## Success Metrics

- **Signup conversion**: % of anonymous tool users who create accounts
- **Contribution rate**: suggestions per community member per month
- **Photo sharing**: photos shared to communities per month
- **Community growth**: new members per community per month
- **Retention**: returning users (7-day, 30-day)

---

## References

- PRD-035: Multi-Community Platform (Session 95)
- PRD-030: Multi-Collection Architecture
- PRD-034: Standalone Tool Suite
- COMMUNITY-001: Community data scoping gaps
- COMMUNITY-002: Workspace switcher UX
- `docs/architecture/PERMISSIONS.md`: Current permission model
- `docs/design/FUTURE_COMMUNITY.md`: Original community design notes
