# Data Safety & Registry Lessons

Lessons about JSON data files, identity registries, photo IDs, and data integrity.
See also: `docs/architecture/DATA_MODEL.md`, `.claude/rules/test-isolation.md`

---

### Lesson 25: Photo ID schemes must be consistent within lookup systems
- **Mistake**: `_build_caches()` used SHA256(filename)[:16] as photo IDs but tried to look up sources from photo_index.json which used inbox_* IDs. 12 of 13 Betty Capeluto photos silently got empty source strings.
- **Rule**: When cross-referencing data between systems with different ID schemes, always include a fallback lookup by a shared key (e.g., filename).
- **Prevention**: Add a test that verifies every photo has a non-empty source after cache building.

### Lesson 29: Maintain ONE authoritative backlog
- **Mistake**: Session-scoped todos in `tasks/todo.md` contained only the current session's work, not the full project backlog. Previous sessions' items were lost.
- **Rule**: `tasks/todo.md` is the SINGLE project backlog. Session-scoped checklists are ephemeral — reconcile them into the backlog after every session.
- **Prevention**: At session end, move completed items to the "Completed" section and ensure all known open items are captured.

### Lesson 36: get_identity() returns a shallow copy — mutate _identities directly
- **Mistake**: `add_note()` and `resolve_proposed_match()` called `get_identity()` which returns `.copy()`. Mutations to the returned dict didn't persist.
- **Rule**: When adding methods to IdentityRegistry that mutate identity data, access `self._identities[id]` directly, not through `get_identity()`.
- **Prevention**: Before adding any mutation method to the registry, check whether `get_identity()` returns a copy.

### Lesson 44: "Skipped" is a deferral, not a resolution
- **Mistake**: Clustering script only included INBOX and PROPOSED faces as candidates. SKIPPED faces (192 — the largest pool of unresolved work) were silently excluded. The script reported "0 candidates" while 192 faces remained unidentified.
- **Rule**: SKIPPED means "I don't recognize this person right now." It is NOT a terminal state. ML pipelines, UI navigation, and stats must all treat skipped faces as active work items.
- **Prevention**: When adding state-based filters, always list what's EXCLUDED (confirmed, dismissed, rejected) rather than what's included. The default should be to include faces, not exclude them.

### Lesson 48: Route handlers must use canonical save functions, not direct .save()
- **Mistake**: `/api/photo/{id}/collection` called `photo_reg.save(photo_index_path)` directly instead of `save_photo_registry(photo_reg)`. Tests patched `save_photo_registry` but the route bypassed it, causing test fixture data to overwrite real `data/photo_index.json` on every test run.
- **Rule**: All data-modifying route handlers MUST use the canonical save functions (`save_registry()`, `save_photo_registry()`, etc.), never call `.save()` directly on registry objects.
- **Prevention**: Grep for `.save(` in route handlers. Any direct `.save(path)` call outside of canonical save functions is a bug.

### Lesson 104: Batch script outputs must write to the SAME data structure the app reads
- **Mistake**: Session 93's batch GEDCOM reanalysis script wrote 69 updated photo location entries to the *root level* of `data/photo_locations.json`. But the app's `_load_photo_locations()` reads only from `data.get("photos", {})`. The Supabase migration also only copied the `"photos"` section. Result: 69 photos showed old/wrong locations in production (e.g., Asheville photo showed Brooklyn). The correct data existed in the file but was invisible to all consumers.
- **Rule**: When a batch/script writes to a structured data file, it MUST write to the EXACT key path that consumers read from. Before writing, grep the codebase for how the file is loaded. If the app does `data.get("photos", {})`, the script must write under `data["photos"]`, not at root level.
- **Prevention**: (1) Batch scripts should load the existing file, modify in-place under the correct key, and save — not append at root level. (2) Add a structural validation test: `photo_locations.json` should have ONLY `version`, `description`, and `photos` at root level. Any other keys indicate orphaned data. (3) After any batch write, verify by loading the file with the SAME function the app uses and checking the affected entries.
- **See also**: Lesson 78 (production-local data divergence), AD-212

### Lesson 105: Supabase sync functions must match actual table schema — test with real upsert, not just mock
- **Mistake**: `sync_photo_locations_batch()` used column names `latitude`, `longitude`, `place` that didn't exist in the actual Supabase `photo_locations` table (real columns: `lat`, `lng`, `location_name`). Also missing `on_conflict="photo_id"` for proper upserts. The function was only tested with mocks that don't validate column names, so the bug was invisible until the first real sync attempt.
- **Rule**: When writing Supabase sync functions, verify column names against the actual table schema. Mock-only tests for database sync are insufficient — they can't catch column name mismatches.
- **Prevention**: (1) Add a comment in each sync function listing the expected table columns. (2) Consider an integration test that does a real upsert to a test table. (3) When creating a new Supabase table, immediately write the sync function AND test it with a real connection before moving on.

### Lesson 116: Sidebar counts and API endpoints must read from the SAME data sources
- **Mistake**: `_compute_sidebar_counts()` reads proposals from BOTH `registry.list_proposed_matches()` AND `proposals.json`. But `/api/proposed-matches` only reads from `registry.list_proposed_matches()`. Result: Fox Family sidebar shows "17 Proposals" but the proposals page content shows "No pending proposals."
- **Rule**: When a count badge and a content API show the same data, they MUST read from identical data sources. Otherwise users see a number they can never access.
- **Prevention**: Extract a shared `_get_all_proposals(community_identity_ids)` function that both sidebar counts and API endpoints call. Never duplicate data source logic in two places.

### Lesson 55: Crop filename formats differ between legacy and inbox — don't assume quality is encoded
- **Mistake**: `face_card()` parsed quality from crop filenames using pattern `_{quality}_{index}.jpg`. Inbox crops use format `inbox_{hash}.jpg` with no quality encoded. Result: "Quality: 0.00" for all inbox faces.
- **Rule**: When a computed value (quality, score, etc.) is stored in different places for different face formats, the lookup must have a fallback chain: filename parse -> embeddings cache -> default.
- **Prevention**: `get_face_quality()` helper provides the fallback. `face_card()` now falls back to embeddings when filename parse returns 0.
