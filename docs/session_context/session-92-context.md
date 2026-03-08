# Session 92 Context — Ship Everything

**Date**: 2026-03-08
**Predecessor**: Session 91b (docs/assessments/session-91b-assessment.md)
**Goal**: Close ALL outstanding gaps from Sessions 90-91b. Deploy, verify, fix, harden.

## What Just Happened (Pre-Session Fixes)

1. **Session 91b code deployed to Railway** — v0.94.1 live (git push triggered deploy)
2. **HTMX reanalyze button fixed** — dots in photo IDs broke CSS selectors. Sanitized to underscores. Commit: 50552c1
3. **Gemini prompt strengthened (AD-209 continuation)** — GEDCOM immigration events now tagged `[PORT OF ENTRY — transit point, NOT necessarily residence]`. Business name matches explicitly strongest signal. RESIDENCE always overrides immigration.
4. **Leon's Restaurant re-analyzed 3x** — Tampa → San Francisco → "United States (tied to Leon Capeluto's residence)". Still not returning "Asheville" because Leon's own GEDCOM data isn't in the context (only Victor/Victoria's).

## Leon's Restaurant Root Cause (CRITICAL FOR TRACK F)

The GEDCOM context builder (`rhodesli_ml/gedcom_context.py`) only includes GEDCOM data for **people pictured in the photo** (Victor Capelluto, Victoria Capuano Capeluto). It doesn't include GEDCOM data for **Leon Capeluto** (the business owner named on the sign) because Leon isn't pictured.

**Fix needed**: When the prompt's Step 2b identifies a business name match to a family member (e.g., "LEON'S RESTAURANT" → Leon Capeluto), the GEDCOM context builder should also include that person's residential history. This requires:
1. Business name → family member name matching (already in prompt as instruction, but context builder doesn't act on it)
2. Including the matched person's GEDCOM record in the context even if they're not pictured
3. Leon's GEDCOM shows: Residence at 33 Elizabeth St, Asheville, NC (1928-1940)

## API Call Logging Gaps (CRITICAL FOR TRACK G)

Current `log_gemini_call()` logs to Supabase `gemini_api_calls` table:
- ✅ photo_id, model_used, call_type, tokens, cost, latency, status, error
- ✅ gemini_config (enrichment level, prompt version, temperature, trigger)
- ✅ response_summary (decade, year, confidence, location)
- ❌ **Full prompt text** — NOT logged (only token count estimate)
- ❌ **Full response JSON** — NOT logged (only summary dict)
- ❌ **GEDCOM context string** — NOT logged (can't see what biographical data was sent)

Without these, you cannot debug WHY Gemini returned a wrong answer.

## Complete Outstanding Items (All Sessions 90-91b)

### Track A: Deploy + Verify + Env Vars (S — 30 min)
- [A1] Deploy to Railway ← DONE (pre-session)
- [A2] Set SENTRY_DSN on Railway
- [A3] Set POSTHOG_API_KEY on Railway
- [A4] Set RESEND_API_KEY on Railway (enables OPS-001 custom SMTP + PRD-028 email notifications)
- [A5] Browser verify: landing, photos, discoveries, notifications, events, person pages
- [A6] Verify confirm→notification E2E (confirm identity → notification row → bell badge)

### Track B: Supabase Tables + Data (S — 15 min)
- [B1] Execute SQL: communities table + seed Rhodes community
- [B2] Execute SQL: life_events table + seed 5 events via seed_life_events.py
- [B3] Execute SQL: notifications table
- [B4] Execute SQL: global_person_links table
- [B5] Test DATA_SOURCE=postgres on Railway (flip flag, verify reads, flip back)

### Track C: Test Hardening (M — 2 hr)
- [C1] Fix e2e test_admin_review_queue_sorted (selector/routing issue after extraction)
- [C2] Fix 7 flaky xfail tests (BACKLOG-FLAKY-001) — route module loading order
- [C3] Test speed optimization (PERF-001) — 43s → <30s target
- [C4] 1 xpassed test needs investigation (xfail now passes)
- [C5] CI/CD pipeline foundation (OPS-002) — GitHub Actions for make test-fast on PR

### Track D: UX Bug Fixes (M — 2 hr)
- [D1] UX-042: /identify/{id} shareable page missing link to source photo (P1)
- [D2] UX-045-046: Compare upload — no loading indicator, no auto-scroll (P1)
- [D3] UX-054-055: Estimate upload — no loading indicator, no auto-scroll (P1)
- [D4] UX-080: 404 page unstyled (P1)
- [D5] UX-081: About page missing navbar (P1)
- [D6] UX-092: Birth year Save Edit race condition (P1)
- [D7] UX-106: Inconsistent contribution CTA phrasing (P2)
- [D8] UX-107: "Identified" badge no tooltip (P2)
- [D9] UX-114: Collection dropdown focus handling fragile (P2)
- [D10] Double admin bar on /events page (cosmetic — from Session 91)

### Track E: Growth Loop — Email Notifications + Share (M — 2 hr)
- [E1] PRD-028 P1: Email notifications (code exists, needs RESEND_API_KEY wired)
- [E2] Verify share flow works E2E (share button → OG card → click → identify)
- [E3] Help Identify mode verification in production
- [E4] Timeline integration for life events (events page built, timeline markers not wired)

### Track F: Gemini + ML Fixes (L — 3 hr)
- [F1] Leon's Restaurant → Asheville fix (GEDCOM context builder needs business-name-owner lookup)
- [F2] Log full prompt text to gemini_api_calls (not just token count)
- [F3] Log full response JSON to gemini_api_calls (not just summary)
- [F4] Log GEDCOM context string to gemini_api_calls
- [F5] ML-053: Multi-pass Gemini — re-label low-confidence photos
- [F6] Active learning pipeline foundation

### Track G: Product Features (L — 4 hr)
- [G1] PRODUCT-002: Face Compare Tier 2 — shared backend architecture (AD-117)
- [G2] PRODUCT-003: NL Archive Query MVP — LangChain (AD-118)
- [G3] PRODUCT-004: Historical Photo Date Estimator standalone
- [G4] Second collection onboarding (Fox family photos)
- [G5] ML service extraction (separate FastAPI service)

### Track H: Architecture + Debt (M — 2 hr)
- [H1] pgvector embeddings migration evaluation
- [H2] Further main.py extraction if needed (currently 9.3K lines — good)
- [H3] Frontend framework migration evaluation (HD-022 — NOT YET TRIGGERED)

## Parallelization Plan

### Round 1 (Independent — 6 parallel worktrees)
| Track | Worktree | Files Touched | Dependencies |
|-------|----------|---------------|--------------|
| A: Deploy+Verify | main (browser only) | No code changes | None |
| B: Supabase Tables | main (SQL only) | No code changes | None |
| C: Test Hardening | session-92/tests | tests/, conftest | None |
| D: UX Bug Fixes | session-92/ux-fixes | app/*_routes.py, app/main.py | None |
| F: Gemini+ML | session-92/gemini-ml | rhodesli_ml/, app/estimate_routes.py, app/supabase_data.py | None |
| G: Product Features | session-92/products | New files mostly | None |

### Round 2 (After Round 1 merges)
| Track | Dependencies |
|-------|-------------|
| E: Growth Loop | Needs A (env vars) + B (tables) |
| H: Architecture | Needs all Round 1 |

## Merge Order
1. A (no code changes, just verification)
2. B (SQL execution, no code changes)
3. C (tests only — no app code conflicts)
4. D (UX fixes — app routes)
5. F (ML code — rhodesli_ml/)
6. G (new product features)
7. E (growth loop — depends on A+B)
8. H (architecture evaluation — docs only)

## Success Criteria
- [ ] All 6 Options from status review addressed
- [ ] Leon's Restaurant shows Asheville, NC
- [ ] Full Gemini API call logging (prompt + response + GEDCOM context)
- [ ] All P1 UX bugs fixed
- [ ] Test speed <30s
- [ ] No flaky tests
- [ ] Email notifications working
- [ ] Confirm→notification E2E verified
- [ ] SENTRY_DSN + POSTHOG_API_KEY + RESEND_API_KEY set
- [ ] DATA_SOURCE=postgres tested on Railway
