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

---

## Disposition

| ID | Severity | This Session? | Disposition |
|----|----------|---------------|-------------|
| FB-001 | P1 | No | BACKLOG UX-131 — needs PRD for merge search |
| FB-002 | P1 | No | BACKLOG UX-132 — community badge on approvals |
| FB-003 | P2 | No | BACKLOG UX-133 — always show community badge |
| FB-004 | P2 | No | BACKLOG UX-134 — auto-resolve annotation after merge |

**Recommendation:** These are all follow-up items. FB-001 (merge search) is the highest impact — it directly blocks the admin workflow when community members provide identifications. Should be a near-term session (1-2 hours).
