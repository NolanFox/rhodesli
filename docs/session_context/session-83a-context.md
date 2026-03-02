# Session 83a Context: User Feedback Triage + Critical UX Fixes

## Origin

Community member **Claude Benatar** (active contributor, Facebook group admin for "Jews of Rhodes: Family Memories & Heritage") messaged Nolan on Facebook Messenger asking:

1. "Why does it say unidentified person?" — referring to a photo that clearly shows **COHEN Isaac** with biographical text (born Rhodes July 17, 1906, arrived Congo 1928, merchant)
2. "See if you can find a match with this picture..." — sent a group family photo wanting face comparison

This is the **first real external user feedback** from a community stakeholder. Responding well matters.

## User Journey Claude Benatar Attempted

1. Viewed a photo on Rhodesli showing Isaac Cohen's document with face detected
2. Saw "Unidentified Person #41" label despite the photo clearly containing the person's name
3. Was confused — why "unidentified" when the name is right there?
4. Wanted to help identify / match this person with a group photo he has
5. It was not clear what to do next or how to use Compare

## What Nolan Attempted (Admin Perspective)

### Attempt 1: Use the public Help Identify page

- URL: `rhodesli.nolanandrewfox.com/identify/7a7effee-4372-4da4-af08-1feaa1a3beca`
- Filled in name "Isaac Cohen", source reference, email
- Clicked "Yes, I know this person!"
- Got "Thank you!" confirmation
- **RESULT: BROKEN** — submission never appeared in admin approvals
- On refresh, the page reset with no indication anything was submitted
- No audit log entry for this submission
- **This is a silent failure affecting real users like Claude Benatar**

### Attempt 2: Name via admin New Matches workflow

- Went to New Matches → Browse view
- Had to Cmd+F to find "445" (no search by person number)
- Clicked through to person page: `/person/7a7effee-4372-4da4-af08-1feaa1a3beca`
- "Edit Name" and "View in Admin" both go to same Focus view
- Focus view shows "Edit Details" which expands a form
- **Name field is labeled "Maiden Name"** — nonsensical for "Isaac Cohen"
- Typed "Isaac Cohen" → saved as metadata → displays as "née Isaac Cohen"
- Confirmed the person → moved to People list
- **RESULT: Person is in People but has NO NAME — only "née Isaac Cohen" as maiden name**
- **It is literally impossible to set a person's primary display name through this flow**

### Attempt 3: Compare with group photo

- Saved photo locally, went to `/compare`
- Uploaded the group photo Claude Benatar sent
- Pipeline ran: Photo received ✓, Detecting faces ✓, Searching archive ✓, Estimating date ✓, Analysis complete ✓
- **RESULT: BROKEN** — redirected to result page that shows "Comparison Not Found: This comparison result doesn't exist or has been removed"
- URL: `rhodesli.nolanandrewfox.com/compare/result/d0ea6e10-202`

---

## Complete Bug/Issue Inventory

### P0 — Silent Failures (Users Are Hitting These NOW)

| ID | Issue | Impact |
|----|-------|--------|
| P0-1 | **Help Identify submissions silently fail** — form accepts input, shows "Thank you!", but nothing reaches admin approvals or audit log | Claude Benatar and others submitting identifications that are lost |
| P0-2 | **Compare result page 404s** — analysis pipeline completes but result page shows "Comparison Not Found" | Core feature broken for the exact use case a real user just requested |
| P0-3 | **Cannot set a person's primary/display name** — "Maiden Name" is the only name field in Edit Details; no field for actual name | Confirmed people have no name. Literally impossible to name someone |

### P1 — Broken Features (Were Working ~10 Sessions Ago)

| ID | Issue | Impact |
|----|-------|--------|
| P1-1 | **Find Similar button in New Matches is dead** — clicking does nothing or errors | Cannot use ML similarity from review workflow |
| P1-2 | **Face cards lack name editing** — no inline or accessible way to set display name from any face card view | Admin cannot name people during review flow |
| P1-3 | **Help Identify submission doesn't trigger confirmation** — adding a name via public page should also move person toward confirmed status (or at least create a pending confirmation) | Names submitted but person stays in limbo |
| P1-4 | **No logging for Help Identify submissions** — no audit trail when community members submit identifications | Cannot track community contributions |

### P2 — UX Confusion / Navigation

| ID | Issue | Impact |
|----|-------|--------|
| P2-1 | **"Unidentified Person" label is confusing** when photo clearly contains a name/document — users don't understand what "unidentified" means in context | First user feedback is literally about this confusion |
| P2-2 | **No search by person number in admin** — have to Cmd+F through hundreds of cards to find "Person 445" | Admin workflow is tedious |
| P2-3 | **No clear linking between admin and public views** — jumping between person page, focus view, browse view requires knowing URLs | Navigation is disorienting |
| P2-4 | **Face cards inconsistent between admin sections** — different capabilities/layouts in New Matches vs People vs Focus view | Confusing which actions are available where |
| P2-5 | **"Maiden Name" label for name field** — misleading for non-maiden names (e.g., Isaac Cohen is male) | Field should be "Display Name" or "Full Name" with maiden name as optional/secondary |
| P2-6 | **"née" prefix auto-added** — saving a maiden name prepends "née" which is wrong for primary display names | Names display incorrectly |
| P2-7 | **Email field shown to logged-in users on Help Identify page** — unnecessary friction, should auto-fill or hide | Minor but adds confusion |
| P2-8 | **No way to link to GEDCOM from face card** — can't connect person to family tree data from the review interface | Missed integration opportunity |
| P2-9 | **Compare feature not discoverable** for the "match this person with this photo" use case that Claude Benatar described | The exact feature exists but users can't find it |
| P2-10 | **Help Identify page resets on refresh** with no indication of prior submission | User has no confirmation their contribution was received |

---

## Claude Benatar Response Strategy

After fixes are deployed, Nolan should be able to respond to Claude with:
1. Acknowledgment that "Unidentified" means the system hasn't confirmed a name yet (even if the source document has one)
2. A working Compare link where Claude can upload his group photo to find matches
3. Ideally: the Isaac Cohen identification already reflected in the system
4. Clear instructions for how to use Help Identify or Compare for future photos

---

## Key Technical Context

- App: FastHTML on Railway, Supabase backend, Cloudflare R2 storage
- ML: InsightFace face detection/embeddings, custom similarity pipeline
- Current stats: 272 photos, 660 faces detected, 60 identified people, 398 in review, 202 needing help
- Version: v0.85.1
- Admin: nolanfox@gmail.com
- The Gatekeeper pattern: ML outputs are proposals → admin confirms/rejects → confirmed data becomes ground truth
