# Session 107b Context — Community Middleware Audit + Approvals UX

**Predecessor:** Session 107 (data fix + sidebar count fix)

## What happened in Session 107

1. **James Henry Fields photos in wrong community** — Two photos uploaded to Fox Family ended up in Rhodes. Root cause: upload done from URL without `/c/fox-family/` prefix, CommunityMiddleware defaulted to Rhodes. Fixed by updating `photo_communities` table in Supabase. Metadata preserved (source=Instagram, collection=Fox Family Internet Research).

2. **Approvals sidebar count = 0** — `_compute_sidebar_counts()` at app/main.py:3235 iterated dict keys (UUID strings) instead of `.values()` (annotation dicts). `.get("status")` on a string returned None, silently caught by `except Exception: pass`. Fixed.

3. **Anonymous pending uploads** — Two Compare Upload entries from 2026-03-13 persist in `pending_uploads.json` on Railway volume. Staging files auto-cleaned after 24h but JSON entries remain. Need auto-expiry.

## Community Middleware Issue History

This is the 7th+ time community scoping has caused problems:
- Session 96c: Community-scoped sidebar counts
- Session 96d: Cross-community identity tagging
- Session 102: DATA-019 community reassignment
- Session 103: Community-scoped suggestions
- Lesson 109: CommunityMiddleware /api/ skip creates dual-path problem
- Lesson 112: Community-scoped pages must filter ALL sections
- Lesson 113: Cross-community badge must check BOTH communities
- Session 107: Upload defaulting to Rhodes

The pattern: CommunityMiddleware defaults to "rhodes" (app/main.py:479,493) when no `/c/{slug}/` prefix. Data-modifying routes trust `request.state.community` without validation.

## Key Routes to Audit

Routes that write data with community context:
- `POST /upload` — app/upload_routes.py:554 — uses `request.state.community`
- `POST /api/match/decide` — app/match_facecompare_routes.py — match decisions
- `POST /api/identity/{id}/merge/{id}` — merges
- `POST /api/identity/{id}/confirm` — confirmations
- `POST /api/annotate/{id}` — annotations/suggestions
- `POST /api/cluster-review/*` — cluster review actions
- `POST /admin/pending/{job}/approve` — upload approval

## Approvals System State

### Data model
- Annotations stored in `annotations.json` (file) and `annotations` table (Supabase)
- Each annotation: `{annotation_id, identity_id, type, suggested_value, submitted_by, submitted_at, status, reason, ...}`
- Status: pending → approved/rejected/skipped
- Approval adds: `reviewed_by, reviewed_at` fields

### Current behavior when approving:
1. Renames the identity to the suggested name
2. Sets annotation status to "approved"
3. Records review metadata (who, when)
4. Sends individual email to submitter via Resend
5. Does NOT confirm the identity (state stays INBOX/PROPOSED)
6. Does NOT store annotation_id in identity rename history
7. Identity rename history records `user_source="approved_name_suggestion"` but no link back

### Gaps identified:
- No batch selection UI (pending uploads page has this pattern already)
- No submission timestamp visible on cards (data exists, not rendered)
- No auto-confirm on approve
- No annotation_id in rename history (can't trace back)
- Person page doesn't show suggestion provenance
- Email goes to submitter's email but in-app notification goes to phantom UUID
- No email batching/digest

### Quick fixes (< 30 min each):
1. Show `submitted_at` on cards — data exists, add render
2. Auto-confirm checkbox — wire to `registry.confirm_identity()`
3. Store annotation_id in rename history — one field addition
4. Auto-expire orphaned pending uploads — check staging dir exists

### Needs PRD:
- Email digest/batching
- Full audit trail on person page with actor attribution
- Consistent batch-action UX across all admin pages

## Fox Family Community ID
`ce335470-0d96-4524-af9c-1ef815e708e4`

## Rhodes Community ID
`72d8e4f0-ed32-4270-9bfe-8f407b78a6a7`

## James Henry Fields Photo State
- 2 photos in `photos` table, community reassigned to Fox Family
- 9 faces in `photo_faces` table
- 0 identities reference these faces (need clustering)
- No local embeddings (Railway-only, need download for ML pipeline)
- Crops exist on R2 (uploaded during web pipeline)
