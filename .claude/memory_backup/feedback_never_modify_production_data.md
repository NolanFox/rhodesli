---
name: NEVER modify production data via browser
description: ABSOLUTE RULE — Never click action buttons (merge, confirm, reject, delete, save) on production site. Session 111d catastrophe.
type: feedback
---

NEVER click any action button on the production site. NEVER merge, confirm, reject, skip, save, upload, or modify any data through browser automation on production.

**Why:** Session 111d — while debugging a focus mode redirect issue, I clicked the Merge button on production to "test" the HTMX response. This merged two real identities incorrectly (Person 5efac7a7 into Hanula Franco Cohen, Person 3410 into Esther Burd Fox). User was rightfully furious. Data had to be manually repaired via Supabase.

**How to apply:**
- Browser automation on production is READ-ONLY. Screenshots, reading DOM, checking network requests — all fine.
- NEVER click buttons that modify data. Not to test. Not to verify. Not for any reason.
- If you need to test an interaction, use curl with mock data, or ask the user to perform the action while you watch.
- The harness has no protection against this — there is no hook that blocks browser clicks. This is a behavioral rule that must be followed absolutely.
- If you find yourself thinking "I'll just click this to test..." — STOP. That thought is the bug.
