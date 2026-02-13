# Feedback Index

All user feedback is tracked here with links to relevant technical files.
Claude Code: READ this file at the start of any session touching UX.
UPDATE this file when completing feedback-related work.

## Active Feedback Threads

| Source | Topic | Status | Linked Files |
|--------|-------|--------|--------------|
| Claude Benatar | Enhancement needed | Researched: hurts ML. UX toggle planned. | docs/ml/PHOTO_ENHANCEMENT_RESEARCH.md, AD-037 |
| Claude Benatar | Faces too small | DONE | .claude/rules/discovery-ux.md #3 |
| Claude Benatar | Scrolling fatigue | DONE | AD-038 quality scoring + ordering |
| Claude Benatar | "I don't know how to identify!" | DONE | proposal system, "I Know Them" button |
| Claude Benatar | Stella HASSON ID | Pending: needs proposal ingestion | proposals |
| Claude Benatar | Photo 986 son of Nace/Arlene | Pending: needs proposal ingestion | proposals |
| Claude Benatar | Other people uploading | DONE | /upload, ROLE-002/003, FE-060 |
| Claude Benatar | Post backs of photos | DONE | FE-071: front/back flip with CSS 3D animation, back_image + back_transcription metadata |
| Claude Benatar | Photos too poor quality | DONE | AD-038 quality scoring |
| Claude Benatar | Need enhancement | Planned: UX-only toggle | PHOTO_ENHANCEMENT_RESEARCH.md |
| Claude Benatar | Adoption concerns | IN PROGRESS: shareable photo pages + OG meta tags for viral loop | FE-070–074 |
| Claude Benatar | Low community engagement | IN PROGRESS: public photo viewer as compelling first experience | FE-070 public_photo_page() |
| Manual testing | Quality ordering broken | DONE (this session) | AD-038, _sort_skipped_by_actionability |
| Manual testing | Test data in production | DONE (this session) | .claude/rules/data-safety.md |
| Manual testing | Pending uploads broken | DONE (this session) | /admin/staging-preview endpoint |
| Manual testing | Duplicate Focus Mode button | DONE (this session) | admin banner cleanup |
| Manual testing | Mobile responsiveness | Verified: already implemented | tests/test_mobile.py |
| Session 20 | Public photo viewer | DONE | FE-070: /photo/{id} shareable page with face overlays, person cards |
| Session 20 | Social sharing (OG tags) | DONE | FE-072: og:title/description/image/url + Twitter Card meta tags |
| Session 20 | Share + download buttons | DONE | FE-073: Web Share API + clipboard fallback, download with Content-Disposition |
| Session 20 | Front/back photo flip | DONE | FE-071: CSS 3D flip, back_image/back_transcription metadata fields |
| Session 20 | Internal links to viewer | DONE | FE-074: "Open Full Page" / "Full Page" links from modal, face cards, photos grid |

## Strategic Insights (from Claude Benatar conversation, Feb 2026)

- Community adoption is the #1 challenge, not technology
- Most people with photos won't bother unless UX is compelling
- Institutional partnerships (museum, archives) = credibility + steady users
- Book-writing workflow = potential use case for photo collection
- Enhancement remains high-priority UX feature despite ML concerns
- The "wow moment" (Photo Context with face overlays) needs to be the first thing people see

## Feedback Sources

| Source | File | Last Updated |
|--------|------|-------------|
| Claude Benatar | docs/feedback/CLAUDE_BENATAR_FEEDBACK.md | 2026-02-12 |
