# UX Improvement Proposals — 2026-02-20

## Executive Summary
The app is in excellent production health. All 35 tested routes work correctly, all auth guards are solid, and all R2 images load. The main fixes applied this session (compare loading indicator, uploaded photo display, resize optimization) address the most impactful UX gap. Remaining improvements are polish-level.

## Critical (should fix ASAP)
| # | Route | Issue | Effort | Impact |
|---|-------|-------|--------|--------|
| 1 | `/compare` | Deploy Session 53 fixes to production | S | High |

## Important (fix in next 2-3 sessions)
| # | Route | Issue | Effort | Impact |
|---|-------|-------|--------|--------|
| 2 | `/timeline`, `/photos` | Lazy loading for 271+ images (will degrade at 500+) | M | Medium |
| 3 | `/person/<nonexistent>` | Return 404 instead of 200 with "not found" message | S | Low |
| 4 | `/activity` | Surface more event types (photo adds, confirmations, uploads) | M | Medium |
| 5 | `/compare` | Show bounding boxes on uploaded photo for multi-face selection | M | Medium |

## Nice to Have (backlog)
| # | Route | Issue | Effort | Impact |
|---|-------|-------|--------|--------|
| 6 | All pages | Add breadcrumb navigation for deeper pages | M | Low |
| 7 | `/compare` | Progressive processing status (detecting -> comparing -> done) | L | Low |
| 8 | `/estimate` | Improve loading indicator message (same pattern as compare) | S | Low |
| 9 | `/timeline` | Add infinite scroll or "Load More" pagination | M | Medium |
| 10 | All | Add service worker for offline-capable photo viewing | L | Low |

## Patterns Observed
- **Storage is solid**: R2 integration works reliably across all pages
- **Auth is bulletproof**: No leakage found in 10 admin route tests
- **Scale concern**: Timeline and photos pages load all 271 images upfront. Current size is manageable but will need lazy loading before 500 photos
- **Activity feed needs enrichment**: Only shows annotation approvals. Could surface photo additions, identity confirmations, compare uploads, etc.

## Recommended Session Plan
1. **Session 54**: Deploy fixes, then Landing Page Refresh (already planned)
2. **Session 55**: Timeline/Photos lazy loading + pagination
3. **Session 56**: PRD-015 Face Alignment (already planned as Session 53)
