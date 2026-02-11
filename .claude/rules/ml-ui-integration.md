---
paths:
  - "scripts/cluster_new_faces.py"
  - "scripts/apply_cluster_matches.py"
  - "data/proposals.json"
  - "app/main.py"
---

# ML-UI Integration Rules

## Proposals Pipeline
1. `cluster_new_faces.py` writes `data/proposals.json` after finding matches (both dry-run and execute modes).
2. Proposals are loaded and cached in `app/main.py` via `_load_proposals()` / `_proposals_cache`.
3. Focus mode prioritizes identities with proposals (sorted by distance ASC).
4. Match mode checks proposals first before falling back to live neighbor search.
5. Browse view shows inline "ML Match" badges on identity cards with proposals.

## proposals.json Schema
```json
{
  "generated_at": "ISO-8601",
  "threshold": 1.05,
  "proposals": [
    {
      "source_identity_id": "uuid",
      "source_identity_name": "Unidentified Person NNN",
      "target_identity_id": "uuid",
      "target_identity_name": "Known Person",
      "face_id": "face-id",
      "distance": 0.76,
      "confidence": "VERY HIGH|HIGH|MODERATE|LOW",
      "margin": 0.45,
      "ambiguous": false
    }
  ]
}
```

## Cache Invalidation
6. `POST /api/sync/push` must invalidate `_proposals_cache` after writing data.
7. proposals.json is tracked in git (`.gitignore` whitelist) and in `OPTIONAL_SYNC_FILES` in `init_railway_volume.py` (synced from bundle to volume on deploy, but not required for app startup).

## Global Reclustering
Clustering operates on ALL unresolved faces (INBOX + SKIPPED), not just inbox.
When SKIPPED faces gain new matches, they are promoted to INBOX with tracking fields.

Promotion fields on identity:
- `promoted_from`: previous status ("SKIPPED")
- `promoted_at`: ISO timestamp
- `promotion_reason`: "new_face_match" | "group_discovery" | "confirmed_match"
- `promotion_context`: human-readable explanation (for confirmed_match)

`source_state` field in proposals.json tracks which proposals come from SKIPPED faces.

## Inbox Triage
The inbox shows a triage bar: Ready to Confirm / Rediscovered / Unmatched.
Focus and Match modes sort by priority: confirmed matches first, then promotions, then unmatched.
Filter parameter `?filter=ready|rediscovered|unmatched` narrows the inbox view.

## Display Rules
8. Confidence labels follow AD-013 calibration: VERY HIGH (<0.85), HIGH (0.85-1.00), MODERATE (1.00-1.10), LOW (>1.10).
9. Show comparative metrics (margin, "15% closer than next-best") rather than absolute distances for non-technical users (Lesson #41).
