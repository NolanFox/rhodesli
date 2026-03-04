# UX Issue Tracker

**Last updated:** 2026-02-21 (Session 49D — 12 fixes: 6 P0 + 6 P1)

## Issue Dispositions
- ✅ FIXED — implemented and verified
- 🔜 PLANNED — scheduled for a specific session
- 📋 BACKLOG — acknowledged, not yet scheduled
- ⏭️ DEFERRED — intentionally postponed with reasoning
- ❌ REJECTED — decided not to do, with reasoning

---

## Issues from Sessions 53-54 (Pre-49B)

| ID | Issue | Disposition | Notes |
|----|-------|------------|-------|
| UX-001 | Compare takes 65s with no feedback | ✅ FIXED (S53) | Loading indicator added |
| UX-002 | Uploaded photo not shown in results | ✅ FIXED (S53) | Photo preview above results |
| UX-003 | Resize only to 1024px (should be 640px) | ✅ FIXED (S54) | 640px for ML path |
| UX-004 | buffalo_sc hybrid detection | ✅ FIXED (S54B) | AD-114 |
| UX-005 | Non-existent person/photo returns 200 | ✅ FIXED (S54) | HTTP 404 semantics |
| UX-006 | Duplicate activity entries | 📋 BACKLOG | Data investigation needed |
| UX-007 | Timeline/photos loads all 271 images | 🔜 PLANNED (S55) | Lazy loading |
| UX-008 | Activity feed only shows 2 events | 🔜 PLANNED (S55) | More event types |
| UX-009 | No breadcrumb navigation | 📋 BACKLOG | Nice to have |
| UX-010 | No infinite scroll on timeline | 📋 BACKLOG | Needed at 500+ photos |
| UX-011 | No service worker / offline | ❌ REJECTED | Online-first |
| UX-012 | No bounding boxes on uploaded photo | 🔜 PLANNED (S56) | Client-side face detection |
| UX-013 | Progressive processing status | 📋 BACKLOG | Spinner sufficient for now |
| UX-014 | Estimate loading indicator | ✅ FIXED (S54) | HTMX indicator |
| UX-015 | "Try Another Photo" unclear | ✅ FIXED (S44) | CTAs added |
| UX-016 | HTMX indicator CSS selector | ✅ FIXED (S53) | HD-009 |
| UX-017 | Compare loading "a few seconds" | ✅ FIXED (S53) | Updated messaging |
| UX-018 | Timeline largest page (443KB) | 🔜 PLANNED (S55) | Same as UX-007 |
| UX-019 | Estimate HTMX CSS fix | ✅ FIXED (S53) | Global fix |
| UX-020 | Upload not in ML pipeline | ⏭️ DEFERRED | AD-110 |
| UX-021 | No face lifecycle states | ⏭️ DEFERRED | AD-111, needs Postgres |
| UX-022 | No processing timeline UI | 📋 BACKLOG | AD-111 |
| UX-023 | No confidence scores on IDs | 📋 BACKLOG | Genealogy differentiation |
| UX-024 | No community verification/voting | 📋 BACKLOG | Future |
| UX-025 | Docker image 3-4GB | 🔜 PLANNED (S56+) | Remove InsightFace |
| UX-026 | Face crops not clickable on share | 📋 BACKLOG | |
| UX-027 | No photo gallery in collections | 📋 BACKLOG | |
| UX-028 | OPS-001 custom SMTP | 📋 BACKLOG | Low priority |
| UX-029 | Admin/Public UX confusion | 📋 BACKLOG | |
| UX-030 | Landing page needs refresh | 🔜 PLANNED (S55) | |
| UX-031 | Session 49B interactive review | ✅ DONE (S49B) | This session |
| UX-032 | Photo 404 for inbox photos | ✅ FIXED (S49C) | Alias resolution |
| UX-033 | Compare upload silent failure | ✅ FIXED (S49C) | onchange auto-submit |
| UX-034 | Version v0.0.0 in footer | ✅ FIXED (S49C) | CHANGELOG in Docker |
| UX-035 | Collection name truncation | ✅ FIXED (S49C) | 6 locations fixed |

---

## Issues from Session 49B — Section 3: Identity Tagging Workflow

| ID | P | Issue | Disposition | Notes |
|----|---|-------|------------|-------|
| UX-036 | P0 | Merge button 404 — `&` instead of `?` in focus mode URL | ✅ FIXED (S49D) | Already fixed in S49B commit 4693203. Regression tests added. |
| UX-037 | P1 | Merge direction unintuitive — neighbor survives, not target | ✅ FIXED (S86) | hx_confirm on all merge buttons with both names. |
| UX-038 | P1 | Operations on merged-away identities return 200 silently | 📋 BACKLOG | Should error or redirect to survivor. |
| UX-039 | P1 | No admin controls on /person/ page | ✅ FIXED (S86) | Inline rename, confirm/skip/reject, merge search. |
| UX-040 | P1 | Identity tagging is 5+ steps with no batching | 📋 BACKLOG | Need "Identify This Person" single form. |
| UX-041 | P1 | /photo/ → identity system disconnect | 📋 BACKLOG | Clicking unidentified face has no path to name it. |
| UX-042 | P1 | /identify/{id} shareable page has no link to source photo | ✅ FIXED (S49D) | Added "See full photo →" links on photo cards. |
| UX-043 | P2 | Community identification workflow gap | 📋 BACKLOG | No "community said this is X" quick-tag. |

## Issues from Session 49B — Item 5: Compare Upload

| ID | P | Issue | Disposition | Notes |
|----|---|-------|------------|-------|
| UX-044 | P0 | Compare upload not in pending queue — "saved to archive" misleading | ✅ FIXED (S49D) | Messaging updated per AD-110: "analyzed for matching but not stored." |
| UX-045 | P1 | No loading indicator during compare upload processing | 📋 BACKLOG | Page appears to hang. Existing indicator not visible. |
| UX-046 | P1 | No auto-scroll to compare results | 📋 BACKLOG | Results below fold, user thinks upload failed. |
| UX-047 | P1 | Face selector is blind — "Face 1/2/3" with no visual | 📋 BACKLOG | No bounding boxes on uploaded photo. See UX-012. |
| UX-048 | P1 | Two-photo compare not supported | 📋 BACKLOG | Core use case. AD-117 tiers. Architecture ready. |
| UX-049 | P2 | Upload area doesn't reset after success | 📋 BACKLOG | |
| UX-050 | P2 | Contradictory confidence tiers vs card labels | 📋 BACKLOG | "Strong Matches" header vs "Possible match" card. |
| UX-051 | P2 | Broken face crop thumbnails (faces 17/18/20) | 📋 BACKLOG | Crop generation failed. |

## Issues from Session 49B — Item 6: Estimate Page

| ID | P | Issue | Disposition | Notes |
|----|---|-------|------------|-------|
| UX-052 | P0 | Estimate upload not in pending queue | ✅ FIXED (S49D) | Same fix as UX-044. |
| UX-053 | P1 | No uploaded photo preview in estimate results | 📋 BACKLOG | Text-only results. Archive flow shows photo. |
| UX-054 | P1 | No loading indicator visible during estimate upload | 📋 BACKLOG | #estimate-upload-spinner CSS issue. |
| UX-055 | P1 | No auto-scroll to estimate results | 📋 BACKLOG | Same pattern as UX-046. |
| UX-056 | P1 | No CTAs after estimate upload (dead end) | 📋 BACKLOG | Archive flow has Share/View/Try Another. |
| UX-057 | P1 | Upload area doesn't reset after estimate | 📋 BACKLOG | |
| UX-058 | P1 | Two completely different result formats (upload vs archive) | 📋 BACKLOG | Should be unified layout. |
| UX-059 | P1 | No face-by-face breakdown for uploads | 📋 BACKLOG | Upload says "17 faces" but shows nothing per-face. |
| UX-060 | P2 | Confidence disagrees between upload and archive flows | 📋 BACKLOG | Gemini vs internal pipeline. |
| UX-061 | P2 | No face bounding boxes on estimate photo | 📋 BACKLOG | |
| UX-062 | P2 | Results sandwiched between upload and gallery | 📋 BACKLOG | Gallery should collapse. |
| UX-063 | P2 | "Select a Photo" grid lacks context | 📋 BACKLOG | No title, collection, identified count. |
| UX-064 | P2 | "+/- 10 years" too vague for low confidence | 📋 BACKLOG | Should say "identify more people". |
| UX-065 | P2 | "How we estimated this" empty for archive flow | 📋 BACKLOG | |
| UX-066 | P2 | Upload processing ~30 seconds with no feedback | 📋 BACKLOG | SSE/streaming (AD-121). |
| UX-067 | P3 | "Share Estimate" button unclear what it shares | 📋 BACKLOG | |
| UX-068 | P3 | No visual evidence clue annotations | 📋 BACKLOG | Callouts on photo for fashion/style clues. |
| UX-069 | P3 | No timeline visualization for date estimate | 📋 BACKLOG | Historical context for family photos. |

## Issues from Session 49B — Item 7: Quick-Identify / Name These Faces

| ID | P | Issue | Disposition | Notes |
|----|---|-------|------------|-------|
| UX-070 | P0 | All HTMX actions fail with targetError on /photo/ pages | ✅ FIXED (S49D) | Added id="photo-modal-content" to /photo/ page container. |
| UX-071 | P0 | Can't exit Name These Faces mode (Done button broken too) | ✅ FIXED (S49D) | Same root cause as UX-070. |
| UX-072 | P0 | Root cause: app/main.py:17353 hardcodes modal target | ✅ FIXED (S49D) | Target now exists in both lightbox and /photo/ page. |
| UX-073 | P1 | Enter key doesn't submit new name | 📋 BACKLOG | Must mouse-click Create button. |
| UX-074 | P1 | "Create new identity" hidden below fold in dropdown | 📋 BACKLOG | Should be at top or triggered by Enter. |
| UX-075 | P1 | No Skip button for unknown faces in sequential mode | 📋 BACKLOG | Can't skip faces you don't know. |
| UX-076 | P2 | Autocomplete matches any word — noisy for shared surnames | 📋 BACKLOG | Many Capeluto/Franco matches. |
| UX-077 | P2 | Two photos rendered in tagging mode (original + duplicate) | 📋 BACKLOG | Confusing layout. |
| UX-078 | P2 | Create button name truncated for long Sephardic names | 📋 BACKLOG | |
| UX-079 | P2 | No visual highlight on active face during tagging | 📋 BACKLOG | Unclear which face is being tagged. |

## Issues from Session 49B — Item 8: Visual Walkthrough

| ID | P | Issue | Disposition | Notes |
|----|---|-------|------------|-------|
| UX-080 | P1 | 404 page unstyled — no Tailwind, no navbar, dark-on-dark text | ✅ FIXED (S49D) | Added Tailwind CDN script to 404 handler. |
| UX-081 | P1 | About page missing navbar | ✅ FIXED (S49D) | Replaced "Back to Archive" with full navbar. |
| UX-082 | P2 | "Explore More Photos" orange CTA in navbar | 📋 BACKLOG | Inconsistent, looks like an ad. |
| UX-083 | P2 | No search on People page | 📋 BACKLOG | 54 people, no filter/search. |
| UX-084 | P2 | No birth/death years on People grid | 📋 BACKLOG | Data available, not displayed. |
| UX-085 | P2 | Face crop quality varies wildly | 📋 BACKLOG | Some very blurry/dark. |
| UX-086 | P2 | Tree names truncated at ~12 chars | 📋 BACKLOG | "Big Leon Cape..." |
| UX-087 | P2 | Tree very wide, requires horizontal scroll | 📋 BACKLOG | Large empty space. Needs zoom. |
| UX-088 | P2 | Face overlay name labels truncated on photos | 📋 BACKLOG | "Albert...", "Morri..." |
| UX-089 | P2 | Person page shows "Died: Unknown", "From: Unknown" | 📋 BACKLOG | Should omit or show "—". |
| UX-090 | P2 | Ancestry link not displayed on person page | 📋 BACKLOG | Data exists, UI doesn't render it. |
| UX-091 | P2 | Face count badge format inconsistent | 📋 BACKLOG | "1/1" vs "1 face" vs "6 faces". |

## Issues from Session 49B — Birth Year Review (Section 1)

| ID | P | Issue | Disposition | Notes |
|----|---|-------|------------|-------|
| UX-092 | P1 | Save Edit doesn't persist typed value (race condition) | ✅ FIXED (S49D) | Accept button moved inside form — both buttons use current input value. |
| UX-093 | P1 | No undo after Accept/Save on birth year review | 📋 BACKLOG | Violates reversibility. Need Confirmed queue. |
| UX-094 | P2 | Person name not clickable on review page | 📋 BACKLOG | Should link to /person/{id}. |
| UX-095 | P2 | Evidence lines don't link to specific photos | 📋 BACKLOG | |
| UX-096 | P2 | No Gemini explanation accessible from review | 📋 BACKLOG | |
| UX-097 | P2 | No source attribution (internal vs Gemini) | 📋 BACKLOG | |
| UX-098 | P2 | Only supports birth year, not full date | 📋 BACKLOG | Data model enhancement. |
| UX-099 | P2 | No date source citation support | 📋 BACKLOG | |
| UX-100 | P2 | Confirmation banners stack and push content down | ✅ FIXED (S49D) | Auto-dismiss after 4s with opacity transition. |
| UX-101 | P2 | Pending count doesn't decrement after confirms | ✅ FIXED (S49D) | OOB swap updates counter on accept/reject. |
| UX-102 | P3 | "Accept All High-Confidence" has no confirmation | 📋 BACKLOG | |

---

## Summary

| Disposition | Count |
|-------------|-------|
| ✅ FIXED | 16 |
| 🔜 PLANNED | 7 |
| 📋 BACKLOG | 74 |
| ⏭️ DEFERRED | 2 |
| ❌ REJECTED | 1 |
| **Total** | **100** |

### Priority Breakdown (BACKLOG items only)

| Priority | Count | Key Items |
|----------|-------|-----------|
| P0 | 6 | Merge button 404, Name These Faces targetError, uploads not queued |
| P1 | 22 | Loading indicators, auto-scroll, merge direction, admin controls |
| P2 | 38 | Polish, truncation, missing data display, layout |
| P3 | 4 | Delight features, visual evidence, timeline |
| Unset | 4 | Legacy items without priority |
