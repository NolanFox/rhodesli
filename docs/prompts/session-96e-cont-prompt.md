# Session 96e Continuation — Complete Fox Family Stabilization

**Context:** `docs/session_context/session-96e-context.md`
**Previous commits:** `30d3bde` (1622 new identities), `b66296b` (registry cache + upload-review fix)
**Priority:** P0 — Fox Family must be usable for admin review

---

## What's Already Done (Session 96e)
1. **Registry TTL cache** — 30s cache on load_registry(), invalidates on save. Deployed.
2. **Upload-review GEDCOM triage** — Now scoped to community (was showing Rhodes people). Deployed.
3. **Cross-community badge fix** — Identity in current community no longer shows wrong badge. Deployed.
4. **Discoveries refactored** — Proposal-only, no more batch computation timeout. Deployed.
5. **Upload pipeline** — group_inbox_identities wired into _background_ingest. Deployed.
6. **1622 new INBOX identities** — Created for unassigned Fox Family faces. Synced to Supabase. Deployed.
7. **Session files renamed** — 97 → 96e. Harness files verified.

## What's NOT Working Yet

### A. Grouping returned 0 merges
`group_inbox_identities()` expects `face_data` as a dict: `{face_id: {"mu": embedding, "sigma_sq": ...}}`.
But it was called with `np.load('data/embeddings.npy', allow_pickle=True)` which returns a numpy array of dicts.

**Fix needed:** Convert embeddings.npy to the dict format before calling grouping:
```python
raw = np.load('data/embeddings.npy', allow_pickle=True)
face_data = {}
for entry in raw:
    fid = entry.get('face_id', '')
    if not fid:
        # Generate face_id from filename + face index
        fid = generate_face_id(entry.get('filename', ''), entry.get('face_index', 0))
    face_data[fid] = {"mu": entry['embeddings'], "sigma_sq": entry.get('sigma_sq')}
```

Then re-run `group_inbox_identities(registry, face_data, photo_reg, dry_run=False)`.
Save registry, sync to Supabase, push.

### B. Cluster Review still empty
The proposals.json has 2008 proposals but they're from BEFORE the 1622 new identities were created.
After grouping, re-run `cluster_new_faces.py` to regenerate proposals:
```bash
python scripts/cluster_new_faces.py --dry-run --threshold 1.3
```

### C. Proposals count = 0 in sidebar
On Railway production, `proposals.json` is read from the DATA_DIR which is the volume.
After the git push + deploy, `init_railway_volume.py` should sync proposals.json.
Verify after deploy: sidebar should show proposal count > 0.

### D. Fox Family shows "1 People" instead of 64+
After grouping creates clusters + syncs to Supabase, the photo-derived identity set
should include many more identities. Verify sidebar counts update.

### E. Betty Capeluto Fox not showing as identified
User feedback: Both Roland Fox and Betty Capeluto Fox are in both communities.
Currently only Roland Fox appears. After identity assignment + grouping,
Betty Capeluto Fox should have Fox Family faces assigned to her.

## Act 1: Fix face_data format and re-run grouping

1. Load embeddings.npy into the correct dict format
2. Check: how does `scripts/cluster_new_faces.py` load face_data? Copy that approach.
3. Run `group_inbox_identities(registry, face_data, photo_reg, dry_run=False)`
4. Save registry + sync to Supabase
5. Expected: hundreds of merges (many fox faces are the same person)

## Act 2: Regenerate proposals

1. Run `python scripts/cluster_new_faces.py --dry-run --threshold 1.3`
2. This generates proposals.json with matches between INBOX/PROPOSED faces and CONFIRMED identities
3. Commit proposals.json

## Act 3: Push and verify

1. `git push origin main` — triggers Railway deploy
2. Wait for deploy SUCCESS
3. Browser verify:
   - Fox Family sidebar: People count >> 1
   - Upload Review: Cluster Review shows matches
   - Upload Review: GEDCOM Triage shows Fox Family identities
   - Discoveries page loads and shows cards
   - Cross-community badge correct (no badge for Fox Family identities)
   - Proposals > 0 in sidebar

## Act 4: Session wrap
1. Update session log, ROADMAP, CHANGELOG
2. Write assessment
3. Clean up worktrees: `rm -rf .claude/worktrees/agent-*`

## Key Files
- `core/grouping.py` — group_inbox_identities function
- `scripts/cluster_new_faces.py` — load_face_data function (reference for dict format)
- `data/identities.json` — identity registry (2455 identities)
- `data/proposals.json` — clustering proposals
- `data/embeddings.npy` — face embeddings (2714 entries)
