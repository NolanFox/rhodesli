# W2 — Live-Site Product + UX + Vision Audit

**Method:** fresh logged-out Playwright browser (no auth), GET-only navigation, no clicks on
mutating controls, no form submits. Desktop 1280px + mobile 375px. Screenshots in
`docs/fable-eval/screenshots/`. Every finding is grounded in a screenshot and/or a live DOM
snapshot / network read from this run. Production auth state: **anonymous throughout.**

## What's genuinely impressive (lead with the strengths)
- **Editorial museum-quality design.** Dark theme, serif display headings, restrained palette.
  The photo page (`photo-desktop.jpeg`) is a standout: date estimate w/ confidence bar, a Leaflet
  location map, "Photo Detective Evidence" (Print/Physical, Fashion, Environment, Technology with
  confidence chips), per-face age/gender/attire analysis. This reads as a real research product,
  not a demo.
- **The growth loop is wired end-to-end for anonymous users.** Every person/photo page has Share
  + a "can you help?" CTA + comment/memory inputs; `/help` is a dedicated identification grid;
  the shareable person gallery (`/c/rhodes/person/{id}/photos`) renders "Photos of <Name>" and is
  correctly community-scoped. Person pages surface Family, Connections, and "Often appears with"
  co-occurrence — the temporal work is paying off visually.
- Clean 404 with recovery CTAs; polished mobile (hamburger nav, wrapping action pills).

## Ranked findings (top 12)

| # | Finding | Route | Viewport | Screenshot | Vision-dependent? | Impact |
|---|---------|-------|----------|-----------|-------------------|--------|
| V2-1 | **All faces on a public photo page show a red "Dismissed" badge** while the page CTA says "Nobody in this photo has been identified yet — can you help?" — an admin-workflow state leaking to the public that reads as "your help was rejected" | `/photo/2e5836aeceae8c6d` | desktop | `photo-desktop.jpeg` | Yes | **High** — contradicts + discourages the #1 contribution CTA |
| V2-2 | **Two of three archive cards show "0 PEOPLE"** (Fox Family 670 photos / 0; Sarah Fox Fader 147 / 0) yet their "Do you recognize anyone?" CTA leads to an empty people set | `/` | desktop | `landing-desktop.jpeg` | Yes | **High** — credibility + dead-end CTA on 2/3 archives |
| V2-3 | **People page count contradiction:** header "131 awaiting identification" but the **"Needs Name (0)"** filter is empty; `/help` separately shows "50 faces awaiting identification". Three surfaces, three counts of the same concept (Lesson 116) | `/c/rhodes/people`, `/help` | both | `people-desktop.jpeg`, `help-desktop.jpeg` | Partial | **High** — the People-page help entry point is a dead end |
| V2-4 | **Community context is dropped on click.** On `/c/rhodes/people` every nav + person-card link is root-relative (`/person/{id}`, `/photos`) — not `/c/rhodes/`-prefixed. Live-DOM confirms W4 code finding V2 (hardcoded links in `app/components/photo_analysis.py`) | `/c/rhodes/people` | desktop | (DOM snapshot) | No (DOM) | **High** — breaks per-archive share context |
| V2-5 | **Fox Family Archive — the owner's own 670-photo archive — shows "670 photos · 0 identities"** while Fox individuals (Roland Fox, 88 photos) appear under the Rhodes People grid. Cross-community identity scoping splits photos from the people in them | `/c/fox-family/` | desktop | `community-fox-desktop.jpeg` | Yes | **High** — flagship family archive looks empty of people |
| V2-6 | **Global top-nav links are near-invisible** (dim gray on dark: Photos/Collections/People/Timeline/Map/Tree/Connect/Compare/Estimate). Recurs on every desktop page. Likely a WCAG contrast fail | all (global head) | desktop | `search-desktop.jpeg`, `compare-desktop.jpeg` | Yes | **Med** — primary nav hard to see; **global head = User Decision** |
| V2-7 | **Photo-count vs face-count conflation:** person header says "Appears in **25** photos" but the Photos gallery shows "**12** photos" (25 = face detections) | `/person/...`, `/c/rhodes/person/.../photos` | desktop | `person-desktop.jpeg`, `person-gallery-desktop.jpeg` | Yes | **Med** — misleading stat on every multi-face person |
| V2-8 | **AI location reasoning self-contradicts:** estimate + map = "Los Angeles, California" but the reasoning text says "possibly Disneyland… or a **similar Florida attraction**" | `/photo/2e5836aeceae8c6d` | desktop | `photo-desktop.jpeg` | Yes | **Med** — undermines trust in the flagship AI feature (see W6 Detroit work) |
| V2-9 | **Scene-tag filter counts exceed the page total:** `/photos` shows "113 photos" but tag chips read Group Portrait (137), Studio (126), Formal Event (100) — tag counts look archive-global while the grid is Rhodes-scoped | `/photos` | desktop | (DOM snapshot) | No (DOM) | **Med** — corroborates W4 V1 unscoped-collections defect |
| V2-10 | **No favicon** — `/favicon.ico` returns 404 (console error on every page). Hurts the browser-tab + share-preview polish the project has invested in | all | desktop | (console read) | No | **Low** — quick win |
| V2-11 | Empty face-crop tiles appear below the fold in full-page captures on `/help` and `/person/*`. **Verified NOT a defect:** 35/35 crop requests returned 200 OK; the blanks are un-triggered lazy-loads in a scroll-less capture | `/help`, `/person/*` | desktop | `help-desktop.jpeg` | Yes→corrected | **Low** — cosmetic in non-scroll/crawler renders only |
| V2-12 | Photo analyzed with **"Gemini 3-flash (v2_rich_metadata)"** while Face Analysis uses "Gemini 3.1-pro-preview" and the harness rule pins 3.1 Pro — possible model-version drift in stored analyses | `/photo/2e5836aeceae8c6d` | desktop | `photo-desktop.jpeg` | Yes | **Low** — verify whether new analyses use the pinned model |

## Growth-loop (Find → Share → Click → Recognize → Respond) verdict
- **Find:** strong. Rich `/photos` filters (decade, scene tag, collection, sort, infinite scroll),
  People grid, NL `/tools/search` with example chips.
- **Share:** present on person/photo/people/gallery; shareable gallery is community-scoped. Good.
- **Click → Recognize:** weakened by V2-1 ("Dismissed" badges), V2-3 (People "Needs Name (0)"),
  and V2-2/V2-5 (archives showing 0 people). A recognizer who lands on a photo sees every face
  marked "Dismissed"; one who lands on People finds the "needs name" queue empty.
- **Respond:** anonymous comment + "Share what you know" inputs exist. But per W5, there is **no
  notify-on-review and no visible submission status** — the loop's final step gives no feedback.

## Screenshots captured (desktop + mobile where noted)
landing (D+M), people (D+M), person (D+M), community-fox (D), compare (D), estimate (D),
search (D), help (D), photos (D), photo (D), person-gallery (D), 404 (D). All in
`docs/fable-eval/screenshots/`.

## Coverage note (honest)
Mobile captured for landing/people/person (the first-run + highest-traffic surfaces). Compare/
estimate/search/photo/help/community/404/gallery captured desktop-only to stay within the run;
mobile parity for those is **not verified** — flagged, not claimed.

## User Decisions (forbidden actions — logged, not executed)
- V2-6 (nav contrast) and any global head/CSS fix touch the excluded global layout — orchestrator/
  Nolan decision.
- V2-1 "Dismissed" public-visibility, V2-2/V2-5 archive people-counts, V2-3 count reconciliation:
  each needs a source-code change → routed to `QUICK_WINS_QUEUE.md` / Phase 2, not done here.
