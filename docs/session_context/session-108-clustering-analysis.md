# Session 108: Clustering Analysis & James Fields Case Study

**Date:** 2026-03-16
**Predecessor:** Session 108 main (data integrity), Session 108b (bug fixes)
**Links to:** PRD-049, AD-226, BACKLOG CLUSTER-001 through CLUSTER-005

## James Fields Background

David Fox (Nolan's dad's cousin) recognized "Jimmy Fields" (James Henry Fields) in an existing Fox Family archive photo. Nolan uploaded 2 known James Fields photos to verify via ML matching. The upload pipeline had an orphan face bug (Lesson 146) — 9 faces were detected but 0 identities were created. After repair, all 9 faces got INBOX identities.

## James Fields Identities (from screenshots)

Viewing Person 28fa8bfa's Similar Identities panel:

| Identity | Match % | Distance | Status | James Fields? | Notes |
|----------|---------|----------|--------|---------------|-------|
| **28fa8bfa** | (source) | — | INBOX, multi-face | Yes | Collage photo with multiple sub-photos |
| **1c8c316f** | 65% | 0.84 | BLOCKED (co-occurrence) | Yes | Same collage photo — different sub-photo |
| **3474** | 62% | 0.87 | Mergeable | Yes | Different photo. Should have been auto-grouped (0.87 < 0.95 threshold) |
| **5e3de5c5** | 59% | 0.91 | BLOCKED (co-occurrence) | Yes | Same collage photo |
| **1646d93d** | 56% | 0.94 | BLOCKED (co-occurrence) | Yes | Same collage photo |
| **3895** | 39% | 1.13 | Mergeable | Possibly | |
| **0cb65795** | 37% | 1.16 | Mergeable | Possibly | |
| **3650** | 33% | 1.20 | Mergeable | Yes | Different photo, lower confidence |
| **3302** | 29% | 1.25 | Mergeable | Unknown | |
| **fdc7d26e** | 29% | 1.26 | Mergeable | Unknown | Rhodes community cross-match |

Everything >= Person 3650 is confirmed James Fields by Nolan.

## Why Clustering Failed for James Fields

1. **Orphan bug** — faces existed in `photo_faces` but had no identities. Grouping couldn't run.
2. **Within-batch only** — even after repair, grouping only compares faces from the SAME upload batch. James Fields faces were never compared against the 1652 existing Fox Family faces.
3. **Proposals only match CONFIRMED** — `find_matches()` only matches against confirmed identities. James Fields has no confirmed identity, so zero proposals.
4. **Similar Identities is display-only** — the panel DOES find matches (INBOX vs INBOX) but results aren't persisted as proposals.

## Empirical Threshold Analysis

Computed from 34 confirmed identities with 2+ anchors (8580 within-identity face pairs):

**Within-identity (same person) distances:**
- Min: 0.17, Mean: 1.03, Median: 1.03, Max: 1.45
- P90: 1.31, P95: 1.34, P99: 1.39

**Nearest different-person distances (family confusion risk):**
- Charles Fox ↔ Roland Fox: 0.50 (father-son)
- Esther Burd Fox ↔ Roland Fox: 0.79
- Albert Fox ↔ Roland Fox: 0.79
- Betty Capeluto ↔ Roland Fox: 0.80
- Big Leon Capeluto ↔ Albert Fox: 0.84
- Victoria Capuano Capeluto ↔ Victoria Cukran Capeluto: 0.87

**Threshold impact:**
| Threshold | Same-person caught | False-positive family pairs |
|-----------|-------------------|---------------------------|
| 0.70 | 12.1% | 4 (including Charles↔Roland) |
| 0.80 | 12.1% | 4 |
| 0.85 | 18.7% | 6 |
| 0.90 | 26.4% | 9 |
| 0.95 | 35.7% | 12 |
| 1.05 | 54.8% | 20 |

**Key finding:** No threshold cleanly separates same-person from different-person. Charles Fox ↔ Roland Fox at 0.50 means even very aggressive auto-merge would create false positives. This data drove the decision: **no auto-merge for cross-batch, proposals only.**

## User Feedback Summary

### Nolan's requirements:
1. **No auto-merge across batches** — Google Photos false positives were frustrating. Human-in-loop for everything cross-batch.
2. **Within-batch grouping is OK** — same upload, same context, auto-merge acceptable at 0.95.
3. **Surface matches proactively** — don't require navigating to each identity to see Similar Identities. Proposals sidebar and notifications.
4. **Notify the uploader** — "your photo matched 3 existing people" is the key value moment.
5. **Non-destructive, reversible** — every merge (manual or auto) must have undo and full audit trail.
6. **Monitor for compounding errors** — if a bad merge happens, it should be detectable before it cascades.
7. **Works for initial upload AND subsequent uploads** — clustering shouldn't be a one-time event.
8. **Resilient to family resemblance** — siblings, parent-child look similar. Don't merge them.

### Design decisions from this analysis:
- Within-batch: auto-merge at 0.95 (existing, unchanged)
- Cross-batch: proposals only (no auto-merge at any threshold)
- Cross-batch Very High (<0.70): prominent notification + one-click merge
- Cross-batch High (0.70-0.95): notification + proposal
- Cross-batch Moderate (0.95-1.05): proposal only
- Admin recluster triggers both within-batch regrouping and cross-batch proposals
- After confirming an identity, re-run proposals against that new confirmed anchor
- All events logged to Supabase audit_log with full provenance

## Screenshots Reference

Session 108 screenshots (stored in conversation, not filesystem):
1. Fox Family photos page showing "Internet Research: 2 photos, 9 faces, 0→9 identified"
2. Similar Identities panel for Person 28fa8bfa showing 9 matches
3. Compare Faces modal: Person 28fa8bfa vs Person 3474 (James Fields)
4. Compare Faces modal: Person 28fa8bfa vs Person 3650 (James Fields at piano)
5. Full Similar Identities list showing Blocked buttons on co-occurrence matches
6. Debbie Fox Schapiro person page showing Similar Identities (Compare button context)
7. Photo Context modal showing missing View Photo link (fixed in 108b)
8. Sidebar search showing "No matches found" for filename (fixed in 108b)
