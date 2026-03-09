# Session 96b Context — Charlie Fox Collection Ingest + Post-Upload Intelligence

**Predecessor:** [Session 96 context](session-96-context.md) (community data scoping hotfix + planning)
**Date:** 2026-03-09
**Type:** Data ingest + feature build
**PRD:** [PRD-037: Post-Upload Intelligence Pipeline](../prds/037_post_upload_intelligence.md)
**Prompt:** [Session 96b prompt](../prompts/session-96b-prompt.md)

---

## What This Session Does
1. Ingest 636 Charlie Fox photos via local pipeline into Fox Family community
2. Auto-cluster new faces against confirmed identities (including Rhodes)
3. Upload to R2 and deploy
4. Build PRD-037 Phase 1: auto-cluster after every upload
5. Build PRD-037 Phase 2: GEDCOM triage page for post-upload identity linking

## Cross-Community Matching: How It Works

### The Scenario
Betty Capeluto and Roland Fox are confirmed identities in the **Rhodes** archive with existing face embeddings. They appear prominently in the Charlie Fox collection being uploaded to the **Fox Family** archive.

### What Happens During Clustering
1. `cluster_new_faces.py` / `core/auto_cluster.py` compares every new face against ALL confirmed identities globally (not scoped to community)
2. Matches against Betty/Roland will produce Tier 1 (<0.85) or Tier 2 (0.85-1.30) results
3. **Tier 1**: Face ID added to the Rhodes identity's `candidate_ids` with `provenance="model"`. The face joins the existing Betty/Roland identity — no new Fox Family identity created.
4. **Tier 2**: Logged in `discovery_log.json` as suggestion for admin review
5. **No match** (>1.30): Face stays as standalone INBOX identity

### UX Implications
- Fox Family photo pages will show faces that link to Rhodes identity pages (e.g., `/person/{betty_id}`)
- Betty's person page will show faces from BOTH Rhodes and Fox Family collections
- Fox Family sidebar "People" count only reflects identities in `identity_communities` for fox-family — shared people like Betty won't appear there unless explicitly cross-tagged
- Discovery suggestions appear globally, not scoped to Fox Family triage

### Known Gaps (watch for these)
- **No cross-community identity tagging** — `identity_communities` table supports it but no UI/pipeline creates multi-community memberships. After clustering, Betty is still "Rhodes only" even though she has Fox Family faces. See AD-213.
- **No "shared person" indicator** — Nothing tells Fox Family users that Betty also appears in Rhodes
- **Discovery routing** — Tier 2 suggestions surface on Rhodes triage, not Fox Family. Admin must check both.
- **Person pages not community-scoped** — `/person/{id}` shows all faces. Correct behavior (one person globally) but may confuse users.

## GEDCOM-First Workflow (Nolan Insight)

### The Optimal Post-Upload Sequence
```
Upload → Face Detect → Auto-Cluster → Surface Top Identities by Face Count
    → Admin Links GEDCOM for Top People → Batch Gemini with Enriched Context
```

### Why GEDCOM Before Gemini
| Without GEDCOM | With GEDCOM |
|----------------|-------------|
| "c. 1950s" (clothing guess) | "1952-1956, high confidence" |
| No birth year math | Born 1925 + apparent age 27 = ~1952 |
| No family context | "With husband (married 1948) and child (born 1950)" |
| ~$0.04 wasted on low-quality estimate | ~$0.04 produces actionable date range |

### Why This Should Be Automatic (PRD-037)
- Works for KNOWN people (Betty, Roland) — cluster matches them, admin links their GEDCOM, Gemini uses it
- Works for UNKNOWN people — admin identifies them via faces, links GEDCOM, Gemini benefits retroactively on re-analysis
- Scales to any community — every upload follows the same flow
- Cost efficiency — GEDCOM linking is free (admin time only), Gemini costs money. Do the free thing first.

## Current Pipeline (Pre-PRD-037)

| Step | Automated? | Code Location |
|------|-----------|---------------|
| Face detection | Yes (in upload thread) | `core/ingest_inbox.py:process_directory()` |
| Embedding storage | Yes | `core/ingest_inbox.py:atomic_append_embeddings()` |
| Photo registration | Yes | `core/ingest_inbox.py` → `photo_index.json` |
| INBOX identity creation | Yes | `core/ingest_inbox.py` |
| Face crop generation | Yes | `core/ingest_inbox.py` |
| R2 upload | Yes (in upload thread) | `app/upload_routes.py:_background_ingest()` |
| Community tagging | Yes (non-Rhodes) | `app/supabase_data.py:add_photo_to_community()` |
| Cache invalidation | Yes | `app/main.py:_invalidate_all_caches()` |
| **Auto-clustering** | **NO — manual script** | `scripts/cluster_new_faces.py` → `core/auto_cluster.py` |
| **GEDCOM linking** | **NO — manual per-identity** | `app/identity_routes.py` search panel |
| **Gemini estimation** | **NO — manual per-photo** | `app/estimate_routes.py` or `scripts/batch_reanalyze.py` |
| **Identity confirmation** | **NO — manual (by design)** | Gatekeeper pattern, AD-179 |

### Clustering Thresholds (AD-179)
- Tier 1: distance < 0.85 → auto-add as `candidate_id` (reversible, admin can reject)
- Tier 2: distance 0.85-1.30 → Discovery suggestion (admin review)
- No match: distance >= 1.30
- Calibrated against 982 same-person pairs (mean=1.01, std=0.19), AUC=0.9577

## Algorithmic Decisions

### AD-213: Cross-Community Identity Sharing (Session 96b)
- **Decision**: When clustering matches a Fox Family face to a Rhodes identity, the face joins the Rhodes identity. No identity duplication.
- **Rationale**: One person = one identity globally. Betty Capeluto is Betty regardless of which archive the photo came from.
- **Gap**: No automatic cross-tagging in `identity_communities`. After clustering, Betty has Fox Family faces but isn't listed as a Fox Family identity. This means she won't appear in Fox Family's "People" sidebar count or people page.
- **Future**: Need a mechanism to auto-tag identities in communities when they gain faces from that community's photos. Could be part of the clustering pipeline.

### AD-214: GEDCOM-First Estimation Workflow (Session 96b)
- **Decision**: Always link GEDCOM before running Gemini estimation. Surface top identities by face count post-upload to prioritize linking.
- **Rationale**: GEDCOM context dramatically improves Gemini accuracy (vague era guess → specific year range). Linking is free (admin time), Gemini costs money. Do free enrichment first.
- **Implementation**: PRD-037 Phases 2-3. Phase 2 builds the triage page, Phase 3 builds batch Gemini with cost estimate.
- **Applies to**: Every upload, not just Charlie Fox. This is a platform-level workflow improvement.

## Risks and Watchpoints for 96b

### Ingest Risks
- **Memory**: ~636 photos × InsightFace = high RAM. Monitor. If OOM, batch in groups of 100.
- **Clustering time**: ~1000 new faces × ~900 confirmed = ~900K distance computations. Should be <30s but monitor.
- **R2 upload**: ~3.2GB total. Use parallel uploads if possible.
- **File format surprises**: "All JPGs" may include corrupt files, wrong extensions, or very large images.

### UX Risks After Deploy
- Fox Family photos page will show 636+ photos but "People" count may be 0 (if cross-community tagging gap isn't addressed)
- Betty/Roland's person pages will suddenly have many more faces — the UI should handle large face grids gracefully
- No Gemini date estimates yet — photos will show no date badges until future session

### Strategic Risk
- This is the first real multi-community upload. If the experience is clunky, it informs what self-service onboarding (TOOLS-006) needs to fix.
- Betty/Roland cross-community matching is the proof point that Rhodesli's global identity system works.

## Post-96b Planning

### Immediate (admin tasks, no code needed)
- Admin links top Fox Family identities to GEDCOM via identity detail pages
- Admin confirms/rejects Tier 1 auto-clustered faces

### Next Code Session
- PRD-037 Phase 3: Batch Gemini UI with cost estimate + enriched GEDCOM context
- Cross-community identity tagging (AD-213 gap fix)
- "Shared person" indicator on identity cards
- CI/CD fix (GitHub Actions venv setup)
- About page community content (COMMUNITY-001)

## Breadcrumbs
- PRD: `docs/prds/037_post_upload_intelligence.md`
- Prompt: `docs/prompts/session-96b-prompt.md`
- Predecessor context: `docs/session_context/session-96-context.md`
- AD-213: Cross-community identity sharing → `docs/ml/ALGORITHMIC_DECISIONS.md`
- AD-214: GEDCOM-first estimation workflow → `docs/ml/ALGORITHMIC_DECISIONS.md`
- BACKLOG: COMMUNITY-001 (about page), UPLOAD-001 (bulk import)
- ROADMAP: Session 96b planned under Session 96 family
