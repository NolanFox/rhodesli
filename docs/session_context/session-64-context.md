# Session 64 Planning Context
# "Verify, Migrate, Harden"
# Created: 2026-02-23

## Session Identity
- Numbering: Session 64 (NOT 63b — this is new scope)
- Prior: Sessions 61C (GEDCOM enrichment winner: gemini-3.1-pro-preview + curated GEDCOM @ $0.02/photo), 62 (face alignment architecture, no real photo test), 63 (calibration AUC 0.9577, GEDCOM import 207k records, batch alignment 127/271 photos)
- Breadcrumbs: AD-090 (face alignment), AD-050 (reasoning-before-conclusion), AD-134/135 (data safety gates), PRD-015 (Gemini face alignment)

## Session 63 Assessment — 7 Concerns to Resolve

### Concern 1: Face alignment stored in JSON, not Supabase
- Session 62 created `face_gemini_alignments` Supabase table
- Session 63 stored results in `data/face_alignments.json` and `results/batch_alignment_*.json`
- **Resolution (Track A Phase 2):** Audit storage, migrate JSON → Supabase table. Eliminate JSON as primary store.
- Breadcrumb: AD-135 (JSON→Supabase migration direction), DATA-001

### Concern 2: 127/271 photos aligned (47%) — remaining 144 need re-run
- Rate limit hit mid-batch. Unknown if GEDCOM-linked faces were in the completed 127.
- **Resolution (Track B Phase 3):** Re-run remaining 144 with `--skip-aligned --delay 2.0`. Prioritize GEDCOM-linked photos first.

### Concern 3: "Combined pipeline" unclear
- Phase 1 goal was combined entry point: face alignment + GEDCOM enrichment + unified extraction in ONE Gemini call
- Batch script appears to be alignment-only (`run_batch_alignment.py`)
- **Resolution (Track B Phase 2):** Audit batch script. If alignment-only, create combined pipeline script that sends GEDCOM context + coordinates in single call. This is the winning "Pro + curated GEDCOM" combination from 61C.

### Concern 4: 22/22 faces — was Vida Capeluto included?
- 3 photos, 22 faces, all aligned. But PRD-015 was motivated by her count mismatch.
- **Resolution (Track B Phase 3):** Explicitly include Vida Capeluto photo in batch. Verify count matches InsightFace detection.

### Concern 5: Calibrated scores not confirmed in UI
- Phase 6 said calibration wired into compare/match display. AUC 0.9577 fitted.
- **Resolution (Track A Phase 3):** Deploy, open a photo with alignment data, check: do per-face cards show? Do similarity scores show calibrated probabilities ("85% match" not raw cosine)?

### Concern 6: Recalibration hooks — are they actually wired?
- `on_face_merge`, `on_match_reject`, `on_identity_confirm` — exist as code or as live hooks?
- **Resolution (Track A Phase 3):** Check if hooks are called from app merge/identify endpoints. If dead code, wire them.

### Concern 7: Cost suspiciously low ($0.78 vs expected $2.50)
- 125 photos × $0.02/photo (Session 61C Pro rate) = $2.50. Actual = $0.78.
- Possible: used Flash instead of Pro, alignment-only cheaper than full extraction, cost tracking incomplete.
- **Resolution (Track B Phase 1):** Create `gemini_api_calls` table. Audit what model was ACTUALLY used per photo. Log everything going forward.

## Data Layer Architecture (Source of Truth)

### Current state (problematic):
- Supabase/Postgres: annotations, identities, GEDCOM tables, calibration pairs ✅
- Cloudflare R2: image blobs ✅
- JSON files in repo: date_labels.json, face detection, clusters, face_alignments ❌ (liability)
- MLflow local: experiment tracking (acceptable to lose/rebuild)

### Target state:
- Postgres = source of truth for ALL structured data
- R2 = image blobs only
- JSON files = cache-only or eliminated entirely
- Flow: R2 stores images → Postgres stores everything about images → app reads from Postgres → JSON exports only for specific offline use

### Migration principle:
- User-entered data MUST be in Supabase (AD-135 from Session 59C)
- ML-generated data should migrate to Supabase (this session starts that)
- Dual-write pattern from migration was a bridge — it should not be permanent

## Gemini Model Research (Feb 23, 2026)

### Current model landscape:
| Model | Input/1M tokens | Output/1M tokens | Status | Free tier |
|-------|----------------|-------------------|--------|-----------|
| gemini-3.1-pro-preview | $2.00 | $12.00 | Preview (Feb 19) | Unknown — check |
| gemini-3-pro-preview | $2.00 | $12.00 | Preview | No (paid only) |
| gemini-3-flash-preview | $0.50 | $3.00 | Preview | Yes |
| gemini-2.5-flash | $0.30 | $2.50 | Stable | Yes |

### Rate limits (Tier 1 paid):
- Preview models: ~250 RPD, 10-50 RPM
- Stable models: higher limits
- Tier 2 requires $250 cumulative spend + 30 days

### Batch API (IMPORTANT — use for remaining 144 photos):
- 50% cost discount on ALL paid models
- 24-hour SLO but often much faster
- Supports multimodal (images)
- JSONL file input, results within 24 hours
- No quality difference vs synchronous
- Context caching available (90% discount on cached tokens)
- gemini-3.1-pro-preview batch: $1.00/$6.00 per 1M tokens
- 144 photos × ~$0.028/photo = ~$4.03 sync. With batch: ~$2.02

### Model decision for this session:
- **Face alignment + GEDCOM enrichment:** gemini-3.1-pro-preview (best vision reasoning, same price as 3.0 Pro, released Feb 19)
- **Batch processing:** Use Batch API for remaining 144 photos (50% discount, no rate limit issues)
- **Fallback:** gemini-3-flash-preview for testing/dry-runs ($0)
- **CRITICAL:** Every API call must log: model used, tokens in/out, cost, latency, status, photo_id

### Gemini 3.1 Pro notable capabilities:
- ARC-AGI-2: 77.1% (2x improvement over 3.0 Pro)
- 1M token context window
- Configurable thinking levels
- Same price as 3.0 Pro (free upgrade)
- maxOutputTokens default is only 8,192 — must set explicitly for full 64K

## Harness Improvements (Skills + Hooks + Worktrees)

### Skills to create this session:

#### 1. `/skill:session-run` — Overnight session execution framework
- Phase decomposition template
- Commit discipline rules
- /clear protocol (NOT /compact)
- Verification gate template
- Session logging (SESSION_HISTORY.md update)
- ~40 lines

#### 2. `/skill:deploy-verify` — Railway deploy + production smoke test
- git push origin main
- Wait for Railway deploy
- Hit key routes: /, /map, /connect, /tree, /timeline, /collections, /compare
- Check for 500s
- Report results
- ~30 lines

#### 3. `/skill:ml-pipeline` — ML code modification protocol
- Read ALGORITHMIC_DECISIONS.md FIRST
- Make changes
- Update AD with decision provenance (accepted/rejected/why/source)
- Run rhodesli_ml/tests/
- Run pytest tests/ -x -q
- ~30 lines

#### 4. `/skill:assess-session` — Automated session output assessment
- Read session transcript/output
- Check each phase: completed/skipped/partial
- Flag concerns (JSON vs Supabase, missing tests, skipped verification)
- Generate structured assessment with red flags
- This replaces the manual "concerns and red flags" review we do every time
- ~50 lines

#### 5. `/skill:build-prompt` — Session prompt builder
- Read ROADMAP.md, BACKLOG.md, last session log
- Check session_context/ for current breadcrumbs
- Apply prompt best practices:
  - Small phases (ONE deliverable per phase)
  - /clear between phases (mandatory, repeated)
  - Verification gate at end of each track
  - Commit per phase
  - Total prompt under 3500 tokens per track
- Generate prompt file to docs/prompts/
- ~50 lines

### Hooks to add:

#### 1. Pre-commit: test gate
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "bash -c 'INPUT=$(cat); CMD=$(echo \"$INPUT\" | jq -r .tool_input.command); if echo \"$CMD\" | grep -qE \"^git commit\"; then cd $CLAUDE_PROJECT_DIR && python -m pytest tests/ -x -q --ignore=tests/e2e/ 2>&1 | tail -5; fi'"
        }]
      }
    ]
  }
}
```

#### 2. Post-edit on ML files: AD reminder
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{
          "type": "command",
          "command": "bash -c 'INPUT=$(cat); FILE=$(echo \"$INPUT\" | jq -r .tool_input.file_path // .tool_input.path // \"\"); if echo \"$FILE\" | grep -qE \"(rhodesli_ml|core)/.*\\.py$\"; then echo \"REMINDER: If this changes ML behavior, update ALGORITHMIC_DECISIONS.md with provenance.\"; fi'"
        }]
      }
    ]
  }
}
```

#### 3. Stop hook: session completion notification
```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "osascript -e 'display notification \"Claude Code session completed\" with title \"Rhodesli\"'"
      }]
    }]
  }
}
```

### Worktrees:
- Track A (verify-migrate) and Track B (batch-complete) run in parallel worktrees
- Setup: `git worktree add ../rhodesli-track-a -b session-64-track-a`
- Setup: `git worktree add ../rhodesli-track-b -b session-64-track-b`
- Merge when both complete
- Fallback if worktree fails: sequential with /clear between tracks

## CLAUDE.md Trim Target
- Current: likely 3000+ chars
- Target: under 2000 chars
- Move domain-specific rules to `.claude/rules/` path-scoped files
- Move workflow knowledge to `.claude/skills/`
- CLAUDE.md retains ONLY: project identity, stack summary, critical invariants, pointer to rules/skills

## Roadmap/Backlog Safety
- Before ANY edit to ROADMAP.md or BACKLOG.md, diff against current version
- No item may be silently removed — only explicitly completed or deprioritized with breadcrumb
- The `/skill:build-prompt` skill should enforce this check

## Files Checklist (for prompt to create/update)
- [ ] `.claude/skills/session-run.md`
- [ ] `.claude/skills/deploy-verify.md`
- [ ] `.claude/skills/ml-pipeline.md`
- [ ] `.claude/skills/assess-session.md`
- [ ] `.claude/skills/build-prompt.md`
- [ ] `.claude/settings.json` (hooks configuration)
- [ ] `CLAUDE.md` (trimmed to <2000 chars)
- [ ] `.claude/rules/ml-development.md`
- [ ] `.claude/rules/data-layer.md`
- [ ] `.claude/rules/session-protocol.md`
- [ ] `gemini_api_calls` Supabase table (migration SQL)
- [ ] Face alignment data migrated to Supabase
- [ ] Remaining 144 photos processed via Batch API
- [ ] UI verification: calibrated scores, face cards, recalibration hooks
- [ ] Vida Capeluto photo explicitly tested
- [ ] ALGORITHMIC_DECISIONS.md updated with session decisions
- [ ] ROADMAP.md updated (no items lost)
- [ ] SESSION_HISTORY.md updated
