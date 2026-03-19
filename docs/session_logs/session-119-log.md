# Session 119 Log — ML Service End-to-End Verification

**Started:** 2026-03-18
**Mode:** Interactive
**Prompt:** docs/prompts/session-119-prompt.md

## Phase Checklist
- [x] Phase 0: Orient + Health Check
- [x] Phase 1: Pre-Warm ML Service
- [x] Phase 2: Upload Test Photo
- [ ] Phase 3: Embedding Comparison
- [ ] Phase 4: Performance & Monitoring
- [ ] Phase 5: Harness Outputs

## Phase 0: Orient + Health Check

**Baseline tests:** 2880 passed, 1 flaky (test_not_available_when_not_configured — passes alone, ordering issue in parallel), 30.55s

**ML Service Health** (`/api/admin/ml-health`):
```json
{
  "status": "connected",
  "ml_service": {
    "status": "ok",
    "version": "0.1.0",
    "models_loaded": false,
    "execution_environment": "railway_ml_service",
    "uptime_seconds": 610.3
  }
}
```

- ML service recently restarted (only 10 min uptime, not 12-24h from Session 118)
- Model not loaded yet (lazy-loads on first detection request)
- Web app → ML service connectivity confirmed

**Web app health:** Landing page served, admin auth working (ML health endpoint accessible via browser).

## Phase 1: Pre-Warm ML Service

**Approach chosen:** Option B — added `/api/v1/warm` endpoint + `POST /api/admin/ml-warm` admin route.

**Bug found and fixed:** `asyncio.run()` destroys event loop, invalidating singleton httpx.AsyncClient. Consecutive admin API calls failed with "Event loop is closed". Fix: create fresh MLServiceClient per `asyncio.run()` call in admin routes.

**Also:** Increased ML client timeout from 60s → 180s.

**Warm results:**
- Model: buffalo_l (detection + recognition)
- Load time: 17.33s (first warm after deploy)
- `models_loaded: true` confirmed on subsequent health check
- Consecutive calls work (event loop fix verified)

**Commits:**
- `c5df461` — warm endpoint + timeout increase
- `20173e4` — admin ml-warm route
- `d9c3be6` — event loop closed bug fix
- `dbb060e` — fresh client per asyncio.run()

## Phase 2: Upload Test Photo

**Photo:** Terry Yanishefsky Collection family photo
- "22-Sol standing 2nd from right with parents to the left and rest of f..."
- Source: Personal Photos (Google Photos link)
- Community: Fox Family Archive
- Size: 79.0 KB
- Large group photo with ~14 people in two rows

**Context:** Email from tyanish@aol.com (Oct 4, 2019) with detailed caption:
- Back row L-R: aunt Mary, husband Sam Barnett, aunt Ruth, grandmother, grandfather, father Solomon, uncle Joe
- Front row L-R: cousins Sidney and Beatrice in front of parents, aunt Fannie and uncle Irving, uncle Bernard and aunt Jenny holding cousin Milton

**Results:**
- Upload job: `c4bf192f`
- **14 faces extracted, 14 added to Inbox** — confirmed in UI
- R2 upload: 15 files (1 photo + 14 crops)
- Auto-cluster: **118 cross-batch matches** found
- ML service log: `POST /api/v1/detect-and-embed → 200 OK`
- Community tagged to Fox Family Archive

**This is the FIRST real production upload through the ML service.**

**Performance concerns during upload:**
- Upload page took >1 min to load initially
- GEDCOM tree query timed out (Supabase statement timeout)
- Audit log spam: ~15 "Could not find 'actor' column" warnings
- PostHog capture error: wrong argument count

## Interactive Feedback (documented in docs/feedback/session-119-feedback.md)

- FB-001 (P1): Merge needs search/type-ahead (UX-131)
- FB-002 (P1): Approvals not community-scoped (UX-132)
- FB-003 (P2): Similar Identities need community tags everywhere (UX-133)
- FB-004 (P2): Skip-after-merge doesn't acknowledge contributor (UX-134)
- FB-005 (P2): Upload form needs annotation/notes field (UX-135)
