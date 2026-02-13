# PRD: Community Contributions v2 — Suggestion Lifecycle

**Author:** Nolan Fox
**Date:** 2026-02-13
**Status:** Implemented (Session 25, 2026-02-13)
**Drives:** Session 25

---

## Problem Statement

Community members can now suggest names for unidentified faces (v0.19.0 guest flow + Session 24b fixes). Claude Benatar successfully submitted "Sarina Benatar Saragossi" via poisson1957@hotmail.com and Nolan approved it. The basic pipeline works.

However, the suggestion has no visible **lifecycle**. After submitting, the contributor sees zero evidence their work was saved. Other visitors can't see or confirm existing suggestions. The admin approval page lacks face thumbnails, undo capability, and audit history. Notifications don't fire.

The result: the app feels broken even when it's working. Contributors doubt their submissions went through. Admins make blind approvals. The community confirmation signal — which could dramatically reduce admin workload — doesn't exist.

## Who This Is For

1. **Anonymous visitors** — someone's aunt who got a WhatsApp link and recognizes a face
2. **Logged-in contributors** — people like Claude Benatar who have accounts and deep genealogical knowledge
3. **Admin (Nolan)** — reviews, approves/rejects suggestions, manages the identity database

### Contributor Mental Model Gap (from Claude Benatar testing)

Claude Benatar's first question after uploading: "does your system do facial recognition with other pictures?" He then suggested uploading identified people to have faces to compare against, not understanding that the system already does this automatically. His mental model: upload → manually tag → system compares. Actual model: upload → face detection → automatic matching against all known faces → human confirms/corrects.

**Implication:** The app needs clearer communication of what happens after upload. A brief status message like "3 faces detected — checking against 261 known faces" would set expectations and demonstrate value immediately. The About page should explain the workflow concisely.

## User Flows

### Flow 1: Contributor Submits a Suggestion

**Current state (what works):**
1. Visitor arrives at `?section=to_review`
2. Clicks on a face in Photo Context modal
3. Types a name in the search input
4. Clicks "Suggest [name]" → saves as `pending_unverified` (anonymous) or `pending` (logged in)
5. Green toast appears for ~3 seconds: "Your suggestion has been submitted for review"
6. Toast disappears → **screen looks identical to before submission** ← THIS IS THE PROBLEM

**Target state:**
1-5. Same as above
6. After toast, the face popup transforms:
   - Input field replaced with: "✓ You suggested: [name] — Pending review"
   - "Suggest another name" link below (collapses back to input if clicked)
   - The face overlay on the photo gets a small badge icon (e.g., 💬 or a colored dot) indicating a suggestion exists
7. If the contributor navigates away and comes back to the same face:
   - The popup shows existing suggestions: "[name] suggested by 1 person"
   - Option to "+1 Agree" if they didn't submit it, or "You suggested this" if they did
8. At the photo level (before clicking any face), faces with pending suggestions show a subtle visual indicator (e.g., amber border instead of the default, or a small badge)

### Flow 2: Second Contributor Confirms a Suggestion

1. A different visitor arrives and clicks the same face
2. They see: "[name] (suggested by 1 person)" with an "I Agree" button
3. They can also type a different name if they disagree
4. Clicking "I Agree" increments the confirmation count
5. Same contributor cannot confirm the same suggestion twice (tracked by session cookie for anonymous, by user ID for logged in)
6. Admin approval card shows: "Suggested by poisson1957@hotmail.com, confirmed by 2 others"

### Flow 3: Admin Reviews and Approves

**Current state issues:**
- Approval cards show raw identity UUIDs (`48ac1614-7e4...`) instead of face thumbnails
- No way to see which face/photo the suggestion is for without navigating away
- No undo after approving/rejecting
- No "Skip" for later review
- Duplicate submissions create duplicate cards instead of being collapsed
- No audit log of past approvals/rejections
- After clicking Approve, unclear what happened downstream

**Target state:**
1. Admin navigates to `/admin/approvals`
2. Each card shows:
   - **Face thumbnail** (the actual face crop being identified)
   - **Photo thumbnail** (the source photo, smaller, for context)
   - Suggested name, who suggested it, confirmation count
   - Approve / Reject / Skip buttons
3. Clicking **Approve**:
   - Face is assigned to the identity (existing or newly created)
   - Card animates to "Approved" state with green highlight (stays visible on page)
   - Undo button appears for 10 seconds
   - Audit log entry created: `{action: "approved", suggestion: "...", admin: "...", timestamp: "..."}`
4. Clicking **Reject**:
   - Card animates to "Rejected" state with red highlight
   - Undo button appears for 10 seconds
   - Audit log entry created
5. Clicking **Skip**:
   - Card moves to bottom of list (or a separate "Skipped" tab)
   - Remains reviewable later
6. Duplicate suggestions for the same face are **collapsed** into a single card:
   - Shows the most-suggested name prominently
   - If multiple different names were suggested, shows all with counts
   - "3 people suggested 'Sarina Benatar Saragossi', 1 suggested 'Sarina Saragossi'"
7. **Audit history** accessible via a link: shows all past approvals/rejections with timestamps

### Flow 4: Notifications

1. When a new suggestion arrives:
   - In-app: Badge count on "Approvals" in sidebar increments (this may already work)
   - Email: Admin receives email notification (batched, not per-suggestion — e.g., daily digest or after 5 new suggestions)
2. When admin approves a suggestion from a logged-in contributor:
   - In-app: Contributor sees a notification on their next visit: "Your suggestion 'Sarina Benatar Saragossi' was approved!"
   - Email (stretch): Optional email to contributor

## Acceptance Criteria (Playwright Tests)

These tests define "done." They must be written BEFORE implementation and must FAIL initially.

```
TEST 1: Suggestion state persists visually
  - Submit a name suggestion for a face
  - Assert: face popup shows "You suggested: [name]"
  - Assert: face overlay has visual indicator (badge/border change)
  - Navigate away and return to same face
  - Assert: suggestion is still visible

TEST 2: No duplicate submissions
  - Submit a name suggestion for a face
  - Attempt to submit the same name again for the same face
  - Assert: second submission is blocked or deduplicated
  - Check admin/approvals: only 1 card exists

TEST 3: Community confirmation
  - User A suggests "Sarina Benatar Saragossi" for a face
  - User B (different session) views the same face
  - Assert: User B sees the existing suggestion with "I Agree" option
  - User B clicks "I Agree"
  - Assert: confirmation count increments
  - User B tries to agree again
  - Assert: blocked (already confirmed)

TEST 4: Admin approval card has face thumbnail
  - Guest submits a suggestion
  - Admin navigates to /admin/approvals
  - Assert: card contains a face crop image (not just UUID text)
  - Assert: card contains photo context thumbnail

TEST 5: Admin approval creates identity
  - Admin clicks Approve on a suggestion
  - Assert: the face is now assigned to the suggested identity
  - Assert: the identity appears in the People list
  - Assert: audit log entry exists

TEST 6: Admin undo
  - Admin approves a suggestion
  - Assert: undo button appears
  - Admin clicks undo within 10 seconds
  - Assert: suggestion returns to pending state

TEST 7: Admin skip
  - Admin clicks Skip on a suggestion
  - Assert: card moves to bottom or separate tab
  - Assert: card is still accessible for later review

TEST 8: Duplicate collapse
  - 3 anonymous users submit "test name" for the same face
  - Admin views /admin/approvals
  - Assert: 1 card (not 3), showing "suggested by 3 people"

TEST 9: Annotation persistence
  - Log in as contributor
  - Navigate to an identity page
  - Submit a Bio annotation with text "Test annotation"
  - Assert: annotation appears on the page after submission
  - Refresh the page
  - Assert: annotation still visible (persisted to disk)

TEST 10: "+205 more" is clickable
  - Navigate to Help Identify focus mode
  - Assert: "+N more" element in Up Next is a clickable link
  - Click it
  - Assert: navigates to full unidentified faces list

TEST 11: Load More filters to unidentified
  - Navigate to Help Identify focus mode
  - Click "Load More" on match candidates
  - Assert: all displayed candidates are unidentified (no named identities)

TEST 12: Tab state is visually distinct
  - Navigate to New Matches (to_review)
  - Assert: "Ready to Confirm" tab has active/selected styling
  - Click "Unmatched" tab
  - Assert: "Unmatched" tab now has active styling, "Ready to Confirm" is muted
  - Assert: content changes to show unmatched faces
```

### Flow 5: Annotation Persistence (Critical Bug)

**Current state:** Claude Benatar submitted a Bio annotation ("A mi querida Estrella de tu hermano Samuel") on Unidentified Person 361 via the "Add annotation" form. After clicking Submit, the annotation disappeared — the form reset to empty. The data appears lost.

**Target state:**
- Annotations submitted via the form persist to disk immediately
- After submission, the annotation appears on the identity/photo page (not just a toast)
- Annotations from community contributors are tagged with submitter info
- All annotation types work: Caption, Date, Location, Story, Source/Donor, Bio

### Flow 6: Help Identify UX Improvements (Claude Benatar Feedback)

**Issue 6a: "+205 more" is not clickable**
In the "Up Next" carousel at the bottom of Help Identify focus mode, the "+205 more" element is a dead end. Clicking it does nothing.
**Target:** Clicking "+205 more" navigates to the full unidentified faces list (View All mode).

**Issue 6b: "Load More" shows already-identified people**
When clicking "Load More" in the match candidates list, identified people appear alongside unidentified ones. Claude Benatar's feedback: "I should only see people not identified, not those already identified."
**Target:** Match candidates list filters to unidentified faces by default. Optional toggle to "Show all" if admin wants to see identified matches too.

**Issue 6c: "Ready to Confirm" vs "Unmatched" tab state is confusing**
The "3 Ready to Confirm" pill stays green even after clicking "1 Unmatched." The content changes but there's no visual indication which tab is active — you have to check the URL or notice the face count changed. Users don't know which view they're in.
**Target:** Active tab gets a distinct selected state (brighter background, underline, or border). Inactive tab is visually muted. Standard tab UX.

**Issue 6d: Tag at upload time (stretch)**
Contributors want to tag faces immediately when uploading, before admin approval. Currently tagging requires the photo to be fully processed first.
**Target (stretch):** Allow provisional tags during upload that get saved when the photo is approved. At minimum, allow contributors to add captions/notes during upload that carry through to the processed photo.

### Flow 7: Community Photo Visibility (Bug Fix)

**Current state:** Claude Benatar uploaded "Sarina2.jpg" — it was processed and appears under "Community Submissions" filter. But:
- Sidebar photo count (156) didn't increment to reflect community photos
- Community photos may not appear in default "All" photos view without the filter

**Target state:**
- Community photos appear in default photos view alongside all other photos
- Sidebar count reflects all photos including community submissions
- Photo count updates immediately after upload approval

### Flow 8: Upload Processing Pipeline (Automation)

**Current state:** After admin approves an upload, someone must manually run `download_staged.py` → move to `raw_photos/` → `ingest_inbox` → upload to R2 → push data. Claude Benatar's second photo (`472157630_10170853657825346...jpg`) sat unprocessed in production staging because no one ran the scripts after approving.

**Target state:** Single command: `./scripts/process_uploads.sh`
- Downloads all staged photos from production
- Moves them to `raw_photos/`
- Runs face detection via `ingest_inbox`
- Uploads processed photos + face crops to R2
- Updates production data
- Idempotent — safe to run repeatedly, skips already-processed photos
- Prints summary: "Processed N new photos, M faces detected"

**Stretch:** Automatic processing triggered by admin approval (no manual script needed). But the one-command script is the minimum viable fix.

## Out of Scope

- Real-time WebSocket updates (polling/page refresh is fine)
- Email notifications beyond basic (complex digest logic)
- Contributor reputation/scoring system
- Merge suggestions from contributors (already specced separately)
- Mobile-specific layouts (should work but not optimized this session)

## Data Model Changes

Annotations need additional fields:
```json
{
  "id": "uuid",
  "face_id": "...",
  "suggested_name": "Sarina Benatar Saragossi",
  "suggested_identity_id": "..." ,
  "submitted_by": "poisson1957@hotmail.com" | "anonymous",
  "session_id": "...",
  "status": "pending" | "approved" | "rejected" | "skipped",
  "confirmations": [
    {"by": "anonymous", "session_id": "abc123", "timestamp": "..."},
    {"by": "user@email.com", "timestamp": "..."}
  ],
  "reviewed_by": "admin@email.com",
  "reviewed_at": "2026-02-13T...",
  "created_at": "2026-02-13T..."
}
```

Audit log (new):
```json
{
  "action": "approved" | "rejected" | "undone",
  "annotation_id": "...",
  "admin": "nolanfox@gmail.com",
  "timestamp": "...",
  "details": "..."
}
```

## Technical Constraints

- FastHTML + HTMX stack (no React, no SPA)
- JSON file storage (no Postgres migration yet)
- Session cookies for anonymous dedup tracking
- HTMX partial swaps for in-place UI updates (no full page reloads)
- Must preserve all existing test data including Claude Benatar's real submission

## Priority Order

1. **Annotation persistence (Flow 5)** — CRITICAL: data loss bug. Claude Code claims fixed but annotation STILL not visible in browser. Needs Playwright test.
2. **Suggestion state visibility (Flow 1)** — highest UX impact, fixes "did it work?" problem
3. **Admin approval with thumbnails (Flow 3)** — fixes blind approval problem
4. **Help Identify UX: "+205 more" clickable + filter unidentified + tab state (Flow 6a, 6b, 6c)** — direct user feedback
5. **Duplicate dedup + collapse (Flow 3.6)** — prevents card spam (annotation was submitted twice because no feedback)
6. **Upload processing script (Flow 8)** — `./scripts/process_uploads.sh` one-command pipeline
7. **Community photo visibility (Flow 7)** — sidebar count, default view inclusion
8. **Admin undo + skip + audit (Flow 3.3-3.7)** — admin workflow completeness
9. **Community confirmation (Flow 2)** — multiplier effect, needs 1-6 first
10. **Tag at upload time (Flow 6d)** — stretch goal
11. **Notifications (Flow 4)** — nice to have, lowest priority
