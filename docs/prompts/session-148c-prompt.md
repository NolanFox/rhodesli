# Session 148c — Resume Fader Collection Fox Identification

**Mode:** Interactive (feedback-driven)
**Predecessor:** Session 148 (Fader exploration started) + 148b (overnight implementation)
**Context:** `docs/session_context/session-148c-context.md`

## Session Goal
Continue systematic identification of Fox family members in the Sarah Fox Fader Collection. User will review candidate photos and provide identifications. Log everything for future sessions.

## Phase 0: Orient (2 min)
- Read context file
- `source venv/bin/activate && make test-fast` (baseline)
- Set session: `echo "148c" > .claude/current_session.txt && echo "interactive" > .claude/session_mode.txt`

## Phase 1: Resume Fader Photo Review
- 20 candidate photos remain (see context file table)
- Present photos to user for identification, starting with high-value group photos:
  - 8-person group: https://rhodesli.nolanandrewfox.com/c/fader-collection/photo/68832ba89824c706
  - 6-person group: https://rhodesli.nolanandrewfox.com/c/fader-collection/photo/496bce2281e8d7b8
  - 4-person group: https://rhodesli.nolanandrewfox.com/c/fader-collection/photo/97db3387982454f3
  - 3-person group: https://rhodesli.nolanandrewfox.com/c/fader-collection/photo/eb8e9667c6fbbd2e
  - Then closer-distance solo/pair photos
- For each identification: log person ID, name, photo, and any family context
- Use TOOLS-007 API to search for newly identified people across collections

## Phase 2: Expand Search Beyond Sherry
- Once Sherry's photos are triaged, search for:
  - **Ira Josowitz** — run same distance search for him
  - **Abraham Fader** / **Nadia Kubrin** — Sherry's parents (if identifiable from older photos)
  - **Fox siblings** — cross-reference with Fox Family collection
- Use `scripts/sherry_search.py` pattern (or TOOLS-007 API) for each new person

## Phase 3: Log Feedback + UX Observations
- This is an interactive session — capture ALL user feedback as FB-NNN items
- Note any UX friction in the cross-collection identification workflow
- Ideas for improving the process → BACKLOG

## Phase 4: Session Close
Standard harness: assessment, CHANGELOG, ROADMAP, deploy, browser verify, memory backup.
