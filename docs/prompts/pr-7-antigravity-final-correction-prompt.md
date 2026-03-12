# Prompt For Antigravity On PR #7: Final Correction Pass

Work only on branch `modern-ui-research` and PR #7:
https://github.com/NolanFox/rhodesli/pull/7

Before you edit anything, re-read:
- `docs/assessments/pr-7-modern-ui-antigravity-revision.md`
- `docs/assessments/pr-7-modern-ui-codex-audit.md`
- `docs/session_logs/pr-7-modern-ui-codex-log.md`
- `docs/session_context/pr-7-modern-ui-codex-context.md`

Important constraints:
- Rhodesli remains `FastHTML + HTMX + Tailwind CDN` per `HD-022`.
- This is still docs-only. Do not touch app code yet.
- Do not disturb ongoing work outside PR #7.
- Preserve explicit attribution boundaries between user, Antigravity, Codex, and PR-thread collaboration.

One more narrow correction pass is required before Session 99 prompt writing.

Please update `docs/assessments/pr-7-modern-ui-antigravity-revision.md` with these repo-backed fixes:

1. Fix the `/identify/{id}` invariants.
- Remove `[data-testid="identify-person-form"]` because that selector does not exist.
- Remove `name="identity_id"` because the route uses `name="person_id"`.
- Replace them with actual public identify invariants from `app/page_routes.py` / tests.
- Safe candidates include:
  - the hidden `name="person_id"` input
  - `name="name"` and `name="relationship"`
  - `hx_post="/api/identify/{person_id}/respond"`
  - `og:title` / `og:image`
- Do not treat `name="email"` or the exact submit button text as globally stable, because they vary by auth/admin state.

2. Fix the workstation smoke-check route.
- Replace `/?section=inbox` everywhere with a valid deterministic route.
- Use `/?section=to_review` unless you have a stronger repo-backed reason to prefer another valid section.
- Update the screenshot-checkpoint route list as well.

3. Resolve the `_public_nav_links` scope contradiction.
- Right now the doc says `_public_nav_links` is `safe to restyle globally`, but that helper is reused by many out-of-scope public routes (`/photos`, `/collections`, `/people`, `/timeline`, `/map`, `/tree`, `/connect`, `/tools/compare`, `/tools/estimate`, etc.).
- If Session 99 remains scoped to `/`, `/identify/{id}`, and `/?section=...`, then `_public_nav_links` must not be globally restyled.
- Update the touch map and leakage rules accordingly. The safer default is `needs scoped variant` or route-local composition.
- If you instead want public nav chrome to become explicitly in-scope across all public routes, then revise the scope-control section to say so and add the corresponding preservation inventory and regression plan. Do not leave this ambiguous.

4. Keep attribution explicit.
- user-directed orchestration
- Antigravity-authored research/revision
- Codex-authored audit/handoff artifacts
- PR-thread collaborative boundary

When finished:
- commit only the revised Antigravity-authored document
- comment on PR #7 summarizing the corrections
