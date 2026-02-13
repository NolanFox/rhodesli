# Claude Benatar Feedback Tracker

**Reviewer:** Claude Benatar (family member, non-technical user)
**Last updated:** 2026-02-12

## Original Feedback (~Feb 2026)

| # | Feedback Item | Status | Resolution |
|---|--------------|--------|------------|
| 1 | Photo enhancement needed — faces too degraded to identify | PARTIAL | AD-037: enhancement is UX-only, not ML. Quality scoring (AD-038) now surfaces best photos first. Full enhancement toggle is future work. |
| 2 | Face crops too small to identify | DONE | Session 19/19b: enlarged to 288px in Focus Mode, 64px minimum in lists. Quality-aware thumbnail selection. |
| 3 | Scrolling fatigue with tiny images | DONE | Quality scoring prioritizes best crops. Actionability sorting puts ML-matched faces first. |
| 4 | "I don't know how to identify!" | DONE | Session 19c: "I Know This Person" button, surname-based onboarding, personalized discovery banner. |
| 5 | Stella HASSON identification (specific person) | PENDING | Requires proposal system verification on production. Identity may already exist in data. |
| 6 | "Son of Nace and Arlene" photo 986 | PENDING | Requires checking photo_index for photo 986 and creating identity link. |
| 7 | Other people uploading photos | DONE | Upload pipeline (BE-022), contributor roles (ROLE-002/003), guest contributions (FE-060). |
| 8 | Post backs of photos (descriptive text on photo reverse) | FUTURE | Would need photo-back as linked asset model. Not yet designed. |

## Follow-up Feedback (Feb 12, 2026)

| # | Feedback Item | Status | Resolution |
|---|--------------|--------|------------|
| 9 | Photos too poor quality to browse | DONE | Quality scoring (AD-038) surfaces best photos first. Hover effects indicate clickable. |
| 10 | Need to enhance full pictures | PARTIAL | Enhancement toggle is future UX work. Quality scoring helps now by showing best available crop. |
| 11 | Full picture should be prominent | DONE | "View Photo" links everywhere. Click any face crop to see full photo context. Photo view with face overlays. |

## Community Submission (Feb 13, 2026)

| # | Feedback Item | Status | Resolution |
|---|--------------|--------|------------|
| 12 | Submitted Sarina2.jpg via upload — "3 people, can't identify the one I know" | DONE | Photo processed: 3 faces detected, uploaded to R2, live on production. No ML matches at threshold 1.05 (low-confidence matches to Boulissa Pizanti, Rosa Sedikaro, Big Leon at 1.24-1.31). |
| 13 | Upload flow lacks per-face annotation during submission | BACKLOG | Benatar wants to annotate which person they know during upload. Current flow only captures collection/source metadata. Would need face detection preview + name input fields. |

## Identification UX Triage (Feb 13, 2026)

| # | Feedback Item | Status | Resolution |
|---|--------------|--------|------------|
| 14 | "I can't create..." — face tag dropdown non-functional for non-admin | DONE | Tag dropdown endpoints (/api/face/tag, /api/face/create-identity) were admin-only. Non-admin users now see "Suggest match" and "Suggest [name]" buttons that submit annotations for review. |
| 15 | "I go to face card... Nothing there either" — navigation after tagging | DONE | "Go to Face Card" button links to correct identity section. Was working but confusing after failed tag attempt. |
| 16 | "I cannot merge her with your pictures" — merge is admin-only | DONE | Non-admin users now get suggestion workflow via annotation system. Same UX (type name, click), but creates annotation for admin review instead of direct merge. |
| 17 | Share button opens OS share sheet instead of copying URL | DONE | Share button now copies to clipboard first with "Link copied!" toast. Mobile still gets native share sheet after copy. |

## Key Takeaways

1. **Quality is the #1 complaint** — both image quality and browsing experience quality. The composite quality score + best-face selection addresses the browsing side. True image enhancement requires ML infrastructure (GFPGAN integration) without breaking face matching.

2. **Identification barriers are high** — non-technical users need explicit guidance ("I Know This Person" button) and context (photo collection, other identified people in same photo) to make identifications.

3. **Upload is desired** — family members WANT to contribute photos. The pipeline exists but needs testing with real contributors.

4. **Photo backs are a unique heritage feature** — the reverse side of physical photos often has handwritten names, dates, and context. This is a unique differentiator for heritage archives that digital photo tools don't support.
