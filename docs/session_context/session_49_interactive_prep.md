# Interactive Session Prep — GEDCOM Upload + Birth Year Review

Created by Session 49 autonomous polish session.
For use in Session 49B (interactive, requires Nolan).

---

## Pre-flight (do these manually in browser before starting)

### Birth Year Bulk Review
- [ ] Go to /admin/review/birth-years
- [ ] Verify pending estimates are shown (32 expected from ML pipeline)
- [ ] Accept Big Leon with correction: ML said ~1907, actual 1902
      (source: Italian census of Rhodes, family records)
- [ ] Review and accept/reject remaining high-confidence estimates
- [ ] After accepting, verify /person/{big_leon_id} shows birth year
- [ ] Verify timeline shows correct ages on photos

### GEDCOM Upload
- [ ] Prepare your real GEDCOM file (export from Ancestry/MyHeritage)
- [ ] Go to /admin/gedcom
- [ ] Upload — note the match count and individual count
- [ ] Review EVERY proposed match (do NOT bulk-accept)
- [ ] Check /tree after confirming matches
- [ ] Check /connect graph with real relationship data

### Visual Walkthrough
- [ ] Browse /photos as a logged-out user (incognito)
- [ ] Click into a photo — face overlays work? Names + ages shown?
- [ ] Click a person name — goes to person page?
- [ ] Person page: birth year shown (if accepted)?
- [ ] /timeline with person filter — ages appear?
- [ ] /map — markers load?
- [ ] /tree — renders with data?
- [ ] /compare — upload works?
- [ ] Share a link in incognito — clean public view?

### Issues Found (fill in during walkthrough)
- [ ] ...

---

## Known Issues to Check

### Already Fixed (verify in production)
- Collection name truncation → fixed Session 49 (wrapping instead of truncate)
- Triage pill tooltips → fixed Session 49 (hover explanations)
- Version display → fixed Session 47 (dynamic from CHANGELOG.md)
- Age on face overlays → fixed Session 48 (Name, ~age format)

### Noted but Not Fixed (for Session 50+)
- `/admin/pending` and `/admin/proposals` use old sidebar layout instead of `_admin_nav_bar()`
- `/admin/review-queue` route exists but isn't linked from admin nav
- Admin UX vs public UX is "two different apps" — needs unification (Session 50)

---

## Session 49 Stats
- Production health: 10/10 public routes 200, 1/1 admin route 401
- Session 47 deliverables: 6/6 PASS
- Session 48 deliverables: 3/3 PASS
- Bugs fixed: 2 (collection truncation, triage tooltips)
- New tests: 5 (1 collection + 2 triage + 2 existing suites green)
