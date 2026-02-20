# UX Improvement Proposals — Updated 2026-02-20 (Session 54)

## Executive Summary
The app is in excellent production health. All 35 tested routes work correctly, all auth guards are solid, and all R2 images load. Session 53 fixed compare loading and uploaded photo display. Session 54 completed the 640px ML resize, 404 semantics, and estimate loading indicator. Remaining improvements are tracked in UX_ISSUE_TRACKER.md.

## Critical (DONE)
| # | Route | Issue | Status |
|---|-------|-------|--------|
| 1 | `/compare` | Deploy Session 53+54 fixes | ✅ FIXED |
| 2 | `/compare` | Resize to 640px for ML | ✅ FIXED (S54) |

## Important (fix in next 2-3 sessions)
| # | Route | Issue | Effort | Impact | Planned |
|---|-------|-------|--------|--------|---------|
| 3 | `/timeline`, `/photos` | Lazy loading for 271+ images | M | Medium | S55 |
| 4 | `/activity` | Surface more event types | M | Medium | S55 |
| 5 | `/compare` | Bounding boxes on uploaded photo for multi-face | M | Medium | S56 |
| 6 | `/` | Landing page refresh with live data | M | High | S55 |

## Nice to Have (backlog)
| # | Route | Issue | Effort | Impact |
|---|-------|-------|--------|--------|
| 7 | All pages | Breadcrumb navigation for deeper pages | M | Low |
| 8 | `/compare` | Progressive processing status | L | Low |
| 9 | `/timeline` | Infinite scroll or "Load More" pagination | M | Medium |
| 10 | All | Processing Timeline UI per photo | L | Medium |

## Rejected
| # | Issue | Reason |
|---|-------|--------|
| 11 | Service worker / offline capability | Heritage archive is online-first. Not a PWA use case. |
| 12 | Serverless GPU (Modal) now | Scale mismatch at 271 photos, 3 users. See AD-112. |
| 13 | Remove ML from serving path entirely | Breaks compare. Need intermediate step first. See AD-113. |

## Full Tracking
See [UX_ISSUE_TRACKER.md](UX_ISSUE_TRACKER.md) for comprehensive issue list with dispositions.

## Recommended Session Plan
1. **Session 49B** (OVERDUE): Interactive review with Nolan — birth years, GEDCOM, manual walkthrough
2. **Session 55**: Landing page + lazy loading + activity feed + processing timeline UI
3. **Session 56**: MediaPipe client-side face detection + Docker slimming + upload pipeline
