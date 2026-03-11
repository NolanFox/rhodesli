# PR #7 Modern UI Research & Scoping: Architecture-Safe Revision

## 1. Attribution Ledger
- **Antigravity-authored:**
  - Original Research (`docs/assessments/modern-ui-research-and-scoping.md`)
  - This revision (`docs/assessments/pr-7-modern-ui-antigravity-revision.md`)
  - Implementation of FastHTML/HTMX architecture constraints
- **Codex-authored reference artifacts:**
  - The audit (`docs/assessments/pr-7-modern-ui-codex-audit.md`)
  - `docs/session_context/pr-7-modern-ui-codex-context.md`
  - `docs/prompts/pr-7-antigravity-follow-up-prompt.md`
- **Collaborative / handoff state:**
  - PR thread and handoff work following the Codex audit.

## 2. Architecture Vow (HD-022)
This revision explicitly acknowledges and adopts **HD-022**: Rhodesli is and will remain a **FastHTML + HTMX + Tailwind CDN** application. 
- A full React/Next.js migration is **not approved** for this scope.
- We will preserve the `DD-001` and `DD-002` archival/editorial visual direction. 
- All UI enhancements moving forward must be implemented as surgical Vanilla JS/CSS enhancements layered over the existing HTMX foundation.

## 3. Evaluation of Previous Research
A significant portion of the initial research proposed generic "AI SaaS" paradigms. As identified in the Codex audit (and recent design discourse), these generic paradigms lead to "AI-slop sameness". 

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

## 4. Rhodesli-Specific Design Direction
To avoid "AI slop", we will lean heavily into the **Editorial Archival** direction:

*   **Public Landing Page (`/`):** Cinematic and story-led. Warm sepia tones, film grain overlays, and high-contrast Playfair Display typography. We will enhance the existing hero mosaic with subtler CSS-based fade-ins.
*   **Public Share-Ready Pages (`/identify/{id}`):** Focus on the mystery and the community's connection. Clear, large imagery with structured simplicity.
*   **Admin/Workstation Pages (`/?section=...`, `/tools/compare`, `/photos`):** Calm, clear, and tactile. Minimum viable motion. Dense information architecture with strict spacing rhythm. No bouncy animations or glowing borders.

## 5. Route-by-Route Preservation Inventory
To ensure zero regressions, any design update must preserve the following repo-verified contracts:

| Route | Preserved Behavior | Repo-Verified DOM Invariants |
| :--- | :--- | :--- |
| **`/` (Landing)** | Anonymous access only; redirects logged-in users. | `.hero-mosaic` (Do not use `[data-testid="community-landing"]` for default). |
| **`/?section=...`** | Workstation root / Admin Dashboard | `[data-testid="admin-nav-bar"]`. Must preserve user sections. |
| **`/photo/{id}`** | Public / Admin photo detail view | `[data-testid="photo-metadata-overlay"]`. Admin edits `[data-testid="photo-inline-edit"]`. |
| **`/person/{id}`** | Public / Admin person profile | `[data-testid="life-details"]`, `[data-testid="person-action-bar"]`. |
| **`/photos`** | Photo grid | HTMX pagination markers and grid structure. |
| **`/identify/{id}`** | Public share-ready ID flows | `[data-testid="quick-identify-form"]`, `[data-testid="quick-identify-btn"]`. |
| **`/timeline`** | Public historical timeline | `[data-testid="decade-marker"]` tags for chronological anchor points. |
| **`/tree`** | Public family tree visualization | SVG/D3 nodes and panning script structure. |

*Note: `/timeline` and `/tree` are public surfaces, not admin-only, and should be treated with narrative purposeful motion.*

## 6. Implementation Prioritization (Session 99)

**In Scope for Session 99 (Prioritized for Redesign):**
1. **`/` (Landing Page):** Implement the cinematic, story-led editorial aesthetic.
2. **`/identify/{id}` (Public Share-Ready):** Redesign the "Can you help?" flow to look premium and tactile.
3. **`/?section=...` (Admin Dashboard Header/Root):** Clean up the workstation typography and spacing rhythm.

**Out of Scope for Session 99 (To Reduce Regression Risk):**
- `/tools/compare` (High complexity with Lock Contention 423 handling).
- `/photos` and `/photo/{id}` (High complexity with metadata, bounds, and bounding boxes).
- `/tree` and `/timeline` (Requires specialized D3/SVG or intense chronological logic).

## 7. Verification Gates (Strict Enforcement)
Before merging any UI changes, the following gates MUST pass:
1.  **Dual Test Suites:** Both `pytest tests/ -x -q` AND `pytest rhodesli_ml/tests/ -x -q` must run clean.
2.  **Repo-Verified DOM Invariants:** Ensure all `[data-testid]` elements listed in Section 5 remain accessible to `BeautifulSoup` inside the pytest suites.
3.  **Route-Specific Smoke Checks:** Using the actual `scripts/production_smoke_test.py` or `curl` to verify `200 OK` on `/`, `/?section=inbox`, and `/identify/random`.
4.  **Screenshot Checkpoints:** We must export rendered screenshots of the three in-scope redesign surfaces (`/`, `/identify/{id}`, and `/?section=inbox`) as visual proofs of the archival aesthetic.

---

### Appendix A: Dated Source References (2025-2026)
*   **Figma 2025 AI Report & Perspectives:** Highlights that human design discipline and taste matter more, not less, when AI generates code rapidly. (Early 2025)
*   **Canva Design Trends 2026:** Emphasizes "Imperfect by Design," tactility, layered storytelling, and raw human visuals over sterile tech looks. (Late 2025)
*   **Creative Bloq (Taste is the New Superpower 2026):** Authentic storytelling replaces generic product abstractions. (2026)
*   **Google Stitch & Gemini 2.5 Flash Image / Nano Banana Series:** Tooling for ultra-fast, high-fidelity UI mockup prototyping (Stitch introduced constraints as an MCP). (Mid 2025 - Early 2026)
*   **Reddit / Social Discourses (r/webdesign & r/Frontend):** "Why do all modern SaaS websites look the same?", specifically calling out uncustomized Shadcn/Linear-clone bento grids and heavy purple/blue gradients as "AI slop". (Late 2025 - Early 2026)

### Appendix B: Migration Case (Not Approved)
*If a future decision dictates a React migration:*
- **Cost:** Rewriting 799+ pytest integration tests; rebuilding HTMX routing into Next.js.
- **Risk:** High chance of breaking the `423 Lock Contention` semantics and upload pipelines.
- **Contracts:** Requires an OpenAPI specification of the current FastHTML backend. **(Rejected per HD-022)**.
