# Session 111d Interactive Feedback (Late Session)

## FB-071: Approve should also confirm the identity
- **Severity:** P0 (workflow — creates extra work)
- **Context:** On /admin/approvals, when admin clicks Approve on a name suggestion, it should also confirm the identity (promote to CONFIRMED). Currently it only approves the name but leaves the identity in INBOX/PROPOSED. Admin can't easily find the approved person afterward. Screenshot shows "Also confirm this person" checkbox — verify this works.
- **Fix:** Approve endpoint should confirm the identity when the checkbox is checked.

## FB-072: Approved names not showing in approval history
- **Severity:** P1 (UX — can't track what was approved)
- **Context:** After approving names, there's no record at the bottom showing what was approved. Admin can't retroactively find approved identities.

## FB-073: Notifications for approved names
- **Severity:** P2 (deferred — needs batching)
- **Context:** Want to send notifications (not emails yet) when names are approved. Emails need batching to avoid spam. In-app notifications can be immediate.

## FB-074: Merge duplicate confirmed identities broken
- **Severity:** P0 (core workflow broken)
- **Context:** On Rhodes community, trying to merge two duplicate Robert Mattatia identities. Click Merge, Name Conflict modal appears (both have same name), but clicking Merge in the modal doesn't work. Button shows "Merging..." but nothing happens.
- **Root cause:** TBD — may be the same-name conflict resolution not handling identical names.

## FB-075: Face overlays missing on Rhodes photos
- **Severity:** P0 (regression — face overlays gone)
- **Context:** https://rhodesli.nolanandrewfox.com/photo/f1ae3676f59943b2 — shows "0/1 identified" but no face bounding box overlay on the photo. Same dimension cache issue from earlier in this session, but on Rhodes community.

## FB-076: Community awareness on approve
- **Severity:** P1 (data integrity)
- **Context:** When approving names from the approvals page, must ensure the identity ends up in the correct community. Don't want cross-community contamination.
