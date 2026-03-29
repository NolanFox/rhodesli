# Session 144 Batch Re-Run Plan

## Stats
- 547 total date_labels
- 192 with GEDCOM context (Session 143 batch)
- 355 without GEDCOM context (need re-run)
- Daily limit: 250 RPD (Tier 1)

## Execution Order

### Step 1: Canary Run (3 photos)
Re-run 3 already-labeled photos to compare old vs new output:
```bash
source venv/bin/activate
python scripts/batch_gemini_for_person.py \
  --photo-ids "inbox_fox-charlie-001_301_01731_p_13akf5twbc1164_z,inbox_fox-charlie-001_490_01828_p_13akf5twbc2277,inbox_fox-charlie-001_124_01889_p_13akf5twbc1710_r" \
  --preset full \
  --dry-run
```
Then without `--dry-run`. Compare output to Session 143 results — should now include:
- Spouse timeline in GEDCOM context
- Birth date confidence annotations
- Structured location with candidates
- Confirmed identities block

### Step 2: Never-Run Photos (up to 247 remaining quota)
```bash
python scripts/batch_gemini_for_person.py \
  --person "Albert Fox" --person "Esther Burd Fox" \
  --skip-existing \
  --preset full
```

### Step 3: Day 2 — Session 142 Photos (remaining ~83)
Re-run photos that had GEDCOM context missing.

## Read-Merge-Write Semantics
The batch script now preserves:
- `date_refinement_history` from previous runs
- `human_date_correction` / `human_location_correction`
- Any field with `source: "human"`
This means re-runs are safe — they won't overwrite manual corrections.

## Verification
After each sub-batch:
1. Check Supabase: `SELECT count(*) FROM date_labels WHERE data->>'gedcom_context_sent' = 'true'`
2. Check a sample photo page in browser
3. Verify location candidates appear in expandable section
