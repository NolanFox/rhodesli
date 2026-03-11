# PR #7 Modern UI Research & Scoping: Architecture-Safe Revision

## 1. Attribution Ledger
- **Antigravity-authored in this revision:**
  - This document (`docs/assessments/pr-7-modern-ui-antigravity-revision.md`)
  - Integration of FastHTML/HTMX architecture constraints
- **Codex-authored reference artifacts:**
  - `docs/assessments/pr-7-modern-ui-codex-audit.md`
  - `docs/session_context/pr-7-modern-ui-codex-context.md`
  - `docs/prompts/pr-7-antigravity-follow-up-prompt.md`
- **Collaborative / handoff state:**
  - Original research (`docs/assessments/modern-ui-research-and-scoping.md`)
  - The github PR thread #7

## 2. Architecture Vow (HD-022)
This revision explicitly acknowledges and adopts **HD-022**: Rhodesli is and will remain a **FastHTML + HTMX + Tailwind CDN** application. 
- A full React/Next.js migration is **not approved** for this scope.
- We will preserve the `DD-001` and `DD-002` archival/editorial visual direction. 
- All UI enhancements moving forward must be implemented as surgical Vanilla JS/CSS enhancements layered over the existing HTMX foundation.

## 3. Evaluation of Previous Research
A significant portion of the initial research proposed generic "AI SaaS" paradigms. As identified in the Codex audit (and recent 2025-2026 design discourse), these generic paradigms lead to "AI-slop sameness". 

### Valid as Inspiration:
- **Immersive Minimalism & Tactile Digitalism:** Using texture (grain, film) rather than sterile glassmorphism.
- **Story & Specificity:** Leveraging actual archive imagery and history over feature grids.
- **Purposeful Motion:** Restraining motion on admin surfaces; using scroll-led narrative only on public storytelling pages.

### Too Generic or React-Specific (Do Not Apply Directly):
- **Bento Grids as substitute for architecture:** We must prioritize clear hierarchy over decorative grids.
- **Default Purple/Blue AI Gradients:** These violate the warm, museum-quality archival framing of Rhodesli.
- **Copy-Paste React Component Libraries:** Shadcn, Aceternity, and Magic UI are built for React pipelines. In Rhodesli, they would require a build step and heavy abstraction, violating HD-022.

### Generative Tooling Inventory:
- **Stitch MCP (Google):** `prototype workflow` — Useful for rapid UI ideation and Figma-to-code iteration, but code must be converted manually to FastHTML structure.
- **Nano Banana 2 / Gemini Image Models:** `prototype workflow` — Excellent for generating high-fidelity mockups of the "editorial archival" aesthetic for layout reference.
- **UI UX Pro Max (Skill):** `prototype workflow` — Useful as an agenting persona for layout critique.
- **Screenshot-to-code tools:** `inspiration only` — Usually output React/Tailwind. We can only use the Tailwind class structure, not the JSX.
- **21st.dev:** `inspiration only` — 3D and reactive assets are interesting, but heavily rely on React/Framer Motion.
- **Shadcn / Aceternity / Magic UI:** `not compatible without architecture change` — These are inherently tied to React/Radix primitives and Framer Motion.
- **Framer Motion:** `not compatible without architecture change` — We will use CSS transitions and surgical vanilla JS (e.g., GSAP if heavily required, or native Web Animations API) instead.

## 4. Rhodesli-Specific Design Direction
To avoid "AI slop", we will lean heavily into the **Editorial Archival** direction:

*   **Public Landing Page (`/`):** Cinematic and story-led. Warm sepia tones, film grain overlays, and high-contrast Playfair Display typography. We will enhance the existing hero mosaic with subtler CSS-based fade-ins and tactile hover states on the face-detection boxes.
*   **Public Share-Ready Pages (`/identify/{id}`):** Focus on the mystery and the community's connection. Clear, large imagery with structured simplicity. The "Can you help?" call to action should feel like a human plea, not a SaaS conversion funnel.
*   **Admin/Workstation Pages (`/tools/compare`, `/timeline`, `/tree`):** Calm, clear, and tactile. Minimum viable motion. Dense information architecture with strict spacing rhythm. No bouncy animations or glowing borders.

## 5. Route-by-Route Preservation Inventory
To ensure zero regressions, any design update must preserve the following contracts:

| Route | Preserved Behavior | DOM/Testing Invariants |
| :--- | :--- | :--- |
| **`/` (Landing)** | Anonymous access only; redirects logged-in users. | `.hero-mosaic`, `[data-testid="community-landing"]`. Must load stats asynchronously if currently doing so. |
| **`/identify/{id}`** | Public view of identity; HTMX swaps for the "I know this person" flow. | `[data-testid="identity-header"]`. HTMX `hx-post` for claims must not be broken by CSS/JS wrapper changes. |
| **`/tools/compare`** | Admin only. Dual-pane face comparison. | Lock contention (423) UI handling. Image zoom/pan state (surgical JS) must survive HTMX updates. |
| **`/upload` & `/photos`** | Admin/Auth borders. Metadata forms. | Upload pipeline HTMX indicators (`.htmx-indicator`). File input `hx-encoding="multipart/form-data"` form boundaries. |
| **Global Layout** | Mobile navigation sliding panel; Auth error hash fragments. | The `document.addEventListener('htmx:beforeSwap')` intercept for 401s must remain intact. |

## 6. Phased FastHTML + HTMX Implementation Plan

*   **Phase 1: Design Tokens & Typography:** Update `tailwind.config` in `app/main.py` (already injecting Playfair Display) to include specific archival colors (sepia, warm charcoal) and typography rules.
*   **Phase 2: CSS Animation Layer:** Add native CSS `@keyframes` and transitions to `app/page_routes.py` (in the `landing_style` block) for tactile hovers and fade-ins, replacing the desire for Framer Motion.
*   **Phase 3: Route Overhauls (HTMX-Safe):**
    *   *Step A:* Overhaul public landing page HTML generation in `landing_page()`.
    *   *Step B:* Overhaul `/identify/{id}` view, treating the HTMX form as black-box to preserve functionality.
    *   *Step C:* Overhaul Admin sidebars and tables with strict spacing rhythm.
*   **Phase 4: Surgical JS:** Update existing standalone scripts (like `family-tree.js`) with modern native browser APIs for interactions, completely avoiding React.

## 7. Verification Gates
Before merging any UI changes, the following gates must pass:
1.  **Tests:** `pytest tests/ -x -q` must run clean.
2.  **DOM Invariants:** Ensure `[data-testid]` elements remain exactly where tests expect them.
3.  **Auth Boundaries:** Verify the global 401 HTMX interceptor still triggers the login modal on protected routes.
4.  **Upload Flows:** Perform a physical file upload to ensure `.htmx-indicator` displays and the form submission succeeds without page reload.
5.  **Visual Checkpoints:** Capture screenshots of the Landing Page, Compare tool, and Face detail view to verify the archival aesthetic is preserved.

---

### Appendix: Migration Case (Not Approved)
*If a future decision dictates a React migration to utilize Aceternity/MagicUI natively:*
- **Cost:** Rewriting 799+ pytest integration tests; rebuilding the entire HTMX routing layer into Next.js App Router; duplicating data-fetching logic.
- **Risk:** High chance of breaking the `423 Lock Contention` semantics and upload pipelines.
- **Contracts:** Would require an OpenAPI specification of the current FastHTML backend to serve purely as an API, plus a new e2e Playwright suite to guarantee feature parity. **(Currently Rejected per HD-022)**.
