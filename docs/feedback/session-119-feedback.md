# Session 119 Feedback — Interactive Triage UX Issues

**Date:** 2026-03-18
**Mode:** Interactive
**Source:** User screenshots + verbal feedback during ML service verification

---

## Summary

Three core issues surfaced during admin triage work:

1. **Merge workflow doesn't help you find the right person** — when you know who someone is (e.g., Eva Deber Shane), there's no search or type-ahead to find them. You have to scroll through ML-suggested similar identities, most of which are wrong.

2. **Community scoping in admin is confusing** — Approvals page shows the same pending annotation (Eva Deber Shane by maalot20@outlook.com) on BOTH `/admin/approvals` (Rhodes) and `/c/fox-family/admin/approvals` (Fox Family). No community tag indicates which archive the annotation belongs to.

3. **Cross-community proposals lack community tags** — In the Fox Family "New Matches" view, similar identities from Rhodes (like Person 056) show a community badge, but most don't. When merging, you can't tell if you're merging within Fox Family or across communities.

---

### FB-001: Merge Needs Search/Type-Ahead (P1)
- **Severity:** P1
- **Context:** User identified Eva Deber Shane from WhatsApp conversation with Ezri Silver. Went to Person page, wanted to merge Unidentified Person 3140 into Eva Deber Shane. The "Similar Identities" list showed ML-ranked suggestions (Person 2931, Person 4034, etc.) but NOT the known match. User had to scroll looking for the right person.
- **Expected:** A search box or type-ahead on the merge panel to find a person by name, not just browse ML suggestions.
- **Root cause:** Merge UI only shows embedding-distance-ranked suggestions. No free-text search to find an arbitrary identity.
- **Fix:** Add a "Search by name" input to the Similar Identities panel that queries existing identities. When you know who someone is, you should be able to type their name and merge directly.
- **BACKLOG:** UX-131 (new)
- **Effort:** 1-2 hours — add search endpoint + HTMX input to merge panel

### FB-002: Approvals Page Not Community-Scoped (P1)
- **Severity:** P1
- **Context:** The exact same pending annotation (Eva Deber Shane, Person 3140, by maalot20@outlook.com) appears on both:
  - `rhodesli.nolanandrewfox.com/admin/approvals` (Rhodes context)
  - `rhodesli.nolanandrewfox.com/c/fox-family/admin/approvals` (Fox Family context)
  No community tag or badge distinguishes which archive the annotation belongs to.
- **Expected:** Either (a) approvals should be scoped to the current community, or (b) each approval card should have a community badge showing which archive it belongs to.
- **Root cause:** Approvals query doesn't filter by community. The annotation is on a Fox Family person but shows in Rhodes admin too.
- **Fix:** Add community badge to each approval card. Optionally filter by current community context.
- **BACKLOG:** UX-132 (new) / relates to COMMUNITY-015
- **Effort:** 1 hour — badge is trivial, community filter query needs testing

### FB-003: Cross-Community Merge Suggestions Need Community Tags (P2)
- **Severity:** P2
- **Context:** On the Fox Family person page for Eva Deber Shane, the Similar Identities list includes Person 056 which correctly shows a "Jewish Community of Rhodes" badge. But most other suggestions (Person 2931, 4034, 3409, 2538, 2885, 3140) have NO community tag. It's unclear whether these are Fox Family or Rhodes people.
- **Expected:** Every suggestion in the Similar Identities panel should show its community affiliation badge.
- **Root cause:** Community badge only shows for cross-community matches. Same-community matches have no badge because it's "obvious" — but when admin manages both, it's NOT obvious.
- **Fix:** Always show community badge on suggestion cards, even for same-community matches.
- **BACKLOG:** UX-133 (new)
- **Effort:** 30 min — badge already exists, just need to show it unconditionally

---

## Real User Engagement Context (WhatsApp with Ezri Silver)

The screenshots show an active conversation where:
- Ezri Silver confirmed person in Fox Family photos is their grandmother **Eva Shane (Maiden Name: Deber)**
- ML matched her across newspaper/old photos and more modern (~1980s) photos — cross-era matching working
- Ezri confirmed the match: "My grandfather" / "This is my grandmother Eva Shane"
- This validates the cross-batch matching pipeline (PRD-049) and the Help Identify loop

**Key insight:** The growth loop is working (Find -> Share -> Click -> Recognize -> Respond), but the admin merge workflow is the bottleneck. When community members identify people via WhatsApp/Help Identify, the admin needs a fast way to merge — not scroll through ML suggestions.

### FB-004: Skip-After-Merge Doesn't Acknowledge Community Contribution (P2)
- **Severity:** P2
- **Context:** User merged Eva Deber Shane's clusters (applied the community member's identification from maalot20@outlook.com). After merge, the annotation still showed as "pending" and the only option was Skip. Skipping doesn't inform the contributor that their identification was accepted — it looks like it was ignored.
- **Expected:** When admin merges/confirms based on a community annotation, the annotation should auto-resolve as "Applied" or there should be an "Accept" option that both applies the name AND acknowledges the contributor.
- **Root cause:** Approvals workflow and merge workflow are decoupled. Merging identities doesn't resolve the pending annotation that prompted it.
- **Fix:** When admin confirms/merges an identity that has a pending name annotation matching the merge target, auto-approve the annotation. Or add "Approve + Merge" combined action.
- **BACKLOG:** UX-134 (new)
- **Effort:** 2-3 hours — need to detect annotation-merge overlap and wire auto-resolution

### FB-005: Upload Form Needs Annotation/Notes Field (P2)
- **Severity:** P2
- **Context:** User uploaded Terry Yanishefsky family photo. Had a detailed email caption identifying every person (back row L-R: aunt Mary, husband Sam Barnett, aunt Ruth, grandmother, grandfather, father Solomon, uncle Joe; front row L-R: cousins Sidney and Beatrice, aunt Fannie and uncle Irving, uncle Bernard and aunt Jenny holding cousin Milton). No way to attach this caption to the upload — it lives only in email.
- **Expected:** An optional "Notes" or "Caption" field on the upload form where you can paste context about the photo. This context should be visible on the photo page and potentially feed into Gemini analysis.
- **Root cause:** Upload form only has Collection, Source, and Source URL fields. No free-text annotation.
- **Fix:** Add optional "Notes" textarea to upload form. Store in photo metadata. Display on photo page.
- **BACKLOG:** UX-135 (new)
- **Effort:** 1 hour

### FB-006: Face Overlay Buttons Too Small/Crowded on Group Photos (P1)
- **Severity:** P1
- **Context:** Terry Yanishefsky family photo has 14 people. Face overlay buttons (confirm/skip/reject) are tiny and overlap each other on small faces. User repeatedly misclicked — accidentally hitting decline/skip when trying to view a person. Speed Loop mode has the same issue with the "Type name to tag..." box overlapping faces.
- **Expected:** Larger click targets, or a different interaction model for dense group photos (e.g., click face to select, then choose action from a panel, rather than tiny overlay buttons).
- **Root cause:** Face overlay buttons scale with face bounding box size. On group photos with 10+ people, faces are small → buttons are too small to reliably target.
- **Fix:** Needs design thinking. Options: (a) click-to-select then panel actions, (b) minimum button size regardless of face size, (c) zoom-on-hover, (d) list-based tagging mode instead of overlay-based.
- **BACKLOG:** UX-136 (new)
- **Effort:** PRD needed — this is a significant interaction redesign

### FB-007: Source URL Not Saved During Upload (P2)
- **Severity:** P2
- **Context:** User entered a Google Photos URL as Source URL during upload. After upload completed, the Source URL field on the photo page was empty.
- **Expected:** Source URL should persist from upload form to photo metadata.
- **Root cause:** Upload pipeline may not be passing source_url through to the photo record.
- **Fix:** Trace upload form → _background_ingest() → photo record creation. Verify source_url is passed and saved.
- **BACKLOG:** UX-137 (new)
- **Effort:** 30 min — likely a missing field in the pipeline

### FB-008: Cross-Batch Matches Should Generate Notifications (P1)
- **Severity:** P1
- **Context:** After uploading the Terry Yanishefsky photo, 118 cross-batch matches were found. The #1 match for Person b34ba944 was Fannie Burd Yanishefsky at distance 1.08 (44% match) — correct identification. The #1 match for Person 79991b6a was Irving Yanishefsky at distance 1.13 (39% match) — also correct. But neither generated a notification or proposal visible to the admin. The admin bar showed "Proposals (0)".
- **Expected:** After upload, admin should see a notification like "New upload: 14 faces found, 2 high-confidence matches to existing people" with direct links to review. Even at 39-44% confidence, these are worth flagging because:
  1. The top match was correct in both cases
  2. The distance gap to the next candidate was significant (+8.3% for Fanny, meaningful)
  3. Admin already has context (just uploaded the photo, knows who's in it)
- **Current thresholds (AD-179):** Tier 1 auto-merge <0.85, Tier 2 proposal 0.85-1.10. Both matches (1.08 and 1.13) are at or above Tier 2 boundary.
- **The system did the right thing** not auto-merging — siblings/cousins at similar distances (Mary Yanishefsky Barnett, Esther Burd Fox) prove that auto-merge would be dangerous here. But the lack of ANY notification means the admin has to manually browse each new face to find matches.
- **Real-world example:** Irving Yanishefsky at distance 1.13 = correct match. Person 359c4b67 at distance 1.13 = different person (same photo, "Seen together"). Same distance, different answers. This validates conservative thresholds but demands better notification.
- **Fix:** After cross-batch matching, generate a "review digest" notification: "N faces with potential matches found. Top: [Person X] → [Match Y] at N% confidence." Surface in Notifications sidebar with direct review links.
- **BACKLOG:** UX-138 (new) — relates to PRD-049 (cross-batch matching), notification UX (feedback_notification_ux.md)
- **Effort:** 2-3 hours for basic notification; full notification redesign needs PRD per feedback_notification_ux.md

---

## Disposition

| ID | Severity | This Session? | Disposition |
|----|----------|---------------|-------------|
| FB-001 | P1 | No | BACKLOG UX-131 — needs PRD for merge search |
| FB-002 | P1 | No | BACKLOG UX-132 — community badge on approvals |
| FB-003 | P2 | No | BACKLOG UX-133 — always show community badge |
| FB-004 | P2 | No | BACKLOG UX-134 — auto-resolve annotation after merge |
| FB-005 | P2 | No | BACKLOG UX-135 — upload annotation/notes field |
| FB-006 | P1 | No | BACKLOG UX-136 — face overlay buttons too small on group photos (needs PRD) |
| FB-007 | P2 | No | BACKLOG UX-137 — source URL not saved during upload |
| FB-008 | P1 | No | BACKLOG UX-138 — cross-batch match notifications |

**Recommendation:** FB-008 (notifications after cross-batch matching) and FB-006 (group photo tagging UX) are the highest-impact items. FB-008 directly addresses the gap between "ML found correct matches" and "admin knows about them." FB-001 (merge search) remains important for the WhatsApp-to-merge workflow.
