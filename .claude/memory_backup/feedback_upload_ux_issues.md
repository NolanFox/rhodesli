---
name: Upload & Pending Page UX Issues (Session 100d)
description: User-reported issues with photo uploads, /admin/pending page, and approval workflow — blocking Claude Benatar feedback loop
type: feedback
---

Critical feedback from Nolan (2026-03-13) while trying to get Claude Benatar to use the platform:

1. **Compare uploads must be saved** — FIXED (Session 100d, commit befd978)
2. **Pending page broken thumbnails** — FIXED (Session 100d, commit af1ae9b — staging dirs preserved for pending jobs)
3. **Pending page not clickable** — Partially addressed (thumbnails now link to staging preview)
4. **Photos missing from Photos section after approval** — FIXED (approval pipeline wired, commit 08089d9)
5. **Approval status doesn't update** — FIXED (HTMX swap ID fix, commit 08089d9)
6. **Face cards don't show name** — Not yet addressed
7. **Approvals are very slow** — Not yet addressed
8. **Need batch approve** — FIXED (Select All + Approve Selected, commits 08089d9 + 60cf962)
9. **Auto-confirm on approval** — FIXED (single-face auto-confirm, commit 08089d9)

Claude Benatar feedback: "To tell you the truth I find it confusing... searching, tagging..."
- He has two emails: poisson1957@hotmail.com (account) and lil_lover_52388@yahoo.com (annotations)
- His annotations: Rachele Capelluto, Frank Roger Treat, Violet Israel (twin), Molly Israel
- Quickstart guide: `docs/guides/claude-benatar-quickstart.md`

**Why:** Nolan is actively onboarding Claude Benatar as a user. Upload stability is existential — if photos disappear or the review flow is broken, trust is destroyed.

**How to apply:** These are P0 issues. Fix before any new features. Test the full upload → pending → approve → visible-in-archive flow end-to-end. Need: contributor activity view, faster approvals.
