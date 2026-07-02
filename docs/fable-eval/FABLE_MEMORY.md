# FABLE_MEMORY — lessons learned during the Fable eval run (2026-07-02)

One lesson per entry: one-line summary first, then why it mattered + source evidence.

- **App monolith has moved: `app/page_routes.py` (13,389 lines) is now larger than `app/main.py` (8,255).** The brief's orientation note said to verify sizes — verified via `wc -l app/*.py`. Any "main.py refactor" framing in docs is stale; the true hotspot for route-sweeps is page_routes.py.

- **Empty face-crop tiles in full-page screenshots are a lazy-load artifact, NOT broken crops.** On `/help` and `/person/*`, below-fold tiles render blank in a `fullPage` capture; network check showed 35/35 crop requests returning 200 OK (all `pub-*.r2.dev/crops/*.jpg`). Discipline win: a vision-only finding ("crops broken, HIGH") was corrected to LOW/cosmetic by cross-checking `browser_network_requests`. Always verify a "broken image" vision finding against the network tab before reporting.
- **On `/c/rhodes/people` the nav + person-card links are root-relative (`/person/{id}`, `/photos`), not `/c/rhodes/`-prefixed** — live DOM confirms W4 code finding V2 (hardcoded root links in `app/components/photo_analysis.py`). Clicking a person drops the community context. Verified via `browser_snapshot`.
- **People page contradiction: header says "131 awaiting identification" but the "Needs Name (0)" filter shows 0**, while `/help` shows "50 faces awaiting identification" with a full grid. Three surfaces, three different counts of the same concept — Lesson 116 (counts from different data sources). Contribution dead-end on the People page.
- **Two of three archive cards on the landing page show "0 PEOPLE"** (Fox Family 670 photos/0 people; Sarah Fox Fader 147/0) — non-Rhodes archives have no surfaced identities; the "Do you recognize anyone?" CTA leads to an empty people set. Verified via landing screenshot.
