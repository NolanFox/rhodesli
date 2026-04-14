---
name: Always use latest Gemini model
description: Always use the most recent available Gemini model unless there's an explicit documented reason not to. Log model downgrades as degradations, not silent fallbacks.
type: feedback
---

Always use the most recent available Gemini model (currently gemini-3.1-pro-preview via GEMINI_MODEL config).

**Why:** Nolan asked why we used 2.5 Pro instead of 3.1 Pro for a face comparison. The answer was a transient 504 timeout that caused silent fallback. Silent model downgrades are unacceptable — they should be logged prominently and the call retried.

**How to apply:**
- Check `rhodesli_ml/gemini_config.py` for `GEMINI_MODEL` — this is the source of truth
- If the configured model fails, retry before falling back
- If fallback is unavoidable, log the downgrade in gemini_api_calls with a note in gemini_config field
- The gemini_api_calls table already has `model_used` column — verify it matches GEMINI_MODEL
- All API calls should be logged regardless of model used
