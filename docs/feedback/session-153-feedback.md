# Session 153 Feedback

## FB-001 — Anchors vs. potential matches: product-level repair UX
**Severity:** P1
**Source:** User, 2026-04-18 during Session 153

### Context
The Harry Fox anchor misassignment (2 of 7 anchors actually being Harry Isaackovitz) required a full Claude Code session to diagnose and will require another session to repair. That's fundamentally too heavy for what is essentially a single-person correction.

The underlying data model conflates:
- "anchors" = the definitional faces of an identity (what the ML is trained against)
- "candidate faces" = faces we think might belong

When a contaminated merge happens, there is no in-product way for an admin to:
1. See the internal consistency of an identity's anchors
2. Detach a specific anchor with provenance
3. Split a multi-cluster identity into two
4. Link a detached cluster to a GEDCOM record

### Desired capabilities
- **Identity health score** on the person page: "This person's 7 anchors have internal embedding distances ranging 0.69-1.43. The 2 outlier anchors are from photos X and Y. See diagnosis."
- **Anchor inspector view**: grid of all anchors for an identity, distance-to-centroid, flagged outliers highlighted
- **One-click split**: "Move these 2 anchors to a new INBOX identity" with audit trail
- **Ancestry link repair**: when splitting, allow pointing the new identity at a GEDCOM record in the same flow
- **Visual side-by-side anchor comparison**: already partially exists in `/tools/compare` but not wired to "show me this identity's 7 anchors vs each other"

### Fix disposition
Needs a PRD. Proposed: `docs/prds/062_anchor_inspector_and_repair_ux.md`. Fold into Session 154 Phase 6 for scoping; implementation likely Session 155+.

### Related existing work
- `docs/ml/ALGORITHMIC_DECISIONS.md` — AD-225 (data integrity), AD-229 (ML proposals)
- PRD-057 (merge-auto-confirm analysis, Session 141)
- `app/components/identity_cards.py` — the place where anchor crops are rendered on the person page

---

## FB-002 — Proactive context management (harness gap)
**Severity:** P1
**Source:** User, 2026-04-18 during Session 153

### Context
User had to explicitly tell the assistant the session was getting long and to plan a wrap. The assistant should have proactively recommended wrap at 60% context or after 2+ rounds of parallel agents.

### Fix disposition
New rule drafted: `.claude/rules/proactive-context-management.md`. Commit in Session 153. Follow-up: add a transcript-line hook that echoes to the USER (not just Claude) at 300 lines.

---

## FB-003 — GEDCOM candidate enumeration must include in-laws by default
**Severity:** P2
**Source:** Session 153 methodology gap

### Context
Session 153's first-pass candidate matrix for the 1918 Detroit photo enumerated Fox siblings and their direct kin, but treated in-laws (spouses of siblings) as a follow-up category. The real answer (Harry Isaackovitz = Bessie's husband) was in the in-law set. A better candidate enumeration should treat in-laws as first-class, not supplementary.

### Fix disposition
Update the Gemini identification prompt scaffold in `rhodesli_ml/gemini_extraction.py` to include:
- All spouses of identified subjects' siblings
- With marriage dates (so pre-marriage timeframes rule them out correctly)

---

## FB-004 — Gemini prompt age estimates are unreliable by ~10-15 years on old B&W photos
**Severity:** P2 (methodology)
**Source:** Session 153 Harry Isaackovitz confirmation

### Context
Gemini estimated the center man in the 1918 Detroit photo as "~22-28" when he is actually Harry Isaackovitz b.1881 = age 36-37. Similarly Bessie Fox (if 3009) is actually age ~40 but Gemini estimated ~20-22.

The 14-18-year error cascaded into the wrong candidate pool in Session 153 analyses.

### Fix disposition
When Gemini age estimates are used for candidate filtering, widen the window by ±10 years on historical (pre-1960) B&W photos. Log this caveat in the estimation output. Document in `docs/ml/ALGORITHMIC_DECISIONS.md`.

---

## FB-005 — Two-photos-same-event signal is unused
**Severity:** P1 (feature)
**Source:** User, Session 153

### Context
User has repeatedly pointed out that photos 02068 and 91b6f6b296e93a60 (and 01659) are from the same Belle Isle Conservatory event. The archive has no automatic mechanism to group them, so each identification analysis starts from scratch on one photo at a time.

### Fix disposition
Session 153 launched a research agent (`af0449b5cd9e68ea0`) for a 3-tier event-clustering feature. See `docs/feedback/session-153-event-clustering-research.md` when complete. Likely becomes PRD-061.

---

## Feedback recording rule (this session)
The user asked mid-session: "don't forget to make sure you record all feedback as you go". This file is the Session 153 feedback log. Future sessions should create one at session start and append throughout.
