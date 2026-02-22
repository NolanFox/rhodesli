# Session 60B UX Review

**Date:** 2026-02-22
**Method:** Chrome Extension live production testing + curl analysis
**Site:** https://rhodesli.nolanandrewfox.com

---

## First-Time Visitor Experience

### Homepage (Public)
- **Clarity: 4/5** — Hero section with compelling tagline about face recognition + Sephardic community. Clear value proposition. Dynamic stats (271 photos, 54 people) build credibility.
- **Delight: 3/5** — Hero photo mosaic is visually striking. Dark theme with warm accents (amber/gold) feels archival and premium. "Face Compare" concept is novel.
- **Friction: Low** — Navigation is clear (Photos, People, Collections, Map, Timeline, Tree, Compare, About, Sign In). No dead ends from hero section.
- **Issue:** Title shows "Rhodesli Identity System" in admin view — developer-speak. Public title "Rhodesli -- Jewish Community of Rhodes Photo Archive" is much better.

### Photos Page (/photos)
- **Clarity: 5/5** — Excellent filtering: decade pills with counts, scene type tags (Group Portrait 137, Studio 126, etc.), collection dropdown, sort, search. 271 results shown with face count badges and decade labels.
- **Delight: 4/5** — Photo cards are well-designed with sepia decade badges, face count indicators. Hovering reveals face names on photos with identified people.
- **Friction: None observed** — Lazy loading works. Decade pills are intuitive.

### People Page (/people)
- **Clarity: 5/5** — Clean grid of 54 identified people with circular face crops, names, photo counts. A-Z sort default.
- **Delight: 3/5** — Functional but could benefit from surname grouping or family tree connections.
- **Friction: Low** — No search on this page (search exists in sidebar on admin view).

### Face Compare (/facecompare)
- **Clarity: 5/5** — Museum-quality design. "Who is in your photo?" headline immediately explains the purpose. File type/size limits shown. "How it works" 3-step guide below.
- **Delight: 5/5** — This is the standout page. Serif font + warm palette creates an editorial feel. Upload drop zone is inviting.
- **Friction: Low** — Mobile-responsive. Clear CTA.

### Photo Detail Page (/photo/{id})
- **Clarity: 4/5** — Face overlays with name labels, identified/unidentified legend. "People in this photo" section below with face crops. AI Analysis section with date estimate + decade probability bars.
- **Delight: 4/5** — The face overlay system is impressive. Probability bars for date estimation are visually clear. "Name These Faces (N unidentified)" CTA is compelling.
- **Friction: Medium** — On photos with many faces (12+), the overlay labels overlap. Navigation arrows work but "Photo N of M" feels like a developer concept.

### Person Detail Page (/person/{id})
- **Clarity: 4/5** — Face crop, name, identification badge, photo count, collections. Metadata (Born/Died/From) shown. Action buttons: Edit Name, Find Similar, View in Admin (admin-only).
- **Delight: 3/5** — Clean but sparse. Could benefit from a "family connections" section or timeline of appearances.
- **Friction: Low** — Share button prominent. All photos linked.

---

## Community Member Experience (Carey Franco Scenario)

### "I recognize someone in this photo — how do I tell the site?"
- **Current flow:** Must log in → admin verifies → admin identifies
- **Gap:** No "Help Identify" mode for non-admin logged-in users (FE-041 in BACKLOG)
- **Workaround:** "Name These Faces" button exists but leads to admin workflow. Non-admins see "Help Identify" links but these aren't fully implemented.
- **Verdict:** P1 gap — the primary community use case requires admin intervention

### "I want to contribute my own photos"
- **Current flow:** Upload button visible but admin-only
- **Gap:** No community upload workflow. User must email photos to admin.
- **Verdict:** P2 gap — expected for current stage, but should have clear instructions

### "I want to see all photos of my grandfather"
- **Current flow:** People page → click person → see all photos
- **Verdict:** Works well for identified people. For unidentified faces, user can't search by face (would need Face Compare).

### "I want to share a result with my cousin"
- **Current flow:** Share button on photo/person pages copies URL. Face Compare results have shareable URLs.
- **Verdict:** PASS — sharing works

---

## Broader Scope Readiness

### Rhodesli-Specific Hardcoding
- **171 references** to "Rhodes", "Jewish", "Ladino", "Sephardic" in app/main.py
- Page titles, meta descriptions, hero text, about content all hardcoded
- Collection names ("Vida Capeluto NYC", "Betty Capeluto Miami") are data-driven
- **Assessment:** Heavy refactoring needed for multi-community support. Would need:
  1. Config-driven community name/description/theme
  2. Template variables for community-specific text
  3. Multi-tenant routing or subdomain support
  4. Currently not close to generalizable — this is a Rhodesli-specific app

### Face Compare as Standalone
- `/facecompare` already uses community-agnostic language ("historical archives")
- Could be extracted as standalone product with less work than the full archive
- `/compare` (internal tool) is more tightly coupled to Rhodesli data

---

## Top 5 UX Improvements (Priority Order)

### 1. Help Identify Mode for Non-Admin Users (P1)
- **Impact:** Enables the primary community use case
- **What:** Let logged-in non-admin users suggest names for unidentified faces
- **Why:** Currently only admin can identify faces, creating a bottleneck
- **How:** Suggestions go to admin approval queue (already exists: /admin/approvals)
- **Effort:** Medium — annotation submission exists, needs public-facing UI

### 2. Contribution Instructions Page (P2)
- **Impact:** Reduces "how do I help?" friction
- **What:** A /contribute or /help page explaining: how to identify faces, how to submit photos (email for now), how to report errors
- **Why:** Community members arrive from Facebook links and need clear guidance
- **Effort:** Low — static page with clear CTAs

### 3. Person Page Family Context (P2)
- **Impact:** Makes identified people more meaningful
- **What:** Show family relationships (spouse, parent/child), link to related people, show timeline of appearances across photos
- **Why:** 19 relationships exist in data but aren't visible on person pages
- **Effort:** Medium — data exists, needs UI rendering

### 4. SSE Upload Visual Feedback in Browser (P2)
- **Impact:** Makes the upload experience feel responsive
- **What:** The SSE backend streams perfectly (7 events), but need to verify the browser JS actually animates progressive stages vs waiting for completion
- **Why:** Progressive feedback is the difference between "wow" and "is it stuck?"
- **Effort:** Low — backend works, may just need JS client tuning

### 5. Mobile Photo Overlay Readability (P2)
- **Impact:** Photos with many faces (12+) have overlapping labels on mobile
- **What:** Reduce label font size or hide labels on mobile, show on tap
- **Why:** The face overlay system is one of the site's strengths but breaks on dense photos
- **Effort:** Low — CSS media query adjustments

---

## Friction Points Log

| # | Page | Severity | Description | Suggested Fix |
|---|------|----------|-------------|---------------|
| 1 | /person | P2 | No family relationships shown despite 19 in data | Render relationships section |
| 2 | /photos | P2 | No "this is you?" CTA on face overlays for visitors | Add suggestion link for logged-in users |
| 3 | Homepage | P2 | Admin view shows "Identity System" title | Already correct for public view |
| 4 | /photo | P2 | Dense photos (12+ faces) have overlapping labels | Responsive label sizing |
| 5 | Global | P1 | No "Help Identify" flow for community members | FE-041 implementation |
| 6 | /people | P2 | No search/filter on people page | Add name search input |
| 7 | /about | P2 | No contribution instructions | Add /contribute page |

---

## What's Working Well

1. **Face Compare (/facecompare)** — Museum-quality design, clear UX, community-agnostic language. The best "front door" for the product.
2. **Photo browsing** — Decade filters, scene tags, lazy loading, face count badges. Professional-grade archive browsing.
3. **AI Analysis on photo pages** — Date estimation with decade probability bars is novel and visually compelling. Confidence levels are human-readable.
4. **Admin workflow** — The review queue (403 to review, 51 ready to confirm) is efficient. ML match suggestions with confidence tiers help prioritize.
5. **Mobile responsiveness** — Bottom nav bar on mobile, responsive grid layouts, Face Compare works perfectly at 375px.
6. **Share functionality** — Every photo and person page has a Share button. Face Compare results have shareable URLs.
7. **Dark theme** — Consistent, premium feel that makes the vintage photos pop.
8. **SSE streaming** — Backend delivers 7 progressive events. The infrastructure for great upload UX is solid.
