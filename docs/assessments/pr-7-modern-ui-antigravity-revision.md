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
| **`/?section=...`** | Workstation root / Dashboard | The HTMX sidebar structure (`hx-get="/?section=..."`) and section count badges. |
| **`/identify/{id}`** | Public share-ready ID flows | The presence of the `[data-testid="identify-person-form"]` and the `name="identity_id"` hidden input, plus `og:title`/`og:image` meta tags. |
| **`/photo/{id}`** | Public / Admin photo detail view | `[data-testid="photo-metadata-overlay"]`. Admin edits `[data-testid="photo-inline-edit"]`. |
| **`/person/{id}`** | Public / Admin person profile | `[data-testid="life-details"]`, `[data-testid="person-action-bar"]`. |
| **`/photos`** | Photo grid | HTMX pagination markers and grid structure. |
| **`/timeline`** | Public historical timeline | `[data-testid="decade-marker"]` tags for chronological anchor points. |
| **`/tree`** | Public family tree visualization | SVG/D3 nodes and panning script structure. |

*Note: `/timeline` and `/tree` are public narrative surfaces, not admin-only, and should be treated with purposeful motion.*

## 4. Shared Surface System & Single Source of Truth
I do not want route-by-route "one-off" styling. Cross-surface primitives must remain identical wherever they appear.

| Primitive | Purpose & Usage | Source of Truth Enforcement |
| :--- | :--- | :--- |
| **Face Cards** | Display a cropped/masked face (Landing, ID flows, Queues) | **Existing shared helper:** Update `app/main.py::face_card` with a scoped aesthetic class or variant pattern. |
| **Metadata / Provenance** | Display collection, date, and source info (`/photo`, `/identify`, Admin) | **Shared CSS class hierarchy:** Create typography classes specifically for metadata blocks in `app/page_routes.py`. |
| **Action Bars / CTAs** | Drive main user action (`/identify`, queues) | **Shared CSS class / Shared helper:** Extract button variants into a new semantic Tailwind abstraction if necessary. |
| **Section Headers** | Title a page or queue state | **Existing shared helper:** Update `app/main.py::section_header` with scoped classes. |
| **Empty States** | Display when no data exists in a queue | **New shared helper:** Rather than inline creation across routes, abstract to a shared function in `main.py`. |
| **Loading / HTMX** | Network activity indicator | **Shared CSS class:** Update global `.htmx-indicator` style definition. |
| **Public Nav Chrome** | Orientation on public pages | **Existing shared helper:** Update `app/main.py::_public_nav_links`. |
| **Workstation Nav Chrome** | Utilities and routing for admins | **Existing shared helper:** Update `app/main.py::sidebar` and `app/main.py::_admin_dashboard_banner`. |

### Consistency Risk Register
- **Face Cards:** If `app/main.py::face_card` is bypassed by an inline implementation on the landing page, the hover physics and aspect ratios will permanently drift.
- **Metadata Panels:** If raw HTML is written in `page_routes.py` without semantic styling classes, the typography rhythm (Playfair titles vs sans-serif data) will shatter across mobile devices.
- **CTA/Action Bars:** Using inline `bg-amber-600 hover:bg-amber-500` wildly across routes prevents global color token adjustments later.
- **Section Headers:** If `app/main.py::section_header` is abandoned, spacing rhythms between queues will become misaligned.
- **Public vs Workstation Nav:** If these bleed together stylistically, users will lose the contextual safety of knowing whether they are in the public "museum" or the private "admin workbench."

## 5. Scope Control for Session 99
To guarantee zero regressions and no accidental spread into high-risk routes, Session 99 is strictly bounded:

### Implementation Touch Map
- `app/page_routes.py::landing_page` ➔ `needs scoped variant` (Update public view).
- `app/page_routes.py` identify route `get(person_id, ...)` ➔ `needs scoped variant`.
- `app/page_routes.py` workstation route (`/?section=...`) ➔ `safe to restyle globally`.
- `app/main.py::_admin_dashboard_banner` ➔ `needs scoped variant` (Reused on out-of-scope admin sub-routes where regression is risky).
- `app/main.py::sidebar` ➔ `needs scoped variant` (Heavily linked to out-of-scope metadata forms and map routes).
- `app/main.py::section_header` ➔ `needs scoped variant` (Heavily reused across `/photos`, `/tools/compare`, and public flows).
- `app/main.py::face_card` ➔ `needs scoped variant` (Used extensively in `/person/{id}`, `/identify/{id}/match/{id}`, and `/timeline`).
- `app/main.py::_public_nav_links` ➔ `safe to restyle globally` (Centralized public typography asset).

### Out-of-Scope Leakage Rules
- `/tools/compare` is HIGH RISK. `must not be touched in Session 99`.
- `/photo/{id}`, `/person/{id}`, `/photos`, `/timeline`, `/tree` are HIGH RISK. `must not be touched in Session 99`.
- **Explicit Shared Helper Rule:** Because `face_card`, `section_header`, `sidebar`, and `_admin_dashboard_banner` are heavily used by out-of-scope routes, **Session 99 MUST NOT restyle them globally.** 
- **Leakage Policy:** To solve this, developers must strictly:
  1. Introduce a scoped rendering variant parameter (e.g., `view_mode="archival"`).
  2. OR apply route-local CSS composition that does not leak out of the `#target-container`.

## 6. Wow Without Slop (Aesthetic Rules)
To elevate Rhodesli from amateur to premium *without* looking like generic AI SaaS, Session 99 must follow these rules:

* **What creates trust:** Restraint. Precise typographic alignment. High-contrast, legible serif headers (Playfair Display) paired with clean sans-serif data.
* **What creates tactility:** Film grain overlays, sepia-toned shadow hints, and subtle borders that imply physical archival mattes. Interactive elements should have slight inset shadows or border color un-mutes on hover.
* **What creates interactivity:** Purposeful state changes. A fade in, a smooth expansion of a metadata panel. Using CSS transitions on transform and opacity only.
* **What feels like AI slop:** Glowing purple/blue gradients. Mindless Bento Grids where normal flexbox lists would suffice. Oversized drop shadows on floating cards.
* **What feels too flashy:** Spring physics, bouncy hover states, scroll-hijacking, and anything that distracts from the photography itself.

## 7. Parallel Tracks + Final Sync (Execution Sequencing)
Session 99 implementation must be executed in strict parallel tracks to avoid getting lost, concluding with a forced unification.

**Track A: Landing Page (`/`)**
- Establish the cinematic, story-led editorial aesthetic using the Shared Surface primitives.
**Track B: Public Share-Ready Page (`/identify/{id}`)**
- Redesign the "Can you help?" flow to look premium, tactile, and connected to the Landing Page aesthetic.
**Track C: Workstation Root (`/?section=...`)**
- Overhaul the header (`_admin_dashboard_banner`), navigation (`sidebar`), and cues (`section_header`) to apply the denser, utilitarian variant.

**Track D: Final Harmonization & Convergence**
- A deliberate pause to run `diff` comparisons across touched files.
- Compare Face Cards rendered on Track A vs Track C to ensure identical classes are used.
- Enforce the "Single Source of Truth Strategy" outlined in Section 4. Reconcile any repeated inline primitives into shared helpers using the scoped variant rules before merge.

## 8. Verification Gates (Strict Enforcement)
Before merging Session 99 changes, the following gates MUST pass:
1.  **Dual Test Suites:** Both `pytest tests/ -x -q` AND `pytest rhodesli_ml/tests/ -x -q` must run clean.
2.  **Repo-Verified DOM Invariants:** Ensure the elements listed in Section 3 remain accessible to `BeautifulSoup` inside the pytest suites.
3.  **Deterministic Route Smoke Checks:** 
    * `/` (Landing)
    * `/?section=inbox` (Workstation root handled in `app/page_routes.py`)
    * `/identify/unknown-1` (Or `test-unidentified-1` based on DB fixtures).
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
