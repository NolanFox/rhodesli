# Prompt For Antigravity On PR #7

Work only on branch `modern-ui-research` and PR #7:
https://github.com/NolanFox/rhodesli/pull/7

Before you do anything, read these files carefully:
- `docs/assessments/modern-ui-research-and-scoping.md` (your original note)
- `docs/assessments/pr-7-modern-ui-codex-audit.md` (Codex audit)
- `docs/session_context/pr-7-modern-ui-codex-context.md` (handoff + attribution)

Important constraints:
- Rhodesli is FastHTML + HTMX + Tailwind CDN, not React/Next.js.
- `HD-022` explicitly keeps FastHTML + surgical JS and rejects a full React migration for now.
- `DD-001` and `DD-002` already establish an archival/editorial visual direction.
- Do not touch app code yet.
- Do not disturb ongoing merge work for sessions 96-98.
- Preserve clear attribution: keep your new work separate from Codex-authored audit artifacts.

Your task:
1. Revise the PR so it becomes stack-correct and implementation-safe.
2. Add a new Antigravity-authored follow-up document rather than overwriting Codex's audit.
3. In that document, do all of the following:
   - explicitly acknowledge the FastHTML/HTMX architecture and `HD-022`
   - identify which parts of your original research remain valid as inspiration
   - identify which recommendations were React-specific or too generic to apply directly
   - synthesize recent 2025-2026 design research on avoiding AI-slop sameness
   - distinguish inspiration-only tools from implementation-ready tools
   - propose a Rhodesli-specific design direction for:
     - public landing page
     - public share-ready pages
     - admin/workstation pages
   - give a route-by-route preservation inventory so no behavior regresses
   - propose a phased FastHTML + HTMX + surgical-JS implementation plan
   - define verification gates: tests, DOM invariants, auth/admin boundaries, share flows, and screenshot checkpoints

Required output file:
- `docs/assessments/pr-7-modern-ui-antigravity-revision.md`

Required attribution section inside that file:
- `Antigravity-authored in this revision`
- `Codex-authored reference artifacts`
- `Collaborative / handoff state`

Required research behavior:
- Use dated citations from 2025-2026 wherever possible.
- Include recent Reddit and YouTube/social/design-community signals, but cite them carefully.
- If you mention Stitch, Nano Banana, 21st.dev, Shadcn, Aceternity, Magic UI, or similar tools, label each one as one of:
  - `inspiration only`
  - `prototype workflow`
  - `stack-compatible now`
  - `not compatible without architecture change`

Important:
- Do not propose React migration as the default path.
- If you think migration is still warranted, put it in a separate appendix called `Migration Case (Not Approved)` with quantified costs, risks, and required contracts. Do not treat it as the active plan.
- Keep the main recommendation aligned with zero-regression FastHTML/HTMX evolution.

When you finish:
- commit only your new Antigravity-authored file(s)
- comment on PR #7 summarizing what changed and how you responded to the Codex audit
