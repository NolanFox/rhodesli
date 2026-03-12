# Session 100 Antigravity Live Review Prompt

Use this only after the Session 100 branch is merged and deployed.

## Read First

- `docs/assessments/session-100-speed-loop-implementation.md`
- `docs/assessments/session-100-antigravity-mockup-pack.md`
- `docs/session_logs/session-100-fox-family-hotfix-log.md`
- `docs/session_context/session-100-context.md`

## Mission

Do a browser-only review of the merged Session 100 Fox Family workflow.

This is **not** an implementation pass unless you find a concrete visual or UX
regression that should be fixed in a narrow follow-up PR.

## Verify In Chrome

1. Fox Family person page performance and usability:
   - `/c/fox-family/person/ae0b181b-db55-4c3e-853d-0fdc904a1000`
2. Person -> photo -> next/previous continuity:
   - stay in person-gallery context, not collection-only context
3. Full photo page speed-tagging loop:
   - `Name These Faces`
   - auto-advance within photo
   - auto-advance to next context photo when current photo is done
   - `Ignore Stranger`
4. Community/admin/share boundary correctness:
   - Fox Family pages should not silently fall back to Rhodes/default routes
5. Dense multi-face presentation:
   - crowded photo should use the wrap-grid fallback, not a tedious horizontal strip
6. Tree path sanity:
   - `/c/fox-family/tree?person=a0a845d7-4eca-4255-b741-77ff310dc619`
   - note speed and obvious interaction regressions only

## Deliverables

Write:
- `docs/assessments/session-100-antigravity-live-review.md`

Update:
- `docs/session_logs/session-100-fox-family-hotfix-log.md`

## Reporting Rules

- Findings first, ordered by severity
- Be explicit about what is:
  - fixed
  - still awkward
  - materially better than before
  - still not good enough for outside contributors
- Include screenshot evidence paths if you capture new screenshots
- Keep attribution explicit:
  - Antigravity = browser review / critique
  - Codex = implementation / test verification / harness trail

## Do Not

- do not broaden scope into unrelated community work
- do not touch data files
- do not deploy
- do not claim the workflow is “done” unless the browser evidence supports it
