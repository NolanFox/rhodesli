# Session 83a Prompt: Critical UX Fixes — User Feedback Response

## PRIORITY

A real community user (Claude Benatar, FB group admin for "Jews of Rhodes") is blocked. Three core features are silently broken. Fix them NOW.

## MANDATORY PRE-WORK

1. Read `docs/session_context/session-83a-context.md` (copy from this prompt's companion file)
2. Read `ALGORITHMIC_DECISIONS.md`, `ROADMAP.md`, `SESSION_HISTORY.md`
3. Read the codebase files related to each workstream BEFORE writing any code
4. Set up git worktrees for parallel work (see Workstream structure below)

## WORKSTREAMS — PARALLELIZE WITH WORKTREES

Create these worktrees and work in parallel where possible:

```bash
git worktree add ../rhodesli-83a-naming fix/83a-naming
git worktree add ../rhodesli-83a-identify fix/83a-identify  
git worktree add ../rhodesli-83a-compare fix/83a-compare
git worktree add ../rhodesli-83a-facecard fix/83a-facecard-ux
```

Merge order: naming → identify → compare → facecard-ux (naming is dependency for others)

---

### Workstream 1: NAMING (P0-3, P2-5, P2-6) — `fix/83a-naming`

**Problem:** There is no way to set a person's primary display name. The only name field is "Maiden Name" which prepends "née". A confirmed person can end up with no name at all.

**Requirements:**
- [ ] Add a **"Display Name" / "Full Name"** field as the PRIMARY name field in Edit Details (Focus view)
- [ ] "Maiden Name" becomes a secondary/optional field (keep it, but it's not the main name)
- [ ] Remove automatic "née" prefix from display — if maiden name is set, show it contextually, not as the primary label
- [ ] The display name field must be the FIRST field in the Edit Details form
- [ ] When a name is saved via Edit Details, it must update the person's display name everywhere: face cards, People list, person profile page, search results
- [ ] Saving a display name in Focus view must actually persist and display correctly (verify by refreshing the page and checking the People list)

**Verification gate:**
1. Navigate to New Matches → Focus view on any unidentified person
2. Click Edit Details
3. Type "Isaac Cohen" in Display Name field
4. Click Save
5. Confirm the person
6. Navigate to People → verify "Isaac Cohen" appears as the name
7. Navigate to `/person/{uuid}` → verify "Isaac Cohen" shows as the heading
8. Search for "Isaac Cohen" in admin search → verify it appears

---

### Workstream 2: HELP IDENTIFY FIX (P0-1, P1-3, P1-4, P2-7, P2-10) — `fix/83a-identify`

**Problem:** The public Help Identify page accepts submissions but they silently disappear. No audit trail. No approval created. Users like Claude Benatar think they've helped but nothing happened.

**Requirements:**
- [ ] **Fix the submission pipeline end-to-end:** form submission → creates a pending annotation/approval → appears in admin Approvals tab → logged in Audit Log
- [ ] Add server-side logging for every Help Identify submission (success AND failure) with timestamp, person UUID, submitted name, submitter email/info
- [ ] If user is logged in, auto-fill their email and don't require it
- [ ] If user is logged in as admin, consider auto-approving or at minimum showing admin-specific UI (e.g., "You're an admin — apply this name directly?")
- [ ] After successful submission, persist the confirmation state — page should show "You submitted: Isaac Cohen" even after refresh (use session/cookie or query param)
- [ ] When a name suggestion is submitted AND approved, the person should be moved toward confirmation (not left in "New Matches" indefinitely)
- [ ] Add error handling: if submission fails, show a clear error message to the user — NEVER show "Thank you!" if the backend didn't actually save
- [ ] Test the full flow: submit name → check approvals → approve → check person is named and confirmed → check audit log

**Verification gate:**
1. Log out. Go to `/identify/{uuid}` for an unidentified person
2. Fill in name, relationship, email
3. Submit → verify "Thank you" appears
4. Log in as admin → go to Approvals → verify the submission appears
5. Approve it → verify person is named and moved toward confirmation
6. Check Audit Log → verify entry exists with timestamp and details
7. Go back to identify page → verify it shows the submission was already made (or shows the person is now identified)

---

### Workstream 3: COMPARE FIX (P0-2, P2-9) — `fix/83a-compare`

**Problem:** Compare pipeline runs to completion (all 5 steps check green) but the result page 404s with "Comparison Not Found."

**Requirements:**
- [ ] Debug and fix the compare result storage/retrieval pipeline — the result must be persisted and retrievable at the result URL
- [ ] Verify the full pipeline: upload photo → detect faces → search archive → estimate date → show results page with matches
- [ ] If no matches found, show "No matches found" — not a 404
- [ ] If the comparison result expired or was cleaned up, show a helpful message ("This result has expired. Please try again.") — not a generic 404
- [ ] Add server-side logging for compare requests: photo received, faces detected count, matches found count, result UUID, success/failure
- [ ] Test with the specific photo Claude Benatar sent (group family photo) — verify it returns results or at minimum a valid "no matches" page

**Verification gate:**
1. Go to `/compare`
2. Upload a test photo containing at least one face
3. Wait for all pipeline steps to complete
4. Verify result page loads at `/compare/result/{uuid}` with actual results
5. Upload a photo with no faces → verify graceful handling
6. Upload a photo, note the result URL, wait 5 minutes, reload → verify it still works

---

### Workstream 4: FACE CARD UX (P1-1, P2-2, P2-3, P2-4, P2-8) — `fix/83a-facecard-ux`

**Problem:** Face cards have regressed from ~10 sessions ago. Find Similar is dead, no search by person number, inconsistent capabilities across views, no GEDCOM linking.

**Requirements:**
- [ ] **Fix Find Similar button** in New Matches (Browse view AND Focus view) — must actually trigger similarity search and display results
- [ ] **Add person search/filter in admin** — typing "445" or "Isaac Cohen" in the admin search box should filter face cards to matching results (by person number OR name)
- [ ] **Consistent face card actions across all views:** Every face card in New Matches (Browse), New Matches (Focus), People, and Discoveries should have the same core actions available: View Photo, Find Similar, Edit Details, and a link to the person's public profile page
- [ ] **Bidirectional linking between admin and public views:** 
  - Face card in admin should have a "View Public Page" link → `/person/{uuid}`
  - Person public page should have "View in Admin" link (for logged-in admins) → Focus view
  - Both should be one-click, not requiring URL manipulation
- [ ] **Add GEDCOM link to face card** — if person is linked to a GEDCOM individual, show a link/icon on the face card; if not, show "Link to GEDCOM" action
- [ ] **Verify all face card buttons actually work** — click every button on a face card in every view and verify it does something (no dead buttons)

**Verification gate:**
1. New Matches Browse view: click Find Similar on any card → verify results appear
2. New Matches Focus view: click Find Similar → verify results appear
3. Type "445" in admin search → verify Person 445 appears
4. Type "Isaac Cohen" in admin search → verify the person appears (after naming fix is merged)
5. On any face card, click every action button → verify none are dead
6. From admin face card, click "View Public Page" → verify correct person page loads
7. From person public page (logged in as admin), click "View in Admin" → verify correct focus view loads

---

## AFTER ALL WORKSTREAMS

### Integration Verification (do this after merging all branches)

1. **Full Claude Benatar scenario replay:**
   - Start at the Isaac Cohen photo page
   - Use Help Identify to submit the name "Isaac Cohen" → verify it works
   - Go to Compare, upload the group photo → verify results page loads
   - As admin, approve the identification → verify Isaac Cohen appears in People with correct name
   - Verify Isaac Cohen's person page shows his name, photo, and collection source

2. **Regression check:**
   - Existing confirmed people (Benvenuta/Bessie Halio Franco, Amada/Mary Gormezano Halio, Rebecca Rousso Gormezano, Samuel Israel Gormezano) still appear correctly in People
   - Existing approval/reject workflow still works
   - Photo upload still works
   - Face detection pipeline still works

### Deploy

```bash
git push origin main  # Deploy via git push, NOT Railway dashboard
```

### Post-Deploy Smoke Test

```bash
# Test Help Identify submission
curl -X POST https://rhodesli.nolanandrewfox.com/api/identify/{test-uuid} \
  -d '{"name": "Test Name", "relationship": "test", "email": "test@test.com"}'

# Test Compare upload
curl -X POST https://rhodesli.nolanandrewfox.com/api/compare \
  -F "photo=@test_photo.jpg"

# Verify the result URL returns 200
curl -s -o /dev/null -w "%{http_code}" https://rhodesli.nolanandrewfox.com/compare/result/{uuid}
```

---

## MANDATORY DOCUMENTATION UPDATES

### ALGORITHMIC_DECISIONS.md

Update with full decision provenance for every change:
- What was the naming schema before? What is it now? Why?
- How does Help Identify submission flow work now vs before? What was broken?
- What was wrong with Compare result storage? How was it fixed?
- Any changes to face card component architecture

### SESSION_HISTORY.md

Add session 83a entry summarizing:
- Origin: Claude Benatar user feedback
- All P0/P1/P2 bugs found and fixed
- Current state of the system after fixes

### ROADMAP.md

- Remove/mark completed any items addressed in this session
- Add follow-up items identified but not fixed in this session
- Keep under 150 lines

### Feedback Log

Create `docs/feedback/2026-03-02-claude-benatar.md` with:
- Verbatim feedback (what he asked, what confused him)
- Screenshots referenced (list the scenarios)
- What was broken that he would have encountered
- What was fixed in response
- Follow-up items for future sessions

---

## CONSTRAINTS

- **No file in docs/ over 300 lines**
- **ROADMAP.md stays under 150 lines**
- **Session context files go to `docs/session_context/`**
- **Use `/clear` between phases, NOT `/compact`** — `/compact` is lossy, `/clear` + re-read from disk is correct
- **Deploy via `git push`, not Railway dashboard**
- **Every change must be verifiable in production** — if you can't verify it works on rhodesli.nolanandrewfox.com after deploy, it's not done
- **Update ALGORITHMIC_DECISIONS.md** with full provenance for every decision: accepted, rejected, why, source
- **No dead buttons. No silent failures. No broken links.** — if something doesn't work yet, disable it with a clear "Coming soon" or remove it entirely
