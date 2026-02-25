# Session 66b Context: Upload Silent Data Loss Fix + B-Path Fix-ups

## Source
- **Date:** 2026-02-25
- **Origin:** Session 66 assessment review by Nolan + Claude
- **Trigger:** Upload still silently drops data after 4 "fix" sessions
- **This is a b-path session.** Session 66 was the first pass. This addresses failures from that pass.

---

## THE UPLOAD BUG — TIMELINE OF FAILURE

| Session | What Was "Fixed" | What Actually Happened |
|---------|-----------------|----------------------|
| 65a | Added PID tracking, 5-min timeout for subprocess | Treated symptom (frozen UI), not cause (subprocess dying) |
| 65c | Replaced subprocess with background thread sharing models | Fixed RAM issue, but only verified via HTTP (curl), not browser |
| 65d | Fixed disk space (.dockerignore, cleanup, monitoring) | Upload endpoints respond, browser showed "0 faces" with synthetic images |
| 66 | Parallel subagent built GEDCOM UI, didn't touch upload | Assessment said "Chrome can't handle file dialogs" — skipped testing |
| **Nolan's manual test** | Uploaded morris_mazal_ancestry_murry_army.jpeg | **UI says "✓ 3 faces extracted, 3 added to Inbox" — BUT faces NOT in Inbox, photo NOT in library** |

**The pattern:** Every session claims upload works based on incomplete evidence. No session has verified that uploaded data actually persists and appears in the application.

## EVIDENCE FROM NOLAN'S SCREENSHOT
- URL: rhodesli.nolanandrewfox.com/upload
- Green success banner: "✓ 3 faces extracted, 3 added to Inbox" with "Refresh to see inbox" link
- Help Identify count: 202 (did NOT increase to 205)
- Sidebar shows: 55 People, 271 Photos (neither increased)
- Conclusion: Face detection runs successfully but database persistence fails silently

## LIKELY ROOT CAUSE HYPOTHESES (investigate all)

1. **Background thread race condition:** The success message is sent from the main thread before the background thread finishes writing to the database. The background thread then fails silently.

2. **Supabase write fails silently:** The insert to Supabase returns an error but the error handling swallows it and still reports success to the UI.

3. **R2 upload failure cascades:** If the photo can't be written to R2 (CloudFlare storage), subsequent steps may fail but the UI already showed success.

4. **Schema mismatch:** The GEDCOM versioning migration (Session 66) may have altered table constraints that now reject new inserts. The `version_id`, `is_current`, or `superseded_by` columns added to face/photo tables may have NOT NULL constraints or foreign key violations.

5. **Environment variable mismatch:** The Railway deployment may use different Supabase credentials or R2 credentials than what works locally.

6. **The "prefer_hybrid" thread change from 65c:** The background thread shares the main process's models, but maybe the thread dies silently on an exception and the main thread never checks.

## HYPOTHESIS #4 IS MOST SUSPICIOUS
Session 66 ran `supabase_migration_002_gedcom_versioning.sql` which added columns to existing tables. If these columns have NOT NULL constraints without defaults, ALL inserts to those tables would fail with a constraint violation. The upload code wouldn't know about these new columns and wouldn't populate them. This would cause EXACTLY the symptom we see: face detection works (it's in-memory), but database writes fail.

**CHECK THIS FIRST:**
```sql
-- Check if new columns have NOT NULL constraints
SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_name IN ('photos', 'faces', 'inbox_items')
AND column_name IN ('version_id', 'is_current', 'superseded_by');
```

---

## B-PATH ITEMS FROM SESSION 66 REVIEW

### Already addressed by upload fix (Phase 0-1):
- Real photo upload not tested ← fixed by using morris_mazal photo

### Additional items (Phases 2-5):
1. **GEDCOM upload not tested with real file** — Use Playwright or curl to bypass file dialog
2. **UX reviewer subagent never invoked** — Delegate session 66 screenshots for review
3. **Session evaluator never invoked** — Let it independently assess session 66
4. **Enrichment validation vague** — Review docs/analysis/enrichment_validation_66.md for substance
5. **/clear not used in headless mode** — Investigate if it even works in `-p` mode
6. **Version string stale (v0.65.0)** — Update to v0.72.1

---

## FILE DIALOG WORKAROUNDS

The Chrome extension cannot interact with native OS file dialogs. Three alternatives:

1. **Playwright `set_input_files()`:**
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto("https://rhodesli.nolanandrewfox.com/upload")
    # Set cookies for admin auth
    page.set_input_files("input[type=file]", "/path/to/photo.jpeg")
    page.click("button[type=submit]")  # or whatever triggers upload
```

2. **curl with admin cookie:**
```bash
curl -X POST \
  -F "file=@/path/to/photo.jpeg" \
  -H "Cookie: session=<admin_session_cookie>" \
  https://rhodesli.nolanandrewfox.com/upload
```

3. **Python requests:**
```python
import requests
with open("/path/to/photo.jpeg", "rb") as f:
    resp = requests.post(
        "https://rhodesli.nolanandrewfox.com/upload",
        files={"file": f},
        cookies={"session": "<admin_session_cookie>"}
    )
```

Use whichever works. The point is: DO NOT SKIP UPLOAD TESTING because of the file dialog limitation.
