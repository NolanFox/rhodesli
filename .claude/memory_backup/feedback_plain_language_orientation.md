---
name: feedback_plain_language_orientation
description: End sessions with a plain-language, menu-style "what we did / your decisions / pick your next move" written TO Nolan — not a dense technical recap
metadata:
  type: feedback
---

**2026-07-14 (Session 171):** After several technically-dense end-of-session summaries, Nolan said
"I'm a bit confused what my next steps are" and asked for a continuation prompt that "at the start
explains what we've done and what's next."

**Why:** Nolan is the product owner + detective, not a code reviewer of the harness. Dense recaps of
commits/audits/CI don't tell him what to DO next. He orients on decisions and next moves, in his own
domain language (cases, evidence, photos), not internals.

**How to apply:** Every substantive session ends with a short doc written in the second person TO him:
(1) *what we did* in plain language (product terms, not commit hashes), (2) *your decisions/actions*
— the human-in-the-loop items only he can do, (3) *pick your next session* — a small menu with the
exact phrase to say to start each, plus an "if unsure" default. Keep the technical detail in the
assessment/log and POINT to it; don't lead with it. Template lives at
`docs/prompts/session-172-CONTINUATION.md` (Session 171). Related: [[feedback_voice_mode]]
[[project_research_desk_pivot]].
