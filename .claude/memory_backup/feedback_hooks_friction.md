---
name: Hooks cause friction at session end
description: Stop hooks and session-end enforcement create friction — need to differentiate continuation vs full session end
type: feedback
---

Hooks aren't working well overall. Specific issue: stop hooks that enforce assessment + clean git don't differentiate between writing a continuation prompt (mid-session handoff due to context pressure) vs. fully ending a session. This wastes time when context is running low and the priority should be committing work + writing the continuation prompt quickly.

**Why:** User observed hooks consuming valuable time during a context-pressure situation (Session 100c). The enforcement overhead exceeds its benefit in mid-session handoffs.

**How to apply:** When context is low and you need to hand off, prioritize: (1) commit all code, (2) write continuation prompt, (3) write assessment. Don't let hook enforcement block the handoff. Consider proposing a hook redesign that has a "continuation" mode vs "session-end" mode.
