# Session 83a Continuation — Address ALL Remaining Gaps

## CONTEXT
Session 83a fixed 4 workstreams (Display Name, Help Identify, Compare 404, Card Search) and added admin auto-confirm on Help Identify. But a review against the original user feedback found 5 remaining gaps. ALL must be fixed this session.

## ORIGINAL FEEDBACK SOURCE
Nolan's original feedback (paraphrased from conversation):
- Claude Benatar confused by "Unidentified Person" label when photo clearly has the person's name
- Not clear what to do next on any page
- Find Similar dead in New Matches
- No way to search for person 445 in admin (fixed ✓)
- No clear linking between admin and share view
- Face cards not consistent between sections
- Can't link to GEDCOM from face card
- Compare not intuitive/discoverable
- Email shown to logged-in users on sharing page (fixed ✓)
- Help Identify page resets on refresh with no indication anything was submitted
- Submissions didn't show in approvals (fixed ✓)
- No logging around submissions (fixed ✓)
- Adding name doesn't confirm (fixed ✓)
- Naming impossible — only "Maiden Name" field (fixed ✓)
- Compare 404 (fixed ✓)

## THE 5 REMAINING GAPS — ALL MUST BE FIXED

### Gap 1: "Unidentified Person" Contextual Explanation (P2-1)
**Problem:** Photo clearly shows "COHEN Isaac" with biographical text, but the app says "Unidentified Person #445". Claude Benatar's first question was "why does it say unidentified?"
**Requirement:**
- On the person page (`/person/{uuid}`), if the person is in INBOX or PROPOSED state, add a clear explanation: "This person hasn't been identified yet — the AI detected a face but doesn't know who they are. Can you help?"
- On the identify page (`/identify/{uuid}`), the heading already says "Can you identify this person?" which is good, but add a brief note below: "The AI found this face in a heritage photo but couldn't determine their name."
- On face cards in the admin browse view, keep "Unidentified Person #N" but add a subtle tooltip or subtitle: "Not yet confirmed"
**Files:** `app/main.py` (person page, identify page, face card component)
**Tests:** Verify the explanation text appears on person page for unidentified, does NOT appear for confirmed people

### Gap 2: Bidirectional Admin/Public Links (P2-3)
**Problem:** Jumping between person page, focus view, and browse view requires knowing URLs. "Edit Name" and "View in Admin" go to the same place.
**Requirement:**
- Person public page (`/person/{uuid}`): For admin users, show a clear "Edit in Admin" button that links to `/?section=to_review&view=focus&current={uuid}` (or confirmed section if confirmed)
- Focus view: Show a "View Public Page" link that goes to `/person/{uuid}`
- Browse view face card: Each card should have a "Profile" link to `/person/{uuid}` (verify this exists, add if missing)
- The identify page (`/identify/{uuid}`): For admin users, show "View in Admin" link
**Files:** `app/main.py` (person page, focus view, browse view cards, identify page)
**Tests:** Verify links exist and point to correct URLs for both admin and non-admin views

### Gap 3: Face Card Consistency Between Views (P2-4)
**Problem:** Different capabilities/layouts in New Matches Browse, New Matches Focus, People, Discoveries. Some have Find Similar, some don't. Some have Profile links, some don't.
**Requirement:**
- Audit ALL face card renderings across: New Matches Browse, New Matches Focus, People section, Discoveries, Help Identify section
- Every face card MUST have these core actions: View Photo, Find Similar, Profile link (`/person/{uuid}`)
- Admin cards additionally get: Edit Details (or link to Focus view), Confirm/Skip/Reject (where applicable)
- Document which actions each view currently has vs should have
- Fix any missing actions
**Files:** `app/main.py` (multiple card rendering functions)
**Tests:** For each view, verify the expected action buttons/links are present

### Gap 4: Compare Discoverability (P2-9)
**Problem:** Claude Benatar wanted to "match this person with this photo" but couldn't figure out how. The Compare feature exists but isn't discoverable from the context where users need it.
**Requirement:**
- On person pages (`/person/{uuid}`), add a "Compare with a photo" CTA button that links to `/compare` (or pre-fills with this person's face)
- On the identify page, add a note: "Have a photo that might match? Try our Compare tool" with link
- On face cards with "Find Similar" results, if no strong match is found, suggest: "Don't see a match? Upload a photo to compare"
**Files:** `app/main.py` (person page, identify page, similar results section)
**Tests:** Verify compare CTAs appear on person page and identify page

### Gap 5: Help Identify Submission Persistence (P2-10)
**Problem:** After submitting on the Help Identify page, refreshing resets the page with no indication anything was submitted. Users don't know their contribution was received.
**Requirement:**
- After successful submission, return a success state that shows "You submitted: [name]" with timestamp
- Use a query parameter (e.g., `?submitted=true&name=Isaac+Cohen`) so the success state survives refresh
- On page load, check for the query param and show the success banner if present
- For admin direct-apply, the success message already shows (verify it includes person link)
**Files:** `app/main.py` (identify page, respond endpoint)
**Tests:** Verify that after submission, the page shows confirmation; verify query param preserves state

## PARALLELIZATION PLAN

These can be parallelized into 2-3 tracks since they touch different parts of app/main.py:

**Track A (worktree):** Gaps 1 + 4 — Person page/identify page additions (contextual text + compare CTAs)
**Track B (worktree):** Gap 3 — Face card consistency audit + fixes (browse cards, focus cards, people cards)
**Track C (main or worktree):** Gaps 2 + 5 — Navigation links + submission persistence

HOWEVER: All tracks modify `app/main.py` so merges will need conflict resolution. Consider doing them sequentially if conflicts are too complex, or use very targeted edits.

## VERIFICATION GATE — MUST USE CLAUDE CHROME (not Playwright)

After all fixes deployed, verify EACH gap in Chrome browser:
1. Go to `/person/{uuid}` for an unidentified person → see contextual explanation
2. From person page (as admin) → click "Edit in Admin" → lands in Focus view
3. From Focus view → click "View Public Page" → lands on person page
4. Check face cards in Browse, Focus, People, Discoveries → all have consistent actions
5. On person page → see "Compare with a photo" CTA
6. On identify page → see Compare suggestion
7. Submit on identify page → refresh → success banner persists

## CONSTRAINTS
- No file over 300 lines in docs/
- Run tests before every commit
- Commit after every sub-task
- Deploy via git push
- Every change verified in Chrome browser
- Update session log, assessment, AD entries as needed
