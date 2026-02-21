# Session 49B Interactive Log — 2026-02-20

## Session Goals
- [ ] Birth year bulk review (accept/reject ML estimates)
- [ ] GEDCOM upload (real family data)
- [ ] Visual walkthrough (admin + public views)
- [ ] Autonomous UX audit (browser-driven)
- [ ] Synthesis and prioritization

## Section Status
- [x] Section 0: Session infrastructure (2026-02-20)
- [x] Section 1: Birth year bulk review (2026-02-20) — 31 estimates reviewed. 28 accepted (10 exact, 18 corrected). ML accuracy: ~32% exact, ~48% within 2 years, mean absolute error ~5.4 years.
- [x] Section 2: GEDCOM upload (2026-02-21) — Real GEDCOM imported (21,809 individuals). 33 identities matched to Ancestry tree. User reviewed all matches in CSV, corrected 15 Ancestry IDs. 19 relationships built (5 spouse, 14 parent-child). 33 identities enriched with GEDCOM birth/death dates, places, gender, Ancestry URLs. Birth years from Section 1 preserved through production merge. ancestry_links.json created. Lesson 78 added (production-local data divergence).
- [-] Section 3: Identity tagging — Thanksgiving Eve 1946 photo (2026-02-21, in progress)
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
- Remaining 6: Albert Cohen, Eleanore Cohen, Ray Franco, Molly Benson, Herman Benson, Belle Franco — awaiting user identification of which face is which in the photo.
