Use `docs/session_context/session-100-context.md` as required context.

Before acting, read all of these files:
- `docs/prds/040_multi_community_bootstrap_and_face_cards.md`
- `docs/assessments/session-100-codex-research.md`
- `docs/assessments/session-100-antigravity-plan-review.md`
- `docs/assessments/session-100-antigravity-workflow-review.md`
- `docs/assessments/session-100-face-tagging-and-fox-family-audit.md`
- `docs/assessments/session-100-fox-family-screenshot-audit.md`
- `docs/session_logs/session-100-planning-log.md`
- `docs/session_logs/session-100-fox-family-hotfix-log.md`

This is a docs/mockups-only design pass. Do not implement app code.

I want a targeted mockup pack for the Rhodesli high-speed tagging workflow.

Design only these surfaces:
1. A batch cluster confirmation surface:
   - “Are these all Roland Fox?”
   - bulk confirm
   - bulk reject
   - bulk ignore noise
   - easy merge/split follow-up affordances
2. A photo-level review loop:
   - tag one face
   - auto-advance to the next unresolved face
   - preserve archive/admin context
   - make “ignore background stranger” fast
3. A dense multi-face expanded view:
   - wrapping grid, not just horizontal strip
   - clear primary/secondary actions
   - source-photo context remains obvious
4. A unified review-shell concept:
   - enough continuity that the user is not forced to mentally switch between
     queue, person, identify, and tree modes for every action

Requirements:
- Keep it Rhodesli-specific, not generic SaaS UI.
- Do not over-index to any single competitor.
- Optimize for speed, confidence, and low click-count.
- Preserve community distinction, admin/public distinction, and review-section clarity.
- Explicitly show what makes the flow feel “lightning fast” versus “CMS-like”.

Create:
- `docs/assessments/session-100-antigravity-mockup-pack.md`

If you generate images/mockups, store them under:
- `docs/assessments/mockups/session-100/`

The mockup pack must include:
- 3-5 concrete mockup concepts
- what problem each solves
- click-count / flow improvements versus current Rhodesli
- risks / over-design traps
- which concept you would recommend implementing first

Update:
- `docs/session_logs/session-100-fox-family-hotfix-log.md`

Do not rewrite the Codex plan in place.
Findings and design reasoning first, mockups second.
