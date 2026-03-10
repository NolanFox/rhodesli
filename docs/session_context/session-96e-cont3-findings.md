# Session 96e-cont3 Findings

## Committed Fixes (de6f3c2)
1. **Proposals sidebar** — `_compute_sidebar_counts(registry, community=community)` in admin_routes.py (2 locations)
2. **Proposals API** — `/api/proposed-matches?community_slug=X` filtering in engagement_routes.py
3. **Discoveries Help Identify** — `community_identity_ids` filter in `_build_help_identify_section()`
4. **Duplicate face filter** — Neighbors with dist < 0.1 AND co-occurrence filtered in identity_routes.py
5. **Name consistency** — "Person NNNN" in neighbor_card (main.py:8031)
6. **Split script** — `scripts/split_oversized_clusters.py` (not needed for local, data already correct)

## Supabase Data Divergence (NOT YET FIXED)
- Local JSON: 3006 identities (correct — max cluster 44 faces)
- Supabase: 4155 identities (stale — still has 252/157/121-face garbage from single-linkage)
- Upserted 3006 to Supabase but 1149 orphans remain
- Orphan breakdown: 1146 INBOX, 3 REJECTED, 230 have merged_into, 919 non-merged
- Non-merged extras are "Unidentified Person 981-984+" — these are old INBOX identities
  whose faces were absorbed by single-linkage merges. The merge targets still have all those faces.
- **CRITICAL**: Must verify Claude Benatar's contributions are in local JSON before deleting Supabase extras
- Safe approach: Delete extras that have merged_into set (these are definitely garbage).
  For the 919 non-merged, check if any were created by Benatar before deleting.

## Upload Bug (NOT YET INVESTIGATED)
- User selected 3 files from ~/Downloads/rhodes_pics_more_testing on Rhodes community
- Files: congo_photos_claude_benatar_*.jpeg (3 files, 7-75KB)
- Files appear in tooltip on hover but upload doesn't start
- URL: rhodesli.nolanandrewfox.com/upload (Rhodes community)
- This is NOT from my changes — I didn't touch upload code
- Need to check: upload route, JS upload handler, file input element

## Upload UX Feedback (from Nolan)
- Current: auto-upload on file select/drop — no feedback
- Wanted: Select files → see file list in scrollable box → click "Upload" button → progress
- Must handle large file counts without breaking
- This is a UX improvement, not a bug fix

## Discoveries on Rhodes = 0
- Nolan screenshot shows 0 discoveries on Rhodes
- This might be correct if all discovery proposals have been reviewed
- Or it might be a filtering issue from my changes (unlikely — discoveries API was already community-filtered)

## Browser Verification Results
- [x] Browse view: "Person NNNN" visible (not truncated) — PASS
- [x] Sort links: stay on `/c/fox-family/` — PASS
- [ ] Clusters: max ~44 faces — FAIL (Supabase still has 252)
- [x] Upload Review: Grouped Identities section visible — PASS
- [x] Upload Review: Proposals filtered (17) — PASS
- [ ] Similar Identities: Dist 0.00 entries — FIXED in code, not yet deployed
- [ ] Match view: Up Next carousel — Not implemented
- [x] Match view: functional with face comparison — PASS
- [ ] All tests pass — PASS (2 pre-existing flaky tests)

## Remaining Work
1. **P0**: Fix Supabase orphans (delete the 230 merged_into, audit 919 non-merged for Benatar data)
2. **P0**: Investigate upload failure on Rhodes
3. **P0**: Deploy fixes and re-verify in browser
4. **P1**: Upload UX improvement (file list + button)
5. **P1**: Match view Up Next carousel
6. **P2**: Verify Benatar annotations preserved
