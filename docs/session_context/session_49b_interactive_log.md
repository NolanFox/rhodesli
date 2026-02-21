# Session 49B Interactive Log — 2026-02-20

## Session Goals
- [x] Birth year bulk review (accept/reject ML estimates) — Section 1
- [x] GEDCOM upload (real family data) — Section 2
- [x] Carey Franco's 8 IDs + Howie/Stu confirmations — Section 3
- [x] Compare upload test (Item 5) — 2026-02-21, 8 UX issues logged
- [x] Estimate page test (Item 6) — 2026-02-21, comprehensive UX audit, 18 issues logged
- [ ] Quick-Identify test (Item 7)
- [ ] Visual walkthrough (admin + public views) (Item 8)
- [ ] Bug list + smoke test + cleanup (Items 9-11)

## Section Status
- [x] Section 0: Session infrastructure (2026-02-20)
- [x] Section 1: Birth year bulk review (2026-02-20) — 31 estimates reviewed. 28 accepted (10 exact, 18 corrected). ML accuracy: ~32% exact, ~48% within 2 years, mean absolute error ~5.4 years.
- [x] Section 2: GEDCOM upload (2026-02-21) — Real GEDCOM imported (21,809 individuals). 33 identities matched to Ancestry tree. User reviewed all matches in CSV, corrected 15 Ancestry IDs. 19 relationships built (5 spouse, 14 parent-child). 33 identities enriched with GEDCOM birth/death dates, places, gender, Ancestry URLs. Birth years from Section 1 preserved through production merge. ancestry_links.json created. Lesson 78 added (production-local data divergence).
- [x] Section 3: Identity tagging (2026-02-21) — 8 people tagged in /photo/8f6a6a0108f019cf (1970s photo, Vida Capeluto NYC). Morris Franco, Isaac Franco merged+confirmed. Albert Cohen, Eleanore Cohen, Ray Franco, Molly Benson, Herman Benson, Belle Franco confirmed. All via direct API calls (merge button 404 bug). 8 P0/P1 UX issues logged.
- [ ] Section 4: Autonomous UX audit
- [ ] Section 5: Synthesis and prioritization

## Issues Found

### Critical (blocks sharing with collaborators)
<!-- Format: - [ ] ROUTE: Description [BACKLOG: yes/no] -->
- [ ] /admin/review/birth-years: Save Edit does not persist edited value — confirmed twice: (1) Mary Maria Capelouto Hasson edited to 1915, saved as 1916; (2) Abraham Moussafer edited to 1895, saved as 1894. Both reverted to original ML value. Likely the HTMX form submit reads the input before the browser updates the DOM value from typed text. Both fixed via /api/identity/{id}/metadata POST workaround. This is a real data integrity bug. [BACKLOG: yes]
- [ ] ML pipeline / Gemini OCR: Confused arrival date with birth date for Mary Maria Capelouto Hasson. Document shows arrival Sep 25, 1916 and birth Aug 8, 1915. ML/Gemini extracted 1916 (arrival) as birth year. This is a systemic risk with document photos — OCR can confuse different date fields. Pipeline needs date-field disambiguation or multiple-date extraction with labeling. [BACKLOG: yes]
- [ ] ML model evaluation: Whether OCR dates are present in a photo is a critical variable for model accuracy. Should segment evaluation by: (1) photos with NO OCR dates — pure visual age estimation, (2) photos with OCR birth dates — nearly free ground truth, (3) photos with OTHER OCR dates (newspaper dates, event dates) — useful for photo dating but not birth year, (4) photos with non-date OCR text. Model accuracy optimization should focus on case 1 (visual-only) since case 2 is essentially solved by extraction. This segmentation matters for honest model evaluation and for knowing where to invest improvement effort. [BACKLOG: yes]

### Critical — Identity Tagging Workflow (Section 3, 2026-02-21)
- [ ] MERGE BUTTON 404: Focus mode merge button generates URL with `&` instead of `?` for query params. `/api/identity/{id}/merge/{neighbor_id}&from_focus=true` → 404. Should be `?from_focus=true`. Bug is at app/main.py:5780. `focus_suffix` starts with `&` not `?`. Fix applied locally but NOT yet deployed. Every merge from Focus mode is broken on production. [BACKLOG: yes, P0]
- [ ] MERGE DIRECTION UNINTUITIVE: When merging A into B via `/api/identity/A/merge/B`, the NEIGHBOR (B) survives, not the target (A). This is counterintuitive — "merge B into A" should mean A survives. Caused metadata loss twice this session: after merging, rename/confirm/metadata was applied to the now-deleted target ID instead of the surviving neighbor ID. Admin has no visibility into which ID survived. [BACKLOG: yes, P1]
- [ ] METADATA LOST ON WRONG MERGE TARGET: Because merge direction is unintuitive, rename + confirm + metadata operations applied to the deleted identity (target) instead of the surviving one (neighbor). All operations returned 200 but silently did nothing useful — the identity was already merged away. No error, no warning. Operations on merged-away identities should either (a) redirect to the surviving identity or (b) return an error. [BACKLOG: yes, P1]
- [ ] NO ADMIN CONTROLS ON PERSON PAGE: /person/{id} shows metadata form (birth year, etc.) but has NO rename, confirm, merge, or state-change buttons. Admin must navigate to the identity system (/?section=...) to find the identity, then use Focus mode. For the tagging workflow (identify a face → name it → confirm it), this means constant tab-switching between the photo page and the admin identity system. Person page needs admin action buttons. [BACKLOG: yes, P1]
- [ ] IDENTITY TAGGING WORKFLOW IS 5+ STEPS: To identify a person: (1) find them in Help Identify/skipped, (2) merge duplicates, (3) rename, (4) confirm, (5) add metadata, (6) link to GEDCOM. Each step is a separate API call with no batching. Should be a single "Identify This Person" form: enter name, select state=confirmed, add metadata, merge candidates — one submit. [BACKLOG: yes]
- [ ] PHOTO PAGE → IDENTITY SYSTEM DISCONNECT: Viewing /photo/{id} shows face overlays with names, but clicking an unidentified face has no path to "name this face". User sees the face, knows who it is, but must leave the photo page entirely to tag them. Need "Name This Face" click action on unidentified face overlays. [BACKLOG: yes]
- [ ] /identify/{id} SHAREABLE PAGE: No way to navigate from the face thumbnail to the full photo page. The "Can you identify this person?" page shows a cropped face but doesn't link to the source photo. This is a critical community engagement failure: (1) hard to identify someone from just a face crop without photo context, (2) misses opportunity to draw people into the app to identify OTHER people in the group photo, (3) loses the social/discovery hook that makes identification fun. The shareable link is the FIRST thing community members see (shared on Facebook), so this is the #1 onboarding path. Was reportedly fixed before but appears broken. Source: Carey Franco's Facebook identification of Albert Cohen — shared /identify/4a993942-... link had no path to the photo. [BACKLOG: yes, P1]
- [ ] COMMUNITY IDENTIFICATION WORKFLOW GAP: Real-world flow is: (1) share photo on Facebook, (2) community member identifies someone, (3) admin needs to tag that identification in the app. Currently step 3 requires finding the identity in the admin system, merging, renaming, confirming — 5+ steps with no direct path from the community response. Need a "community said this is X" quick-tag workflow. [BACKLOG: yes]

### Notable (should fix but not blocking)
<!-- Format: - [ ] ROUTE: Description [BACKLOG: yes/no] -->
- [ ] /: Landing page stat counters all show "0" (should be 271 photos, 46 people, 857 faces, 680 awaiting). Likely JS animation counter not firing. [BACKLOG: yes]
- [ ] /admin/review/birth-years: No undo after Accept/Save — confirmed rows disappear with no way to revert. Violates reversibility principle. Need a "Confirmed" queue (like other review pages) where you can see accepted estimates and revert if needed. [BACKLOG: yes]
- [ ] /admin/review/birth-years: Person name is not clickable — should link to /person/{id} so reviewer can see full context before deciding. [BACKLOG: yes]
- [ ] /admin/review/birth-years: Evidence lines (e.g. "1949: age ~22") don't link to the specific photo. Outlier detection requires seeing which photo produced which estimate. Each evidence line should link to the photo. [BACKLOG: yes]
- [ ] /admin/review/birth-years: No way to see the full Gemini explanation behind an age estimate. Should be accessible with one click from the evidence line (or via the linked photo). [BACKLOG: yes]
- [ ] /admin/review/birth-years: No indication whether age estimate came from internal model vs. external (Gemini). Source attribution needed per evidence line. [BACKLOG: yes]
- [ ] /admin/review/birth-years: Only supports birth year, not full birth date. User wants to enter day/month/year + birthplace when known (e.g. "28 JUN 1902, Milas, Mugla, Turkey"). Data model enhancement needed. [BACKLOG: yes]
- [ ] /admin/review/birth-years: No way to link a birth/death date to a specific source. People born 100+ years ago who moved countries often have conflicting dates across sources (census, immigration records, family records). Need source citation per date so we know what's authoritative. [BACKLOG: yes]
- [ ] /admin/review/birth-years: No way to express date precision/confidence. Need to differentiate: exact date (5 JAN 1850), rough date (year 1851, month unknown), approximate date ("abt. 1850"). Ancestry uses "abt." prefix for approximates, and allows entering just a year, month+year, or full date. Current UI only accepts a year with no confidence qualifier. [BACKLOG: yes]
- [ ] /admin/review/birth-years: Person name not clickable to person card or photos. With similar Sephardic names, reviewer needs to see photos to disambiguate people. Currently must open separate tab, go to main site, search name — too many clicks. Name should link to person page. [BACKLOG: yes] (Note: also logged above, but user re-emphasized with concrete friction example)
- [ ] ML pipeline / document OCR: When a photo IS a document containing birth date text (e.g. Mose Capelluto's Brazilian immigration card shows "Rhodes 11-2-1911"), the app should flag this — the answer is literally in the image. Could use OCR or Gemini to detect document-type photos and extract dates automatically. [BACKLOG: yes]
- [ ] ML pipeline: Could improve date estimation by using relative ages of known people in the same photo. If a spouse's age is known, comparing apparent relative ages could help ground both the photo date and the unknown person's age. Cross-person constraint propagation. [BACKLOG: yes]

### Cosmetic (nice to have)
<!-- Format: - [ ] ROUTE: Description -->
- [ ] /admin/review/birth-years: Confirmed row (Big Leon) stays visible on page instead of fading/collapsing
- [ ] /admin/review/birth-years: No main site navigation — no way to return to public site without browser back button [BACKLOG: yes]
- [ ] /admin/review/birth-years: "Accept All High-Confidence" button has no confirmation — could accidentally bulk-accept without reviewing evidence [BACKLOG: yes]
- [ ] /admin/review/birth-years: Evidence section says "9 photos with age data" for Victoria but only shows 3 data points — remaining evidence not displayed [BACKLOG: yes]
- [ ] /admin/review/birth-years: "Save Edit" button label is confusing — should just be "Save" [BACKLOG: yes]
- [ ] /admin/review/birth-years: Confirmation banners stack and push review items down the page. After 3+ confirms, most of the viewport is banners. Banners should auto-dismiss or collapse into a summary count. [BACKLOG: yes]
- [ ] /admin/review/birth-years: Pending count stays at "31" after confirming 3 entries — doesn't decrement. [BACKLOG: yes]

## Browser Tool Status
- Chrome extension: CONNECTED — can screenshot, navigate, click on live site
- Playwright MCP: CONNECTED — public pages confirmed working
- Auth strategy: Chrome extension has admin session (nolanfox@gmail.com logged in)
- Sections 1-3 (interactive): Claude navigates directly via Chrome extension

## Standing Instructions
- While reviewing birth years, note any UX issues spotted in screenshots (layout, confusing interactions, accessibility). Log to Issues Found section above.
- Categorize all findings: Critical / Notable / Cosmetic
- Data changes logged for ML provenance in Data Changes section

## Decisions Made
<!-- AD-XXX entries needed, with breadcrumbs -->

## Data Changes
<!-- What was accepted/rejected/uploaded — for ML provenance -->
- Big Leon Capeluto: ML estimated ~1907, corrected to 1902 via Save Edit. Source: Italian census of Rhodes, family records. Admin correction saved. Full birth date known: 28 JUN 1902, Milas, Mugla, Turkey (cannot enter full date yet — logged as feature request).
- Victoria Cukran Capeluto: ML estimated ~1927 (range 1921–1929), corrected to 1918 via Save Edit. Source: Naturalization records, Florida. Full birth date known: 17 MAY 1918, Istanbul, Turkey. ML was 9 years off — thought she looked younger.
- Betty Capeluto: ML estimated ~1951 (range 1950–1954), corrected to 1953 via Save Edit. Source: family records. Full birth date known: 17 SEP 1953, Havana, Cuba. ML was 2 years off — close.
- Selma Capeluto: ML estimated ~1917 (range 1915–1921), corrected to 1926 via Save Edit. Source: family records. Full birth date known: 17 JUN 1926, Asheville, Buncombe, North Carolina, USA. ML was 9 years off — thought she looked older.
- Moise Capeluto: ML estimated ~1919 (range 1911–1924), corrected to 1904 via Save Edit. ML was 15 years off. Source: cross-referenced Italian census of Rhodes (~1920s) against US records. US records show 8 NOV 1905, but census shows Leon=1903, Moise=1904, Haim(Victor)=1906. Given Leon's confirmed 1902 birth, Moise ~1904 and Victor ~1906 fits sibling spacing. Birthplace unclear — Rhodes or Milas. Brother Victor Capelluto (aka Haim) born 21 JAN 1906 per US records. Note: this is a case where cross-person constraint (sibling ages) resolved conflicting records.
- Victoria Capuano Capeluto: ML estimated ~1916 (range 1911–1922), corrected to 1905 via Save Edit. ML was 11 years off. Conflicting sources: US naturalization records say 24 SEP 1903 in Rhodes; tombstone + Florida death index say 25 SEP 1905. Leon Capouano's family history book lists sibling order (Morris, Zeb, Lenora, Matilda, Rachel, Victoria, David) with Rachel born 19 MAR 1903 — Victoria after Rachel rules out 1903. Best estimate: 25 SEP 1905, Rhodes, Greece.
- Rica Moussafer Pizante: ML estimated ~1907 (range 1904–1908), ACCEPTED as-is. Source: family records confirm 15 MAR 1907, Rhodes. ML was correct.
- Leon Capeluto: ML estimated ~1972 (range 1971–1974), corrected to 1975 via Save Edit. ML was 3 years off. Full name: Leon Nessim Capeluto, born ~8 JAN 1975, Tampa, Florida. Grandson of Big Leon Capeluto. Son of Nace (Nessim) Capeluto. Named per Sephardic tradition: firstborn son named after paternal grandfather; middle name = father's name. Note: Sephardic naming pattern context logged — Behor/Behora tradition, strict naming order, exceptions for deceased fathers.
- Esther Diana Taranto Capouano: ML estimated ~1903 (range 1903–1903), ACCEPTED as-is. Source: family records confirm 20 FEB 1903, Rhodes. ML was correct.
- Louis Pizante: ML estimated ~1900 (range 1900–1900), corrected to 1899 via Save Edit. ML was 1 year off. Source: family records, 15 JUL 1899, Rhodes.
- Morris Mazal: ML estimated ~1921 (range 1921–1921), corrected to 1923 via Save Edit. ML was 2 years off. Source: family records, 19 MAR 1923, New York.
- Rachel Capouya Capuano: ML estimated ~1900 (range 1900–1900), corrected to 1907 via Save Edit. ML was 7 years off. Source: family records, 18 MAY 1907, Rhodes. (Note: Rachel is sister of Victoria Capuano Capeluto per Leon Capouano's family history book, born 19 MAR 1903.)
- Mary Maria Capelouto Hasson: ML estimated ~1916 (range 1916–1916). Intended correction to 1915 (8 AUG 1915) but Save Edit saved 1916 instead — BUG (Save Edit race condition or input not captured). FIXED via /api/identity/{id}/metadata POST workaround. Birth year now correctly shows 1915. Source: family records, 8 AUG 1915. Note: ML's 1916 was actually the ARRIVAL date from the document, not birth date — OCR date-field confusion.
- Mose Capelluto: ML estimated ~1911 (range 1911–1911), ACCEPTED as-is. Source: Brazilian immigration card literally shows "Rhodes 11-2-1911". Full date: 11 FEB 1911. ML was correct — and the answer was in the document photo itself.
- Laura Franco Capelluto: ML estimated ~1921 (range 1921–1921), corrected to 1918 via Save Edit. ML was 3 years off. Source: family records, 1 APR 1918, Rhodes.
- David Raymond Capouano: ML estimated ~1908 (range 1908–1908), ACCEPTED as-is. Source: family records confirm 14 AUG 1908, Rhodes. ML was correct.
- Selma Capouya Capouano: ML estimated ~1921 (range 1921–1921), corrected to 1916 via Save Edit. ML was 5 years off. Source: family records, 1 OCT 1916, Rhodes.
- Debbie Fox Schapiro: ML estimated ~1956 (range 1956–1956), ACCEPTED as-is. Source: family records, 1 FEB 1956. Born as Deborah Lynn Fox. ML was correct.
- Betty Capeluto Fox: ML estimated ~1940 (range 1940–1940), corrected to 1935 via Save Edit. ML was 5 years off. Source: family records, 5 JAN 1935 (some records say Jan 6), Asheville, NC.
- Abraham Moussafer: ML estimated ~1894 (range 1894–1894), intended correction to 1895 — Save Edit bug struck again, saved as 1894. FIXED via API to 1895. Source: best guess is Alberto Musafir who ended up in Brazil, born ~18 DEC 1895, Rhodes. Identity match uncertain.
- Zeb Capuano: ML estimated ~1898 (range 1898–1898), corrected to 1893 via Save Edit (used form_input method — worked correctly). ML was 5 years off. Source: family records, 28 DEC 1893, Rhodes.
- NOTE: Save Edit apparent bug — root cause is click interference (user clicking elsewhere on page steals focus from input field mid-edit, so typed value doesn't land). Not a code bug per se, but highlights the need for: (1) a "Confirmed" queue where you can review and edit already-confirmed birth years, (2) resilience to accidental input issues, (3) ability to revise estimates when new genealogical information emerges. The person page metadata form (/person/{id}) is a workaround but not discoverable from the review page.
- Hanula Mosafir Capuano: ML estimated ~1873 (range 1873–1873), ACCEPTED as-is. Source: family records confirm ~1873, Rhodes. ML was correct (approximate).
- Rosa Sedikaro: ML estimated ~1906 (range 1906–1906), corrected to 1909 via Save Edit (form_input). ML was 3 years off. Source: family records, ~1909, Rhodes.
- Victor Capelluto: ML estimated ~1919 (range 1919–1919), corrected to 1906 via Save Edit (form_input). ML was 13 years off. Source: family records, 21 JAN 1906, Rhodes. This is Victor/Haim Capelluto, brother of Big Leon and Moise. Note: user had to check person page to disambiguate — many Victor/Haim Capelutos exist, and single face thumbnail wasn't clear enough. Reinforces clickable-name feature request.
- Abraham Capuano: ML estimated ~1870, ACCEPTED as-is. Source: family records, ~1870, Istanbul or nearby. ML was correct (approximate).
- Rahamin Capeluto: ML estimated ~1885, corrected to 1884 via Save Edit (form_input). ML was 1 year off. Source: family records, ~10 AUG 1884.
- Marcos Capelluto: ML estimated ~1903, corrected to 1909 via Save Edit (form_input). ML was 6 years off. Source: family records, ~15 OCT 1909, Rhodes.
- Felicita Russo Capelluto: ML estimated ~1915, ACCEPTED as-is. Source: family records, ~2 JAN 1915, Rhodes. ML was correct.
- Abraham Almaleh: ML estimated ~1895, corrected to 1896 via Save Edit (form_input). ML was 1 year off. Source: family records, ~15 MAR 1896, Rhodes.
- Isaac Capelouto: ML estimated ~1902, corrected to 1888 via Save Edit (form_input). ML was 14 years off. Source: family records, ~10 AUG 1888, Rhodes.
- Esther Brenda Israel: ML estimated ~1948, corrected to 1945 via Save Edit (form_input). ML was 3 years off. Source: family records, 11 AUG 1945, Los Angeles.
- Mathilda Capouano Capelouto: ML estimated ~1899, corrected to 1897 via Save Edit (form_input). ML was 2 years off. Source: family records, ~15 MAY 1897, Rhodes.

### Section 3: Identity Tagging — Thanksgiving Eve 1946 Photo (2026-02-21)
Photo: /photo/0f83d98adbea2d7e — "Jews of Rhodes: Family Memories & Heritage", Thanksgiving Eve 1946, Central Plaza
Target: 8 people to identify (Albert Cohen, Eleanore Cohen, Morris Franco, Ray Franco, Molly Benson, Herman Benson, Belle Franco, Isaac Franco)

- Morris Franco: Person 039 + Person 399 merged. Surviving ID: a772360a-64f6-4daf-8312-fcc7586304a7. Renamed, confirmed, metadata (birth_year=1888, gender=M, ancestry_id=132508216815). Note: merge button was broken (404 from `&` vs `?` bug), used direct API call. Rename/confirm applied to correct surviving identity on second attempt after discovering merge direction issue.
- Isaac Franco: Person 049 + Person 400 merged. Surviving ID: ac3b43b2-3e74-4237-ab71-b8ded0f8bfda. Renamed, confirmed, metadata (birth_year=1893, gender=M, ancestry_id=132395618061). Morris' brother-in-law. First attempt: rename/confirm/metadata applied to wrong (deleted) identity ID — all returned 200 but were no-ops. Fixed by applying to surviving ID. Ancestry: https://www.ancestry.com/family-tree/person/tree/162873127/person/132395618061/facts
- CORRECTION: The Cohens/Bensons/Francos are in /photo/8f6a6a0108f019cf (1970s photo, Vida Capeluto NYC Collection), NOT /photo/0f83d98adbea2d7e (1940s Thanksgiving). Source: Carey Franco Facebook post.
- Carey Franco's identifications (from Facebook): "Top left in picture is Albert and Eleanore Cohen. Morris and Ray Franco my aunt and Uncle. Molly and Herman Benson my aunt and uncle. Right is my mother and father Belle and Isaac Franco not sure on the Others."
- Albert Cohen: Identity 4a993942-2ed7-4cba-bb78-ada588853642 confirmed by Carey Franco via Facebook reply to /identify/ shareable link.
- Eleanore Cohen: Identity bac7731a-a1d2-4350-b528-c11f1b947b3a. Renamed, confirmed, metadata (gender=F). Albert's wife. Back row, next to Albert Cohen. Tagged via production API.
- Ray Rica Franco: Identity e26383e0-ee4e-40bd-9f8a-e3ae87a9dfc5. Renamed, confirmed, metadata (gender=F, ancestry_id=132395618059). To the right of Morris Franco. Tagged via production API. Note: user accidentally pasted same /identify/ URL as Eleanore — found correct identity from open browser tab.
- Molly Benson: Identity d85b2279-caac-4e56-b572-5431c4be48e5. Renamed, confirmed, metadata (gender=F). Back row right, one of the couple. Carey's aunt. Tagged via production API.
- Herman Benson: Identity 9dfc300a-1c86-460a-85df-e62c6781eb6d. Renamed, confirmed, metadata (gender=M). Back row right, one of the couple. Carey's uncle. Relationship to Franco/Cohen family TBD. Tagged via production API.
- Belle/Bella Bennoun Franco: Identity 1549d2b4-5d1f-4b0d-8ef2-430087a76d67. Renamed, confirmed, metadata (gender=F, ancestry_id=132765098259). Isaac Franco's wife, Carey Franco's mother. Immediately to left of Isaac. Tagged via production API.
- ALL 8 PEOPLE TAGGED in /photo/8f6a6a0108f019cf: Albert Cohen, Eleanore Cohen, Morris Franco, Ray Franco, Molly Benson, Herman Benson, Belle Franco, Isaac Franco. All confirmed via production API calls (merge button was broken, direct API used throughout). ~3-4 unidentified faces remain in this photo ("not sure on the Others" — Carey Franco).
- METHODOLOGY: All tagging done via JavaScript fetch() calls in Chrome DevTools due to merge button 404 bug. Workflow: rename → confirm → metadata for each identity. Production data is updated but local data/ files are NOT synced yet.

### DATA DIVERGENCE WARNING (Lesson 78 — READ BEFORE ANY PUSH)

**Production has data that local does NOT have.** Pushing local data/ files will OVERWRITE production changes.

**What's on production but NOT local:**
All Section 3 identity changes (8 people tagged via production API):

| Identity ID | Name | Operations | Metadata |
|---|---|---|---|
| a772360a-64f6-4daf-8312-fcc7586304a7 | Morris Franco | merge(039+399), rename, confirm | birth_year=1888, gender=M, ancestry_id=132508216815 |
| ac3b43b2-3e74-4237-ab71-b8ded0f8bfda | Isaac Israel Franco | merge(049+400), rename, confirm | birth_year=1893, gender=M, ancestry_id=132395618061 |
| 4a993942-2ed7-4cba-bb78-ada588853642 | Albert Cohen | confirm | gender=M |
| bac7731a-a1d2-4350-b528-c11f1b947b3a | Eleanore Cohen | rename, confirm | gender=F |
| e26383e0-ee4e-40bd-9f8a-e3ae87a9dfc5 | Ray Rica Franco | rename, confirm | gender=F, ancestry_id=132395618059 |
| d85b2279-caac-4e56-b572-5431c4be48e5 | Molly Benson | rename, confirm | gender=F |
| 9dfc300a-1c86-460a-85df-e62c6781eb6d | Herman Benson | rename, confirm | gender=M |
| 1549d2b4-5d1f-4b0d-8ef2-430087a76d67 | Belle Bennoun Franco | rename, confirm | gender=F, ancestry_id=132765098259 |

**Also on production from Section 2 (GEDCOM import, previous context):**
- 33 identities enriched with ancestry_id, birth/death dates, gender, places
- 19 relationships (5 spouse, 14 parent-child)
- ancestry_links.json created
- 31 birth year corrections from Section 1

**Safe to push:** Code changes ONLY (app/main.py merge button fix). Do NOT push data/ files.
**Before ANY data push:** Run `python scripts/sync_from_production.py` FIRST to pull production data locally, THEN merge local changes on top.
**Recovery:** If data is accidentally overwritten, this table + the Section 1/2 data changes log above contain enough detail to re-apply all changes via API.

### Section 4: Item 5 — Compare Upload Test (2026-02-21)

**Test photo:** `howie_frano_collection_59639822_10216844893127554_6438337993123037184_n.jpg` from `~/Downloads/rhodesli_photo_testing/`

**Results:**
- 17 faces detected in group photo
- Face 1 → Isaac Franco (54%, 53%) — **CORRECT** (confirmed by Nolan)
- Face 2 → Morris Franco (55%, 54%) — **CORRECT** (switched face, results updated)
- Face switching (Face 1/2/3 buttons) works functionally
- Herman Benson appeared as Possible Match for Face 2 at 38%
- Only 3/20 matches were named people (Isaac Franco x2, Morris Franco x2, Albert Cohen, Herman Benson). Rest were unidentified "Face #N"

**UX Issues Found:**

#### P0 — Compare Upload Not Saved
- [ ] COMPARE UPLOAD NOT IN PENDING QUEUE: The Compare page says "Photos are saved to help grow the archive" but the upload did NOT appear in /admin/pending (showed "0 uploads awaiting review"). Investigation found: uploads save to R2 immediately, but only enter pending_uploads.json if user clicks a "Contribute" button. The "saved to help grow the archive" message is misleading — it stores the file but doesn't queue it for admin review automatically. The Contribute button is at the very bottom of results and easy to miss. For the use case of community members uploading family photos, this is a major gap — most users won't scroll past results to find and click Contribute. [BACKLOG: yes, P0]

#### P1 — Loading & Feedback
- [ ] NO LOADING INDICATOR: Absolutely no loading indicator during compare upload processing. Page appears to hang completely. User thought upload failed. Need spinner, progress bar, or "Analyzing faces..." message. The loading indicator that was built (AD-121 area, block display + button disable + auto-scroll) either isn't wired to the compare flow or isn't visible. [BACKLOG: yes, P1]
- [ ] NO AUTO-SCROLL TO RESULTS: After upload completes, results appear below the fold. Page stays at the top showing the empty upload area. User sees no change and thinks upload failed. Must auto-scroll to results section. [BACKLOG: yes, P1]
- [ ] UPLOAD AREA DOESN'T RESET: After successful upload, the upload area still shows "Drop a photo here or click to browse" — should show the uploaded filename or a success state. [BACKLOG: yes, P2]

#### P1 — Face Selector UX
- [ ] FACE SELECTOR IS BLIND: Compare page uses "Face 1", "Face 2", etc. as text-only buttons with no visual indication of which face is which. No bounding boxes on the uploaded photo. Contrast with /photo/ page which draws face bounding boxes with name labels directly on the photo — dramatically better UX. The uploaded photo preview should have clickable face overlay boxes like the photo page does. [BACKLOG: yes, P1]

#### P2 — Confidence Labels
- [ ] CONTRADICTORY CONFIDENCE TIERS: "Strong Matches" section header says "High confidence — likely the same person" but individual cards show "Possible match" at 54%. "Possible Matches" header says "Moderate confidence — worth investigating" but cards show "Unlikely match" at 41%. The tier grouping thresholds and the per-card confidence labels use different scales. Need to align them. [BACKLOG: yes, P2]

#### P2 — Broken Thumbnails
- [ ] BROKEN FACE CROP THUMBNAILS: Face #17, #18, #20 showed empty/broken crop images (frame icon placeholder, no face). These are faces detected in the uploaded photo but the server-side crop generation failed or the crop URL is broken. [BACKLOG: yes, P2]

#### P1 — Missing Feature: Two-Photo Compare
- [ ] TWO-PHOTO COMPARE NOT SUPPORTED: Currently Compare only matches an uploaded face against the existing archive. There is no mode to upload TWO photos and compare faces between them (e.g., "is this person in photo A the same as this person in photo B?"). This was originally in scope and discussed at length. This is a core use case for family historians who have two photos and want to know if the same person appears in both. The architecture supports it (just compute cosine similarity between two uploaded embeddings) but no UI or route exists. See AD-117 Face Compare tiers. [BACKLOG: yes, P1]

#### P2 — Source/Collection Assignment
- [ ] NO SOURCE/COLLECTION ON COMPARE UPLOADS: If a user contributes a compare upload, there's no mechanism for them to specify source (e.g., "Howie Franco's Facebook") or collection. Admin would need to assign manually. Should prompt contributor for source/collection during contribute flow. [BACKLOG: yes, P2]

### Section 5: Item 6 — Estimate Page Test (2026-02-21)

**Test photo:** Same `howie_frano_collection_59639822_10216844893127554_6438337993123037184_n.jpg`
**User context:** Isaac Franco (born 1917) is in the photo, looks ~40s. User confirmed c.1962 is approximately correct.

**Two flows tested:**
1. **Upload flow** (POST /api/estimate/upload via HTMX) — uploaded test photo
2. **Archive selection flow** (GET /estimate?photo=d4fd0727068369ec) — clicked archive photo

#### Upload Flow Results
- 17 faces detected (consistent with Compare test)
- Estimated: c. 1962, Range: 1959–1965, Confidence: high
- Gemini analysis: B&W photo, white border, bouffant hairstyles, narrow ties, "Mad Men" era suits, sleeveless dresses, boat necklines — late 1950s to early 1960s
- Photo is NOT saved to pending_uploads.json (ephemeral storage only in uploads/estimate/ on R2)

#### Archive Selection Results (same photo in archive)
- Shows actual photo in result area
- Estimated: c. 1962, +/- 10 years, Low confidence
- "Based on scene analysis" — no per-face age evidence shown
- Has CTAs: Share Estimate | View Photo Page | Try Another

#### UX Issues — Comprehensive Estimate Page Audit

##### P0 — Upload Not Saved to Archive
- [ ] EST-001: ESTIMATE UPLOAD NOT IN PENDING QUEUE: Like Compare (Item 5), the estimate upload saves to R2 (`uploads/estimate/{id}.jpg`) but does NOT enter `pending_uploads.json`. No admin review path. Community members uploading family photos for date estimation have no way to contribute them to the archive. Same fundamental gap as Compare page. [BACKLOG: yes, P0]

##### P1 — Critical UX Gaps (Upload Flow)
- [ ] EST-002: NO UPLOADED PHOTO PREVIEW: Upload results show only text — face count, date estimate, Gemini analysis. The photo itself is NEVER displayed. User cannot confirm which photo was analyzed. Contrast with archive selection flow which shows the photo prominently. This is the single biggest UX gap — a date estimation tool should show the photo alongside the estimate. [BACKLOG: yes, P1]
- [ ] EST-003: NO LOADING INDICATOR VISIBLE: Code has a `#estimate-upload-spinner` div with `htmx-indicator` class, but it didn't appear during the ~30s processing time. The HTMX indicator CSS rule uses `display: inline` which may conflict with the spinner's layout. Same issue as Compare (logged in Item 5). User sees zero feedback during ML processing. [BACKLOG: yes, P1]
- [ ] EST-004: NO AUTO-SCROLL TO RESULTS: After upload completes, results appear below the upload area but page stays at top. User sees the unchanged upload zone and thinks nothing happened. Compare page has same issue. The `hx_target="#estimate-upload-result"` swaps content into a div below the form but doesn't scroll to it. [BACKLOG: yes, P1]
- [ ] EST-005: NO CTAs AFTER UPLOAD: Archive selection shows Share Estimate / View Photo Page / Try Another buttons. Upload results show NOTHING — no way to share, no "try another", no "contribute this photo". Dead end. User has to manually scroll back up or refresh. [BACKLOG: yes, P1]
- [ ] EST-006: UPLOAD AREA DOESN'T RESET: After successful upload, the upload zone still shows "Upload a photo to estimate its date" with the dashed border and upload icon — as if nothing happened. Should either show the uploaded filename/thumbnail, show a "Upload another" state, or collapse the upload area. [BACKLOG: yes, P1]

##### P1 — Inconsistency Between Upload vs Archive Flows
- [ ] EST-007: TWO COMPLETELY DIFFERENT RESULT FORMATS: Upload and archive selection produce dramatically different result UIs for the same feature. Upload: text-only (face count → estimate → range → confidence → Gemini text). Archive: photo + estimate + confidence badge + "How we estimated this" + CTAs. These should be the same layout. A user who tries upload first gets a broken-feeling experience; one who clicks an archive photo gets a polished one. [BACKLOG: yes, P1]
- [ ] EST-008: CONFIDENCE DISAGREES BETWEEN FLOWS: Same photo gets "high confidence, Range: 1959–1965" via upload (Gemini) but "Low confidence, +/- 10 years" via archive selection (internal pipeline). The upload path trusts Gemini's self-reported confidence; the archive path computes confidence from identified people with known birth years. These should be reconciled — or at minimum, the method should be clearly labeled so users understand why results differ. [BACKLOG: yes, P2]

##### P1 — Missing "Wow Factor" Features
- [ ] EST-009: NO FACE-BY-FACE BREAKDOWN (UPLOAD): Upload says "17 faces detected" but shows nothing about individual faces. The archive flow can show per-face age evidence cards (person name, birth year, apparent age, estimated year). Upload should detect faces, show face crop thumbnails, and for any that match known people, show per-person date evidence — this is the most compelling part of the tool. [BACKLOG: yes, P1]
- [ ] EST-010: NO FACE BOUNDING BOXES ON PHOTO: Neither flow draws face bounding boxes on the photo (Compare does for uploaded photos). For date estimation, showing detected faces with age estimates overlaid would be powerful — "We found 17 people and estimated their ages" with clickable face boxes. [BACKLOG: yes, P2]
- [ ] EST-011: NO VISUAL EVIDENCE CLUES: Gemini analysis mentions specific visual clues (hairstyles, suit styles, dress styles) but these are just text. Annotating the photo with callouts or highlighted regions ("narrow ties typical of 1960s" with an arrow) would be genuinely impressive and educational. Longer-term but high wow factor. [BACKLOG: yes, P3]

##### P2 — Layout & Polish
- [ ] EST-012: RESULTS SANDWICHED BETWEEN UPLOAD AND GALLERY: Upload results appear between the upload zone (above) and "Select a Photo" grid (below). The gallery should collapse or hide when showing upload results, or results should replace the entire content area. Currently feels like results are squeezed in as an afterthought. [BACKLOG: yes, P2]
- [ ] EST-013: "SELECT A PHOTO" GRID LACKS CONTEXT: Archive photo thumbnails show only face count badges. No photo title, collection name, date range, or identifiable people shown. For date estimation, the most interesting photos are group photos with many faces — but user can't tell which photos have identified people (which produce better estimates). Should show "3 of 6 identified" or highlight photos with strong estimates. [BACKLOG: yes, P2]
- [ ] EST-014: ARCHIVE RESULT SHOWS "+/- 10 YEARS" — TOO VAGUE: Low confidence with +/- 10 years means the estimate is essentially 1952–1972. This is barely useful. When confidence is this low, the UI should say something like "Not enough data for a precise estimate — identify more people to narrow it down" rather than presenting a confident-looking "Estimated: c. 1962" heading. [BACKLOG: yes, P2]
- [ ] EST-015: "HOW WE ESTIMATED THIS" EMPTY: Archive selection shows "How we estimated this" heading with just "Based on visual analysis. Identify more people to improve this estimate." — no actual methodology explanation. Should show what signals were used (photo style, clothing, hair, known people if any). The upload flow actually DOES show this via Gemini analysis, but the archive flow doesn't. [BACKLOG: yes, P2]
- [ ] EST-016: "SHARE ESTIMATE" BUTTON — WHAT DOES IT SHARE? Only appears on archive flow. Appears to be a share/link button but unclear what URL/content it shares. Clipboard? Social media? No tooltip or feedback. [BACKLOG: yes, P3]

##### P2 — Performance & Speed
- [ ] EST-017: UPLOAD PROCESSING TIME ~30 SECONDS: The upload took approximately 30 seconds with zero user feedback. Breakdown: face detection (InsightFace hybrid) + Gemini API call. For the "wow factor", this needs to be under 10 seconds or show progressive results (faces detected first → then Gemini analysis streams in). SSE/streaming architecture (AD-121) would help here. [BACKLOG: yes, P2]

##### P3 — Delight / Wow Factor Opportunities
- [ ] EST-018: NO TIMELINE VISUALIZATION: The date estimate could be shown on a visual timeline with key historical events for context ("Your photo was likely taken around the time of the Cuban Missile Crisis, 1962"). For a heritage archive, connecting family photos to historical context would be genuinely moving and shareable. [BACKLOG: yes, P3]

#### Summary
The Estimate page has two dramatically different quality levels:
- **Archive selection**: Decent — shows photo, has CTAs, clean layout. But lacks depth (no per-face evidence, low confidence on most photos).
- **Upload flow**: Broken-feeling — no photo preview, no loading indicator, no CTAs, results squeezed in. The Gemini analysis is actually BETTER content than the archive flow gets, but the presentation is far worse.

The core value proposition ("When was this photo taken?") is compelling and the ML results are reasonable (c. 1962 for a ~1960 photo is solid). But the UX actively undermines the results. A first-time user uploading a family photo would: (1) see no loading indicator and think it's broken, (2) not scroll down to see results, (3) see text-only results with no photo, (4) hit a dead end with no next action. Every step loses engagement.

**Priority for making this shippable:**
1. Show the uploaded photo in results (EST-002)
2. Fix loading indicator (EST-003)
3. Auto-scroll to results (EST-004)
4. Add CTAs to upload results (EST-005)
5. Show face-by-face breakdown (EST-009)
6. Unify upload and archive result layouts (EST-007)

### Remaining Plan (Items 6-11)

**Items 6-7: Interactive feature tests (requires Nolan)**
- Item 6: Estimate page — face counts, pagination, Gemini analysis display
- Item 7: Quick-Identify — click unidentified face → inline naming, "Name These Faces" mode

**Item 8: Visual walkthrough (partly autonomous)**
- Incognito browsing: photos, person pages, timeline, map, 404 handling
- Admin views: health endpoint, version footer

**Items 9-11: Wrap-up (mostly autonomous)**
- Item 9: Compile bug list, prioritize (8 P0/P1 issues already logged from Section 3)
- Item 10: Production smoke test (`python scripts/production_smoke_test.py`)
- Item 11: UX tracker update, push CODE ONLY to production, session log finalization

**Push strategy:**
1. Push CODE changes only (merge button fix) — `git push origin main`
2. Do NOT include data/ in the push
3. After push, verify production still has all tagged identities (check photo page)
4. If data sync needed later, ALWAYS pull production first
