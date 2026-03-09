# PRD-037: Post-Upload Intelligence Pipeline

**Author:** Nolan Fox + Claude
**Date:** 2026-03-09
**Status:** DRAFT
**Priority:** P1 — blocks Fox Family Archive population
**Estimated effort:** 1 session (pipeline + UI) + ongoing Gemini cost
**Origin:** Session 96, Charlie Fox collection upload planning

---

## Problem Statement

After uploading photos, **everything is manual**: clustering, GEDCOM linking, Gemini date estimation. For a 636-photo collection, this means hundreds of individual admin actions before photos are useful. The current pipeline creates INBOX identities and stops.

The optimal workflow Nolan identified:
1. Upload → auto-detect faces (exists)
2. Auto-cluster against known identities (exists but manual)
3. **Surface top identities by face count** so admin can GEDCOM-link the most impactful people first
4. **Batch Gemini with enriched GEDCOM context** after linking
5. Results appear on community pages

This is especially valuable when uploading into a community that shares people with the Rhodes archive (Betty Capeluto, Roland Fox appear in both).

---

## User Flows

### Flow 1: Post-Upload Auto-Cluster (automatic)
1. Admin uploads N photos via `/c/fox-family/upload`
2. Face detection runs (existing)
3. **NEW: Auto-clustering runs immediately after ingest completes**
4. Tier 1 matches auto-added as candidates on confirmed identities
5. Tier 2 matches logged as discoveries
6. Admin sees toast: "636 photos processed. 47 faces matched to known people."

### Flow 2: GEDCOM-First Triage Page
1. After upload, admin visits **"New Upload Review"** page (or is redirected there)
2. Page shows:
   - **Top identities by face count** (descending) — "Roland Fox: 38 faces", "Betty Capeluto: 22 faces", "Unknown Person 1: 15 faces"
   - Each identity shows: face thumbnail grid, GEDCOM link status (linked/unlinked), match confidence
   - **Quick GEDCOM link button** inline — search + link without navigating away
3. Admin links top identities to GEDCOM records (5-10 clicks for the most important people)
4. When done linking, admin clicks **"Run Date Estimation"**

### Flow 3: Batch Gemini with GEDCOM Context
1. Admin triggers batch estimation (from triage page or dedicated button)
2. System processes photos that have GEDCOM-linked people:
   - Photos with linked identities get enriched prompts (birth years, family relationships)
   - Photos without links get basic prompts
3. Progress shown via SSE or polling
4. Results stored in `date_labels` / `photo_locations` + Supabase
5. Cost estimate shown before running: "~$X.XX for N photos with Gemini Pro"

---

## Acceptance Criteria

1. [ ] After upload completes, auto-clustering runs without admin intervention
2. [ ] Admin sees a summary of matched faces immediately after upload
3. [ ] Triage page ranks identities by face count (most faces = most impactful to link)
4. [ ] GEDCOM linking is possible inline on the triage page
5. [ ] Batch Gemini estimation runs with GEDCOM context for linked identities
6. [ ] Cost estimate shown before Gemini batch runs
7. [ ] All results persisted to Supabase

---

## Technical Design

### Phase 1: Auto-Cluster After Upload (in `_background_ingest()`)
```python
# After process_directory() succeeds in upload_routes.py:
from core.auto_cluster import run_backfill
result = run_backfill(identities_data, face_data, dry_run=False)
# Log: "Auto-clustered {result.tier1_count} Tier 1, {result.tier2_count} Tier 2"
```

**Risk:** Auto-clustering loads all embeddings + confirmed identities. For 636 new photos with ~1000+ new faces against ~900 existing identities, this is O(N*M) distance computations. With 512-dim embeddings, this should be <30 seconds on Railway.

### Phase 2: Upload Review / GEDCOM Triage Page
- New route: `/admin/upload-review/{job_id}` or `/c/{slug}/upload-review`
- Queries: new INBOX identities from this upload batch
- Groups by identity, counts faces per identity
- Shows GEDCOM link status per identity
- Inline GEDCOM search (reuse existing search component from identity page)

### Phase 3: Batch Gemini with GEDCOM
- Extend `scripts/batch_reanalyze.py` to accept a photo set (e.g., by community or upload batch)
- Pre-flight: count photos, estimate cost, show to admin
- Execute: call Gemini for each photo with enriched context
- Progress: SSE or polling endpoint
- Results: write to `date_labels.json` + Supabase `gemini_api_calls`

---

## Data Model Changes

### upload_batches table (exists, extend)
- Add: `cluster_status` (pending/running/complete)
- Add: `cluster_results_json` (tier1_count, tier2_count, matched_identities)
- Add: `gemini_status` (pending/running/complete)
- Add: `gemini_cost_usd`

### New: upload_review_cache (optional, could be computed)
- `upload_batch_id`, `identity_id`, `face_count`, `gedcom_linked` (boolean)
- Precomputed after clustering for fast triage page rendering

---

## Out of Scope
- Google Drive API integration (TOOLS-006, separate PRD)
- Non-admin upload flows (WORKSPACE-003)
- Cross-community identity merging (GEN-001)
- ML model retraining from new faces

---

## Cost Estimate
- 636 photos × Gemini Pro @ ~$0.04/photo = ~$25
- 636 photos × Gemini Flash @ ~$0.005/photo = ~$3
- Recommendation: Flash for initial pass, Pro for photos with GEDCOM context

---

## Open Questions
1. Should auto-clustering run in the same background thread as ingest, or as a separate job?
2. Should the triage page be community-scoped or global?
3. Should we auto-redirect to triage page after upload, or show a link?
4. For cross-community matches (Betty Capeluto in Rhodes + Fox Family), should the match surface in both communities?
