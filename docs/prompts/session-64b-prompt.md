# Session 64b: Execute What 64 Deferred
# Rhodesli Heritage Photo Archive
# Created: 2026-02-23

# ═══════════════════════════════════════════════════════
# READ FIRST — MANDATORY
# ═══════════════════════════════════════════════════════

Read these files IN ORDER before doing anything else:
1. `CLAUDE.md`
2. `docs/session_context/session_64_context.md`
3. `ALGORITHMIC_DECISIONS.md` — read AD-152 and the 5 entries before it
4. `ROADMAP.md`

Confirm you have read all four. Print: last AD number, ROADMAP line count, and whether these tables exist in Supabase:
```bash
psql "$DATABASE_URL" -c "\dt face_gemini_alignments" 2>&1
psql "$DATABASE_URL" -c "\dt gemini_api_calls" 2>&1
```

# ═══════════════════════════════════════════════════════
# SESSION RULES (NON-NEGOTIABLE)
# ═══════════════════════════════════════════════════════

1. ONE deliverable per phase. Do not combine.
2. Commit after EVERY phase. Message: `feat|fix|docs(scope): description`
3. Print context % after EVERY phase.
4. If context < 40%: `/clear` and re-read CLAUDE.md + this prompt.
5. If context < 20%: STOP. Log progress to SESSION_HISTORY.md.
6. NEVER use `/compact`. Always `/clear` + re-read from disk.
7. Every Gemini API call → log via `log_gemini_call()` to gemini_api_calls table.
8. Postgres is source of truth. JSON files are fallback cache only.

# ═══════════════════════════════════════════════════════
# PHASE 1: Create Supabase tables (~5 min)
# Session 64 wrote the SQL but never executed it.
# ═══════════════════════════════════════════════════════

Find the SQL migration scripts that Session 64 created. They should define:
- `gemini_api_calls` table
- `face_gemini_alignments` table (if not already existing from Session 62)

Execute them against Supabase:
```bash
# Find the SQL files
find . -name "*.sql" -newer .claude/skills/session-run.md | head -10

# Execute (adjust path based on what you find)
psql "$DATABASE_URL" -f <path_to_migration_sql>
```

After execution, verify:
```bash
psql "$DATABASE_URL" -c "\dt gemini_api_calls"
psql "$DATABASE_URL" -c "\dt face_gemini_alignments"
psql "$DATABASE_URL" -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'gemini_api_calls' ORDER BY ordinal_position;"
psql "$DATABASE_URL" -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'face_gemini_alignments' ORDER BY ordinal_position;"
```

Print all output. Both tables must exist with correct schemas before proceeding.

If no SQL files exist, create and execute them using the schema from `session_64_context.md`.

Commit: `feat(data): execute Supabase table migrations for gemini_api_calls + face_gemini_alignments`

# ═══════════════════════════════════════════════════════
# PHASE 2: Migrate existing face alignment data (~5 min)
# Session 63 stored results in JSON. Move them to Supabase.
# ═══════════════════════════════════════════════════════

1. Find Session 63's alignment results:
```bash
ls -la data/face_alignments.json 2>/dev/null
ls -la results/batch_alignment_*.json 2>/dev/null
# Also check if there's alignment data already in code
grep -rn "face_alignment" rhodesli_ml/ --include="*.py" | grep -v __pycache__ | grep -v test | head -20
```

2. Read the JSON data and insert into `face_gemini_alignments` table.
   - Each record needs: photo_id, alignment_data (JSONB), model_used, created_at
   - If model_used isn't in the JSON, set it to 'unknown — session_63_backfill'

3. Verify migration:
```bash
psql "$DATABASE_URL" -c "SELECT count(*) as total, count(alignment_data) as with_data FROM face_gemini_alignments;"
```

The count should match the number of photos that were aligned in Session 63 (127 photos).

4. Verify the app reads from Supabase (not JSON):
```bash
grep -rn "face_alignments.json\|load.*alignment.*json" --include="*.py" . | grep -v __pycache__ | grep -v test
```

If any code still reads alignment from JSON as primary source, update it to read from Supabase first with JSON as fallback.

Commit: `feat(data): migrate 127 face alignments from JSON to Supabase`

**Print context %. If < 40%, /clear and re-read CLAUDE.md + this prompt.**

# ═══════════════════════════════════════════════════════
# PHASE 3: Implement GEDCOM context builder (~10 min)
# Session 64 left _build_parsed_gedcom_from_supabase() 
# as a stub. Without it, the combined pipeline sends
# coordinates WITHOUT genealogical context.
# ═══════════════════════════════════════════════════════

1. Find the stub:
```bash
grep -rn "_build_parsed_gedcom\|build_parsed_gedcom\|build_gedcom_context" --include="*.py" . | grep -v __pycache__
```

2. Implement it. The function should:
   - Query the GEDCOM Supabase tables (created in Session 63: 207,533 records across 4 tables)
   - For a given photo_id, find linked GEDCOM individuals via `gedcom_face_links`
   - Build a curated context string with: full names, birth years, death years, relationships, residence timelines
   - This is what made Session 61C's results so good — the genealogical context dramatically improved Gemini's analysis

3. The curated context format (from Session 61C winner):
```
Known individuals in this photo:
- Isaac Franco (b. 1920, Rhodes) — son of Morris Franco and Rebecca Notrica
- Vida Capeluto (b. 1895, Rhodes) — married to Bohor Capeluto
Family context: The Franco and Capeluto families were part of the Sephardic Jewish community of Rhodes.
```

4. Wire it into `run_combined_pipeline.py`:
   - Before the Gemini call, call `build_parsed_gedcom_from_supabase(photo_id)`
   - Include the result in the Gemini prompt alongside InsightFace coordinates

Tests:
- `test_gedcom_context_builder_returns_string`
- `test_gedcom_context_includes_birth_years`
- `test_gedcom_context_handles_no_links`
- `test_combined_pipeline_includes_gedcom_in_prompt`

Commit: `feat(ml): implement GEDCOM context builder for combined Gemini pipeline`

# ═══════════════════════════════════════════════════════
# PHASE 4: Dry-run combined pipeline on 3 photos (~5 min)
# Validate end-to-end BEFORE committing to batch.
# ═══════════════════════════════════════════════════════

Pick 3 photos strategically:
1. A photo WITH GEDCOM face links (to test enriched context)
2. The Vida Capeluto photo (PRD-015 motivating case)
3. A group photo with 5+ faces (stress test alignment)

Run the combined pipeline on these 3 photos ONLY:
```bash
# Use Flash for free-tier dry run
GEMINI_API_KEY=$GEMINI_API_KEY python -m rhodesli_ml.scripts.run_combined_pipeline \
    --photos <photo_id_1>,<photo_id_2>,<photo_id_3> \
    --model gemini-3-flash-preview \
    --dry-run
```

If `--dry-run` flag doesn't exist, add it (processes N photos, prints results, does NOT save to Supabase).

Print the FULL output for all 3 photos. Specifically check:
- Did GEDCOM context appear in the prompt sent to Gemini?
- Did Vida Capeluto's face count match InsightFace detection?
- Was every API call logged to `gemini_api_calls` table?
- What model was actually used? (verify it matches what was specified)

```bash
# Verify API calls were logged
psql "$DATABASE_URL" -c "SELECT photo_id, model_used, call_type, status, cost_usd FROM gemini_api_calls ORDER BY created_at DESC LIMIT 5;"
```

If the dry-run fails (rate limit, API key missing, error):
- Log the error
- Print what would have been sent (the full prompt for one photo)
- Document what's needed to run it successfully
- Continue to Phase 5 — do NOT block on API availability

Commit: `test(ml): dry-run combined pipeline on 3 strategic photos`

**Print context %. If < 40%, /clear and re-read CLAUDE.md + this prompt.**

# ═══════════════════════════════════════════════════════
# PHASE 5: Production deploy + smoke test (~5 min)
# Session 64 never verified production.
# ═══════════════════════════════════════════════════════

```bash
git push origin main
```

Wait 60 seconds, then verify production at `rhodesli.nolanandrewfox.com`:

```bash
BASE_URL="https://rhodesli.nolanandrewfox.com"

echo "=== ROUTE CHECK ==="
for route in "/" "/map" "/connect" "/tree" "/timeline" "/collections" "/compare"; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$route")
    echo "$route → $STATUS"
done

echo ""
echo "=== FEATURE CHECK ==="
# Check if a photo page loads with face data
# Find a photo that has alignment data
PHOTO_ID=$(psql "$DATABASE_URL" -t -c "SELECT photo_id FROM face_gemini_alignments LIMIT 1;" 2>/dev/null | tr -d ' ')
if [ -n "$PHOTO_ID" ]; then
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/photo/$PHOTO_ID")
    echo "Photo page ($PHOTO_ID) → $STATUS"
    # Check if the response contains alignment/calibration-related HTML
    curl -s "$BASE_URL/photo/$PHOTO_ID" | grep -c "match\|calibrat\|similarity\|face-card" || echo "No calibration/face-card markers found in HTML"
fi
```

Print ALL output.

If any route returns 500: STOP other work, fix it, re-deploy, re-verify.

Commit: `docs: Session 64b production verification results`

# ═══════════════════════════════════════════════════════
# PHASE 6: AD entries + documentation (~5 min)
# Session 64 collapsed everything into AD-152.
# Split into proper individual entries.
# ═══════════════════════════════════════════════════════

Add these individual AD entries to ALGORITHMIC_DECISIONS.md (use next available numbers):

1. **AD-XXX: Gemini API call tracking infrastructure**
   - Decision: Every Gemini call logged to `gemini_api_calls` table with model, cost, tokens, status
   - Why: Session 63 cost discrepancy ($0.78 vs expected $2.50), model drift across sessions
   - Enables: Cost analysis, model comparison, rate limit detection
   - Breadcrumb: Session 63 assessment concern #7

2. **AD-XXX: Face alignment storage migration JSON → Supabase**
   - Decision: `face_gemini_alignments` table is source of truth, JSON is cache-only
   - Why: JSON not queryable, not accessible via REST API, drifts from database (AD-135)
   - Breadcrumb: Session 63 concern #1, AD-135 (data safety gates)

3. **AD-XXX: Combined Gemini pipeline (alignment + GEDCOM + extraction)**
   - Decision: Single API call per photo combining coordinate bridging, curated GEDCOM context, and full extraction
   - Model: gemini-3.1-pro-preview (centralized config, no hardcoded strings)
   - Why: Session 61C proved curated GEDCOM + Pro is the winning combination
   - Breadcrumb: AD-090 (face alignment), Session 61C results

4. **AD-XXX: Harness architecture — skills, hooks, rules**
   - Decision: Move repeatable workflow knowledge to `.claude/skills/`, hard constraints to hooks, domain rules to `.claude/rules/`
   - Why: CLAUDE.md was 4922 chars, prompts re-explained architecture every session
   - Result: CLAUDE.md → 1952 chars, 5 skills, 3 hooks, 3 rule files

5. **AD-XXX: Gemini Batch API for bulk photo processing**
   - Decision: Use Batch API (50% discount, 24h SLO) for remaining 144+ photos
   - Cost: ~$2 batch vs ~$4 synchronous for 144 photos
   - Rate limits: Avoids RPM/RPD issues that blocked Session 63
   - Status: Infrastructure ready, awaiting API key + execution
   - Breadcrumb: Session 63 concern #2

Update ROADMAP.md:
- Mark Session 64/64b completed items
- DIFF against current version first — print the diff
- Confirm no items silently dropped

Update SESSION_HISTORY.md with 64b entry.

Commit: `docs: AD entries 153-157, ROADMAP, SESSION_HISTORY updates`

# ═══════════════════════════════════════════════════════
# PHASE 7: Self-assessment (~2 min)
# ═══════════════════════════════════════════════════════

Print a structured assessment:

```
## Session 64b Assessment
- Duration: X minutes
- Phases: N/7 completed
- Tests: +N new, NNNN total

## Session 63 Concerns — Final Status
1. Face alignment JSON-only → [RESOLVED/PARTIAL]
2. 144 photos rate-limited → [RESOLVED/PARTIAL]
3. Combined pipeline unclear → [RESOLVED/PARTIAL]
4. Vida Capeluto not tested → [RESOLVED/PARTIAL]
5. Calibrated scores not in UI → [RESOLVED/PARTIAL]
6. Recalibration hooks dead → [RESOLVED/PARTIAL]
7. Cost suspiciously low → [RESOLVED/PARTIAL]

## Remaining for Session 65
[list]

## Recommended Session 65 priorities
[list]
```

Commit: `docs: Session 64b self-assessment`

# ═══════════════════════════════════════════════════════
# WHAT THIS SESSION DELIVERS
# ═══════════════════════════════════════════════════════
#
# 1. Supabase tables actually exist (not just SQL scripts)
# 2. 127 face alignments migrated from JSON to Postgres
# 3. GEDCOM context builder wired into combined pipeline
# 4. Dry-run validates end-to-end on 3 real photos
# 5. Production verified (routes + feature check)
# 6. Proper AD entries (not collapsed into one)
# 7. Vida Capeluto photo explicitly tested (PRD-015)
#
# This is the "execute what was deferred" session.
# No new architecture. Just make the existing code real.
# ═══════════════════════════════════════════════════════
