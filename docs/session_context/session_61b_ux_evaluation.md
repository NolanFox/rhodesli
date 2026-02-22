# Session 61B UX Evaluation

**Date**: 2026-02-22
**Evaluator**: Claude Code
**App Thesis**: Help community members identify, share, find relatives, solve mysteries

## Page: Homepage (Admin View)
- **Serves thesis?** Partially — shows match review workflow (admin-focused), but first-time visitors land here too
- [x] P2: Homepage is admin-centric — non-admin visitors see the identity system dashboard, not a welcoming landing page. First-time visitors from Facebook should see: "What is this?" + "Upload your photo" + "Browse the archive"
- [x] P3: Stats bar ("403 To Review, 54 People, 203 Help Identify") is meaningless to non-admin visitors
- [x] P2: No clear CTA for new visitors — the "Upload" button is admin-only, there's no "Compare a Face" or "Explore Photos" prominent CTA

## Page: Compare Faces
- **Serves thesis?** Yes — upload-first design, clear purpose
- [x] P3: "Compare 2-5 photos at once" link is subtle — could be more prominent for users with multiple family photos
- [x] P3: "Sign in to contribute it to the archive" text is useful but could be more inviting
- **Sharing**: No share button on this page (appropriate — nothing to share yet)
- **Discoverability**: Good — clear upload zone, single action path

## Page: Estimate ("When Was This Photo Taken?")
- **Serves thesis?** Yes — clear value proposition, browse + upload
- [x] P3: Photo grid thumbnails are small — hard to browse on mobile
- **Discoverability**: Excellent — question-as-title is compelling
- **Next action**: Clear — upload or select from grid

## Page: Photo Detail (Family Photo)
- **Serves thesis?** Strongly yes — face overlays with names, share button, evidence
- [x] P2: "Admin: Add a back image" section is visible to admin but takes up prime real estate above the evidence
- [x] P3: "Front orientation" controls visible but rarely used — could be collapsed
- **Sharing**: "Share This Photo" button prominent and well-placed
- **AI Analysis**: Date estimate with probability bars is excellent
- **Evidence sections** (Scene, Visible Text, Tags, Photo Detective Evidence, Subject Ages) are well-organized

## Page: Face Compare Standalone
- **Serves thesis?** Yes — museum-quality entry point for new users
- [x] P3: "How it works" section could include sample results to set expectations
- **Discoverability**: Excellent — "Who is in your photo?" is compelling
- **Design**: Professional serif font, warm palette, no archive nav clutter

## Summary
- P1 issues (blocking adoption): 0
- P2 issues (degrading experience): 3
  1. Homepage admin-centric for non-admin visitors
  2. Admin controls above evidence on photo pages
  3. No prominent CTA for new visitors on homepage
- P3 issues (nice to have): 5
- Quick wins (< 30 min each):
  1. Collapse admin tools behind an "Admin" toggle on photo pages
  2. Add "Compare a Face" CTA card on public-facing homepage
  3. Make "Compare 2-5 photos" link more prominent on /compare

## BACKLOG Items Created
- UX-130: Homepage visitor experience — non-admin landing page (P2)
- UX-131: Photo page admin tools below evidence (P2)
- UX-132: Homepage "Compare a Face" CTA for visitors (P2)
