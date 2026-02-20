# UX Issue Tracker

**Last updated:** 2026-02-20 (Session 54)

## Issue Dispositions
- ✅ FIXED — implemented and verified
- 🔜 PLANNED — scheduled for a specific session
- 📋 BACKLOG — acknowledged, not yet scheduled
- ⏭️ DEFERRED — intentionally postponed with reasoning
- ❌ REJECTED — decided not to do, with reasoning

---

## Issues from Session 53 Production Audit

| ID | Issue | Source | Disposition | Session | Notes |
|----|-------|--------|------------|---------|-------|
| UX-001 | Compare takes 65s with no feedback | PROD_SMOKE | ✅ FIXED (S53) | 53 | Loading indicator + spinner added |
| UX-002 | Uploaded photo not shown in results | PROD_SMOKE | ✅ FIXED (S53) | 53 | Photo preview above results |
| UX-003 | Resize only to 1024px (should be 640px) | FIX_LOG #4 | ✅ FIXED (S54) | 54 | Changed to 640px for ML path, original to R2 |
| UX-004 | buffalo_sc hybrid detection | Architecture | ✅ FIXED (S54B) | 54B | Hybrid approach: det_500m + w600k_r50. See AD-114. |
| UX-005 | Non-existent person/photo returns 200 not 404 | PROD_SMOKE minor #1 | ✅ FIXED (S54) | 54 | HTTP 404 semantics |
| UX-006 | Duplicate activity entries | PROD_SMOKE minor #2 | 📋 BACKLOG | — | Data investigation needed |
| UX-007 | Timeline/photos loads all 271 images | UX_FINDINGS | 🔜 PLANNED | 55 | Lazy loading before 500 photos |
| UX-008 | Activity feed only shows 2 annotation events | UX_FINDINGS | 🔜 PLANNED | 55 | Enrich with more event types |
| UX-009 | No breadcrumb navigation on deep pages | PROPOSALS #6 | 📋 BACKLOG | — | Nice to have, not critical |
| UX-010 | No infinite scroll on timeline | PROPOSALS #9 | 📋 BACKLOG | — | Needed at 500+ photos |
| UX-011 | No service worker / offline capability | PROPOSALS #10 | ❌ REJECTED | — | Heritage archive is online-first. Not a PWA use case. |
| UX-012 | Bounding boxes on uploaded photo for multi-face | PROPOSALS #5 | 🔜 PLANNED | 56 | Part of client-side face detection work |
| UX-013 | Progressive processing status | PROPOSALS #7 | 📋 BACKLOG | — | Spinner + messaging is sufficient for now |
| UX-014 | Estimate loading indicator message | PROPOSALS #8 | ✅ FIXED (S54) | 54 | Verified HTMX indicator applies |
| UX-015 | "Try Another Photo" flow unclear | User report | ✅ FIXED (S44) | 44 | Button exists in compare results (Session 44 CTAs) |

## Issues from Session 53 UX Findings

| ID | Issue | Source | Disposition | Session | Notes |
|----|-------|--------|------------|---------|-------|
| UX-016 | HTMX indicator CSS only had descendant selector | FIX_LOG #1 | ✅ FIXED (S53) | 53 | Dual-selector fix (HD-009) |
| UX-017 | Compare loading message said "a few seconds" | FIX_LOG #2 | ✅ FIXED (S53) | 53 | Updated to "up to a minute for group photos" |
| UX-018 | Timeline is largest page (443KB, 271 imgs) | UX_FINDINGS | 🔜 PLANNED | 55 | Same as UX-007 |
| UX-019 | Estimate page — same HTMX CSS fix applies | UX_FINDINGS | ✅ FIXED (S53) | 53 | CSS fix is global |

## Issues from Architecture Review (Session 54)

| ID | Issue | Source | Disposition | Session | Notes |
|----|-------|--------|------------|---------|-------|
| UX-020 | Upload not running through ML pipeline | Architecture | ⏭️ DEFERRED | 56+ | Requires full pipeline wiring. AD-110. |
| UX-021 | No face lifecycle states visible to user | Expert review | ⏭️ DEFERRED | Phase F | Requires Postgres (AD-111) |
| UX-022 | No processing timeline UI | Expert review | 📋 BACKLOG | — | Trust restoration. See AD-111. |
| UX-023 | No confidence scores on identifications | Expert review | 📋 BACKLOG | — | Genealogy-specific differentiation |
| UX-024 | No community verification / voting | Expert review | 📋 BACKLOG | — | "Wikipedia for historical faces" |
| UX-025 | Docker image 3-4GB (was 200MB) | Architecture | 🔜 PLANNED | 56+ | Remove InsightFace after client-side detection |

## Issues from Earlier Sessions

| ID | Issue | Source | Disposition | Session | Notes |
|----|-------|--------|------------|---------|-------|
| UX-026 | Face crops not clickable on share page | Session 46 | 📋 BACKLOG | — | Discovery path improvement |
| UX-027 | No photo gallery/carousel in collections | Session planning | 📋 BACKLOG | — | Arrow key navigation |
| UX-028 | OPS-001 custom SMTP for branded email | ROADMAP | 📋 BACKLOG | — | Low priority |
| UX-029 | Admin/Public UX confusion | Session 46/50 | 📋 BACKLOG | — | Progressive admin enhancement pattern |
| UX-030 | Landing page needs refresh | ROADMAP | 🔜 PLANNED | 55 | Live-data entry points, mobile-first |
| UX-031 | Session 49B interactive review overdue | ROADMAP | 🔜 PLANNED | 49B | Requires Nolan — OVERDUE |

## Issues from Community Feedback (Session 49C)

| ID | Issue | Source | Disposition | Session | Notes |
|----|-------|--------|------------|---------|-------|
| UX-032 | Photo 404 for community/inbox photos | Session 49C | ✅ FIXED (S49C) | 49C | Alias resolution in _build_caches() |
| UX-033 | Compare upload silent failure | Session 49C | ✅ FIXED (S49C) | 49C | onchange auto-submit |
| UX-034 | Version v0.0.0 in admin footer | Session 49C | ✅ FIXED (S49C) | 49C | CHANGELOG.md in Docker image |
| UX-035 | Collection name truncation | Session 49C | ✅ FIXED (S49C) | 49C | 6 remaining locations |

---

## Summary

| Disposition | Count |
|-------------|-------|
| ✅ FIXED | 15 |
| 🔜 PLANNED | 7 |
| 📋 BACKLOG | 10 |
| ⏭️ DEFERRED | 2 |
| ❌ REJECTED | 1 |
| **Total** | **35** |
