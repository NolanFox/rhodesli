# Batch Data Pipeline Rules

Triggers: When writing scripts that process data in batch (scripts/*.py),
or when running any script that produces data consumed by the web app.

## Rule: Batch outputs MUST write to Supabase (source of truth)

Any script that produces data the web app reads MUST write to the
Supabase table the app reads from, not just a local JSON file.

### Before writing a batch script, check:
1. Where does the app READ this data? (`grep` for the loader function)
2. Does the app read from Supabase or local JSON?
3. If Supabase: the script MUST upsert to that table
4. If JSON on Railway volume: the script must deploy the file

### After a batch run completes:
1. Verify the data is in the Supabase table (`SELECT count(*) FROM table`)
2. Verify the production UI shows the data (browser check, not just API)
3. If the UI says "no data" — the write path is broken

### Known data paths:
- `date_labels` → Supabase `date_labels` table (photo_id, data JSONB)
- `identities` → Supabase `identities` table
- `photo_faces` → Supabase `photo_faces` table
- `gemini_api_calls` → Supabase `gemini_api_calls` table (audit log)

## Why this exists (Session 142)
Batch Gemini script wrote 84 date labels to local `rhodesli_ml/data/date_labels.json`.
Production app reads from Supabase `date_labels` table. User checked the photo page
and saw "No AI analysis" even though the data existed locally. The disconnect
between batch output and production read path went undetected for ~20 hours.

See: Lesson 162, data-layer.md
