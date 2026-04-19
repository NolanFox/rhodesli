# PRD-062: Anchor Inspector & Identity Repair UX

**Status:** Specified (Session 153b planned; Session 155+ implementation)
**Author:** Session 153b (Claude + Nolan)
**Date:** 2026-04-19
**Priority:** P1 — data integrity is the #1 recurring failure mode (Lessons 153–156)
**Source:** `docs/feedback/session-153-feedback.md` FB-001
**Session reference:** Planned in Session 153b Phase 6; implementation targeted Session 155+

## Problem Statement

The Harry Fox anchor misassignment — 2 of 7 anchors on identity `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` were actually Harry Isaackovitz (Bessie Fox's husband, face IDs from the 1917 Detroit photo) — took a **full Claude Code session to diagnose (Session 152)** and will require a second session to repair (Session 153+). This is fundamentally too heavy for what is ultimately a single-person correction that the admin could do unassisted in <3 minutes given the right tools.

The underlying data model conflates two distinct things:
- **"anchors"** = the definitional faces of an identity (what ML is trained against; the ground-truth centroid)
- **"candidate faces"** = faces the system thinks *might* belong (ranked by embedding distance)

When a contaminated merge or a bad confirm happens, there is **no in-product way** for an admin to:
1. See the internal consistency of an identity's anchors (are they clustered tightly, or are there 2 outliers ruining the centroid?)
2. Detach a specific anchor with provenance (who attached it? when? via which merge?)
3. Split a multi-cluster identity into two with an audit trail
4. Link the detached cluster to a GEDCOM record in the same flow

Data integrity is the project's #1 recurring failure category (Lessons 153–156, 10+ occurrences). Every bad anchor silently degrades the centroid, which propagates into every future proposal involving this identity. The cost compounds.

## User Stories

- **As an admin on a person page**, I want a health score at the top of the page: "This person's 7 anchors have internal embedding distances 0.69–1.43. The 2 outlier anchors are from photos X and Y. See diagnosis →"
- **As an admin debugging a misassigned identity**, I want an anchor inspector grid showing every anchor, its distance to the centroid, and outliers highlighted, without opening a Claude Code session.
- **As an admin**, I want to select ≥1 outlier anchors and one-click split them into a new INBOX identity, with an audit_log row capturing the provenance and a rollback path.
- **As an admin completing a split**, I want to immediately point the new identity at a GEDCOM record (without navigating to a separate page), because the whole reason I'm splitting is that I know who those 2 anchors actually are.
- **As an admin**, I want a visual side-by-side comparison of an identity's anchors (already partially in `/tools/compare`), wired from the person page so I can eyeball outliers before splitting.

## Canonical Test Case

**Identity `d74cb556-6d44-4288-ade3-1cc8fa2b45a6` (Harry Fox, 7 anchors).**

2 anchors are from the 1917 Detroit photo and are actually Harry Isaackovitz, not Harry Fox. The 5 legitimate anchors have tight intra-cluster distances; the 2 outliers pull the centroid toward Isaackovitz's face, polluting every Harry Fox proposal.

**Acceptance question:** Would this PRD's tools have let Nolan catch and fix this in <3 clicks without needing a Claude Code session?

If the answer is "yes," ship it. If "no," the PRD needs more design.

## Proposed Capabilities

### 1. Identity Health Score

Surface on every person page with ≥3 anchors. Computed server-side with a 300s TTL cache keyed on `(identity_id, last_mutation_timestamp)`.

**Score components:**
- **Intra-cluster max distance** — the largest pairwise L2 embedding distance between any two anchors. High = internal dispersion.
- **Centroid distance stddev** — stddev of each anchor's distance to the anchor centroid. High = outliers.
- **Connected components at threshold 1.15** — count anchors as "connected" if pairwise distance < 1.15 (Fox family threshold per AD-235). If there are 2+ components, the identity is likely contaminated.

**Health bands:**
- **Healthy** (green): max distance <1.00, stddev <0.10, single component — "7 anchors, tightly clustered"
- **Review** (amber): 1.00–1.30 max, 0.10–0.20 stddev, single component — "Wider than typical; verify anchors"
- **Contaminated** (red): >1.30 max OR 2+ components — "Outliers detected; 2 anchors >1.30 from centroid"

Rendered as a single badge at the top of the person page, clickable to expand the anchor inspector.

### 2. Anchor Inspector Grid

Route: `/c/{community}/identity/{identity_id}/anchors`

Grid of all anchors for the identity:
- Crop thumbnail
- Source photo link
- Distance to centroid (numeric + color-coded bar)
- Attached-via provenance: "original anchor" / "merged from {source_id}" / "manually added by {user}"
- Attached timestamp
- Checkbox for selection

**Sortable by:** distance-to-centroid (default, descending — outliers first), attached timestamp, source photo date.

**Filter:** outliers-only toggle (shows only anchors >1σ from centroid).

Below the grid: "Compare selected anchors side-by-side" button that pipes selected anchor crop URLs into `/tools/compare` with pre-filled IDs.

### 3. One-Click Split

From the anchor inspector, with ≥1 anchor selected:
- Button: **"Split selected into new INBOX identity"**
- Confirmation modal: "Move {N} anchors to a new unidentified person? This is reversible via snapshot."
- On confirm:
  1. Snapshot the current identity state (anchor_ids, candidate_ids, metadata) to `identity_snapshots` table — same pattern as existing reversible merge/restore infra (AD-225).
  2. Create a new identity with `state=INBOX`, `name="Unidentified Person {next_N}"`, `anchor_ids=[selected_anchors]`.
  3. Remove the selected anchors from the source identity's `anchor_ids`.
  4. Write `audit_log` row with `actor`, `action="split_anchors"`, `source_identity_id`, `new_identity_id`, `moved_anchor_ids`, `snapshot_id`, `reason` (optional admin note).
  5. Recompute the source identity's centroid (surgical cache invalidation per session 141 pattern).
  6. Redirect admin to the new INBOX identity's page.

**Target: ≤3 clicks from person page to completed split** (badge → inspector → split button).

### 4. Ancestry Link Repair (in-flow)

After a split completes, the new INBOX identity page renders a "Link to GEDCOM record" panel **inline, not as a separate page**:
- Uses the existing GEDCOM search endpoint (Session 133 TOOLS-004 substrate: `/api/gedcom/search`)
- Top 5 candidates based on family context (if source identity had a GEDCOM link, surface its relatives first)
- One-click: "This is {GEDCOM name} ({birth_year}–{death_year})" — writes `identity_gedcom_links` row, renames identity, promotes state `INBOX → CONFIRMED`.

**Rationale:** The whole reason the admin is splitting is that they know who the outlier anchors are. Forcing them to navigate to a separate GEDCOM search page loses context and breaks the workflow.

### 5. Visual Side-by-Side Anchor Comparison

Extend `/tools/compare` to accept a `?identity_id=X&show_all_anchors=true` query param. When present, it renders every anchor of identity X as tiles in the comparison grid with pairwise distances between them (matrix view).

This is effectively "wire `/tools/compare` to the person page." The compare infrastructure already exists (PRD-007, Session 122 TOOLS-003). The person page just needs a "Compare all 7 anchors" link.

### 6. Audit Trail

Every split, detach, and merge writes an `audit_log` row (AD-225, AUDIT-001 — already in production as of Session 114). Anchor inspector surfaces the audit trail inline: "2 anchors attached via merge of Person 3299 on 2026-03-15."

Every mutation is reversible via the existing snapshot/restore infra. No new rollback system required.

## Acceptance Criteria (Quantitative)

1. **Health score visible on every person page with ≥3 anchors.** Badge renders with color band (green/amber/red), clickable to inspector.
2. **Anchor inspector loads in <500ms for identities with ≤20 anchors.** (Typical max anchor count: ~30. Upper-bound stress case: 50.)
3. **Split flow completes in ≤3 clicks** for a 2-anchor outlier set: (a) click health badge, (b) check 2 outliers, (c) click "split" + confirm.
4. **Audit trail visible on the anchor inspector** within the same page (no navigation to separate audit page).
5. **All splits reversible via existing snapshot/restore UI** — no new rollback infrastructure. Snapshot written before each mutation.
6. **Canonical test case (Harry Fox 2-of-7 misassignment) resolvable unassisted in <3 minutes** by a logged-in admin, with no Claude Code session required. This is the ship gate.
7. **No data loss on split.** Zero face orphans post-split (verified by the existing post-merge integrity check added in Session 141; extend to post-split).
8. **Community-scoped.** Splits are scoped to a single community. Anchor inspector on an identity in community A does not surface anchors or GEDCOM candidates from community B.

## Data Model

### No new tables required

Reuses existing infrastructure:
- `identity_snapshots` — already used for reversible merges (AD-225)
- `audit_log` — already used for all identity mutations (AUDIT-001, Session 114)
- `identity_gedcom_links` — already used for GEDCOM linking (Session 96)

### New columns (nullable, additive)

- `identities.health_score_cached` (numeric) — last computed score, updated on mutation or TTL expiry. Null for identities with <3 anchors.
- `identities.health_band_cached` (text) — 'healthy' / 'review' / 'contaminated' / null.

### New endpoint

`GET /api/identity/{id}/anchor-health` — returns `{max_intra_distance, centroid_stddev, connected_components, band, outlier_face_ids}`. Cached 300s server-side.

## Out of Scope (v1)

- **Automated re-clustering** — that's PRD-049 (cross-batch clustering). This PRD is strictly about admin repair UX for already-confirmed identities.
- **Bulk migrate tools** — if an admin needs to migrate 50+ anchors, they can write a SQL script. v1 is per-identity triage.
- **Machine reasoning about "is this the right identity"** — the tool surfaces the signal; the admin decides. Health score is descriptive, not prescriptive.
- **Automatic anchor rejection based on health score** — health score never auto-removes an anchor. Admin action only.
- **Cross-identity outlier detection** ("this anchor belongs to identity Y") — surface the top-3 nearest CONFIRMED identities as a hint, but the admin still confirms. No auto-move.
- **Retroactive health scoring of all identities at once** — compute on-demand per identity view, with background job for precomputation only if the on-demand latency exceeds 500ms in production.

## Dependencies

- **No blockers.** All required infrastructure exists:
  - Snapshot/restore system (AD-225, Session 105b)
  - audit_log (AUDIT-001, Session 114)
  - Surgical cache invalidation (Session 141 perf work)
  - GEDCOM search endpoint (Session 96)
  - `/tools/compare` (PRD-007, Session 122 TOOLS-003)
- **Soft dependency:** Ships better *after* PRD-058 merge-auto-confirm analysis is resolved, because auto-confirm behavior affects which anchors get added without admin review.

## Algorithmic Decision Entries Required

Before implementation (per `.claude/rules/ml-development.md`):

- **AD-239:** Identity Health Score — Intra-Cluster Dispersion Metric. Rationale: max distance + centroid stddev + connected-components triad chosen over single-metric alternatives because no single metric catches all contamination patterns. Thresholds calibrated on Fox family confirmed set (AD-235).
- **AD-240:** Split vs Detach Semantics. Rationale for modeling as "move anchors to a new INBOX identity" rather than "detach and re-cluster." Former is admin-intentional; latter is ML-probabilistic. Reversibility simpler for the admin-intentional path.

## Reference Existing Work

- `app/components/identity_cards.py` — where anchor crops render on the person page; health badge inserts here.
- `core/registry.py` — anchor list mutations, snapshot/restore pattern (AD-225).
- `core/neighbors.py` — FROZEN (per CLAUDE.md invariants); do not modify. Read embeddings only.
- `core/perf_cache.py` — L2-normalized embedding matrix (Session 111f). Health score computation reuses this.
- PRD-007 (Face Comparison) — `/tools/compare` substrate.
- PRD-049 (Cross-Batch Clustering) — the auto-clustering side; this PRD is the admin-repair side.
- PRD-057 (Triage Workflow) — confirm vs identify separation.
- PRD-058 (Merge Auto-Confirm) — soft dependency.
- AD-225 — snapshot/restore for reversible mutations.
- AD-229 — ML proposals vs ground-truth anchors distinction.
- AUDIT-001 — audit_log infrastructure (Session 114).
- Lessons 153–156 — recurring data integrity failures.

## Why This PRD Now

From FB-001, Session 153:

> The Harry Fox anchor misassignment required a full Claude Code session to diagnose and will require another session to repair. That's fundamentally too heavy for what is essentially a single-person correction.

Data integrity is the project's #1 recurring failure mode. Every session-long Claude diagnosis of a misassignment is both:
1. A cost the project cannot sustain at scale (1977 identities, growing)
2. An admission that the product doesn't give its admin the tools it needs

The Harry Fox case is not an edge case. It's typical of how bad merges happen:
- A face gets proposed with a plausible distance
- An auto-confirm or bulk-confirm attaches it as an anchor
- The centroid drifts
- Future proposals using this identity get worse

The health score + inspector + split flow turns a multi-session investigation into a <3-minute admin task. That's the ROI.

## Related

- `docs/feedback/session-153-feedback.md` FB-001 — source feedback item
- `docs/feedback/session-152-feedback.md` — Harry Fox diagnosis session
- PRD-049, PRD-057, PRD-058 — adjacent triage/repair work
- AD-225 (data integrity), AD-229 (ML proposals), AD-235 (Family Cluster Score thresholds), AUDIT-001 (audit log)
- Lessons 153, 154, 155, 156 — recurring data integrity occurrences
- CLAUDE.md invariants: "UI never deletes a face" (splits move, never delete); "Merges reversible" (splits reversible via same snapshot infra)
