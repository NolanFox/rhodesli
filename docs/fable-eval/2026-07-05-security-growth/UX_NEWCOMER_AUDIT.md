# UX Newcomer Audit — live site, desktop + mobile (2026-07-05)

**Method:** Fresh, unauthenticated Playwright browser (a newcomer clicking a Facebook link has no
admin session — the owner's Chrome does, so it was deliberately not used). Desktop 1440x900 and
mobile 390x844. Read-only: GET navigation, screenshots, DOM reads only. All screenshots in
`screenshots/`. Persona: a Rhodes-descended person who has never seen the site and just tapped a
shared link on Facebook (mobile-first).

**Live-state verification at run time:** `/health` 200 (1,824 identities, 1,127 photos, supabase
ok). `/sitemap.xml` live with 1,267 URLs (1,127 photo + 136 person + tools/help/root). Console: 0
JS errors on every page visited (1 benign warning/page).

**Verdict in one line:** the Rhodes archive landing, person page, and photo page are genuinely
strong share objects — but the platform root speaks internal changelog language, the tree leaks
another family's genealogy into the Rhodes archive, the compare front door takes photos without
saying it keeps them, and the tools pages break on the exact device FB traffic arrives on.

---

## Severity key
P0 = trust-breaking or wrong-data on a newcomer path · P1 = confusing/dead-end on the growth loop ·
P2 = polish that erodes credibility · OK = verified strength (kept honest: what already works).

---

## Findings

### F1 (P0) — /c/rhodes/tree renders the FOX family's GEDCOM
- **Screenshot:** `screenshots/desktop-11-tree-loaded.jpeg`
- **Code:** `app/page_routes.py:10939` (`/api/tree/data`) — tree adjacency is built from the global
  GEDCOM tables with **no community filter**; `community_slug` is used only for `nav_prefix` link
  generation (`app/page_routes.py:10949-10951`).
- **What a newcomer sees:** A Rhodes descendant opens "Family Tree" on the Jewish Community of
  Rhodes archive and sees *Meyer Fox, Sadie Fox Levine, Leyba Fox, Fader, Newman* — an Ashkenazi
  family from Minsk/Dayton, not a single Rhodes Sephardic name (no Capeluto, Franco, Halio).
- **Impact:** For the exact audience this product courts (genealogy-literate Rhodes descendants),
  this reads as "the data is wrong" — the single fastest way to lose them. It is also the clearest
  live demonstration that community scoping is not enforced on every surface: the moment a second
  family uploads a GEDCOM, trees cross-contaminate bidirectionally (composite community-scoped PKs
  exist in the schema since Session 164, but this reader ignores them).
- **Neither prior draft caught this** — both audited routing/permissions, not the rendered tree.

### F2 (P0) — /tools/compare stores your photo and never tells you
- **Screenshots:** `screenshots/desktop-06-tools-compare.jpeg`, `screenshots/mobile-04-compare.jpeg`
- **Code:** `app/compare_routes.py:1664-1700` — anonymous upload → R2 `uploads/pending/{job_id}/` +
  a durable `pending_uploads` entry. `app/compare_routes.py:1684-1704` — **logged-in uploads are
  auto-approved straight into the archive** (`upload_status = "approved"`, background ingest).
- **What a newcomer sees:** "Drop a photo here — JPG, PNG up to 10 MB." Nothing else. No retention
  statement, no "your photo will be reviewed by an admin," no privacy note, no deletion promise.
- **Impact:** This is the consent half of the spam problem. The 51 pending selfies exist because
  users reasonably believe compare is ephemeral. Flip side: when self-service signup widens, the
  auto-approve path means any logged-in stranger's compare upload *enters the archive without
  review*. Both directions of the boundary are wrong. (Full design → `SPAM_BOUNDARY_DESIGN.md`.)

### F3 (P0) — Mobile horizontal overflow on /tools/compare
- **Screenshot:** `screenshots/mobile-04-compare.jpeg`
- **Measured:** `document.documentElement.scrollWidth = 793` at viewport 390 (verified via DOM; by
  contrast `/help`, `/tools/estimate`, `/photo/*`, `/person/*`, `/`, `/c/rhodes/` all measure 390).
- **Cause:** the tools-page top nav renders all items (Photos … Estimate + Help Identify + Sign In)
  in one non-collapsing row; landing/person/photo pages use a hamburger, tools pages don't.
- **Impact:** FB traffic is mobile. The single most likely deep-link destination for a curious
  newcomer ("upload a photo of grandma, see who matches") requires two-axis scrolling and looks
  broken. The historical "almost unusable on mobile" complaint is fixed on content pages but NOT on
  this tool page.

### F4 (P1) — The platform root speaks internal changelog language to the public
- **Screenshot:** `screenshots/desktop-01-root.jpeg`, `screenshots/mobile-01-root.jpeg`
- **Code:** `app/page_routes.py:799` (`_platform_root_page`).
- **Copy on the live page:** "Rhodesli keeps platform, archive, and contribution contexts
  distinct." · "This removes the old Rhodes-by-default ambiguity." · "Browse the Rhodes **demo**
  archive" · "It stays available as an explicit demo path, not the silent default."
- **Impact:** These are sentences written for the repo's session logs, rendered to a newcomer.
  "Demo archive" actively undermines the flagship: a Rhodes descendant is told the real archive of
  their community — the one with 498 photos and a Holocaust memorial mission — is a "demo."
  Nobody arriving from Facebook knows or cares what "Rhodes-by-default ambiguity" was.
- Also visible here: **the Fox Family personal archive is publicly listed** with photo counts and
  enter buttons — the privacy-unenforced gap (`app/page_routes.py:799-840` iterates all communities
  with no privacy filter) is not theoretical; it's on the front page today.

### F5 (P1) — Unprefixed /help mixes every community's faces
- **Screenshots:** `screenshots/desktop-07-help-identify.jpeg`, `screenshots/desktop-08-help-bottom-viewport.jpeg`
- **Observed:** cards sourced from "Old Fox Photos from Extended Family," "Charles Fox Dayton Ohio
  Collection," "Sarah Fox Fader Family" interleaved with "Jews of Rhodes" and Capeluto collections.
  (Documented fail-open for root/Rhodes — Session 168 G1/G2/G7 — so this is by-design today, but it
  is the wrong design once a second real family exists, and it already dilutes the Rhodes pitch:
  a Rhodes helper is shown Dayton, Ohio faces they cannot possibly recognize.)
- **Impact:** Help-Identify is the highest-leverage contribution surface; every irrelevant face
  lowers the hit rate and the helper's sense that their knowledge matters.

### F6 (P1) — Three different navigation systems; person-page nav is visibly broken
- **Screenshot:** `screenshots/desktop-04-person-page.jpeg` (compare with desktop-01 and desktop-02)
- **Observed:** (a) root nav: Compare/Estimate/About/Sign In; (b) archive landing: hamburger +
  Photos/Collections/People/Map/Timeline/Tree/Compare/About/Recognize-Anyone; (c) person/tools nav:
  Photos/Collections/People/Timeline/Map/|/Tree/Connect/Compare/Estimate/Help-Identify/Sign-In.
  On the person page the logo collides with the first item ("**RhodesliPhotos**") and a stray
  purple "Explore More Photos" link overflows the right edge. Mobile root shows the same collision
  ("RhodesliCompare", `screenshots/mobile-01-root.jpeg`).
- **Impact:** Navigation identity is how a newcomer decides "is this a real, maintained site?"
  Three navs + a colliding logo reads as unfinished. "Connect" is an unlabeled mystery to a
  first-timer.

### F7 (P1) — Cross-surface count contradictions on the same community
- **Screenshots:** `screenshots/desktop-02-rhodes-landing.jpeg` ("142 of 3372 faces identified",
  "142 PEOPLE IDENTIFIED") vs `screenshots/desktop-09-people-grid.jpeg` ("88 people in the archive
  · 87 named · 765 awaiting identification") — and the landing's other counter says "2124 awaiting."
- **Impact:** A genealogist audience notices numbers. Two Rhodes surfaces disagreeing by 60%+
  (142 vs 87-88; 2,124 vs 765) suggests either different definitions (faces vs identities vs
  scoping) or a scoping bug — either way it needs one canonical definition rendered everywhere.
  (Related history: the platform's #1 recurring bug class is split-brain counts — Lessons 78/144/150.)

### F8 (P2) — Anonymous comments publish instantly with no moderation
- **Code:** `app/person_routes.py:2291-2334` — `status: "visible"` immediately, rendered into the
  page on submit; in-memory 5/hr/IP limit only. (Read from code — not exercised on prod.)
- **Screenshot (surface):** `screenshots/desktop-04-person-page.jpeg` (Comments (0) + open form).
- **Impact:** On memorial-adjacent pages (Holocaust-era subjects), an unmoderated instant-publish
  text field is a content-liability and dignity risk that scales with exactly the sharing you want.
  Today's obscurity is the only protection.

### F9 (P2) — Empty AI section headers and internal model names on the photo page
- **Screenshot:** `screenshots/desktop-05-photo-page.jpeg`
- **Observed:** "AI Reasoning — AI Estimated" and "Tags — AI Estimated" render as headers with no
  content; the Face Analysis block leads with "Gemini coordinate bridging (gemini-3.1-pro-preview)".
- **Impact:** Empty scaffolding + debug vocabulary quietly say "prototype." The actual AI content
  (date c.1978 high confidence, Miami location + map, detective evidence) is *excellent* — it just
  needs the empty/debug bits hidden.

### F10 (P2) — Help-Identify / landing face teasers are not quality-curated
- **Screenshots:** `screenshots/desktop-03-rhodes-identify-faces-viewport.jpeg` (rightmost teaser
  circle is a near-black blob), `screenshots/desktop-07-help-identify.jpeg` (many heavily pixelated
  crops).
- **Impact:** "Can you identify these faces?" is the emotional hook; leading with unrecognizable
  crops wastes it. Sorting the public queue by crop quality × face size would raise recognition
  odds and perceived care. (The queue caps at 50 with no "show more" except See-all → same page.)

### F11 (P2) — Photo-count context: "Photo 1 of 108" scoping unclear
- **Screenshot:** `screenshots/desktop-05-photo-page.jpeg`, `screenshots/mobile-06-photo.jpeg`
- Photo nav says "Photo 1 of 108" (collection-scoped) with no label saying *of what*; a newcomer
  arriving on a shared photo doesn't know if they're paging the archive, collection, or person.
  (Session 165 fixed the person-scoped case; the label still doesn't say which scope is active.)

---

## Verified strengths (keep, and lean on these)
- **Person page is a real share object** (`screenshots/desktop-04-person-page.jpeg`): complete OG
  profile card (og:title/description/image/type=profile verified in DOM; canonical == og:url),
  "Share what you know" CTA, "Often appears with" social proof, upload CTA, open comments.
- **Photo page is the best page in the product** (`desktop-05`, `mobile-06`): named face overlays,
  date + location with confidence, map, and it's flawless at 390px.
- **/c/rhodes/ landing hero is genuinely moving and mobile-solid** (`mobile-02-rhodes-landing.jpeg`):
  the 450-years/Ladino/July-1944 paragraph does trust-in-30-seconds work all by itself.
- **No false positives shipped:** landing zero-stats and blank face circles are scroll-triggered
  lazy-load, verified rendering correctly in-viewport (`desktop-03`); stats read
  1,127 / 142 / 3,372 / 2,124.
- **SEO plumbing is live:** robots + sitemap (1,267 URLs) resolve; person/photo pages have full OG
  + twitter cards.

## Growth-loop walkthrough (the loop the owner cares about)
find → **share** (person/photo OG: strong) → **click** (mobile content pages: good; tools: broken
F3) → **recognize** (help queue diluted F5, uncurated F10) → **contribute** (comment publishes
instantly F8; Help-Identify submits into a void — no status, no notify — prior evals' Bet 2, still
true in code) → **return** (nothing brings a contributor back: no notification, no "your
contribution was approved" moment). The loop's weakest links are the last two stages, exactly
where the one real external tester churned.
