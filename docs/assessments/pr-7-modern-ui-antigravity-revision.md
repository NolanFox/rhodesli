# PR #7 Modern UI Research & Scoping: Architecture-Safe Revision

## 1. Attribution Ledger
- **User-directed Orchestration:**
  - Establishing constraints, prioritizing scope, and defining the aesthetic boundary for Session 99.
- **Antigravity-authored:**
  - Original Research (`docs/assessments/modern-ui-research-and-scoping.md`)
  - This revision (`docs/assessments/pr-7-modern-ui-antigravity-revision.md`)
  - Implementation plan for FastHTML/HTMX architecture constraints
- **Codex-authored reference artifacts:**
  - The audit (`docs/assessments/pr-7-modern-ui-codex-audit.md`)
  - `docs/session_context/pr-7-modern-ui-codex-context.md`
  - `docs/prompts/pr-7-antigravity-follow-up-prompt.md`
- **Collaborative / Handoff state:**
  - PR thread #7 and handoff work following the Codex audit.

## 2. Architecture Vow (HD-022)
This revision explicitly acknowledges and adopts **HD-022**: Rhodesli is and will remain a **FastHTML + HTMX + Tailwind CDN** application. 
- A full React/Next.js migration is **not approved** for this scope.
- We will preserve the `DD-001` and `DD-002` archival/editorial visual direction. 
- All UI enhancements moving forward must be implemented as surgical Vanilla JS/CSS enhancements layered over the existing HTMX foundation.

## 3. Route-by-Route Preservation Inventory
To ensure zero regressions, any design update must preserve the following repo-verified contracts:

| Route | Preserved Behavior | Repo-Verified DOM Invariants |
| :--- | :--- | :--- |
| **`/` (Landing)** | Anonymous access only; redirects logged-in users. | `.hero-mosaic`. (There is no `[data-testid="community-landing"]` for the default Rhodes view). |
| **`/?section=...`** | Workstation root / Dashboard | The HTMX sidebar structure (`hx-get="/?section=..."`) and section count badges. (Do NOT rely on `[data-testid="admin-nav-bar"]` as that is admin-only). |
| **`/identify/{id}`** | Public share-ready ID flows | The `<form>` containing `name="name"`, `name="relationship"`, `name="email"`, and the "Yes, I know this person!" submission text. |
| **`/photo/{id}`** | Public / Admin photo detail view | `[data-testid="photo-metadata-overlay"]`. Admin edits `[data-testid="photo-inline-edit"]`. |
| **`/person/{id}`** | Public / Admin person profile | `[data-testid="life-details"]`, `[data-testid="person-action-bar"]`. |
| **`/photos`** | Photo grid | HTMX pagination markers and grid structure. |
| **`/timeline`** | Public historical timeline | `[data-testid="decade-marker"]` tags for chronological anchor points. |
| **`/tree`** | Public family tree visualization | SVG/D3 nodes and panning script structure. |

*Note: `/timeline` and `/tree` are public narrative surfaces, not admin-only, and should be treated with purposeful motion.*

## 4. Shared Surface System (Session 99 Critical)
To maintain coherence across the application, the following cross-surface primitives must remain visually and behaviorally consistent wherever they appear:

1. **Face Cards / Face-Image Treatments:**
   * **Purpose:** Display a cropped or masked person's face.
   * **Where it appears:** Landing page mystery faces, `/identify/{id}` targets, workstation triage queues.
   * **Must stay consistent:** Aspect ratio (circles/squares), border treatment (e.g., subtle archival amber ring), and hover physics.
   * **May vary by surface:** Dimensions (larger on detail pages, smaller in grids).
2. **Metadata Panels / Provenance Blocks:**
   * **Purpose:** Display collection, date, and source info.
   * **Where it appears:** `/photo/{id}`, `/identify/{id}`, workstation sidebars.
   * **Must stay consistent:** Typography hierarchy (Playfair for titles, monospaced/sans for raw metadata), muted text colors.
   * **May vary by surface:** Collapsible states on mobile.
3. **Action Bars / CTA Hierarchy:**
   * **Purpose:** Drive the primary user action (e.g., "Yes, I know this person").
   * **Where it appears:** `/identify/{id}`, admin approval queues.
   * **Must stay consistent:** Button weights, interaction states (focus/active), and color semantics (e.g., amber for primary archival actions).
   * **May vary by surface:** Stickiness (pinned to bottom on mobile).
4. **Section Headers & Empty States:**
   * **Purpose:** Title a page or indicate no data.
   * **Where it appears:** Workstation queues, timeline decades.
   * **Must stay consistent:** Spacing rhythm, typography scale, and the use of tactile icons (not generic SVG blobs).
5. **Loading / HTMX Indicators:**
   * **Purpose:** Communicate background network activity.
   * **Where it appears:** Anywhere `hx-post` or `hx-get` occurs.
   * **Must stay consistent:** The visual spinner/progress bar styling (e.g., a top-edge loading bar rather than blocking central spinners).
6. **Navigation Chrome (Public vs Workstation):**
   * **Purpose:** Site orientation.
   * **Where it appears:** Public top nav vs Workstation sidebar.
   * **Must stay consistent:** Link hover states, typography.
   * **May vary by surface:** Public nav should feel cinematic; workstation nav must be dense, clear, and utilitarian.

## 5. Scope Control for Session 99
To guarantee zero regressions and no accidental spread into high-risk routes, Session 99 is strictly bounded:

**Allowed to Touch (In Scope):**
1. `/` (Public Landing Page)
2. `/identify/{id}` (Public Share-Ready Flow)
3. `/?section=...` (Workstation Root / Header Chrome)
4. The Shared Surface System primitives as they apply to the above routes.

**Must Remain Untouched (Out of Scope):**
1. `/tools/compare` (High complexity with Lock Contention 423 handling).
2. `/photos` and `/photo/{id}` (High complexity with metadata, bounds, and bounding boxes).
3. `/person/{id}`, `/timeline`, and `/tree` (Specialized visualization logic).

## 6. Wow Without Slop (Aesthetic Rules)
To elevate Rhodesli from amateur to premium *without* looking like generic AI SaaS, Session 99 must follow these rules:

* **What creates trust:** Restraint. Precise typographic alignment. High-contrast, legible serif headers (Playfair Display) paired with clean sans-serif data.
* **What creates tactility:** Film grain overlays, sepia-toned shadow hints, and subtle borders that imply physical archival mattes. Interactive elements should have slight inset shadows or border color un-mutes on hover.
* **What creates interactivity:** Purposeful state changes. A fade in, a smooth expansion of a metadata panel. Using CSS transitions on transform and opacity only.
* **What feels like AI slop:** Glowing purple/blue gradients. Mindless Bento Grids where normal flexbox lists would suffice. Oversized drop shadows on floating cards.
* **What feels too flashy:** Spring physics, bouncy hover states, scroll-hijacking, and anything that distracts from the photography itself.

## 7. Sequencing + Convergence Plan
Implementation MUST follow this strict order to avoid getting lost:

**Track 1: Landing Page (`/`)**
- Establish the cinematic, story-led editorial aesthetic using the Shared Surface primitives.
**Track 2: Public Share-Ready Page (`/identify/{id}`)**
- Redesign the "Can you help?" flow to look premium, tactile, and connected to the Landing Page aesthetic.
**Track 3: Workstation Root (`/?section=...`)**
- Overhaul the header and navigation chrome to apply the denser, utilitarian variant of the Shared Surface primitives.

**Harmonization & Convergence:**
- Execute a final harmonization pass across all three touched surfaces.
- Conduct a consistency audit to ensure repeated primitives (e.g., face cards) are reconciled into single CSS classes before merge.

## 8. Verification Gates (Strict Enforcement)
Before merging Session 99 changes, the following gates MUST pass:
1.  **Dual Test Suites:** Both `pytest tests/ -x -q` AND `pytest rhodesli_ml/tests/ -x -q` must run clean.
2.  **Repo-Verified DOM Invariants:** Ensure the elements listed in Section 3 remain accessible to `BeautifulSoup` inside the pytest suites.
3.  **Deterministic Route Smoke Checks:** 
    * `/` (Landing)
    * `/?section=inbox` (Workstation)
    * `/identify/test-unidentified-1` (Or dynamically extracting an unidentified ID from the landing page to curl). Do not rely on `/identify/random`.
4.  **Screenshot Checkpoints:** Export rendered screenshots of the three in-scope redesign surfaces (`/`, `/identify/{id}`, and `/?section=inbox`) as visual proofs of the archival aesthetic.

---

### Appendix A: Dated Source References (2025-2026)
*   **Figma 2025 AI Report & Perspectives:** Highlights that human design discipline and taste matter more, not less, when AI generates code rapidly. (Early 2025)
*   **Canva Design Trends 2026:** Emphasizes "Imperfect by Design," tactility, layered storytelling, and raw human visuals over sterile tech looks. (Late 2025)
*   **Creative Bloq (Taste is the New Superpower 2026):** Authentic storytelling replaces generic product abstractions. (2026)
*   **Google Stitch & Gemini 2.5 Flash Image / Nano Banana Series:** Tooling for ultra-fast, high-fidelity UI mockup prototyping. (Mid 2025 - Early 2026)
*   **Reddit / Social Discourses (r/webdesign & r/Frontend):** "Why do all modern SaaS websites look the same?", specifically calling out uncustomized Shadcn/Linear-clone bento grids and heavy purple/blue gradients as "AI slop". (Late 2025 - Early 2026)

### Appendix B: Migration Case (Not Approved)
*If a future decision dictates a React migration:*
- **Cost:** Rewriting 799+ pytest integration tests; rebuilding HTMX routing into Next.js.
- **Risk:** High chance of breaking the `423 Lock Contention` semantics and upload pipelines.
- **Contracts:** Requires an OpenAPI specification of the current FastHTML backend. **(Rejected per HD-022)**.
