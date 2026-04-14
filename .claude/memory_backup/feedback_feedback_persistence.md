---
name: Feedback must persist to disk immediately
description: All user feedback must be written to disk via background subagents immediately — cannot rely on conversation context surviving
type: feedback
---

Write all feedback to disk IMMEDIATELY via background subagents. Don't wait for a batch write. If session crashes, feedback must survive.

**Why:** User worried that session might "accidentally cave" (compact/crash). Feedback is the primary deliverable of interactive sessions.

**How to apply:** On every piece of feedback, spawn a background subagent to append to the feedback file. Don't block the conversation. Verify file has all entries at milestones.
