# Session 49B — Interactive Review Checklist

Created by Session 49 autonomous polish session.
Updated by Session 51 with Quick-Identify and community feedback items.
Updated by Session 54D with Sessions 52-54c changes.
For use in Session 49B (interactive, requires Nolan).

---

## 1. Enter Carey Franco's 8 IDs from the Thanksgiving Eve photo
- Tests Quick-Identify / "Name These Faces" mode (built Session 51)
- Names: Albert Cohen, Eleanore Cohen, Morris Franco, Ray Franco,
  Molly Benson, Herman Benson, Belle Franco, Isaac Franco
- Source: Carey Franco's Facebook comment (Feb 18, 2026)
- Photo: "Welcome Home Our Boys" / Thanksgiving Eve 1946

## 2. Enter Howie/Stu confirmations
- Isaac Franco (Howie's father) — confirmed in Facebook thread
- Morris Franco (Howie's uncle) — confirmed in Facebook thread
- Stu Nadel confirmed face match: "Looks the same to me..!!"

## 3. Birth year bulk review
- [ ] Go to /admin/review/birth-years
- [ ] Verify pending estimates are shown (32 expected from ML pipeline)
- [ ] Accept Big Leon with correction: ML said ~1907, actual 1902
      (source: Italian census of Rhodes, family records)
- [ ] Review and accept/reject remaining high-confidence estimates
- [ ] After accepting, verify /person/{big_leon_id} shows birth year
- [ ] Verify timeline shows correct ages on photos

## 4. Real GEDCOM upload + match review
- [ ] Prepare your real GEDCOM file (export from Ancestry/MyHeritage)
- [ ] Go to /admin/gedcom
- [ ] Upload — note the match count and individual count
- [ ] Review EVERY proposed match (do NOT bulk-accept)
- [ ] Check /tree after confirming matches
- [ ] Check /connect graph with real relationship data

## 5. Test Compare upload with a real photo
- Use Howie Franco's grandmother comparison use case
- Verify error handling works (Session 49C + 50 fixes)
- Test with valid photo, invalid file, oversized file
- **Hybrid detection now active (AD-114)** — det_500m + w600k_r50
- Expected timing: ~50s on production (was ~65s pre-Session 54, CPU-bound)
- Verify uploaded photo displays in results (Session 53 fix)
- Verify loading indicator appears during processing (Session 53 fix)
- Verify results show match scores/tiers with confidence labels

## 6. Test the new /estimate page
- Verify face counts show real numbers (Session 50 BUG-009 fix)
- Test pagination (24 per page)
- Test upload zone
- Check evidence display for photos with rich Gemini data
- **Gemini 3.1 Pro now wired to estimate upload (Session 52)**
- Verify evidence display shows Gemini analysis data
- Verify loading indicator with "This may take a moment" message (Session 54 fix)

## 7. Test Quick-Identify (Session 51)
- [ ] Click unidentified face on photo page → inline name input (tag dropdown)
- [ ] Test autocomplete search
- [ ] Click "Name These Faces" button → sequential mode activates
- [ ] Verify progress banner shows "X of Y identified"
- [ ] Name a face → auto-advance to next unidentified face
- [ ] Click "Done" → exits sequential mode
- [ ] Enter remaining identifications from Facebook thread

## 8. Visual walkthrough
- [ ] Browse /photos as a logged-out user (incognito)
- [ ] Click into a photo — face overlays work? Names + ages shown?
- [ ] Click a person name — goes to person page?
- [ ] Person page: birth year shown (if accepted)?
- [ ] /timeline with person filter — ages appear?
- [ ] /map — markers load?
- [ ] /compare — upload works?
- [ ] Share a link in incognito — clean public view?
- [ ] Verify 404 pages for non-existent person/photo IDs (Session 54)
- [ ] Health endpoint returns ML status: `curl .../health` (Session 52)
- [ ] Admin footer shows correct version (Session 49C fix)

## 9. Bug list from manual testing
- [ ] Note any issues found during the above tasks
- [ ] Prioritize for next autonomous session

## 10. Run production smoke test
- [ ] `python scripts/production_smoke_test.py` — all 11 paths should pass
- [ ] Note any failures for autonomous fix session

## 11. After interactive session
- [ ] Log all bugs found in docs/ux_audit/session_findings/session_49b_findings.md
- [ ] Update UX_ISSUE_TRACKER.md with new items
- [ ] Create Session 49B log in docs/session_context/session_49b_log.md
- [ ] Push results: `git push origin main`

---

## Known Issues to Check

### Already Fixed (verify in production)
- Collection name truncation → fixed Session 49
- Triage pill tooltips → fixed Session 49
- Version display → fixed Session 47
- Age on face overlays → fixed Session 48
- Photo 404 for inbox photos → fixed Session 49C
- Compare upload silent failure → fixed Session 49C
- Estimate page "0 faces" → fixed Session 50
- Compare 640px ML resize → fixed Session 54
- HTTP 404 for invalid person/photo → fixed Session 54
- Hybrid detection for faster compare → Session 54B (AD-114)
- UX tracker 35/35 coverage → verified Session 54B
- HTMX indicator CSS fix → fixed Session 53
- Compare loading message updated → fixed Session 53
- Estimate loading indicator → fixed Session 54

### Noted but Not Fixed
- `/admin/pending` and `/admin/proposals` use old sidebar layout instead of `_admin_nav_bar()` (UX backlog)
- `/admin/review-queue` route exists but isn't linked from admin nav (UX backlog)
- Duplicate activity entries (UX-006, needs data investigation)
- Timeline loads all 271 images — no lazy loading (UX-007, planned Session 55)
- Activity feed only shows 2 annotation events (UX-008, planned Session 55)
- Docker image 3-4GB (UX-025, planned Session 56+)
- Compare still ~50s on production (CPU-bound, no GPU on Railway)
