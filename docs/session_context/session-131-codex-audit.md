# Session 131 — Codex Audit: Merge Face Transfer Integrity

**Auditor:** Claude Opus 4.6
**Date:** 2026-03-22
**Files reviewed:** `core/registry.py` (lines 600-770), `tests/test_merge_face_transfer.py`, `tests/test_merge_orphan_audit.py`

---

## 1. `core/registry.py` — Post-Merge Verification (lines 742-763)

### P2: Force-added faces bypass co-occurrence validation

The post-merge verification force-adds orphaned faces directly to `target["anchor_ids"]` (line 761) without running `validate_merge()` or checking co-occurrence constraints. If a face was legitimately skipped during the merge loop (e.g., `_face_id_from_entry` returned `None` due to a corrupt entry), the force-add appends the raw face ID string, not the original entry object. This is correct for string entries but would lose metadata for dict-format entries.

**Risk:** Low in practice — the only scenario where orphans exist is when the transfer loop above already attempted to process them. The co-occurrence check runs once at the start of `merge_identities()` and covers all faces from both identities, so any co-occurrence conflict would have blocked the merge entirely before reaching this code. The force-add path is a safety net, not a primary path.

**Recommendation:** Add a comment clarifying that co-occurrence was already validated pre-merge.

### P3: Duplicate face IDs possible via force-add path

The verification builds `target_face_set` from the current target state (line 745-747), then checks source faces against it. If the normal transfer loop added a face as a dict entry `{"face_id": "X", ...}` but `_face_id_set` extracts just `"X"`, and then a corrupt/unexpected entry format in the source causes `_face_id_from_entry` to return a slightly different string, the face could be force-added as a duplicate.

**Risk:** Extremely low — `_face_id_from_entry` and `_face_id_set` use the same normalization logic. Would require data corruption in the source between the transfer loop and the verification (impossible within a single function call).

**Recommendation:** No action needed.

### P3: `faces_merged` counter updated but return dict already constructed

The force-add path increments `faces_merged` (line 762), but the return dict is constructed after the verification block (line 765-772), so the updated count IS included. This is correct.

### P2: Performance for large merges

The verification iterates all source faces (O(n)) and checks membership in a set (O(1) per check). Force-adds are O(k) where k is orphan count. For an identity with 1000 faces, this adds ~1ms. No performance concern.

### P1: Verification reads source faces AFTER `merged_into` is set

Source's `anchor_ids` and `candidate_ids` are read at line 748-751, but source was marked as `merged_into` at line 673. This is fine because the merge does NOT clear source face lists — it only sets `merged_into` as a soft-delete marker. The source dict still contains all original face IDs. However, this is a fragile assumption: if any future code change clears source faces during merge (e.g., as a cleanup), the verification would always see zero orphans and become useless.

**Recommendation:** Add a defensive comment: `# NOTE: source face lists are intentionally preserved (not cleared) during merge — verification depends on this.`

---

## 2. `tests/test_merge_face_transfer.py`

### P2: Missing test — merge with dict-format face entries

All tests use plain string face IDs (`"face_a1"`, etc.). The codebase supports dict-format entries (`{"face_id": "X", "quality": 0.9}`). The post-merge verification's `_face_id_from_entry` handles both formats, but no test exercises the dict path through merge + verification.

**Recommendation:** Add a test with mixed string/dict face entries to verify the verification handles both formats.

### P2: Missing test — merge where source has `candidate_ids`

The fixture creates both identities with only `anchor_ids`. No test exercises a merge where the source has faces in `candidate_ids` that need to transfer to the target's `candidate_ids` list and then be verified.

**Recommendation:** Add a test with source having both anchors and candidates.

### P3: Missing test — `_find_merge_orphans` with chained merged_into

If A merges into B, and B merges into C, `_find_merge_orphans` checks A's faces against B (its `merged_into` target). But B is also merged, so B's face lists may be stale (faces transferred to C). The test `TestChainedMerges.test_chained_merge_preserves_all_faces` runs `_find_merge_orphans` after the chain, but B's faces would appear orphaned relative to its `merged_into` target IF B's face lists were cleared. Since they're not cleared, B still has its original faces AND they exist in C, so no orphan is reported. But A's faces in B's `merged_into` check would look at B (which still has A's faces copied in), so it passes. This is correct but relies on source lists never being cleared.

### P1: No test for the force-add path actually firing

The post-merge verification's force-add code (lines 759-763) is a safety net. No test verifies it fires. Ideally, there would be a test that patches the transfer loop to deliberately skip a face, then asserts the verification catches and force-adds it.

**Recommendation:** Add a test that monkeypatches the transfer to skip a face, verifying the safety net works.

---

## 3. `tests/test_merge_orphan_audit.py`

### P2: `_ensure_list` handles JSON strings but not nested JSON

`_ensure_list` handles `str` by trying `json.loads`. This covers the known Supabase JSONB-as-string issue (Lesson 142). Good.

### P3: Test skips gracefully when Supabase is unavailable

The `supabase_client` fixture skips on ImportError and on `client is None`. This is CI-safe. Good.

### P2: No assertion on chained merged_into targets

The test checks each merged identity against its immediate `merged_into` target. If the target itself is merged (chained merge), the check still passes as long as the immediate target has the faces. But if the chain is A→B→C and B's faces were transferred to C, then A's faces checked against B would pass (B still has them). This is correct behavior for the current data model.

### P3: No limit on orphan output in assertion message

`orphans[:5]` limits the assertion message. Good for readability.

---

## 4. Supabase Data Repair (112 orphaned faces → 18 target identities)

### P1: No verification that repaired faces don't violate co-occurrence

The repair added 112 face IDs to 18 target identities' `anchor_ids`. If any of those faces appear in the same photo as another face already in the target identity, the co-occurrence invariant is violated. The merge_identities() function validates this pre-merge, but a direct Supabase UPDATE bypasses that validation entirely.

**Recommendation:** Run a one-time co-occurrence audit: for each of the 18 repaired identities, verify no two faces in anchor_ids share the same photo_id.

### P2: No audit trail in Supabase for the repair

The repair was done as direct Supabase UPDATEs. There's no `audit_log` entry, no `merge_history` entry, and no `version_id` bump for the 18 modified identities. If someone investigates these identities later, there's no record of why their anchor_ids changed.

**Recommendation:** Insert audit_log rows for the 18 repaired identities with action="data_repair", session="131", and the list of added face IDs.

### P2: JSONB array mutation safety

When adding face IDs to `anchor_ids` via Supabase, the approach matters:
- If done via `UPDATE ... SET anchor_ids = '[...]'` (full replacement): safe but races with concurrent writes.
- If done via `anchor_ids || '["new_face"]'::jsonb` (append): safe and concurrent-friendly.
Since this was a one-time repair with no concurrent writes, either is fine. But the approach should be documented.

---

## 5. Summary of Findings

| # | Severity | File | Finding |
|---|----------|------|---------|
| 1 | P1 | registry.py | Verification reads source faces after `merged_into` set — fragile if future code clears source lists |
| 2 | P1 | test_merge_face_transfer.py | No test exercises the force-add safety net path |
| 3 | P1 | Supabase repair | No co-occurrence validation on 112 repaired face assignments |
| 4 | P2 | registry.py | Force-added faces bypass co-occurrence validation (mitigated by pre-merge check) |
| 5 | P2 | test_merge_face_transfer.py | No test with dict-format face entries |
| 6 | P2 | test_merge_face_transfer.py | No test with source having candidate_ids |
| 7 | P2 | Supabase repair | No audit_log entries for the 18 modified identities |
| 8 | P2 | test_merge_orphan_audit.py | No chained merged_into validation |
| 9 | P3 | registry.py | Duplicate risk via force-add (extremely unlikely) |
| 10 | P3 | test_merge_orphan_audit.py | Graceful CI skip — good |

## 6. Recommended Actions

1. **P1 — Add defensive comment** in `registry.py` at line 742 noting source lists must not be cleared before verification.
2. **P1 — Add force-add path test** that deliberately skips a face in the transfer loop and asserts the safety net catches it.
3. **P1 — Run co-occurrence audit** on the 18 repaired identities (can be a one-time script or added to the production audit test).
4. **P2 — Add dict-format and candidate_ids merge tests** to `test_merge_face_transfer.py`.
5. **P2 — Insert audit_log rows** for the Supabase repair (retroactive).
