---
name: Browser vs API usage guidance
description: Use Chrome browser for testing/verification, use API/programmatic for deep analysis in interactive sessions
type: feedback
---

Chrome browser tools vs programmatic API access — use the right tool for the job.

**Why:** During Session 145, I used Chrome browser to try to find Rachel's similar matches by scrolling through the UI. Nolan pointed out I should have fetched it programmatically via API for deep analysis.

**How to apply:**
- **Chrome browser**: Use for testing, verification, screenshots, UX evaluation, and visual confirmation after deploys. READ-ONLY on production.
- **Programmatic (API/scripts/python)**: Use for deep analysis, embedding comparisons, data queries, batch operations during interactive sessions. Much faster and more precise.
- **Rule of thumb**: If you need to extract data for analysis, use the API. If you need to verify how something looks to a user, use Chrome.
