# Session 100 Antigravity Plan Review

**Date:** 2026-03-11
**Author:** Antigravity
**Target Plan:** `docs/prds/040_multi_community_bootstrap_and_face_cards.md`

## 1. Verdict

The Codex plan successfully identifies the necessary architectural fixes (`COMMUNITY-015`, `016`, `017`) for multi-community routing and rightly proposes a shared `face_card()` UI contract.

**However, the plan is too passive regarding adoption and discoverability.** A "neutral root" without a directory risks creating a dead-end lobby. Furthermore, the proposed "horizontal strip" for multi-face cards will degrade into a frustrating experience for dense group photos (10+ faces). The plan is materially sufficient to let the admin (Nolan) bootstrap a new archive, but it falls short in ensuring a first-time visitor knows how to use it safely and effectively.

Before implementation, we must define the exact UX of the neutral root, replace passive "generic community copy" with active contribution calls-to-action, and ensure dense face-galleries can wrap into a grid.

## 2. Findings (Ordered by Severity)

1. **The "Neutral Root" Dead End (Adoption Risk):** Changing `/` from an implicit Rhodes route to a neutral platform entry is correct for trust. However, because self-serve archive creation and public directories are explicitly out of scope for Session 100, `/` risks becoming a locked door ("You are not in a community" + Login button). This would severely hurt top-of-funnel adoption.
2. **Face-Card Gallery Scalability (Interaction Risk):** The plan proposes a progressive disclosure model with a scroll-snap strip for expanded faces. While an improvement over micro-thumbnails, a horizontal scroll-snap strip fails ergonomically on mobile for a group photo of 15-20 people. It requires tedious linear scrolling.
3. **Passive Contribution Paths (Discoverability Risk):** The plan addresses first-run experience by adding "generic community landing/about fallback" copy. "About" text does not drive contribution. A non-expert family member needs a clear, prioritized "Tasks for you" or "Help Identify" workflow immediately upon entering an archive.
4. **Missing "Lens" Affordance:** The Codex plan dismisses zoom/lens as a "secondary enhancement." For a card showing a cropped thumbnail of a person in a 30-person wedding photo, the ability to inspect the context (or zoom in) is a primary workflow requirement for accurate identification, not just visual polish.

## 3. What I Agree With

- **No Implicit Routing:** Stop defaulting unknown visitors into Rhodes. This is the single most important trust fix.
- **`face_card` Explicit Modes:** Defining `summary`, `gallery`, `public`, and `workstation` modes for the face card is exactly the right architectural move. It stops the proliferation of bespoke card states.
- **FastHTML / Vanilla Stance:** Rejecting React-heavy libraries (like `21st.dev` as dependencies) in favor of CSS `scroll-snap` and minimal JS aligns perfectly with the current stack's strengths and zero-regression requirement.
- **Community Context Persistence:** Enforcing that internal links remain community-prefixed is a non-negotiable correctness fix.

## 4. What I Would Change Before Implementation

1. **Root Entry UX Definition:** Specify exactly what an anonymous user sees on `/`. It must include a welcoming platform explanation, a CTA to "Log In," and explicitly feature a link to the "Rhodes Family Archive" as a public flagship demo so the root is never completely bare.
2. **Dense Gallery Grid Fallback:** Update the Face Card Pillar to explicitly require that the expanded gallery can wrap into a grid (or pop a full-screen grid modal) when the face count exceeds a certain threshold (e.g., > 5 faces). 
3. **Active Contribution CTA:** Update Pillar B to include an active "Contribution Widget" (e.g., "5 Photos Need Identification") on `_community_landing_page()`, replacing the idea of just having "generic community copy."
4. **Re-evaluate Lens Inspection:** Add a requirement for a lightweight "view full source photo" or zoom affordance directly accessible from the expanded multi-face card. It shouldn't require complex JS, but it must be easily reachable without losing one's place.

## 5. Suggested Antigravity-Owned Work if Session 100 Proceeds

1. **Mockup the Neutral Root (`/`):** Design the anonymous platform entry to ensure it explains Rhodesli, provides login/invite flows, and highlights a public demo archive.
2. **Face Card Interaction Prototype:** Build a browser-first prototype of the expanded face gallery handling a 15-person photo, comparing a horizontal strip against a wrapping grid.
3. **Design the Community Landing CTA:** Design the specific UI for the "How to help" contribution block on the community landing page.

## 6. Attribution

- **Codex:** Architecture, repo audit, multi-community scoping strategy, routing fixes, and face-card structural refactor.
- **Antigravity:** Critical review, adoption and discoverability critique, interaction requirement adjustments (grid vs strip), and root UX strategy.
- **Collaborative/Handoff:** Translating the Antigravity UX requirements (Grid fallback, Root UX, Landing CTA) into the final implementation plan before coding begins.

## 7. Adoption / Discoverability Risks & Questions Answered

*Does the neutral root create a better top-of-funnel than the current Rhodes default?*
Only if designed intentionally. If it just says "No community selected," it's worse. If it explains the platform and links to the Rhodes public demo, it builds trust and clearly separates platform from content.

*Will a non-expert family member know how to get from landing page to useful contribution?*
Not under the current plan. "Generic copy fallbacks" do not pull users into workflows. They need a prominent, impossible-to-miss "Start Identifying" button on the community root.

*Does the face-card plan improve picture legibility, or just add more UI?*
It improves legibility by prioritizing a "hero face." However, shifting remaining faces to an expanded strip might just hide the problem behind a click if the expanded state isn't designed for high density.

*Where are the likely dead ends or moments of confusion?*
1. Landing on `/` with no active session and no directory.
2. Reaching the end of a single photo's identification flow without being handed the *next* priority task.

*What is the smallest change that would most improve adoption?*
Putting a dynamic "Help Identify" block (e.g., showing 3 blurry faces needing tags) front-and-center on the new `_community_landing_page()`.

## 8. What Should Be More Obvious to a First-Time User

- **Where they are:** The community name and context (vs the platform shell).
- **What is expected from them:** A clear path to contribution (e.g., "We need your help identifying these 10 photos").
- **How to navigate:** A clear distinction between "browse the archive" and "help the archive".

## 9. What Should Be Removed Because It Adds Clutter

- **Repeated Admin Actions in Thumbnails:** The Codex plan already addresses this, but to reiterate: tiny "edit" or "detach" links under every face in a multi-face view must be removed. Move them to a single identity-level overflow menu or explicitly isolate them to the `workstation` mode.
- **Ambiguous Platform/Community Branding:** Remove any remaining Rhodes-specific branding from the platform shell (`/`), keeping it strictly at the community level.
