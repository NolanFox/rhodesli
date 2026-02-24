# Session 65d Context: Disk Space Fix, GEDCOM Versioning, Self-Improving Harness

## Source
- **Date:** 2026-02-24
- **Origin:** 65c browser test showing Errno 28, Nolan requirements for GEDCOM update flow, research on self-improving prompt systems
- **Previous sessions:** 65a (upload error detection), 65b (skipped upload), 65c (fixed RAM — but disk is now full)
- **App version:** v0.70.0
- **Production URL:** https://rhodesli.nolanandrewfox.com

---

## PART 1: UPLOAD ROOT CAUSE — DISK FULL (Errno 28)

### What Nolan Saw
Screenshot from Feb 24: uploaded `morris_mazal_ancestry_murry_army.jpeg` and got:
```
Error: Unknown error
• morris_mazal_ancestry_murry_army.jpeg: [Errno 28] No space left on device
```

### This Is NOT the Same Bug as 65a/65c
- **65a/65c diagnosis:** RAM issue — subprocess loading duplicate InsightFace models. FIXED by switching to background thread with shared models.
- **65d diagnosis:** DISK SPACE — the Railway container's filesystem is full. The upload correctly processes the file (no more RAM crash) but fails when writing to disk.
- The 65c fix actually worked for RAM. The upload pipeline runs now, but hits a new wall: no disk space.

### Why the Disk Is Full — Likely Causes
1. **InsightFace model files cached on disk** (~300-500MB for buffalo_l). Multiple deploys may have accumulated cached model files.
2. **Temp files from processing** not cleaned up. Every upload creates temp files during face detection.
3. **Docker layers accumulated** from repeated deploys. Railway's ephemeral storage fills with build artifacts.
4. **Logs growing unbounded** — application logs or Supabase client logs filling disk.
5. **Railway volume at capacity** — if using a volume, it may be stuck at default 500MB or 1GB from initial creation.
6. **Git history / node_modules / Python packages** — the container may have large directories.

### How to Investigate
```bash
# SSH into Railway container or run via Railway CLI
# Check disk usage
df -h
du -sh /* | sort -rh | head -20
du -sh /app/* | sort -rh | head -20
du -sh /tmp/* | sort -rh | head -10

# Check for InsightFace model cache
find / -name "*.onnx" -o -name "buffalo*" 2>/dev/null | head -10
du -sh ~/.insightface/ 2>/dev/null

# Check temp files
ls -la /tmp/ | head -20
du -sh /tmp/

# Check Railway volume
echo $RAILWAY_VOLUME_MOUNT_PATH
du -sh $RAILWAY_VOLUME_MOUNT_PATH/* 2>/dev/null | sort -rh | head -10

# Check logs
du -sh /var/log/* 2>/dev/null | sort -rh | head -10
```

### Fix Strategies
**Immediate (get upload working NOW):**
1. Add cleanup of temp files after each upload (the processing pipeline should delete temp files when done)
2. Set InsightFace model cache to a known location, ensure only one copy exists
3. Add a startup script that cleans old temp files on app boot
4. If Railway volume is too small: resize it in Railway dashboard (Settings → Volume → Grow)

**Structural (prevent recurrence):**
1. Add a `scripts/cleanup_disk.py` that runs periodically or at startup
2. Set `INSIGHTFACE_ROOT` env var to control where models are stored
3. Add disk space monitoring — log available space at startup, warn if <100MB
4. Ensure temp file cleanup is in a `finally` block (runs even on errors)
5. Add `.dockerignore` to minimize container size (exclude tests, docs, .git)

**Railway-specific:**
- Ephemeral container storage is up to 100GB but shared across all services
- Volumes have a "Grow" option in settings — may need to increase from default
- Build artifacts don't persist to runtime, but cached layers do

### Impact Assessment
If the disk has been full for a while, this ALSO means:
- Session 65a/65b/65c commits that wrote to disk may have partially failed
- Session logs, assessment files, and other docs may not have been saved properly
- The 65c "upload fix" verification via HTTP requests may have worked because HTTP responses don't need disk, but file writes fail
- We need to verify ALL recent session work persisted after freeing disk space

---

## PART 2: GEDCOM VERSIONING ARCHITECTURE

### Use Case
When labeling people in Rhodesli, Nolan discovers new family connections not yet in his Ancestry tree. He wants to:
1. Update his tree in Ancestry with new info
2. Re-export the GEDCOM from Ancestry
3. Upload the new GEDCOM to Rhodesli
4. Have Rhodesli intelligently merge changes without losing data

### Data Model: Temporal Versioned GEDCOM

**Core principle:** Every GEDCOM import creates a new version. Old data is never deleted, only superseded. The app always reads the "current" state, but the full history is preserved for auditing and understanding how knowledge grew over time.

#### Tables

**`gedcom_versions`** — Each import creates a version
```sql
CREATE TABLE gedcom_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version_number INTEGER NOT NULL,  -- auto-incrementing per community
  community_id TEXT NOT NULL DEFAULT 'rhodesli',
  imported_at TIMESTAMPTZ DEFAULT NOW(),
  imported_by UUID,
  source_file TEXT,                  -- original filename
  source_hash TEXT,                  -- SHA256 of the file for dedup
  individual_count INTEGER,
  family_count INTEGER,
  notes TEXT
);
```

**`gedcom_individuals`** — Add version columns to existing table
```sql
-- Add to existing table:
ALTER TABLE gedcom_individuals ADD COLUMN version_id UUID REFERENCES gedcom_versions(id);
ALTER TABLE gedcom_individuals ADD COLUMN superseded_by UUID;  -- NULL = current
ALTER TABLE gedcom_individuals ADD COLUMN is_current BOOLEAN DEFAULT TRUE;
```

**`gedcom_change_log`** — Track what changed between versions
```sql
CREATE TABLE gedcom_change_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  version_id UUID REFERENCES gedcom_versions(id),
  change_type TEXT NOT NULL,  -- 'added', 'modified', 'removed'
  entity_type TEXT NOT NULL,  -- 'individual', 'family', 'event'
  xref_id TEXT NOT NULL,
  field_name TEXT,            -- which field changed (NULL for adds/removes)
  old_value TEXT,
  new_value TEXT,
  changed_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Views for Current State

```sql
CREATE VIEW current_gedcom_individuals AS
SELECT * FROM gedcom_individuals
WHERE is_current = TRUE AND superseded_by IS NULL;
```

**All Gemini queries, GEDCOM searches, and enrichment pipeline should read from `current_gedcom_individuals` view, never the raw table.**

#### Import Flow
1. Parse new GEDCOM file
2. Create new `gedcom_versions` entry
3. For each individual in new GEDCOM:
   a. Match to existing individual by `xref_id`
   b. If new: INSERT with `version_id`, `is_current=TRUE`
   c. If modified: Mark old row `is_current=FALSE`, `superseded_by=new_row_id`. INSERT new row.
   d. If unchanged: Keep existing row as-is (no new row needed)
   e. If removed from new GEDCOM: Mark old row `is_current=FALSE` (don't delete)
4. Log all changes to `gedcom_change_log`
5. Return summary: N added, N modified, N removed, N unchanged

#### Re-queueing Gemini Enrichment
When an individual's GEDCOM data changes:
- Find all photos containing that individual (via `gedcom_face_links`)
- Queue those photos for re-enrichment
- Log the reason: "GEDCOM update: [field] changed for [person]"
- **Do not auto-run** — queue for admin review first (Gatekeeper pattern)
- When re-running, log both the old and new Gemini results for comparison
- Track whether improvements are from GEDCOM changes vs model upgrades (add a `trigger` field: 'gedcom_update' vs 'model_upgrade' vs 'manual_rerun')

#### Multi-Community Future
The `community_id` field in `gedcom_versions` prepares for multiple communities. Each community can have its own GEDCOM lineage. When Nolan adds his Hungarian Jewish community or Marcus family, each gets its own version chain. Individuals can be cross-linked between communities (e.g., Roland Fox appears in both Rhodesli and Fox family).

**Schema supports this now, implementation deferred to Session 68+.**

---

## PART 3: SELF-IMPROVING HARNESS — RESEARCH FINDINGS

### The Problem
Our harness has persistent failure modes:
- Assessment files get skipped when context compacts
- Upload verification gets skipped with excuses
- Lessons learned don't automatically improve future prompts
- Post-session evaluation is a prompt instruction, not an enforced step

### Research: What SOTA Looks Like

#### 1. Stop Hook Pattern (O'Reilly / Jarek Orzel)
Claude Code has hooks that run automatically. The **Stop hook** fires when Claude finishes work and returns control to the user. Use it to trigger a subagent that reviews the session's work.

Key insight: "Asking the main agent to mark its own homework isn't a good approach." A separate subagent reviewing modified files catches what the main agent missed.

**Implementation for Rhodesli:**
Create `.claude/hooks/stop.sh`:
```bash
#!/bin/bash
# Post-session evaluation hook
# Triggered automatically when Claude Code finishes
# Uses a subagent to review work against the prompt

PROMPT_FILE=$(cat .claude/current_prompt.txt 2>/dev/null)
if [ -z "$PROMPT_FILE" ]; then exit 0; fi

# Launch evaluation subagent
claude --print "You are a session evaluator. Read $PROMPT_FILE and compare it against the actual work done (check git log, modified files, test results). Write docs/assessments/session-XXX-assessment.md with PASS/FAIL for each item. If any FAIL: suggest specific fix-ups." 
```

#### 2. Reflect System (haddock-development/claude-reflect-system)
A self-learning skill for Claude Code that captures corrections and permanently learns from them. When you correct Claude ("No, use uv instead of pip"), the system detects the correction pattern, updates the skill file, and Claude never repeats that mistake.

**Applicable to Rhodesli:**
- When Claude skips browser verification → `/reflect` captures "always verify in browser"
- When Claude compacts instead of clears → captured and prevented next time
- When assessment files are skipped → captured and enforced

#### 3. Langfuse Prompt Improvement Loop
Score traces → aggregate feedback → have Claude analyze patterns → propose prompt updates → apply and re-evaluate. This is the automated version of what we do manually in these review conversations.

### Recommended Implementation for Rhodesli

**Phase 1 (this session):** Create the Stop hook + evaluation subagent. This is the highest-leverage change — it runs automatically, can't be skipped by context compaction, and catches gaps we currently find manually.

**Phase 2 (Session 66):** Create a Reflect-style skill that captures recurring mistakes and updates CLAUDE.md rules automatically.

**Phase 3 (Session 67+):** Add Langfuse-style prompt scoring — after each session, score the prompt's effectiveness and have the system suggest improvements for the next prompt template.

---

## PART 4: CHROME PLUGIN IS WORKING

Screenshot 2 from Nolan shows:
```
Claude in Chrome (Beta)
Status: Enabled
Extension: Installed
Usage: claude --chrome or claude --no-chrome
```

**The Chrome plugin IS installed and enabled.** Previous sessions that said "Chrome tool not connected" were wrong — they likely didn't use the `--chrome` flag or didn't invoke the browser tool correctly.

**For this session:** Use `--chrome` flag when launching Claude Code. The browser tool inherits Nolan's admin session, solving the auth problem completely.

**How to use in prompts:**
- Claude Code can use the `browser` tool to navigate, click, type, upload files, and take screenshots
- Nolan is logged in as admin — all admin features are accessible
- Take screenshots at every verification step

---

## PART 5: CONTEXT COMPACTION RULES

### Problem
65b used /compact at some point, which is lossy. Our harness mandates /clear between phases.

### Rules (add to CLAUDE.md)
1. **ALWAYS use /clear between phases, NEVER /compact**
2. After /clear: re-read CLAUDE.md + context file + SESSION_LOG.md from disk
3. If context feels heavy MID-phase: commit current work, then /clear and re-read
4. /compact should NEVER be used — it's lossy and causes instruction amnesia
5. If /compact was used: note it in the assessment as a red flag
6. The assessment should log whether /clear or /compact was used between each phase

---

## PART 6: SESSION PRIORITY ORDER

1. **CRITICAL:** Fix disk space issue (free space on Railway, add cleanup)
2. **CRITICAL:** Verify upload works end-to-end in browser with Chrome plugin
3. **HIGH:** GEDCOM versioning architecture (schema + import flow)
4. **HIGH:** Stop hook for automatic post-session evaluation
5. **MEDIUM:** Harness rules updates (compaction ban, assessment mandate, Chrome usage)
6. **HOUSEKEEPING:** Docs sync, verify prior session work persisted
